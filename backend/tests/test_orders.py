from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base
from app.models import Order, PaymentRecord
from app.services.orders import DuplicateTransactionError, apply_cheki_result, create_order, submit_payment_reference

@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()

def test_create_order_and_submit_payment(db):
    order = create_order(db, customer_telegram_id=12345, service_code="document_preview", amount="250.00")
    payment = submit_payment_reference(db, order_id=order.id, provider="cbe", transaction_reference="CBE-REF-001", submitted_amount="250.00")
    assert order.status == "pending_payment"
    assert payment.status == "pending"
    assert payment.provider == "cbe"

def test_duplicate_provider_reference_is_blocked(db):
    first = create_order(db, customer_telegram_id=1, service_code="a", amount=100)
    second = create_order(db, customer_telegram_id=2, service_code="b", amount=100)
    submit_payment_reference(db, order_id=first.id, provider="cbe", transaction_reference="SAME-REF", submitted_amount=100)
    with pytest.raises(DuplicateTransactionError):
        submit_payment_reference(db, order_id=second.id, provider="cbe", transaction_reference="SAME-REF", submitted_amount=100)

def test_same_reference_on_different_providers_is_separate(db):
    first = create_order(db, customer_telegram_id=1, service_code="a", amount=100)
    second = create_order(db, customer_telegram_id=2, service_code="b", amount=100)
    submit_payment_reference(db, order_id=first.id, provider="cbe", transaction_reference="REF-123", submitted_amount=100)
    other = submit_payment_reference(db, order_id=second.id, provider="telebirr", transaction_reference="REF-123", submitted_amount=100)
    assert other.provider == "telebirr"

def test_submitted_amount_must_match_order(db):
    order = create_order(db, customer_telegram_id=1, service_code="a", amount=100)
    with pytest.raises(ValueError):
        submit_payment_reference(db, order_id=order.id, provider="telebirr", transaction_reference="REF", submitted_amount=99)

def test_verified_cheki_result_marks_order_paid(db):
    from app.services.payment_verification import PaymentProvider, PaymentVerification
    order = create_order(db, customer_telegram_id=1, service_code="a", amount=100)
    payment = submit_payment_reference(db, order_id=order.id, provider="cbe", transaction_reference="REF-OK", submitted_amount=100)
    result = PaymentVerification(status="verified", provider=PaymentProvider.CBE_BANK, reference="REF-OK",
                                 verified=True, amount=Decimal("100"), currency="ETB")
    updated = apply_cheki_result(db, payment_id=payment.id, result=result)
    assert updated.status == "verified"
    assert db.get(Order, order.id).status == "paid"

def test_unverified_result_does_not_mark_order_paid(db):
    from app.services.payment_verification import PaymentProvider, PaymentVerification
    order = create_order(db, customer_telegram_id=1, service_code="a", amount=100)
    payment = submit_payment_reference(db, order_id=order.id, provider="cbe", transaction_reference="REF-PENDING", submitted_amount=100)
    result = PaymentVerification(status="manual_review", provider=PaymentProvider.CBE_BANK,
                                 reference="REF-PENDING", verified=False, reason="Not confirmed")
    apply_cheki_result(db, payment_id=payment.id, result=result)
    assert db.get(Order, order.id).status == "pending_payment"
    assert db.get(PaymentRecord, payment.id).status == "manual_review"
