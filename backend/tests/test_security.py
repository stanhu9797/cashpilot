"""Security and input-validation tests added during the audit. Each one maps to a bug or risk in the report."""
from fastapi.testclient import TestClient

from app.main import app
from app.routers.transactions import escape_like
from app.services.receipts import sniff_type

client = TestClient(app)
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20


def headers(email):
    r = client.post("/api/auth/register", json={"email": email, "password": "password123"})
    if r.status_code != 200:
        r = client.post("/api/auth/login", json={"email": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_password_over_72_bytes_rejected():
    r = client.post("/api/auth/register", json={"email": "emoji@test.com", "password": "😀" * 25})
    assert r.status_code == 422 and "too long" in r.json()["detail"]


def test_login_is_rate_limited_per_account():
    headers("brute@test.com")
    codes = [client.post("/api/auth/login", json={"email": "brute@test.com", "password": "wrong-pass"}).status_code for _ in range(7)]
    assert codes[:5] == [401] * 5 and codes[5] == 429


def test_search_wildcards_match_literally():
    h = headers("like@test.com")
    client.post("/api/transactions", json={"date": "2026-09-01", "merchant": "FIGMA", "amount": -15}, headers=h)
    assert client.get("/api/transactions?search=%25", headers=h).json() == []
    assert client.get("/api/transactions?search=_", headers=h).json() == []
    assert escape_like("50%_off") == "50\\%\\_off"


def test_whitespace_merchant_rejected():
    h = headers("ws@test.com")
    r = client.post("/api/transactions", json={"date": "2026-09-01", "merchant": "   ", "amount": -5}, headers=h)
    assert r.status_code == 422


def test_dates_before_2000_rejected():
    h = headers("old@test.com")
    r = client.post("/api/transactions", json={"date": "1900-01-01", "merchant": "X", "amount": -5}, headers=h)
    assert r.status_code == 422 and "2000" in r.json()["detail"]


def test_whitespace_question_rejected_before_ai():
    h = headers("askws@test.com")
    r = client.post("/api/ask", json={"question": "      "}, headers=h)
    assert r.status_code == 422


def test_sql_injection_text_is_stored_as_plain_text():
    h = headers("sqli@test.com")
    evil = "x'; DROP TABLE users;--"
    r = client.post("/api/transactions", json={"date": "2026-09-01", "merchant": evil, "amount": -5}, headers=h)
    assert r.json()["merchant"] == evil
    assert client.get("/api/auth/me", headers=h).status_code == 200  # users table intact


def test_csv_row_cap():
    h = headers("bigcsv@test.com")
    big = "Date,Description,Amount\n" + "".join(f"09/01/2026,M{i},-1\n" for i in range(5001))
    r = client.post("/api/transactions/import", files={"file": ("big.csv", big, "text/csv")}, headers=h)
    assert r.status_code == 400 and "5,000" in r.json()["detail"]


def test_fake_image_rejected_by_content_check():
    h = headers("fake@test.com")
    r = client.post("/api/receipts", files={"file": ("r.jpg", b"hello not an image", "image/jpeg")}, headers=h)
    assert r.status_code == 400 and "isn't a real image" in r.json()["detail"]
    assert sniff_type(PNG) == "image/png"
    assert sniff_type(b"%PDF-1.7 ...") == "application/pdf"


def test_users_cannot_touch_each_others_transactions():
    a, b = headers("owner@test.com"), headers("intruder@test.com")
    t = client.post("/api/transactions", json={"date": "2026-09-01", "merchant": "MINE", "amount": -5}, headers=a).json()
    assert client.patch(f"/api/transactions/{t['id']}/category", json={"category": "Meals"}, headers=b).status_code == 404
    assert client.delete(f"/api/transactions/{t['id']}", headers=b).status_code == 404
    assert all(x["merchant"] != "MINE" for x in client.get("/api/transactions", headers=b).json())


def test_tampered_token_rejected():
    h = headers("tamper@test.com")
    token = h["Authorization"].split()[1]
    bad = token[:-2] + ("AA" if token[-2:] != "AA" else "BB")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {bad}"}).status_code == 401


def test_security_headers_present():
    r = client.get("/health")
    for name in ("X-Content-Type-Options", "X-Frame-Options", "Content-Security-Policy", "Referrer-Policy"):
        assert name in r.headers
    assert client.get("/api/categories").headers["Cache-Control"] == "no-store"


def test_server_errors_hide_details():
    from app.main import unhandled
    import asyncio

    resp = asyncio.run(unhandled(None, RuntimeError("secret db password in traceback")))
    assert b"secret" not in resp.body
