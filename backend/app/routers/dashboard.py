import datetime as dt
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import current_user
from ..config import get_settings
from ..database import get_db
from ..models import Transaction, User

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def dashboard(user: User = Depends(current_user), db: Session = Depends(get_db)):
    today = dt.date.today()
    month_start = today.replace(day=1)
    rows = db.scalars(
        select(Transaction).where(Transaction.user_id == user.id, Transaction.date >= month_start)
    ).all()
    money_in = sum((t.amount for t in rows if t.amount > 0 and t.category != "Transfers"), Decimal("0"))
    money_out = sum((-t.amount for t in rows if t.amount < 0 and t.category != "Transfers"), Decimal("0"))
    by_cat: dict[str, Decimal] = {}
    for t in rows:
        if t.amount < 0 and t.category != "Transfers":
            by_cat[t.category] = by_cat.get(t.category, Decimal("0")) - t.amount
    review = db.scalar(
        select(func.count()).select_from(Transaction).where(Transaction.user_id == user.id, Transaction.needs_review == True)  # noqa: E712
    )
    total = db.scalar(select(func.count()).select_from(Transaction).where(Transaction.user_id == user.id))
    return {
        "month_label": today.strftime("%B %Y"),
        "money_in": float(money_in),
        "money_out": float(money_out),
        "net": float(money_in - money_out),
        "top_categories": [
            {"category": k, "total": float(v)} for k, v in sorted(by_cat.items(), key=lambda kv: -kv[1])[:6]
        ],
        "needs_review": review or 0,
        "transaction_count": total or 0,
        "current_balance": float(user.current_balance) if user.current_balance is not None else None,
        "ai_available": get_settings().ai_configured,
        "demo_mode": get_settings().demo_mode,
    }
