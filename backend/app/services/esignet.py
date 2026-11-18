"""Fayda eSignet OTP client, ported from the user's supplied project archive.

Keep one client per active identity session. Never log FANs, OTPs, tokens, or identity payloads.
The resident API authorization header is deliberately supplied through environment configuration;
the credential embedded in the legacy archive is not copied into this repository.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

import requests

AUTH_BASE = "https://auth.fayda.et/v1/esignet"
RESIDENT_BASE = "https://api-resident.fayda.et/esignet"
CLIENT_ID = "ajcCvwQcVm1dAr6HaW4Y5ObnDmwPPTpH9oDaZSPPrpo"
REDIRECT_URI = "https://resident.fayda.et/callback"
SCOPE = "openid profile email"
ACR_VALUES = "mosip:idp:acr:generated-code"
CLAIMS = {"userinfo": {name: {"essential": True} for name in (
    "name", "phone_number", "email", "picture", "gender", "birthdate",
    "address", "nationality", "individual_id",
)}}


class EsignetError(Exception):
    """Safe, user-displayable eSignet workflow error."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class EsignetClient:
    """One short-lived client per user identity workflow."""

    def __init__(self, *, timeout: float = 30):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
        )
        self.timeout = timeout
        self.code_verifier = ""
        self.code_challenge = ""
        self.nonce = ""
        self.state = ""
        self.csrf_token = ""
        self.txn_id = ""
        self.oauth_details_key = ""
        self.oauth_details_hash = ""
        self.fan = ""
        self.resident_jwt = ""

    @staticmethod
    def _rand(n: int = 32) -> str:
        return base64.urlsafe_b64encode(os.urandom(n)).rstrip(b"=").decode()

    @staticmethod
    def _sha256_b64url(value: str) -> str:
        digest = hashlib.sha256(value.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()

    @staticmethod
    def _wrap(body: dict) -> dict:
        now = datetime.now(timezone.utc)
        stamp = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
        return {"requestTime": stamp, "request": body}

    def _auth_headers(self, extra: dict | None = None) -> dict:
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/json",
            "Origin": "https://auth.fayda.et",
            "Referer": "https://auth.fayda.et/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Ch-Ua": '"Google Chrome";v="149","Chromium";v="149","Not)A;Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
        }
        if self.csrf_token:
            headers["X-XSRF-TOKEN"] = self.csrf_token
        headers.update(extra or {})
        return headers

    def check_configuration(self) -> None:
        """Fail before requesting an OTP if the resident API credential is absent."""
        if not os.getenv("FAYDA_RESIDENT_AUTHORIZATION", "").strip():
            raise EsignetError(
                "CONFIG_MISSING",
                "Fayda resident API authorization is not configured by the operator.",
            )

    def _resident_headers(self, extra: dict | None = None) -> dict:
        authorization = os.getenv("FAYDA_RESIDENT_AUTHORIZATION", "").strip()
        if not authorization:
            raise EsignetError(
                "CONFIG_MISSING",
                "Fayda resident API authorization is not configured by the operator.",
            )
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Authorization": authorization,
            "Origin": "https://resident.fayda.et",
            "Referer": "https://resident.fayda.et/",
        }
        headers.update(extra or {})
        return headers

    @staticmethod
    def _response_body(response: requests.Response) -> dict:
        response.raise_for_status()
        try:
            data = response.json()
        except ValueError as exc:
            raise EsignetError("BAD_RESPONSE", "Fayda returned an unreadable response.") from exc
        errors = data.get("errors") if isinstance(data, dict) else None
        if errors:
            first = errors[0] if isinstance(errors, list) and errors else {}
            raise EsignetError(
                str(first.get("errorCode", "FAYDA_ERROR")),
                str(first.get("errorMessage", "Fayda rejected the request.")),
            )
        if not isinstance(data, dict):
            raise EsignetError("BAD_RESPONSE", "Fayda returned an unexpected response.")
        return data.get("response", data)

    def initialize(self, fan: str) -> None:
        fan = str(fan).strip()
        if not fan or len(fan) > 64:
            raise EsignetError("INVALID_FAN", "Enter a valid Fayda number.")
        self.fan = fan
        self.code_verifier = self._rand(32)
        self.code_challenge = self._sha256_b64url(self.code_verifier)
        self.nonce = self._rand(16)
        self.state = self._rand(16)
        # Fayda's CSRF endpoint can intermittently stall. Retry this safe GET
        # a small number of times; never retry OTP or identity POST requests.
        response = None
        last_error = None
        for attempt in range(3):
            try:
                response = self.session.get(
                    f"{AUTH_BASE}/csrf/token",
                    headers=self._auth_headers({
                        "Accept": "application/json, application/xml, text/xml, */*",
                    }),
                    timeout=(10, self.timeout),
                )
                if response.status_code in (502, 503, 504) and attempt < 2:
                    response.close()
                    time.sleep(2 ** attempt)
                    continue
                response.raise_for_status()
                break
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = exc
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
        if response is None:
            raise last_error or requests.RequestException("Fayda CSRF request failed")

        token = ""
        content_type = response.headers.get("Content-Type", "").lower()
        if "json" in content_type:
            try:
                data = response.json()
            except ValueError:
                data = {}
            token = (
                data.get("token") or data.get("csrfToken")
                or (data.get("response") or {}).get("token")
            )
        else:
            # The browser-visible Fayda endpoint may return SupplierCsrfToken XML.
            try:
                root = ET.fromstring(response.content)
                for node in root.iter():
                    if node.tag.rsplit("}", 1)[-1].lower() in ("token", "csrftoken"):
                        token = (node.text or "").strip()
                        if token:
                            break
            except ET.ParseError:
                try:
                    data = response.json()
                except ValueError:
                    data = {}
                token = (
                    data.get("token") or data.get("csrfToken")
                    or (data.get("response") or {}).get("token")
                )
        token = token or self.session.cookies.get("XSRF-TOKEN", "")
        if not token:
            raise EsignetError("NO_CSRF", "Could not start a secure Fayda session.")
        self.csrf_token = token
        self.session.cookies.set("XSRF-TOKEN", token, domain="auth.fayda.et")

    def get_oauth_details(self) -> None:
        body = {
            "clientId": CLIENT_ID, "redirectUri": REDIRECT_URI,
            "responseType": "code", "scope": SCOPE, "state": self.state,
            "nonce": self.nonce, "codeChallenge": self.code_challenge,
            "codeChallengeMethod": "S256", "acrValues": ACR_VALUES, "claims": CLAIMS,
        }
        response = self.session.post(
            f"{AUTH_BASE}/authorization/v2/oauth-details",
            json=self._wrap(body), headers=self._auth_headers(), timeout=self.timeout,
        )
        result = self._response_body(response)
        self.txn_id = str(result.get("transactionId", ""))
        if not self.txn_id:
            raise EsignetError("NO_TXN", "Fayda did not create an authorization session.")
        self.oauth_details_key = self.txn_id
        compact = json.dumps(result, separators=(",", ":"), ensure_ascii=False)
        self.oauth_details_hash = self._sha256_b64url(compact)

    def send_otp(self) -> dict:
        response = self.session.post(
            f"{AUTH_BASE}/authorization/send-otp",
            json=self._wrap({
                "transactionId": self.txn_id, "individualId": self.fan,
                "otpChannels": ["email", "phone"],
            }),
            headers=self._auth_headers({
                "oauth-details-key": self.oauth_details_key,
                "oauth-details-hash": self.oauth_details_hash,
            }),
            timeout=self.timeout,
        )
        result = self._response_body(response)
        return {
            "maskedEmail": str(result.get("maskedEmail", "")),
            "maskedMobile": str(result.get("maskedMobile", "")),
        }

    def verify_otp(self, otp: str) -> None:
        otp = str(otp).strip()
        if not otp or len(otp) > 32:
            raise EsignetError("INVALID_OTP", "Enter the OTP sent to your registered contact.")
        response = self.session.post(
            f"{AUTH_BASE}/authorization/v2/authenticate",
            json=self._wrap({
                "transactionId": self.txn_id, "individualId": self.fan,
                "challengeList": [{
                    "authFactorType": "OTP", "challenge": otp,
                    "format": "alpha-numeric",
                }],
            }),
            headers=self._auth_headers({
                "oauth-details-key": self.oauth_details_key,
                "oauth-details-hash": self.oauth_details_hash,
            }),
            timeout=self.timeout,
        )
        self._response_body(response)

    def get_auth_code(self) -> str:
        response = self.session.post(
            f"{AUTH_BASE}/authorization/auth-code",
            json=self._wrap({
                "transactionId": self.txn_id,
                "acceptedClaims": [
                    "name", "phone_number", "email", "picture", "gender",
                    "birthdate", "address", "nationality", "individual_id",
                ],
                "permittedAuthorizeScopes": ["openid", "profile", "email", "phone", "address"],
            }),
            headers=self._auth_headers({
                "oauth-details-key": self.oauth_details_key,
                "oauth-details-hash": self.oauth_details_hash,
            }),
            timeout=self.timeout,
        )
        result = self._response_body(response)
        code = result.get("code") or result.get("authCode")
        if not code:
            raise EsignetError("NO_CODE", "Fayda did not return an authorization code.")
        return str(code)

    def exchange_auth_code(self, auth_code: str) -> None:
        response = requests.post(
            f"{RESIDENT_BASE}/exchangeAutheCode",
            json={
                "code": auth_code, "code_verifier": self.code_verifier,
                "redirect_uri": REDIRECT_URI, "client_id": CLIENT_ID,
                "nonce": self.nonce, "state": self.state,
            },
            headers=self._resident_headers(), timeout=60,
        )
        response.raise_for_status()
        token = response.text.strip()
        if token.count(".") != 2 or token.startswith("{"):
            raise EsignetError("BAD_JWT", "Fayda did not return a valid resident session.")
        self.resident_jwt = token

    def get_identity(self) -> dict:
        if not self.resident_jwt:
            raise EsignetError("NO_JWT", "Complete OTP verification first.")
        response = requests.post(
            f"{RESIDENT_BASE}/exchangeResident",
            json={"headers": {"Content-Type": "application/json"}},
            headers=self._resident_headers({
                "X-Authorization": f"Bearer {self.resident_jwt}",
            }),
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            raise EsignetError("BAD_IDENTITY", "Fayda returned an unexpected identity response.")
        return result

    @staticmethod
    def parse_identity(raw: dict, fan: str) -> dict:
        """Normalize the eSignet response for the legacy card renderer."""
        data = raw.get("data") or raw.get("response") or {}
        identity = data.get("identity") or raw.get("identity") or data or raw
        user = (
            data.get("userInfo") or data.get("userinfo")
            or raw.get("userInfo") or raw.get("userinfo") or {}
        )

        def bilingual(value: Any) -> dict:
            if isinstance(value, list):
                return {
                    "eng": next((str(x.get("value", "")) for x in value if x.get("language") == "eng"), ""),
                    "amh": next((str(x.get("value", "")) for x in value if x.get("language") == "amh"), ""),
                }
            if isinstance(value, dict):
                return {"eng": str(value.get("eng", "")), "amh": str(value.get("amh", ""))}
            return {"eng": str(value or ""), "amh": ""}

        photo = (
            identity.get("photo") or identity.get("Photo") or identity.get("photograph")
            or identity.get("face") or data.get("photo") or data.get("picture")
            or user.get("picture") or raw.get("picture") or raw.get("photo") or ""
        )
        if isinstance(photo, dict):
            photo = photo.get("value", "") or next(iter(photo.values()), "")
        uin = str(
            identity.get("UIN") or identity.get("uin") or user.get("individual_id")
            or raw.get("individual_id") or raw.get("sub") or ""
        )
        name = identity.get("fullName") or identity.get("name") or user.get("name") or raw.get("name") or ""
        gender_raw = identity.get("gender") or user.get("gender") or raw.get("gender") or ""
        if isinstance(gender_raw, str):
            gender_eng = gender_raw.strip().capitalize()
            gender = {"eng": gender_eng, "amh": {"male": "ወንድ", "man": "ወንድ", "female": "ሴት", "woman": "ሴት"}.get(gender_eng.lower(), "")}
        else:
            gender = bilingual(gender_raw)
        region = bilingual(identity.get("region") or {})
        zone = bilingual(identity.get("zone") or {})
        woreda = bilingual(identity.get("woreda") or {})
        address = user.get("address") or raw.get("address") or {}
        if not region["eng"]:
            if isinstance(address, dict):
                region["eng"] = address.get("region") or address.get("locality", "")
                zone["eng"] = address.get("zone", "")
                woreda["eng"] = address.get("woreda") or address.get("street_address", "")
            elif isinstance(address, str):
                region["eng"] = address
        nationality = identity.get("residenceStatus") or identity.get("nationality") or raw.get("nationality") or ""
        nat = bilingual(nationality) if nationality else {"eng": "", "amh": ""}
        if nationality and not nat["eng"]:
            nat = {"eng": str(nationality), "amh": ""}
        return {
            "fullName": bilingual(name), "dateOfBirth": (
                identity.get("dateOfBirth") or identity.get("dob")
                or user.get("birthdate") or raw.get("birthdate") or ""
            ),
            "gender": gender,
            "phone": str(identity.get("phone") or identity.get("phoneNumber") or user.get("phone_number") or raw.get("phone_number") or ""),
            "uin": uin, "fin": uin, "uniqueId": fan,
            "region": region, "zone": zone, "woreda": woreda,
            "residenceStatus": nat,
            "email": str(identity.get("email") or user.get("email") or raw.get("email") or ""),
            "photo": photo, "qr_jwt": "",
        }

    def close(self) -> None:
        self.session.close()
