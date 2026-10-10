import datetime as dt
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.database import SessionLocal
from app.models import Transaction, User
from app.services.ask import QueryPlan, run_plan


def test_rejects_unknown_category():
    with pytest.raises(ValidationError):
        QueryPlan(categories=["Lambos"])


def test_swaps_reversed_dates():
    p = QueryPlan(date_from=dt.date(2026, 9, 30), date_to=dt.date(2026, 9, 1))
    assert p.date_from < p.date_to


def test_run_plan_only_sees_own_data_and_sums_correctly():
    db = SessionLocal()
    a = User(email="a@test.com", password_hash="x")
    b = User(email="b@test.com", password_hash="x")
    db.add_all([a, b])
    db.flush()
    d = dt.date(2026, 9, 10)
    db.add_all(
        [
            Transaction(user_id=a.id, date=d, merchant="ADOBE", amount=Decimal("-59.99"), category="Software & Subscriptions"),
            Transaction(user_id=a.id, date=d, merchant="FIGMA", amount=Decimal("-15.00"), category="Software & Subscriptions"),
            Transaction(user_id=a.id, date=d, merchant="CLIENT", amount=Decimal("2000"), category="Income"),
            Transaction(user_id=b.id, date=d, merchant="ADOBE", amount=Decimal("-999"), category="Software & Subscriptions"),
        ]
    )
    db.commit()
    plan = QueryPlan(metric="sum", direction="out", categories=["Software & Subscriptions"], group_by="merchant")
    result = run_plan(db, a.id, plan)
    assert result["count"] == 2
    assert result["total"] == pytest.approx(74.99)
    assert result["groups"][0]["key"] == "ADOBE"
    db.close()
