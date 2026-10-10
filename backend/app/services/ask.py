"""'Ask your books' — the AI plans the question, the backend does the math.

1. The AI turns the question into a small, structured QueryPlan (never raw SQL).
2. The backend validates the plan and runs it with SQLAlchemy against this user's data only.
3. The AI writes a one- or two-sentence answer using ONLY the computed numbers.
4. The response includes the exact transactions behind the answer.
"""
import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.client import AIUnavailable, call_text, call_tool, to_json
from ..categories import CATEGORIES
from ..models import Transaction


class QueryPlan(BaseModel):
    answerable: bool = True
    reason_if_not: str | None = None
    metric: Literal["sum", "count", "average", "list"] = "sum"
    direction: Literal["out", "in", "all"] = "out"
    categories: list[str] = []
    merchant_contains: str | None = None
    date_from: dt.date | None = None
    date_to: dt.date | None = None
    group_by: Literal["none", "category", "merchant", "month"] = "none"
    top_n: int = Field(default=10, ge=1, le=50)

    @field_validator("categories")
    @classmethod
    def _known(cls, v):
        bad = [c for c in v if c not in CATEGORIES]
        if bad:
            raise ValueError(f"Unknown categories: {bad}")
        return v

    @field_validator("merchant_contains")
    @classmethod
    def _short(cls, v):
        return v.strip()[:60] if v else None

    @model_validator(mode="after")
    def _dates(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            self.date_from, self.date_to = self.date_to, self.date_from
        return self


PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "answerable": {"type": "boolean", "description": "False if the question can't be answered from transactions"},
        "reason_if_not": {"type": ["string", "null"]},
        "metric": {"type": "string", "enum": ["sum", "count", "average", "list"]},
        "direction": {"type": "string", "enum": ["out", "in", "all"], "description": "out = spending, in = income"},
        "categories": {"type": "array", "items": {"type": "string", "enum": CATEGORIES}},
        "merchant_contains": {"type": ["string", "null"]},
        "date_from": {"type": ["string", "null"], "description": "YYYY-MM-DD, inclusive"},
        "date_to": {"type": ["string", "null"], "description": "YYYY-MM-DD, inclusive"},
        "group_by": {"type": "string", "enum": ["none", "category", "merchant", "month"]},
        "top_n": {"type": "integer", "minimum": 1, "maximum": 50},
    },
    "required": ["answerable", "metric", "direction", "categories", "group_by"],
}


def plan_question(db: Session, user_id: int, question: str, today: dt.date | None = None) -> QueryPlan:
    today = today or dt.date.today()
    system = (
        "You convert a freelancer's question about their own transactions into a query plan. "
        f"Today is {today.isoformat()} ({today.strftime('%A')}). Resolve relative dates like 'last month', "
        "'this quarter', or 'year to date' into exact date_from/date_to. Calendar quarters: Q1 Jan-Mar, Q2 Apr-Jun, "
        "Q3 Jul-Sep, Q4 Oct-Dec. 'Top' or 'biggest' questions use group_by with metric sum. "
        "If the question needs information transactions can't provide (advice, tax law, predictions), set answerable=false."
    )
    raw = call_tool(
        feature="ask_plan",
        system=system,
        content=f"Question: {question}",
        tool_name="make_query_plan",
        tool_description="Describe which transactions to select and how to aggregate them.",
        schema=PLAN_SCHEMA,
        db=db,
        user_id=user_id,
        summary=question,
        max_tokens=600,
    )
    try:
        return QueryPlan.model_validate(raw)
    except Exception as e:
        raise AIUnavailable("I couldn't turn that into a safe query. Try rephrasing with a category or time period.") from e


def run_plan(db: Session, user_id: int, plan: QueryPlan) -> dict:
    q = select(Transaction).where(Transaction.user_id == user_id)
    if plan.direction == "out":
        q = q.where(Transaction.amount < 0)
    elif plan.direction == "in":
        q = q.where(Transaction.amount > 0)
    if plan.categories:
        q = q.where(Transaction.category.in_(plan.categories))
    if plan.merchant_contains:
        q = q.where(Transaction.merchant.ilike(f"%{plan.merchant_contains}%"))
    if plan.date_from:
        q = q.where(Transaction.date >= plan.date_from)
    if plan.date_to:
        q = q.where(Transaction.date <= plan.date_to)
    rows = db.scalars(q.order_by(Transaction.date.desc())).all()

    def magnitude(t):  # spending shown as positive numbers
        return abs(t.amount) if plan.direction == "out" else t.amount

    total = sum((magnitude(t) for t in rows), Decimal("0"))
    result = {"count": len(rows), "total": float(total)}
    if plan.metric == "average":
        result["average"] = float(total / len(rows)) if rows else 0.0

    groups = []
    if plan.group_by != "none":
        buckets: dict[str, Decimal] = {}
        counts: dict[str, int] = {}
        for t in rows:
            key = {"category": t.category, "merchant": t.merchant, "month": t.date.strftime("%Y-%m")}[plan.group_by]
            buckets[key] = buckets.get(key, Decimal("0")) + magnitude(t)
            counts[key] = counts.get(key, 0) + 1
        ordered = sorted(buckets.items(), key=(lambda kv: kv[0]) if plan.group_by == "month" else (lambda kv: -kv[1]))
        if plan.group_by != "month":
            ordered = ordered[: plan.top_n]
        groups = [{"key": k, "total": float(v), "count": counts[k]} for k, v in ordered]
    result["groups"] = groups

    result["transactions"] = [
        {
            "id": t.id,
            "date": t.date.isoformat(),
            "merchant": t.merchant,
            "amount": float(t.amount),
            "category": t.category,
        }
        for t in rows[:100]
    ]
    return result


def fallback_answer(plan: QueryPlan, result: dict) -> str:
    noun = "spent" if plan.direction == "out" else "received" if plan.direction == "in" else "moved"
    if result["count"] == 0:
        return "No transactions match that question."
    if plan.group_by != "none" and result["groups"]:
        top = result["groups"][0]
        return f"Top result: {top['key']} at ${top['total']:,.2f} across {top['count']} transactions."
    if plan.metric == "count":
        return f"{result['count']} matching transactions."
    if plan.metric == "average":
        return f"Average of ${result['average']:,.2f} across {result['count']} transactions."
    return f"You {noun} ${result['total']:,.2f} across {result['count']} transactions."


def answer_question(db: Session, user_id: int, question: str) -> dict:
    plan = plan_question(db, user_id, question)
    if not plan.answerable:
        return {
            "answer": plan.reason_if_not or "That question can't be answered from your transactions alone.",
            "plan": plan.model_dump(mode="json"),
            "result": None,
        }
    result = run_plan(db, user_id, plan)
    summary_for_ai = {k: v for k, v in result.items() if k != "transactions"}
    try:
        answer = call_text(
            feature="ask_answer",
            system=(
                "Answer the user's question in one or two plain sentences using ONLY the numbers provided. "
                "Do not calculate new figures, round differently, or add advice. Format money like $1,234.56. "
                "Mention the date range if one was used."
            ),
            prompt=f"Question: {question}\nQuery plan: {to_json(plan.model_dump(mode='json'))}\nComputed results: {to_json(summary_for_ai)}",
            db=db,
            user_id=user_id,
            max_tokens=200,
        )
    except AIUnavailable:
        answer = fallback_answer(plan, result)
    return {"answer": answer or fallback_answer(plan, result), "plan": plan.model_dump(mode="json"), "result": result}
