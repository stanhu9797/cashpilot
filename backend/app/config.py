"""App configuration, loaded from environment variables (or a .env file)."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", ROOT_DIR / "backend" / ".env"),
        extra="ignore",
    )

    # Core
    app_env: str = "development"
    database_url: str = ""
    jwt_secret: str = "change-me-in-production"
    jwt_expire_hours: int = 72
    cors_origins: str = "http://localhost:5173"

    # AI: "anthropic" (direct API key) or "bedrock" (AWS credentials / IAM role)
    ai_provider: str = "anthropic"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5-5"
    aws_region: str = "us-east-1"
    bedrock_model_id: str = ""  # copy from the Bedrock console, e.g. a Claude Sonnet inference profile ID

    # Receipt storage: local folder by default, S3 when a bucket is set
    s3_bucket: str = ""
    upload_dir: str = str(ROOT_DIR / "backend" / "uploads")
    max_upload_mb: int = 10

    # Demo mode: runs on the container's own SQLite file and re-creates the demo account on every start.
    # For class demos and previews only; data resets whenever the service redeploys or restarts.
    demo_mode: bool = False

    # Review threshold: anything below this confidence is flagged for the user
    review_threshold: float = 0.80

    @property
    def ai_configured(self) -> bool:
        if self.ai_provider == "bedrock":
            return bool(self.bedrock_model_id)
        return bool(self.anthropic_api_key)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
