"""One place for every AI call.

- Works with the Anthropic API (API key) or Amazon Bedrock (AWS credentials / IAM role).
- Uses forced tool calls so the model must return JSON that matches a schema.
- Logs every call (success or failure) to the ai_logs table.
"""
import json
import time
from typing import Any

from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import AILog


class AIUnavailable(Exception):
    """Raised when AI isn't configured or the provider call fails."""


_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    settings = get_settings()
    if not settings.ai_configured:
        raise AIUnavailable(
            "AI isn't set up yet. Add ANTHROPIC_API_KEY (or Bedrock settings) to your .env file and restart the server."
        )
    import anthropic

    if settings.ai_provider == "bedrock":
        _client = anthropic.AnthropicBedrock(aws_region=settings.aws_region)
    else:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def model_name() -> str:
    s = get_settings()
    return s.bedrock_model_id if s.ai_provider == "bedrock" else s.anthropic_model


def _log(db: Session | None, user_id, feature, summary, output, success, error, started):
    if db is None:
        return
    db.add(
        AILog(
            user_id=user_id,
            feature=feature,
            model=model_name(),
            input_summary=summary[:2000],
            output=output,
            success=success,
            error=error,
            latency_ms=int((time.time() - started) * 1000),
        )
    )
    db.commit()


def call_tool(
    *,
    feature: str,
    system: str,
    content: list[dict] | str,
    tool_name: str,
    tool_description: str,
    schema: dict,
    db: Session | None = None,
    user_id: int | None = None,
    summary: str = "",
    max_tokens: int = 2000,
) -> dict[str, Any]:
    """Ask the model and force it to answer by calling a single tool with JSON input."""
    started = time.time()
    try:
        client = _get_client()
        response = client.messages.create(
            model=model_name(),
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": content}],
            tools=[{"name": tool_name, "description": tool_description, "input_schema": schema}],
            tool_choice={"type": "tool", "name": tool_name},
        )
        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and block.name == tool_name:
                result = dict(block.input)
                _log(db, user_id, feature, summary, result, True, None, started)
                return result
        raise AIUnavailable("The AI response didn't include structured output.")
    except AIUnavailable as e:
        _log(db, user_id, feature, summary, None, False, str(e), started)
        raise
    except Exception as e:  # network, auth, rate limit, etc.
        _log(db, user_id, feature, summary, None, False, repr(e), started)
        raise AIUnavailable(f"The AI service didn't respond: {e.__class__.__name__}. Check your key and try again.") from e


def call_text(
    *, feature: str, system: str, prompt: str, db: Session | None = None, user_id: int | None = None, max_tokens: int = 600
) -> str:
    """Plain-text answer (used only for explaining numbers the backend already calculated)."""
    started = time.time()
    try:
        client = _get_client()
        response = client.messages.create(
            model=model_name(),
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in response.content if getattr(b, "type", None) == "text").strip()
        _log(db, user_id, feature, prompt[:500], {"text": text}, True, None, started)
        return text
    except AIUnavailable as e:
        _log(db, user_id, feature, prompt[:500], None, False, str(e), started)
        raise
    except Exception as e:
        _log(db, user_id, feature, prompt[:500], None, False, repr(e), started)
        raise AIUnavailable(f"The AI service didn't respond: {e.__class__.__name__}.") from e


def to_json(obj) -> str:
    return json.dumps(obj, default=str, indent=None)
