"""Data models. Amounts are signed: negative = money out, positive = money in."""
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    current_balance: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    balance_as_of: Mapped[date | None] = mapped_column(Date, nullable=True)
    low_balance_threshold: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("1000"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    merchant: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(500), default="")
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    category: Mapped[str] = mapped_column(String(80), default="Other")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    category_source: Mapped[str] = mapped_column(String(20), default="none")  # your_rule | rule | ai | user | none
    needs_review: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str] = mapped_column(String(20), default="manual")  # manual | csv | receipt | demo
    receipt_id: Mapped[int | None] = mapped_column(ForeignKey("receipts.id"), nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user = relationship("User", back_populates="transactions")


class Receipt(Base):
    __tablename__ = "receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    file_key: Mapped[str] = mapped_column(String(500))
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="pending")  # extracted | failed | saved
    extracted: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CategoryRule(Base):
    """A rule the user taught the app by correcting a category."""

    __tablename__ = "category_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    merchant_key: Mapped[str] = mapped_column(String(255), index=True)
    category: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Correction(Base):
    """Every time the user changes a suggested category. Used as examples for the AI."""

    __tablename__ = "corrections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    transaction_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True)
    merchant: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(500), default="")
    old_category: Mapped[str] = mapped_column(String(80))
    new_category: Mapped[str] = mapped_column(String(80))
    old_source: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AILog(Base):
    """Audit trail of every AI call: what was asked, what came back, how long it took."""

    __tablename__ = "ai_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    feature: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(120))
    input_summary: Mapped[str] = mapped_column(Text, default="")
    output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
