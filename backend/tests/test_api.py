from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def auth_headers(email="api@test.com"):
    r = client.post("/api/auth/register", json={"email": email, "password": "password123", "name": "Test"})
    if r.status_code == 409:
        r = client.post("/api/auth/login", json={"email": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_requires_sign_in():
    assert client.get("/api/transactions").status_code == 401


def test_register_validates_password_length():
    r = client.post("/api/auth/register", json={"email": "x@test.com", "password": "short"})
    assert r.status_code == 422 and "password" in r.json()["detail"]


def test_csv_import_dedupes_and_categorizes_with_rules():
    h = auth_headers("csv@test.com")
    csv_text = "Date,Description,Amount\n09/03/2026,ADOBE CREATIVE CLOUD,-59.99\n09/04/2026,SQ *JOES COFFEE,-6.25\n"
    files = {"file": ("bank.csv", csv_text, "text/csv")}
    first = client.post("/api/transactions/import", files=files, headers=h).json()
    assert first["imported"] == 2 and first["skipped_duplicates"] == 0
    second = client.post("/api/transactions/import", files={"file": ("bank.csv", csv_text, "text/csv")}, headers=h).json()
    assert second["imported"] == 0 and second["skipped_duplicates"] == 2

    txns = client.get("/api/transactions", headers=h).json()
    adobe = next(t for t in txns if "ADOBE" in t["merchant"])
    coffee = next(t for t in txns if "JOES" in t["merchant"])
    assert adobe["category"] == "Software & Subscriptions" and not adobe["needs_review"]
    assert coffee["needs_review"]  # no rule and no AI in tests


def test_correction_creates_rule_used_next_time():
    h = auth_headers("rule@test.com")
    t = client.post(
        "/api/transactions", json={"date": "2026-09-05", "merchant": "SQ *JOES COFFEE #12", "amount": -5.5}, headers=h
    ).json()
    assert t["needs_review"]
    client.patch(f"/api/transactions/{t['id']}/category", json={"category": "Meals"}, headers=h)
    t2 = client.post(
        "/api/transactions", json={"date": "2026-09-06", "merchant": "SQ *JOES COFFEE #98", "amount": -4.0}, headers=h
    ).json()
    assert t2["category"] == "Meals" and t2["category_source"] == "your_rule" and not t2["needs_review"]


def test_ask_without_ai_returns_clear_message():
    h = auth_headers("ask@test.com")
    r = client.post("/api/ask", json={"question": "How much did I spend on software?"}, headers=h)
    assert r.status_code == 503 and "AI isn't set up" in r.json()["detail"]


def test_forecast_needs_balance_then_works():
    h = auth_headers("fc@test.com")
    assert client.get("/api/forecast", headers=h).status_code == 400
    client.put("/api/auth/settings", json={"current_balance": 5000, "low_balance_threshold": 1000}, headers=h)
    f = client.get("/api/forecast", headers=h).json()
    assert len(f["series"]) == 90
