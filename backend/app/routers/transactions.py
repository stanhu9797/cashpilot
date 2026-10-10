from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..auth import current_user
from ..categories import CATEGORIES
from ..config import get_settings
from ..database import get_db
from ..models import CategoryRule, Correction, Transaction, User
from ..schemas import CategoryUpdate, TransactionIn, TransactionOut
from ..services.categorizer import Suggestion, categorize_many, normalize_merchant
from ..services.csv_import import MAX_ROWS, CSVFormatError, dedupe_key, parse_csv
from .. import ratelimit


def escape_like(text: str) -> str:
    """Make % and _ match literally instead of acting as wildcards."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

router = APIRouter(prefix="/api", tags=["transactions"])


@router.get("/categories")
def categories():
    return CATEGORIES


@router.get("/transactions", response_model=list[TransactionOut])
def list_transactions(
    needs_review: bool | None = None,
    category: str | None = None,
    search: str | None = Query(default=None, max_length=100),
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=200, le=1000),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    q = select(Transaction).where(Transaction.user_id == user.id)
    if needs_review is not None:
        q = q.where(Transaction.needs_review == needs_review)
    if category:
        q = q.where(Transaction.category == category)
    if search and search.strip():
        like = f"%{escape_like(search.strip())}%"
        q = q.where(or_(Transaction.merchant.ilike(like, escape="\\"), Transaction.description.ilike(like, escape="\\")))
    if date_from:
        q = q.where(Transaction.date >= date_from)
    if date_to:
        q = q.where(Transaction.date <= date_to)
    return db.scalars(q.order_by(Transaction.date.desc(), Transaction.id.desc()).limit(limit)).all()


def _apply(t: Transaction, s: Suggestion):
    t.category, t.confidence, t.category_source, t.needs_review = s.category, s.confidence, s.source, s.needs_review


@router.post("/transactions", response_model=TransactionOut)
def create_transaction(body: TransactionIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    t = Transaction(
        user_id=user.id,
        date=body.date,
        merchant=body.merchant.strip(),
        description=body.description.strip(),
        amount=body.amount,
        source="receipt" if body.receipt_id else "manual",
        receipt_id=body.receipt_id,
        dedupe_key=dedupe_key(user.id, body.date, body.amount, body.merchant),
    )
    if body.category:  # the user chose it, so it's confirmed
        t.category, t.confidence, t.category_source, t.needs_review = body.category, 1.0, "user", False
    else:
        _apply(t, categorize_many(db, user.id, [{"merchant": t.merchant, "description": t.description, "amount": t.amount}])[0])
    db.add(t)
    db.commit()
    return t


@router.post("/transactions/import")
async def import_csv(file: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)):
    ratelimit.check(f"import:{user.id}", 20, 3600, "Too many imports in the last hour.")
    data = await file.read()
    if len(data) > get_settings().max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File is larger than {get_settings().max_upload_mb} MB.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    try:
        rows = parse_csv(text)
    except CSVFormatError as e:
        raise HTTPException(400, str(e))

    existing = set(db.scalars(select(Transaction.dedupe_key).where(Transaction.user_id == user.id)).all())
    new_rows = []
    for r in rows:
        key = dedupe_key(user.id, r["date"], r["amount"], r["description"])
        if key not in existing:
            existing.add(key)
            new_rows.append({**r, "dedupe_key": key})

    suggestions = categorize_many(db, user.id, new_rows)
    for r, s in zip(new_rows, suggestions):
        t = Transaction(user_id=user.id, source="csv", **r)
        _apply(t, s)
        db.add(t)
    db.commit()
    by_source = {}
    for s in suggestions:
        by_source[s.source] = by_source.get(s.source, 0) + 1
    return {
        "imported": len(new_rows),
        "skipped_duplicates": len(rows) - len(new_rows),
        "needs_review": sum(1 for s in suggestions if s.needs_review),
        "categorized_by": by_source,
        "ai_available": get_settings().ai_configured,
    }


@router.patch("/transactions/{txn_id}/category", response_model=TransactionOut)
def set_category(txn_id: int, body: CategoryUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    t = db.get(Transaction, txn_id)
    if not t or t.user_id != user.id:
        raise HTTPException(404, "Transaction not found.")
    if t.category != body.category:
        db.add(
            Correction(
                user_id=user.id,
                transaction_id=t.id,
                merchant=t.merchant,
                description=t.description,
                old_category=t.category,
                new_category=body.category,
                old_source=t.category_source,
            )
        )
    if body.remember:
        key = normalize_merchant(t.merchant)
        if key:
            rule = db.scalar(select(CategoryRule).where(CategoryRule.user_id == user.id, CategoryRule.merchant_key == key))
            if rule:
                rule.category = body.category
            else:
                db.add(CategoryRule(user_id=user.id, merchant_key=key, category=body.category))
    t.category, t.confidence, t.category_source, t.needs_review = body.category, 1.0, "user", False
    db.commit()
    return t


@router.post("/transactions/{txn_id}/confirm", response_model=TransactionOut)
def confirm(txn_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    t = db.get(Transaction, txn_id)
    if not t or t.user_id != user.id:
        raise HTTPException(404, "Transaction not found.")
    t.needs_review = False
    db.commit()
    return t


@router.post("/transactions/recategorize")
def recategorize(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Re-run rules + AI on everything still waiting for review."""
    ratelimit.check(f"recat:{user.id}", 10, 3600, "Suggestions were re-run too many times.")
    pending = db.scalars(
        select(Transaction).where(Transaction.user_id == user.id, Transaction.needs_review == True)  # noqa: E712
    ).all()
    suggestions = categorize_many(
        db, user.id, [{"merchant": t.merchant, "description": t.description, "amount": t.amount} for t in pending]
    )
    for t, s in zip(pending, suggestions):
        _apply(t, s)
    db.commit()
    return {"updated": len(pending), "still_needs_review": sum(1 for s in suggestions if s.needs_review)}


@router.delete("/transactions/{txn_id}")
def delete_transaction(txn_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    t = db.get(Transaction, txn_id)
    if not t or t.user_id != user.id:
        raise HTTPException(404, "Transaction not found.")
    db.delete(t)
    db.commit()
    return {"deleted": txn_id}
