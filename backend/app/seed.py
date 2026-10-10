"""Create a demo account with ~4 months of realistic freelancer transactions.

Run from the backend folder:   python -m app.seed
Then sign in with:             demo@cashpilot.app / demo-password
"""
import datetime as dt
import random
from decimal import Decimal

from sqlalchemy import delete, select

from .auth import hash_password
from .database import SessionLocal, init_db
from .models import CategoryRule, Correction, Receipt, Transaction, User
from .services.categorizer import categorize_many
from .services.csv_import import dedupe_key

EMAIL, PASSWORD = "demo@cashpilot.app", "demo-password"


def build_rows(today: dt.date) -> list[dict]:
    rnd = random.Random(42)
    rows = []
    start = today - dt.timedelta(days=120)

    def add(d, merchant, amount):
        if start <= d <= today:
            rows.append({"date": d, "merchant": merchant, "description": merchant, "amount": Decimal(str(round(amount, 2)))})

    d = start
    while d <= today:
        dom = d.day
        if dom == 1:
            add(d, "WEWORK MEMBERSHIP", -450)
        if dom == 3:
            add(d, "ADOBE CREATIVE CLOUD", -59.99)
            add(d, "NOTION LABS", -10)
        if dom == 8:
            add(d, "VERIZON WIRELESS", -85.40)
        if dom == 12:
            add(d, "GOOGLE WORKSPACE", -14.40)
        if dom == 15:
            add(d, "HISCOX INSURANCE", -32.50)
        if dom == 20:
            add(d, "FIGMA", -15)
        if dom == 15:
            add(d, "STRIPE PAYOUT", 2600)  # retainer client
        if dom == 16:
            add(d, "TRANSFER TO PERSONAL CHECKING", -2400)  # owner's pay
        if d.weekday() == 4 and rnd.random() < 0.18:
            add(d, rnd.choice(["UPWORK ESCROW", "ACME DESIGN CO ACH"]), rnd.choice([450, 600, 800]))
        if d.weekday() < 5 and rnd.random() < 0.45:
            add(d, rnd.choice(["SQ *JOES COFFEE #4421 CHARLOTTE NC", "STARBUCKS STORE 08812", "TST* MAMA RICOTTAS"]), -rnd.uniform(4.5, 38))
        if rnd.random() < 0.06:
            add(d, rnd.choice(["AMAZON MKTPLACE PMTS", "STAPLES 00123", "BEST BUY 00431"]), -rnd.uniform(18, 240))
        if rnd.random() < 0.03:
            add(d, rnd.choice(["UBER TRIP", "DELTA AIR LINES", "MARRIOTT CHARLOTTE"]), -rnd.uniform(22, 420))
        if rnd.random() < 0.02:
            add(d, "META ADS", -rnd.uniform(40, 150))
        d += dt.timedelta(days=1)

    # One quarterly estimated tax payment
    add(today - dt.timedelta(days=20), "IRS USATAXPYMT", -1850)
    return rows


def main():
    init_db()
    db = SessionLocal()
    user = db.scalar(select(User).where(User.email == EMAIL))
    if user:
        for model in (Transaction, Correction, CategoryRule, Receipt):
            db.execute(delete(model).where(model.user_id == user.id))
    else:
        user = User(email=EMAIL, name="Demo Freelancer", password_hash=hash_password(PASSWORD))
        db.add(user)
        db.flush()
    user.current_balance = Decimal("6200")
    user.balance_as_of = dt.date.today()
    user.low_balance_threshold = Decimal("2500")

    rows = build_rows(dt.date.today())
    suggestions = categorize_many(db, user.id, rows, use_ai=False)  # demo data uses rules only, no API cost
    for r, s in zip(rows, suggestions):
        db.add(
            Transaction(
                user_id=user.id,
                source="demo",
                category=s.category,
                confidence=s.confidence,
                category_source=s.source,
                needs_review=s.needs_review,
                dedupe_key=dedupe_key(user.id, r["date"], r["amount"], r["description"]),
                **r,
            )
        )
    db.commit()
    review = sum(1 for s in suggestions if s.needs_review)
    print(f"Demo account ready: {EMAIL} / {PASSWORD}")
    print(f"{len(rows)} transactions created, {review} waiting for review.")


if __name__ == "__main__":
    main()
