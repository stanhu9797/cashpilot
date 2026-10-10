"""Request and response shapes, with input validation."""
import datetime as dt
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .categories import CATEGORIES


MIN_DATE = dt.date(2000, 1, 1)


def _password_bytes(v: str) -> str:
    # bcrypt only reads the first 72 bytes; longer passwords would be silently truncated
    if len(v.encode("utf-8")) > 72:
        raise ValueError("Password is too long. Use 72 characters or fewer (emoji count as several).")
    return v


class RegisterIn(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=72)
    name: str = Field(default="", max_length=120)

    _pw = field_validator("password")(classmethod(lambda cls, v: _password_bytes(v)))

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Enter a valid email address.")
        return v


class LoginIn(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(max_length=200)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    name: str
    current_balance: Decimal | None
    balance_as_of: dt.date | None
    low_balance_threshold: Decimal


class AuthOut(BaseModel):
    token: str
    user: UserOut


class SettingsIn(BaseModel):
    current_balance: Decimal = Field(ge=-1_000_000, le=100_000_000)
    low_balance_threshold: Decimal = Field(ge=0, le=10_000_000)
    name: str | None = Field(default=None, max_length=120)


class TransactionIn(BaseModel):
    date: dt.date
    merchant: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=500)
    amount: Decimal = Field(description="Negative = money out, positive = money in")
    category: str | None = None
    receipt_id: int | None = None

    @field_validator("amount")
    @classmethod
    def _nonzero(cls, v):
        if v == 0:
            raise ValueError("Amount can't be zero.")
        if abs(v) > 10_000_000:
            raise ValueError("That amount looks too large. Check for a typo.")
        return v.quantize(Decimal("0.01"))

    @field_validator("date")
    @classmethod
    def _sensible_date(cls, v):
        if v > dt.date.today() + dt.timedelta(days=1):
            raise ValueError("Date can't be in the future.")
        if v < MIN_DATE:
            raise ValueError("Date must be in 2000 or later.")
        return v

    @field_validator("merchant", "description")
    @classmethod
    def _strip(cls, v, info):
        v = " ".join(v.split())  # trim and collapse whitespace
        if info.field_name == "merchant" and not v:
            raise ValueError("Enter who you paid or who paid you.")
        return v

    @field_validator("category")
    @classmethod
    def _cat(cls, v):
        if v is not None and v not in CATEGORIES:
            raise ValueError("Pick a category from the list.")
        return v


class CategoryUpdate(BaseModel):
    category: str
    remember: bool = True  # create a rule for this merchant

    @field_validator("category")
    @classmethod
    def _cat(cls, v):
        if v not in CATEGORIES:
            raise ValueError("Pick a category from the list.")
        return v


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    date: dt.date
    merchant: str
    description: str
    amount: Decimal
    category: str
    confidence: float
    category_source: str
    needs_review: bool
    source: str
    receipt_id: int | None


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=300)

    @field_validator("question")
    @classmethod
    def _real_question(cls, v):
        v = " ".join(v.split())
        if len(v) < 3:
            raise ValueError("Type a question first.")
        return v
