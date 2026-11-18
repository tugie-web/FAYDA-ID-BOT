"""Customer payment API. All customer actions require signed Telegram initData."""
from __future__ import annotations

import os
from decimal import Decimal, InvalidOperation
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_telegram_user
from app.database import get_db
from app.models import Order, PaymentRecord
from app.services.orders import (
    DuplicateTransactionError,
    PaymentStateError,
    apply_cheki_result,
    create_order,
    submit_payment_reference,
)
from app.services.payment_verification import PaymentProvider, verify_payment

router = APIRouter(prefix="/api/v1", tags=["payments"])

# Prices are controlled by the server operator, never supplied by the Mini App.
def service_catalog() -> dict[str, Decimal]:
    raw = os.getenv("SERVICE_CATALOG_JSON", "{}")
    try:
        import json
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError
        catalog = {str(k): Decimal(str(v)) for k, v in parsed.items()}
        if any(v <= 0 for v in catalog.values()):
            raise ValueError
        return catalog
    except (ValueError, TypeError, InvalidOperation):
        raise HTTPException(status_code=503, detail="Service prices are not configured.")


class CreateOrderRequest(BaseModel):
    service_code: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")


class SubmitPaymentRequest(BaseModel):
    provider: Literal["cbe", "telebirr", "cbebirr"]
    transaction_reference: str = Field(min_length=1, max_length=500)


def order_payload(order: Order) -> dict:
    return {
        "order_id": order.public_id,
        "service_code": order.service_code,
        "amount": str(order.amount),
        "currency": order.currency,
        "status": order.status,
    }


@router.post("/orders", status_code=201)
def create_customer_order(
    body: CreateOrderRequest,
    user: dict = Depends(require_telegram_user),
    db: Session = Depends(get_db),
):
    catalog = service_catalog()
    amount = catalog.get(body.service_code)
    if amount is None:
        raise HTTPException(status_code=404, detail="Service not found.")
    order = create_order(
        db, customer_telegram_id=user["id"], service_code=body.service_code, amount=amount
    )
    return order_payload(order)


@router.get("/orders")
def list_customer_orders(
    user: dict = Depends(require_telegram_user),
    db: Session = Depends(get_db),
):
    orders = db.execute(
        select(Order).where(Order.customer_telegram_id == user["id"])
        .order_by(Order.created_at.desc()).limit(50)
    ).scalars().all()
    return {"orders": [order_payload(order) for order in orders]}


@router.post("/orders/{order_id}/payments", status_code=202)
async def submit_customer_payment(
    order_id: int,
    body: SubmitPaymentRequest,
    user: dict = Depends(require_telegram_user),
    db: Session = Depends(get_db),
):
    order = db.execute(
        select(Order).where(
            Order.id == order_id,
            Order.customer_telegram_id == user["id"],
        )
    ).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    try:
        payment = submit_payment_reference(
            db,
            order_id=order.id,
            provider=body.provider,
            transaction_reference=body.transaction_reference,
            submitted_amount=order.amount,
        )
    except DuplicateTransactionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ValueError, PaymentStateError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if body.provider == "cbebirr":
        payment.status = "manual_review"
        payment.verification_source = "manual"
        payment.verification_reason = "Automatic Cheki verification is not enabled for CBE Birr."
        db.commit()
        db.refresh(payment)
    else:
        expected_name = os.getenv(f"{body.provider.upper()}_RECEIVER_NAME") or None
        expected_suffix = os.getenv(f"{body.provider.upper()}_RECEIVER_ACCOUNT_SUFFIX") or None
        result = await verify_payment(
            provider=PaymentProvider(body.provider),
            reference=payment.transaction_reference,
            expected_amount=order.amount,
            expected_receiver_name=expected_name,
            expected_receiver_account_suffix=expected_suffix,
        )
        try:
            payment = apply_cheki_result(db, payment_id=payment.id, result=result)
        except (ValueError, PaymentStateError) as exc:
            raise HTTPException(status_code=409, detail="Payment state changed; contact support.") from exc

    return {
        "payment_id": payment.id,
        "order_id": order.public_id,
        "provider": payment.provider,
        "status": payment.status,
        "message": (
            "Payment confirmed." if payment.status == "verified"
            else "Payment submitted for manual review." if payment.status == "manual_review"
            else "Payment was not accepted."
        ),
    }
