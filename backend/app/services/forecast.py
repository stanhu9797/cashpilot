"""90-day cash flow forecast. Plain statistics, no AI — the AI only explains the result.

Method:
  1. Find recurring transactions (same merchant, similar amount, regular weekly or monthly gaps).
  2. Project each recurring item forward on its schedule.
  3. Everything else becomes an average daily amount from the last 90 days ("everyday spending/income").
  4. Start from the user's current balance and walk forward one day at a time.
"""
import datetime as dt
from collections import defaultdict
from dataclasses import dataclass
from statistics import median

from .categorizer import normalize_merchant

HISTORY_DAYS = 90
HORIZON_DAYS = 90


@dataclass
class Recurring:
    merchant: str
    amount: float
    interval_days: int
    last_date: dt.date
    label: str  # weekly | biweekly | monthly

    def occurrences(self, start: dt.date, end: dt.date) -> list[dt.date]:
        out = []
        k = 1
        while True:
            d = _add_months(self.last_date, k) if self.label == "monthly" else self.last_date + dt.timedelta(days=self.interval_days * k)
            if d > end:
                return out
            if d >= start:
                out.append(d)
            k += 1


def _add_months(d: dt.date, months: int) -> dt.date:
    """Same day next month (Jan 31 -> Feb 28), so monthly bills don't drift."""
    m = d.month - 1 + months
    year, month = d.year + m // 12, m % 12 + 1
    last_day = (dt.date(year + (month == 12), month % 12 + 1, 1) - dt.timedelta(days=1)).day
    return dt.date(year, month, min(d.day, last_day))


def _classify_interval(days: float) -> tuple[int, str] | None:
    if 6 <= days <= 8:
        return 7, "weekly"
    if 13 <= days <= 16:
        return 14, "biweekly"
    if 26 <= days <= 35:
        return 30, "monthly"
    return None


def find_recurring(txns: list[dict]) -> list[Recurring]:
    """txns: [{date, merchant, amount}] (amount signed float)."""
    groups: dict[tuple[str, bool], list[dict]] = defaultdict(list)
    for t in txns:
        key = normalize_merchant(t["merchant"])
        if key:
            groups[(key, t["amount"] > 0)].append(t)

    found = []
    for (key, _), items in groups.items():
        if len(items) < 2:
            continue
        items = sorted(items, key=lambda t: t["date"])
        gaps = [(b["date"] - a["date"]).days for a, b in zip(items, items[1:])]
        cls = _classify_interval(median(gaps))
        if not cls:
            continue
        # Gaps must be consistent (no single gap more than 40% off the typical gap)
        if any(abs(g - median(gaps)) > 0.4 * median(gaps) for g in gaps):
            continue
        amounts = [t["amount"] for t in items]
        typical = median(amounts)
        # Two occurrences can be coincidence, so they must match almost exactly; 3+ can vary up to 20%
        tolerance = 0.02 if len(items) == 2 else 0.2
        if any(abs(a - typical) > tolerance * abs(typical) + 1 for a in amounts):
            continue
        found.append(Recurring(items[-1]["merchant"], round(typical, 2), cls[0], items[-1]["date"], cls[1]))
    return found


def build_forecast(
    txns: list[dict],
    current_balance: float,
    low_threshold: float,
    today: dt.date | None = None,
) -> dict:
    today = today or dt.date.today()
    window_start = today - dt.timedelta(days=HISTORY_DAYS)
    history = [t for t in txns if window_start <= t["date"] <= today]
    recurring = find_recurring(history)
    recurring_keys = {(normalize_merchant(r.merchant), r.amount > 0) for r in recurring}

    everyday = [t for t in history if (normalize_merchant(t["merchant"]), t["amount"] > 0) not in recurring_keys]
    days_of_data = max(1, min(HISTORY_DAYS, (today - min((t["date"] for t in history), default=today)).days or 1))
    daily_out = sum(t["amount"] for t in everyday if t["amount"] < 0) / days_of_data
    daily_in = sum(t["amount"] for t in everyday if t["amount"] > 0) / days_of_data

    end = today + dt.timedelta(days=HORIZON_DAYS)
    scheduled: dict[dt.date, list[dict]] = defaultdict(list)
    for r in recurring:
        for d in r.occurrences(today + dt.timedelta(days=1), end):
            scheduled[d].append({"merchant": r.merchant, "amount": r.amount})

    balance = current_balance
    series = []
    first_below = None
    lowest = {"date": today.isoformat(), "balance": round(balance, 2)}
    for i in range(1, HORIZON_DAYS + 1):
        d = today + dt.timedelta(days=i)
        balance += daily_out + daily_in + sum(x["amount"] for x in scheduled.get(d, []))
        series.append({"date": d.isoformat(), "balance": round(balance, 2)})
        if balance < lowest["balance"]:
            lowest = {"date": d.isoformat(), "balance": round(balance, 2)}
        if first_below is None and balance < low_threshold:
            first_below = d

    warnings = []
    if first_below:
        window = [
            {"date": d.isoformat(), **x}
            for d, xs in sorted(scheduled.items())
            if first_below - dt.timedelta(days=10) <= d <= first_below
            for x in xs
            if x["amount"] < 0
        ]
        biggest = sorted(window, key=lambda x: x["amount"])[:2]
        why = (
            " Charges due just before then: " + ", ".join(f"{b['merchant']} (${abs(b['amount']):,.2f})" for b in biggest) + "."
            if biggest
            else ""
        )
        warnings.append(
            f"Your balance may drop below ${low_threshold:,.0f} around {first_below.strftime('%B %-d')}.{why}"
        )
    if daily_out + daily_in < 0 and not any(r.amount > 0 for r in recurring):
        warnings.append("No regular income detected in the last 90 days, so the forecast assumes income stays irregular.")
    if len(history) < 20:
        warnings.append("There are fewer than 20 transactions in the last 90 days, so treat this forecast as rough.")

    upcoming = sorted(
        ({"date": d.isoformat(), **x} for d, xs in scheduled.items() if d <= today + dt.timedelta(days=30) for x in xs),
        key=lambda x: x["date"],
    )
    return {
        "starting_balance": round(current_balance, 2),
        "low_threshold": low_threshold,
        "series": series,
        "lowest": lowest,
        "first_below_threshold": first_below.isoformat() if first_below else None,
        "ending_balance": series[-1]["balance"] if series else current_balance,
        "daily_everyday_spending": round(-daily_out, 2),
        "daily_everyday_income": round(daily_in, 2),
        "recurring": [
            {"merchant": r.merchant, "amount": r.amount, "schedule": r.label, "next": r.occurrences(today + dt.timedelta(days=1), end)[0].isoformat() if r.occurrences(today + dt.timedelta(days=1), end) else None}
            for r in sorted(recurring, key=lambda r: r.amount)
        ],
        "upcoming_30_days": upcoming,
        "warnings": warnings,
        "method": "Recurring items projected on their schedule; everything else averaged per day over the last 90 days.",
    }
