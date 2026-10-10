import datetime as dt

from app.services.forecast import build_forecast, find_recurring

TODAY = dt.date(2026, 10, 1)


def monthly(merchant, amount, day, months=3):
    out = []
    for m in range(months):
        month = TODAY.month - months + m + 1
        year = TODAY.year + (month - 1) // 12 if month > 0 else TODAY.year - 1
        month = (month - 1) % 12 + 1
        out.append({"date": dt.date(year, month, day), "merchant": merchant, "amount": amount})
    return out


def test_detects_monthly_subscription():
    txns = monthly("ADOBE CREATIVE CLOUD", -59.99, 3)
    rec = find_recurring(txns)
    assert len(rec) == 1 and rec[0].label == "monthly" and rec[0].amount == -59.99


def test_ignores_irregular_amounts():
    txns = [
        {"date": dt.date(2026, 7, 3), "merchant": "AMAZON", "amount": -20},
        {"date": dt.date(2026, 8, 3), "merchant": "AMAZON", "amount": -240},
        {"date": dt.date(2026, 9, 3), "merchant": "AMAZON", "amount": -75},
    ]
    assert find_recurring(txns) == []


def test_flat_balance_with_no_activity():
    f = build_forecast([], current_balance=5000, low_threshold=1000, today=TODAY)
    assert f["ending_balance"] == 5000
    assert f["first_below_threshold"] is None


def test_warns_before_balance_drops_below_threshold():
    txns = monthly("WEWORK", -1500, 1)
    f = build_forecast(txns, current_balance=3500, low_threshold=1000, today=TODAY)  # 2 rent payments in window
    assert f["first_below_threshold"] is not None
    assert any("drop below" in w for w in f["warnings"])
    assert f["ending_balance"] == 500


def test_monthly_bills_land_on_the_same_day_each_month():
    txns = monthly("ADOBE", -59.99, 3)
    f = build_forecast(txns, current_balance=5000, low_threshold=0, today=TODAY)
    days = {u["date"][-2:] for u in f["upcoming_30_days"]}
    assert days == {"03"}
