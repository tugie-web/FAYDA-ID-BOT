"""Transactional order/payment operations; not public endpoints."""
from __future__ import annotations
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.models import Order, PaymentRecord

class DuplicateTransactionError(ValueError):
    pass

class PaymentStateError(ValueError):
    pass

def create_order(db: Session, *, customer_telegram_id: int, service_code: str, amount: Decimal | str | int) -> Order:
    price = Decimal(str(amount))
    if customer_telegram_id <= 0 or not service_code.strip() or price <= 0:
        raise ValueError("A valid customer, service, and positive price are required.")
    order = Order(public_id=str(uuid4()), customer_telegram_id=customer_telegram_id,
                  service_code=service_code.strip(), amount=price, currency="ETB", status="pending_payment")
    db.add(order)
    db.commit()
    db.refresh(order)
    return order

def submit_payment_reference(db: Session, *, order_id: int, provider: str,
                             transaction_reference: str, submitted_amount: Decimal | str | int) -> PaymentRecord:
    provider = provider.strip().lower()
    reference = transaction_reference.strip()
    amount = Decimal(str(submitted_amount))
    if provider not in {"cbe", "telebirr", "cbebirr"}:
        raise ValueError("Unsupported payment provider.")
    if not reference or amount <= 0:
        raise ValueError("A transaction reference and positive amount are required.")
    order = db.get(Order, order_id)
    if order is None:
        raise ValueError("Order not found.")
    if order.status != "pending_payment":
        raise PaymentStateError("This order is not awaiting payment.")
    if amount != order.amount:
        raise ValueError("Submitted amount must exactly match the order amount.")
    record = PaymentRecord(order_id=order.id, provider=provider, transaction_reference=reference,
                           submitted_amount=amount, status="pending")
    db.add(record)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateTransactionError("This transaction reference has already been submitted for this provider.") from exc
    db.refresh(record)
    return record

def apply_cheki_result(db: Session, *, payment_id: int, result) -> PaymentRecord:
    payment = db.execute(select(PaymentRecord).where(PaymentRecord.id == payment_id).with_for_update()).scalar_one_or_none()
    if payment is None:
        raise ValueError("Payment record not found.")
    if payment.status not in {"pending", "manual_review"}:
        raise PaymentStateError("This payment has already reached a final state.")
    if result.provider.value != payment.provider or result.reference != payment.transaction_reference:
        raise PaymentStateError("Verification result does not match the submitted payment.")
    payment.status = result.status
    payment.verification_source = "cheki"
    payment.verified_amount = result.amount
    payment.currency = result.currency
    payment.receiver_name = result.receiver_name
    payment.receiver_account = result.receiver_account
    payment.verification_reason = result.reason
    if result.can_activate_service:
        order = db.execute(select(Order).where(Order.id == payment.order_id).with_for_update()).scalar_one()
        if order.status != "pending_payment":
            raise PaymentStateError("Order is no longer awaiting payment.")
        order.status = "paid"
    db.commit()
    db.refresh(payment)
    return payment

def review_payment_manually(db: Session, *, payment_id: int, reviewer_telegram_id: int,
                            decision: str, note: str) -> PaymentRecord:
    """Admin-only fallback; the calling route must authenticate the reviewer."""
    if decision not in {"approve", "reject"}:
        raise ValueError("Decision must be approve or reject.")
    if reviewer_telegram_id <= 0 or not note.strip():
        raise ValueError("Reviewer ID and an audit note are required.")
    payment = db.execute(select(PaymentRecord).where(PaymentRecord.id == payment_id).with_for_update()).scalar_one_or_none()
    if payment is None:
        raise ValueError("Payment record not found.")
    if payment.status not in {"pending", "manual_review"}:
        raise PaymentStateError("This payment has already reached a final state.")
    order = db.execute(select(Order).where(Order.id == payment.order_id).with_for_update()).scalar_one()
    if decision == "approve":
        if order.status != "pending_payment":
            raise PaymentStateError("Order is no longer awaiting payment.")
        payment.status = "verified"
        payment.verification_source = "manual"
        order.status = "paid"
    else:
        payment.status = "rejected"
        payment.verification_source = "manual"
    payment.reviewed_by = reviewer_telegram_id
    payment.review_note = note.strip()
    db.commit()
    db.refresh(payment)
    return payment
