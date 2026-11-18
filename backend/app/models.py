"""Persistent order and payment records."""
from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_orders_amount_positive"),
        Index("ix_orders_customer_created", "customer_telegram_id", "created_at"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    customer_telegram_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    service_code: Mapped[str] = mapped_column(String(80), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="ETB")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending_payment")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    payments: Mapped[list["PaymentRecord"]] = relationship(back_populates="order", cascade="all, delete-orphan")

class PaymentRecord(Base):
    __tablename__ = "payment_records"
    __table_args__ = (
        UniqueConstraint("provider", "transaction_reference", name="uq_payment_provider_reference"),
        CheckConstraint("submitted_amount > 0", name="ck_payment_submitted_amount_positive"),
        Index("ix_payment_status_created", "status", "created_at"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    transaction_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    submitted_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    verification_source: Mapped[str | None] = mapped_column(String(20))
    verified_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    receiver_name: Mapped[str | None] = mapped_column(String(160))
    receiver_account: Mapped[str | None] = mapped_column(String(100))
    verification_reason: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[int | None] = mapped_column(Integer)
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    order: Mapped[Order] = relationship(back_populates="payments")
