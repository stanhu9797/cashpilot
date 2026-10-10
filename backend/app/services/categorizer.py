"""Rules first, AI second.

Order of decisions for each transaction:
  1. A rule the user created by correcting a category  -> confidence 1.00
  2. A built-in vendor rule                              -> confidence 0.95
  3. The AI (only for what's left)                       -> model's own confidence
  4. Nothing matched / AI unavailable                    -> "Other", flagged for review
"""
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.client import AIUnavailable, call_tool, to_json
from ..categories import CATEGORIES
from ..config import get_settings
from ..models import CategoryRule, Correction

# Prefixes payment processors add to bank descriptions
_PREFIXES = re.compile(r"^(SQ \*|SQ\*|TST\* ?|TST \*|PAYPAL \*|PP\*|SP \*|SP\*|POS |DEBIT CARD PURCHASE |ACH |CHECKCARD \d+ )", re.I)
_NOISE = re.compile(r"(#\s*\d+|\b\d{3,}\b|\bstore\b|[*#]|\.com\b|\binc\b|\bllc\b)", re.I)
_STATE_SUFFIX = re.compile(r"(?<=\S)\s+[A-Z]{2}$")  # trailing ' NC', ' CA' after a real name

# keyword -> category. Matched against the normalized merchant key.
BUILTIN_RULES: list[tuple[str, str]] = [
    ("ADOBE", "Software & Subscriptions"),
    ("GITHUB", "Software & Subscriptions"),
    ("NOTION", "Software & Subscriptions"),
    ("FIGMA", "Software & Subscriptions"),
    ("DROPBOX", "Software & Subscriptions"),
    ("GOOGLE WORKSPACE", "Software & Subscriptions"),
    ("GSUITE", "Software & Subscriptions"),
    ("MICROSOFT", "Software & Subscriptions"),
    ("ZOOM", "Software & Subscriptions"),
    ("SLACK", "Software & Subscriptions"),
    ("CANVA", "Software & Subscriptions"),
    ("ANTHROPIC", "Software & Subscriptions"),
    ("OPENAI", "Software & Subscriptions"),
    ("AWS", "Software & Subscriptions"),
    ("AMAZON WEB SERVICES", "Software & Subscriptions"),
    ("SQUARESPACE", "Software & Subscriptions"),
    ("SHOPIFY", "Software & Subscriptions"),
    ("STAPLES", "Office Supplies"),
    ("OFFICE DEPOT", "Office Supplies"),
    ("STARBUCKS", "Meals"),
    ("DOORDASH", "Meals"),
    ("UBER EATS", "Meals"),
    ("GRUBHUB", "Meals"),
    ("CHIPOTLE", "Meals"),
    ("DELTA", "Travel"),
    ("AMERICAN AIR", "Travel"),
    ("UNITED AIR", "Travel"),
    ("SOUTHWEST", "Travel"),
    ("AIRBNB", "Travel"),
    ("MARRIOTT", "Travel"),
    ("HILTON", "Travel"),
    ("LYFT", "Travel"),
    ("UBER", "Travel"),  # after UBER EATS, so food still matches first
    ("FACEBOOK ADS", "Advertising & Marketing"),
    ("META ADS", "Advertising & Marketing"),
    ("GOOGLE ADS", "Advertising & Marketing"),
    ("LINKEDIN ADS", "Advertising & Marketing"),
    ("MAILCHIMP", "Advertising & Marketing"),
    ("VERIZON", "Phone & Internet"),
    ("AT&T", "Phone & Internet"),
    ("T-MOBILE", "Phone & Internet"),
    ("COMCAST", "Phone & Internet"),
    ("XFINITY", "Phone & Internet"),
    ("SPECTRUM", "Phone & Internet"),
    ("DUKE ENERGY", "Rent & Utilities"),
    ("WEWORK", "Rent & Utilities"),
    ("STATE FARM", "Insurance"),
    ("GEICO", "Insurance"),
    ("HISCOX", "Insurance"),
    ("OVERDRAFT", "Bank Fees"),
    ("MONTHLY SERVICE FEE", "Bank Fees"),
    ("WIRE FEE", "Bank Fees"),
    ("IRS", "Taxes"),
    ("US TREASURY", "Taxes"),
    ("NCDOR", "Taxes"),
    ("STRIPE PAYOUT", "Income"),
    ("STRIPE TRANSFER", "Income"),
    ("UPWORK", "Income"),
    ("FIVERR", "Income"),
    ("TRANSFER TO SAVINGS", "Transfers"),
    ("TRANSFER TO PERSONAL", "Transfers"),
    ("TRANSFER FROM SAVINGS", "Transfers"),
]


def normalize_merchant(text: str) -> str:
    """'SQ *JOES COFFEE #4421 CHARLOTTE NC' -> 'JOES COFFEE CHARLOTTE'"""
    s = (text or "").upper().strip()
    s = _PREFIXES.sub("", s)
    s = _NOISE.sub(" ", s)
    s = re.sub(r"[^A-Z0-9&' -]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return _STATE_SUFFIX.sub("", s).strip()


@dataclass
class Suggestion:
    category: str
    confidence: float
    source: str  # your_rule | rule | ai | none
    reason: str = ""

    @property
    def needs_review(self) -> bool:
        return self.confidence < get_settings().review_threshold


def match_builtin(merchant_key: str) -> str | None:
    for keyword, category in BUILTIN_RULES:
        if re.search(rf"(^|\b){re.escape(keyword)}(\b|$)", merchant_key):
            return category
    return None


def match_user_rule(db: Session, user_id: int, merchant_key: str) -> str | None:
    rule = db.scalar(
        select(CategoryRule).where(CategoryRule.user_id == user_id, CategoryRule.merchant_key == merchant_key)
    )
    return rule.category if rule else None


def rule_suggestion(db: Session, user_id: int, merchant: str, amount: float) -> Suggestion | None:
    key = normalize_merchant(merchant)
    if not key:
        return None
    if cat := match_user_rule(db, user_id, key):
        return Suggestion(cat, 1.0, "your_rule", "Matches a rule you created")
    if cat := match_builtin(key):
        # A positive amount at a known vendor is usually a refund, not income
        if amount > 0 and cat != "Income":
            return Suggestion(cat, 0.6, "rule", "Known vendor, but money came in (refund?)")
        return Suggestion(cat, 0.95, "rule", "Known vendor")
    return None


AI_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "category": {"type": "string", "enum": CATEGORIES},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "reason": {"type": "string", "description": "Under 12 words"},
                },
                "required": ["index", "category", "confidence", "reason"],
            },
        }
    },
    "required": ["results"],
}


def _examples(db: Session, user_id: int, limit: int = 15) -> list[dict]:
    rows = db.scalars(
        select(Correction).where(Correction.user_id == user_id).order_by(Correction.created_at.desc()).limit(limit)
    ).all()
    return [{"merchant": r.merchant, "description": r.description, "category": r.new_category} for r in rows]


def ai_suggestions(db: Session, user_id: int, items: list[dict]) -> dict[int, Suggestion]:
    """items: [{index, merchant, description, amount}] -> {index: Suggestion}"""
    if not items:
        return {}
    examples = _examples(db, user_id)
    system = (
        "You categorize bank transactions for a freelancer or very small business. "
        "Pick exactly one category from the allowed list. Negative amounts are money out; positive are money in. "
        "Be honest about uncertainty: use confidence below 0.8 whenever the merchant name alone could reasonably "
        "fit more than one category. Never guess wildly; use 'Other' with low confidence if you can't tell."
    )
    prompt = (
        f"Allowed categories: {to_json(CATEGORIES)}\n\n"
        f"How this user has corrected categories before (follow their preferences):\n{to_json(examples) if examples else 'None yet.'}\n\n"
        f"Transactions to categorize:\n{to_json(items)}"
    )
    result = call_tool(
        feature="categorize",
        system=system,
        content=prompt,
        tool_name="record_categories",
        tool_description="Record one category suggestion per transaction.",
        schema=AI_SCHEMA,
        db=db,
        user_id=user_id,
        summary=f"{len(items)} transactions",
    )
    out: dict[int, Suggestion] = {}
    for r in result.get("results", []):
        cat = r.get("category")
        if cat not in CATEGORIES:
            continue
        conf = max(0.0, min(1.0, float(r.get("confidence", 0))))
        out[int(r["index"])] = Suggestion(cat, round(conf, 2), "ai", str(r.get("reason", ""))[:200])
    return out


def categorize_many(db: Session, user_id: int, txns: list[dict], use_ai: bool = True) -> list[Suggestion]:
    """txns: [{merchant, description, amount}] -> one Suggestion per txn, same order."""
    suggestions: list[Suggestion | None] = []
    pending = []
    for i, t in enumerate(txns):
        s = rule_suggestion(db, user_id, t["merchant"], float(t["amount"]))
        suggestions.append(s)
        if s is None:
            pending.append({"index": i, "merchant": t["merchant"], "description": t.get("description", ""), "amount": float(t["amount"])})

    if pending and use_ai and get_settings().ai_configured:
        for start in range(0, len(pending), 40):  # batch to keep prompts small
            chunk = pending[start : start + 40]
            try:
                found = ai_suggestions(db, user_id, chunk)
            except AIUnavailable:
                found = {}
            for item in chunk:
                if item["index"] in found:
                    suggestions[item["index"]] = found[item["index"]]

    return [s or Suggestion("Other", 0.0, "none", "No rule matched") for s in suggestions]
