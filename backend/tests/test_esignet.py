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
