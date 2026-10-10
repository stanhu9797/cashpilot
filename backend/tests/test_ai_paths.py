"""AI features tested with a fake model, so we check OUR logic (validation, math, fallbacks) for free."""
import datetime as dt
from decimal import Decimal

import pytest

from app.ai.client import AIUnavailable
from app.database import SessionLocal
from app.models import Transaction, User
from app.services import ask as ask_service
from app.services import receipts as receipt_service


def test_receipt_sanity_check_flags_totals_that_dont_add_up(monkeypatch):
    monkeypatch.setattr(
        receipt_service,
        "call_tool",
        lambda **_: {
            "is_receipt": True,
            "merchant": "Joe's Coffee",
            "date": "2026-09-14",
            "total": 25.00,
            "subtotal": 10.00,
            "tax": 0.80,
            "confidence": {"merchant": 0.95, "date": 0.9, "total": 0.95},
            "line_items": [],
        },
    )
    data = receipt_service.extract_receipt(b"fake", "image/jpeg")
    assert data.confidence["total"] <= 0.6
    assert any("total reads" in w for w in data.warnings)


def test_receipt_missing_fields_get_zero_confidence(monkeypatch):
    monkeypatch.setattr(
        receipt_service,
        "call_tool",
        lambda **_: {"is_receipt": True, "merchant": None, "date": None, "total": 12.5,
                     "confidence": {"merchant": 0.9, "date": 0.9, "total": 0.9}, "line_items": []},
    )
    data = receipt_service.extract_receipt(b"fake", "image/png")
    assert data.confidence["merchant"] == 0 and data.confidence["date"] == 0


def test_receipt_rejects_unsupported_file_type():
    with pytest.raises(ValueError):
        receipt_service.extract_receipt(b"x", "text/plain")


def test_ask_uses_backend_math_and_falls_back_if_explainer_fails(monkeypatch):
    db = SessionLocal()
    u = User(email="askmock@test.com", password_hash="x")
    db.add(u)
    db.flush()
    db.add_all([
        Transaction(user_id=u.id, date=dt.date(2026, 9, 2), merchant="ADOBE", amount=Decimal("-60"), category="Software & Subscriptions"),
        Transaction(user_id=u.id, date=dt.date(2026, 9, 9), merchant="FIGMA", amount=Decimal("-15"), category="Software & Subscriptions"),
    ])
    db.commit()

    monkeypatch.setattr(ask_service, "call_tool", lambda **_: {
        "answerable": True, "metric": "sum", "direction": "out", "categories": ["Software & Subscriptions"],
        "date_from": "2026-09-01", "date_to": "2026-09-30", "group_by": "none",
    })

    def broken_explainer(**_):
        raise AIUnavailable("down")

    monkeypatch.setattr(ask_service, "call_text", broken_explainer)
    out = ask_service.answer_question(db, u.id, "How much on software in September?")
    assert out["result"]["total"] == 75.0
    assert "$75.00" in out["answer"]
    assert len(out["result"]["transactions"]) == 2
    db.close()


def test_ask_rejects_plan_with_invented_category(monkeypatch):
    monkeypatch.setattr(ask_service, "call_tool", lambda **_: {
        "answerable": True, "metric": "sum", "direction": "out", "categories": ["Yachts"], "group_by": "none",
    })
    with pytest.raises(AIUnavailable):
        ask_service.plan_question(None, 1, "yacht spending?")
