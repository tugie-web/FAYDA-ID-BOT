from decimal import Decimal

import httpx
import pytest

from app.services.payment_verification import PaymentProvider, verify_payment


def make_client(payload, status_code=200):
    def handler(request):
        assert request.url.path == "/api/verify"
        return httpx.Response(status_code, json=payload)
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://cheki.et")


@pytest.mark.asyncio
async def test_cbe_payment_verified_only_for_cbe_and_exact_amount():
    client = make_client({
        "success": True, "verified": True, "bankCode": "cbe",
        "amount": 250, "currency": "ETB",
        "receiverName": "FAYDA SERVICE", "receiverAccount": "1****1234",
    })
    async with client:
        result = await verify_payment(
            provider=PaymentProvider.CBE_BANK,
            reference="https://mbreciept.cbe.com.et/example",
            expected_amount=Decimal("250"),
            expected_receiver_name="Fayda Service",
            expected_receiver_account_suffix="1234",
            client=client,
        )
    assert result.can_activate_service is True


@pytest.mark.asyncio
async def test_cross_provider_receipt_is_rejected():
    client = make_client({
        "success": True, "verified": True, "bankCode": "telebirr",
        "amount": 250, "currency": "ETB",
    })
    async with client:
        result = await verify_payment(
            provider=PaymentProvider.CBE_BANK,
            reference="some-telebirr-reference",
            expected_amount=250,
            client=client,
        )
    assert result.status == "rejected"
    assert result.can_activate_service is False


@pytest.mark.asyncio
async def test_wrong_amount_is_rejected():
    client = make_client({
        "success": True, "verified": True, "bankCode": "cbe",
        "amount": 200, "currency": "ETB",
    })
    async with client:
        result = await verify_payment(
            provider="cbe", reference="cbe-receipt",
            expected_amount=250, client=client,
        )
    assert result.status == "rejected"


@pytest.mark.asyncio
async def test_unverified_receipt_goes_to_manual_review():
    client = make_client({
        "success": True, "verified": False, "bankCode": "telebirr",
        "error": "Receipt not found",
    })
    async with client:
        result = await verify_payment(
            provider="telebirr", reference="bad-reference",
            expected_amount=250, client=client,
        )
    assert result.status == "manual_review"
    assert result.can_activate_service is False


@pytest.mark.asyncio
async def test_wrong_receiver_is_rejected():
    client = make_client({
        "success": True, "verified": True, "bankCode": "cbe",
        "amount": 250, "currency": "ETB",
        "receiverName": "OTHER MERCHANT", "receiverAccount": "1****1234",
    })
    async with client:
        result = await verify_payment(
            provider="cbe", reference="cbe-receipt",
            expected_amount=250, expected_receiver_name="FAYDA SERVICE",
            client=client,
        )
    assert result.status == "rejected"
