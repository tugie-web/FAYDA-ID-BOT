"""Provider-specific Ethiopian payment verification through Cheki.

Only Cheki's verified=true response can confirm a receipt. Provider, amount,
currency, and configured receiver checks must also match. A transaction ID's
shape or a screenshot is never sufficient proof.

Callers must persist transaction references with a UNIQUE constraint and
atomically claim them before activating a paid service. This module does not
replace database-level duplicate protection.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any

import httpx


CHEKI_VERIFY_URL = "https://cheki.et/api/verify"
CHEKI_TIMEOUT_SECONDS = 65.0


class PaymentProvider(str, Enum):
    CBE_BANK = "cbe"
    TELEBIRR = "telebirr"


@dataclass(frozen=True)
class PaymentVerification:
    status: str
    provider: PaymentProvider
    reference: str
    verified: bool
    amount: Decimal | None = None
    currency: str | None = None
    receiver_name: str | None = None
    receiver_account: str | None = None
    reason: str | None = None

    @property
    def can_activate_service(self) -> bool:
        return self.status == "verified" and self.verified


async def verify_payment(
    *,
    provider: PaymentProvider | str,
    reference: str,
    expected_amount: Decimal | str | int | float,
    expected_receiver_name: str | None = None,
    expected_receiver_account_suffix: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> PaymentVerification:
    """Verify one CBE Bank or Telebirr receipt using the selected provider.

    Prefer a current CBE receipt ID or mbreciept link for CBE Bank. Telebirr
    uses its transaction reference. The selected provider is sent to Cheki and
    the returned bankCode is enforced, so cross-provider references are denied.

    Network/API failures return manual_review and never approve a payment.
    """
    try:
        selected_provider = PaymentProvider(provider)
    except ValueError:
        raise ValueError("Unsupported payment provider. Choose CBE Bank or Telebirr.")

    cleaned_reference = reference.strip()
    if not cleaned_reference:
        raise ValueError("Transaction ID or receipt reference is required.")

    try:
        expected = Decimal(str(expected_amount))
    except (InvalidOperation, ValueError, TypeError):
        expected = None
    if expected is None or expected <= 0:
        raise ValueError("Expected payment amount must be a positive number.")

    payload = {"bank": selected_provider.value, "reference": cleaned_reference}
    owns_client = client is None

    try:
        if owns_client:
            client = httpx.AsyncClient(timeout=CHEKI_TIMEOUT_SECONDS)
        assert client is not None
        response = await client.post(CHEKI_VERIFY_URL, json=payload)
        if response.status_code == 429:
            return PaymentVerification(
                status="manual_review", provider=selected_provider,
                reference=cleaned_reference, verified=False,
                reason="Cheki rate limit reached; admin review required.",
            )
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        return PaymentVerification(
            status="manual_review", provider=selected_provider,
            reference=cleaned_reference, verified=False,
            reason=f"Automatic verification unavailable: {type(exc).__name__}.",
        )
    finally:
        if owns_client and client is not None:
            await client.aclose()

    if not isinstance(data, dict):
        return PaymentVerification(
            status="manual_review", provider=selected_provider,
            reference=cleaned_reference, verified=False,
            reason="Cheki returned an unexpected response.",
        )

    if data.get("bankCode") != selected_provider.value:
        return PaymentVerification(
            status="rejected", provider=selected_provider,
            reference=cleaned_reference, verified=False,
            reason="The receipt belongs to a different payment provider.",
        )

    # verified=true is Cheki's only bank-confirmed success signal.
    if data.get("verified") is not True:
        return PaymentVerification(
            status="manual_review", provider=selected_provider,
            reference=cleaned_reference, verified=False,
            reason=data.get("error") or "The provider did not confirm this transaction.",
        )

    try:
        actual_amount = Decimal(str(data.get("amount")))
    except (InvalidOperation, ValueError, TypeError):
        actual_amount = None

    if actual_amount is None or actual_amount != expected:
        return PaymentVerification(
            status="rejected", provider=selected_provider,
            reference=cleaned_reference, verified=False,
            amount=actual_amount, currency=data.get("currency"),
            reason="Verified transaction amount does not match the service price.",
        )

    currency = data.get("currency")
    if currency != "ETB":
        return PaymentVerification(
            status="rejected", provider=selected_provider,
            reference=cleaned_reference, verified=False,
            amount=actual_amount, currency=currency,
            reason="Transaction currency is not ETB.",
        )

    receiver_name = data.get("receiverName")
    receiver_account = data.get("receiverAccount")

    if expected_receiver_name and (
        not isinstance(receiver_name, str)
        or receiver_name.strip().casefold() != expected_receiver_name.strip().casefold()
    ):
        return PaymentVerification(
            status="rejected", provider=selected_provider,
            reference=cleaned_reference, verified=False,
            amount=actual_amount, currency=currency,
            receiver_name=receiver_name, receiver_account=receiver_account,
            reason="Payment was sent to an unexpected receiver.",
        )

    if expected_receiver_account_suffix:
        suffix = "".join(ch for ch in expected_receiver_account_suffix if ch.isdigit())
        received_digits = "".join(ch for ch in str(receiver_account or "") if ch.isdigit())
        if not suffix or not received_digits.endswith(suffix):
            return PaymentVerification(
                status="rejected", provider=selected_provider,
                reference=cleaned_reference, verified=False,
                amount=actual_amount, currency=currency,
                receiver_name=receiver_name, receiver_account=receiver_account,
                reason="Receiving account does not match the configured merchant account.",
            )

    return PaymentVerification(
        status="verified", provider=selected_provider,
        reference=cleaned_reference, verified=True,
        amount=actual_amount, currency=currency,
        receiver_name=receiver_name, receiver_account=receiver_account,
    )
