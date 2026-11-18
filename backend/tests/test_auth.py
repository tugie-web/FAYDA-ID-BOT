import hashlib
import hmac
import json
from urllib.parse import urlencode

import pytest

from app.auth import validate_init_data


def make_init_data(token, user_id=123, auth_date=1_700_000_000):
    values = {
        "auth_date": str(auth_date),
        "query_id": "AAE-test",
        "user": json.dumps({"id": user_id, "first_name": "Test"}, separators=(",", ":")),
    }
    check = "\n".join(f"{k}={v}" for k, v in sorted(values.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(values)


def test_valid_telegram_init_data():
    token = "123456:TEST_TOKEN"
    result = validate_init_data(make_init_data(token), token, now=1_700_000_100)
    assert json.loads(result["user"])["id"] == 123


def test_invalid_signature_is_rejected():
    with pytest.raises(ValueError):
        validate_init_data("auth_date=1700000000&hash=bad", "123456:TEST_TOKEN", now=1_700_000_100)


def test_expired_init_data_is_rejected():
    token = "123456:TEST_TOKEN"
    with pytest.raises(ValueError):
        validate_init_data(make_init_data(token), token, now=1_700_001_000, max_age_seconds=300)


def test_missing_bot_token_fails_closed():
    with pytest.raises(ValueError):
        validate_init_data("auth_date=1&hash=x", "", now=1)
