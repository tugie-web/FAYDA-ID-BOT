"""Telegram Mini App initData authentication."""
from __future__ import annotations

import hashlib
import hmac
import time
from urllib.parse import parse_qsl

from fastapi import Header, HTTPException
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    telegram_bot_token: str = ""
    telegram_auth_max_age_seconds: int = 300
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


auth_settings = AuthSettings()


def validate_init_data(init_data: str, bot_token: str, *, now: int | None = None,
                       max_age_seconds: int = 300) -> dict[str, str]:
    if not bot_token:
        raise ValueError("Telegram bot authentication is not configured.")
    if not init_data or len(init_data) > 8192:
        raise ValueError("Missing or oversized Telegram initData.")

    pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    data = dict(pairs)
    if len(data) != len(pairs) or "hash" not in data or "auth_date" not in data:
        raise ValueError("Malformed Telegram initData.")

    received_hash = data.pop("hash")
    check_string = "\n".join(f"{key}={value}" for key, value in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated_hash, received_hash):
        raise ValueError("Telegram initData signature is invalid.")

    try:
        auth_date = int(data["auth_date"])
    except (TypeError, ValueError) as exc:
        raise ValueError("Telegram auth_date is invalid.") from exc

    current = int(time.time()) if now is None else now
    if auth_date > current + 30 or current - auth_date > max_age_seconds:
        raise ValueError("Telegram initData has expired.")

    return data


async def require_telegram_user(
    authorization: str | None = Header(default=None),
) -> dict:
    if not authorization or not authorization.startswith("tma "):
        raise HTTPException(status_code=401, detail="Telegram authentication required.")
    try:
        data = validate_init_data(
            authorization[4:],
            auth_settings.telegram_bot_token,
            max_age_seconds=auth_settings.telegram_auth_max_age_seconds,
        )
        import json
        user = json.loads(data["user"])
        user_id = int(user["id"])
        if user_id <= 0:
            raise ValueError("Invalid Telegram user.")
        return {"id": user_id, "first_name": str(user.get("first_name", ""))[:100]}
    except (ValueError, KeyError, TypeError, Exception) as exc:
        # Do not leak signature, token, or parsing details to the caller.
        raise HTTPException(status_code=401, detail="Telegram authentication is invalid or expired.") from exc
