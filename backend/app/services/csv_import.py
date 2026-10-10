"""Bank CSV import. Handles the common export formats:
  - date, description, amount            (negative = money out)
  - date, description, debit, credit     (two columns)
Column names are matched loosely ("Transaction Date", "Posting Date", "Payee", "Withdrawal", ...).
"""
import csv
import hashlib
import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

DATE_COLS = ["date", "transaction date", "posting date", "posted date", "trans date"]
DESC_COLS = ["description", "merchant", "payee", "name", "details", "memo"]
AMOUNT_COLS = ["amount", "transaction amount"]
DEBIT_COLS = ["debit", "withdrawal", "withdrawals", "money out", "debit amount"]
CREDIT_COLS = ["credit", "deposit", "deposits", "money in", "credit amount"]
MAX_ROWS = 5000  # one import; keeps AI cost and request time bounded
DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d-%b-%Y", "%b %d, %Y", "%Y/%m/%d"]


class CSVFormatError(ValueError):
    pass


def _find(headers: dict[str, str], options: list[str]) -> str | None:
    for opt in options:
        if opt in headers:
            return headers[opt]
    return None


def parse_date(value: str) -> date:
    v = (value or "").strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    raise CSVFormatError(f"Couldn't read the date '{v}'. Use a format like 2026-09-30 or 09/30/2026.")


def parse_money(value: str) -> Decimal | None:
    v = (value or "").strip().replace("$", "").replace(",", "")
    if not v:
        return None
    negative = v.startswith("(") and v.endswith(")")
    v = v.strip("()")
    try:
        d = Decimal(v)
    except InvalidOperation:
        raise CSVFormatError(f"Couldn't read the amount '{value}'.")
    return -d if negative else d


def dedupe_key(user_id: int, d: date, amount: Decimal, description: str) -> str:
    raw = f"{user_id}|{d.isoformat()}|{amount:.2f}|{description.strip().upper()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def parse_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    if not reader.fieldnames:
        raise CSVFormatError("The file is empty.")
    headers = {h.strip().lower(): h for h in reader.fieldnames if h}
    date_col = _find(headers, DATE_COLS)
    desc_col = _find(headers, DESC_COLS)
    amount_col = _find(headers, AMOUNT_COLS)
    debit_col, credit_col = _find(headers, DEBIT_COLS), _find(headers, CREDIT_COLS)
    if not date_col or not desc_col or not (amount_col or debit_col or credit_col):
        raise CSVFormatError(
            "The CSV needs a date column, a description column, and either an amount column or debit/credit columns. "
            f"Found: {', '.join(reader.fieldnames)}"
        )

    rows = []
    for line_no, row in enumerate(reader, start=2):
        if len(rows) >= MAX_ROWS:
            raise CSVFormatError(f"The file has more than {MAX_ROWS:,} transactions. Split it into smaller date ranges.")
        if not any((v or "").strip() for v in row.values()):
            continue
        try:
            d = parse_date(row[date_col])
            if amount_col:
                amount = parse_money(row[amount_col])
            else:
                debit = parse_money(row.get(debit_col, "")) if debit_col else None
                credit = parse_money(row.get(credit_col, "")) if credit_col else None
                amount = (credit or Decimal("0")) - abs(debit or Decimal("0"))
            if amount is None:
                continue
        except CSVFormatError as e:
            raise CSVFormatError(f"Row {line_no}: {e}")
        if d < date(2000, 1, 1) or d > date.today():
            raise CSVFormatError(f"Row {line_no}: the date {d.isoformat()} is outside the supported range.")
        desc = " ".join((row[desc_col] or "").split())
        rows.append({"date": d, "merchant": desc[:255] or "Unknown", "description": desc[:500], "amount": amount})
    if not rows:
        raise CSVFormatError("No transactions were found in the file.")
    return rows
