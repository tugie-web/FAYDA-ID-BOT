import asyncio
from decimal import Decimal

import httpx

from app.services.payment_verification import PaymentProvider, verify_payment


def make_client(payload):
    def handler(request):
        assert request.url.path == "/api/verify"
        return httpx.Response(200, json=payload)
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://cheki.et")


def run_check(payload, **kwargs):
    client = make_client(payload)
    async def run():
        async with client:
            return await verify_payment(client=client, **kwargs)
    return asyncio.run(run())


def test_cbe_payment_verified_for_cbe_and_exact_amount():
    result = run_check(
        {"success": True, "verified": True, "bankCode": "cbe",
         "amount": 250, "currency": "ETB", "receiverName": "FAYDA SERVICE",
         "receiverAccount": "1****1234"},
        provider=PaymentProvider.CBE_BANK,
        reference="https://mbreciept.cbe.com.et/example",
        expected_amount=Decimal("250"),
        expected_receiver_name="Fayda Service",
        expected_receiver_account_suffix="1234",
    )
    assert result.can_activate_service is True


def test_cross_provider_receipt_is_rejected():
    result = run_check(
        {"success": True, "verified": True, "bankCode": "telebirr",
         "amount": 250, "currency": "ETB"},
        provider=PaymentProvider.CBE_BANK,
        reference="some-telebirr-reference",
        expected_amount=250,
    )
    assert result.status == "rejected"
    assert result.can_activate_service is False


def test_wrong_amount_is_rejected():
    result = run_check(
        {"success": True, "verified": True, "bankCode": "cbe",
         "amount": 200, "currency": "ETB"},
        provider="cbe", reference="cbe-receipt", expected_amount=250,
    )
    assert result.status == "rejected"


def test_unverified_receipt_goes_to_manual_review():
    result = run_check(
        {"success": True, "verified": False, "bankCode": "telebirr",
         "error": "Receipt not found"},
        provider="telebirr", reference="bad-reference", expected_amount=250,
    )
    assert result.status == "manual_review"
    assert result.can_activate_service is False


def test_wrong_receiver_is_rejected():
    result = run_check(
        {"success": True, "verified": True, "bankCode": "cbe",
         "amount": 250, "currency": "ETB", "receiverName": "OTHER MERCHANT",
         "receiverAccount": "1****1234"},
        provider="cbe", reference="cbe-receipt", expected_amount=250,
        expected_receiver_name="FAYDA SERVICE",
    )
    assert result.status == "rejected"
