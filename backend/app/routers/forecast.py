import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.client import AIUnavailable, call_text, to_json
from ..auth import current_user
from ..database import get_db
from ..models import Transaction, User
from ..services.forecast import HISTORY_DAYS, build_forecast
from .. import ratelimit

router = APIRouter(prefix="/api/forecast", tags=["forecast"])


def _forecast_for(user: User, db: Session) -> dict:
    if user.current_balance is None:
        raise HTTPException(400, "Set your current balance first so the forecast has a starting point.")
    since = dt.date.today() - dt.timedelta(days=HISTORY_DAYS)
    rows = db.scalars(select(Transaction).where(Transaction.user_id == user.id, Transaction.date >= since)).all()
    txns = [{"date": t.date, "merchant": t.merchant, "amount": float(t.amount)} for t in rows]
    return build_forecast(txns, float(user.current_balance), float(user.low_balance_threshold))


@router.get("")
def forecast(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _forecast_for(user, db)


@router.post("/explain")
def explain(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ratelimit.check(f"explain:{user.id}", 20, 3600, "Too many explanations in the last hour.")
    f = _forecast_for(user, db)
    brief = {k: v for k, v in f.items() if k not in ("series",)}
    try:
        text = call_text(
            feature="forecast_explain",
            system=(
                "Explain a 90-day cash flow forecast to a freelancer in 3 short sentences. Use only the numbers given. "
                "Say what drives the trend, when the low point is, and one concrete thing to watch. "
                "Do not give tax, legal, or investment advice. Format money like $1,234."
            ),
            prompt=to_json(brief),
            db=db,
            user_id=user.id,
            max_tokens=250,
        )
    except AIUnavailable as e:
        raise HTTPException(503, str(e))
    return {"explanation": text}
