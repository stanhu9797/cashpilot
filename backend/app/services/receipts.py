"""Receipt photo or PDF -> validated, structured fields with per-field confidence."""
import base64
import datetime as dt

from pydantic import BaseModel, Field, ValidationError, field_validator

from ..ai.client import AIUnavailable, call_tool

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "application/pdf"}


def sniff_type(data: bytes) -> str | None:
    """Identify the file from its first bytes instead of trusting the browser's label."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    return None

RECEIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "is_receipt": {"type": "boolean", "description": "False if the image is not a receipt or invoice"},
        "merchant": {"type": ["string", "null"]},
        "date": {"type": ["string", "null"], "description": "YYYY-MM-DD"},
        "total": {"type": ["number", "null"], "description": "Final amount paid, including tax and tip"},
        "subtotal": {"type": ["number", "null"]},
        "tax": {"type": ["number", "null"]},
        "tip": {"type": ["number", "null"]},
        "currency": {"type": ["string", "null"], "description": "ISO code, e.g. USD"},
        "payment_method": {"type": ["string", "null"], "description": "e.g. 'Visa ending 4417', 'cash'"},
        "line_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"description": {"type": "string"}, "amount": {"type": ["number", "null"]}},
                "required": ["description"],
            },
        },
        "confidence": {
            "type": "object",
            "description": "0-1 confidence for each field. Use < 0.8 if blurry, cut off, handwritten, or guessed.",
            "properties": {
                "merchant": {"type": "number"},
                "date": {"type": "number"},
                "total": {"type": "number"},
            },
            "required": ["merchant", "date", "total"],
        },
        "notes": {"type": ["string", "null"], "description": "Anything the user should double-check"},
    },
    "required": ["is_receipt", "merchant", "date", "total", "confidence", "line_items"],
}

SYSTEM = (
    "You read receipts and invoices for bookkeeping. Extract only what is printed on the document. "
    "If a field is missing or unreadable, return null for it and give it low confidence. Never invent a value. "
    "The total is the final amount charged (after tax, tip, and discounts). Dates must be YYYY-MM-DD."
)


class LineItem(BaseModel):
    description: str
    amount: float | None = None


class ReceiptData(BaseModel):
    is_receipt: bool = True
    merchant: str | None = None
    date: dt.date | None = None
    total: float | None = Field(default=None)
    subtotal: float | None = None
    tax: float | None = None
    tip: float | None = None
    currency: str | None = "USD"
    payment_method: str | None = None
    line_items: list[LineItem] = []
    confidence: dict[str, float] = {}
    notes: str | None = None
    warnings: list[str] = []

    @field_validator("date", mode="before")
    @classmethod
    def _blank_date(cls, v):
        return v or None

    @field_validator("confidence")
    @classmethod
    def _clamp(cls, v):
        return {k: max(0.0, min(1.0, float(x))) for k, x in v.items()}


def sanity_check(data: ReceiptData) -> ReceiptData:
    """Checks the AI can't do reliably on its own. Lower confidence when something doesn't add up."""
    warnings = []
    conf = dict(data.confidence)
    if data.total is not None and data.total <= 0:
        warnings.append("Total is zero or negative.")
        conf["total"] = min(conf.get("total", 0), 0.3)
    if data.subtotal is not None and data.total is not None:
        expected = round(data.subtotal + (data.tax or 0) + (data.tip or 0), 2)
        if abs(expected - data.total) > 0.05:
            warnings.append(f"Subtotal + tax + tip = {expected:.2f}, but the total reads {data.total:.2f}.")
            conf["total"] = min(conf.get("total", 0), 0.6)
    if data.date is not None:
        if data.date > dt.date.today():
            warnings.append("Date is in the future.")
            conf["date"] = min(conf.get("date", 0), 0.3)
        elif (dt.date.today() - data.date).days > 730:
            warnings.append("Date is more than two years ago.")
            conf["date"] = min(conf.get("date", 0), 0.6)
    for field in ("merchant", "date", "total"):
        if getattr(data, field) is None:
            conf[field] = 0.0
    data.confidence = conf
    data.warnings = warnings
    return data


def extract_receipt(file_bytes: bytes, content_type: str, db=None, user_id=None) -> ReceiptData:
    if content_type not in ALLOWED_TYPES:
        raise ValueError("Upload a JPG, PNG, WEBP, or PDF.")
    b64 = base64.standard_b64encode(file_bytes).decode()
    if content_type == "application/pdf":
        doc = {"type": "document", "source": {"type": "base64", "media_type": content_type, "data": b64}}
    else:
        doc = {"type": "image", "source": {"type": "base64", "media_type": content_type, "data": b64}}
    raw = call_tool(
        feature="receipt_extract",
        system=SYSTEM,
        content=[doc, {"type": "text", "text": "Extract this receipt."}],
        tool_name="record_receipt",
        tool_description="Record the fields read from the receipt.",
        schema=RECEIPT_SCHEMA,
        db=db,
        user_id=user_id,
        summary=f"receipt ({content_type}, {len(file_bytes)} bytes)",
    )
    try:
        data = ReceiptData.model_validate(raw)
    except ValidationError as e:
        raise AIUnavailable(f"The AI returned fields that didn't pass validation: {e.errors()[0]['msg']}") from e
    return sanity_check(data)
