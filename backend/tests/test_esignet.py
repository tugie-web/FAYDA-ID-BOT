from app.services.esignet import EsignetClient, EsignetError


def test_parse_identity_normalizes_bilingual_fields():
    raw = {
        "data": {
            "identity": {
                "UIN": "123456789012",
                "fullName": [
                    {"language": "eng", "value": "Example Name"},
                    {"language": "amh", "value": "ምሳሌ"},
                ],
                "gender": "Female",
                "region": {"eng": "Oromia", "amh": "ኦሮሚያ"},
            },
            "userInfo": {"birthdate": "1990-01-01", "phone_number": "+251900000000"},
        }
    }
    result = EsignetClient.parse_identity(raw, "FAN-TEST")
    assert result["uin"] == "123456789012"
    assert result["uniqueId"] == "FAN-TEST"
    assert result["fullName"] == {"eng": "Example Name", "amh": "ምሳሌ"}
    assert result["gender"] == {"eng": "Female", "amh": "ሴት"}
    assert result["region"]["eng"] == "Oromia"
    assert result["dateOfBirth"] == "1990-01-01"


def test_resident_authorization_must_be_configured(monkeypatch):
    monkeypatch.delenv("FAYDA_RESIDENT_AUTHORIZATION", raising=False)
    try:
        EsignetClient()._resident_headers()
    except EsignetError as exc:
        assert exc.code == "CONFIG_MISSING"
    else:
        raise AssertionError("Missing resident authorization must fail closed.")


def test_retrieve_identity_checks_resident_configuration_before_auth_code(monkeypatch):
    monkeypatch.delenv("FAYDA_RESIDENT_AUTHORIZATION", raising=False)
    client = EsignetClient()
    called = []
    monkeypatch.setattr(client, "get_auth_code", lambda: called.append("auth_code") or "code")
    try:
        client.retrieve_identity()
    except EsignetError as exc:
        assert exc.code == "CONFIG_MISSING"
    else:
        raise AssertionError("Missing resident authorization must fail closed.")
    assert called == []


def test_retrieve_identity_runs_resident_exchange_after_configuration(monkeypatch):
    monkeypatch.setenv("FAYDA_RESIDENT_AUTHORIZATION", "Basic test-only")
    client = EsignetClient()
    client.fan = "FAN-TEST"
    calls = []
    monkeypatch.setattr(client, "get_auth_code", lambda: calls.append("auth_code") or "one-time-code")
    monkeypatch.setattr(client, "exchange_auth_code", lambda code: calls.append(("exchange", code)))
    monkeypatch.setattr(client, "get_identity", lambda: calls.append("identity") or {
        "data": {"identity": {"UIN": "123456789012", "fullName": "Example Person"}}
    })
    result = client.retrieve_identity()
    assert calls == ["auth_code", ("exchange", "one-time-code"), "identity"]
    assert result["uin"] == "123456789012"
    assert result["fullName"]["eng"] == "Example Person"
