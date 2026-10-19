import json
import logging

import pytest

from platform_observability import app_service_scope, configure_logging, get_logger
from platform_observability.redaction import REDACTED, mask_email, mask_phone, redact

SECRET_JWT = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxMjM0NTYifQ.c2lnbmF0dXJl"


def test_redact_denies_sensitive_keys_and_masks_tokens() -> None:
    cleaned = redact(
        {
            "user": "u1",
            "password": "hunter2",
            "nested": {"otp_code": "123456", "Authorization": "Bearer abcdefghijkl", "ok": 1},
            "code": "654321",
            "note": f"token was {SECRET_JWT}",
            "items": [{"api_key": "k"}, "card 4111 1111 1111 1111"],
        }
    )
    assert cleaned["user"] == "u1"
    assert cleaned["password"] == REDACTED
    assert cleaned["nested"]["otp_code"] == REDACTED
    assert cleaned["nested"]["Authorization"] == REDACTED
    assert cleaned["nested"]["ok"] == 1
    assert cleaned["code"] == REDACTED
    assert SECRET_JWT not in cleaned["note"]
    assert cleaned["items"][0]["api_key"] == REDACTED
    assert "4111" not in cleaned["items"][1]


def test_masks() -> None:
    assert mask_email("alice@example.com") == "a***@example.com"
    assert mask_phone("+919876543210") == "+********3210"


def test_logs_are_json_correlated_and_redacted(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(level="INFO", service_name="test-svc", version="1.0", env="test")
    log = get_logger("unit")
    with app_service_scope("auth"):
        log.info(
            "login_failed",
            password="hunter2",
            reason="bad_credentials",
            email=mask_email("a@b.com"),
        )
    logging.getLogger("third.party").warning("foreign message")

    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    ours = next(line for line in lines if line["event"] == "login_failed")
    assert ours["severity"] == "INFO"
    assert ours["app.service"] == "auth"
    assert ours["service.name"] == "test-svc"
    assert ours["password"] == REDACTED
    assert ours["email"] == "a***@b.com"
    assert "hunter2" not in json.dumps(lines)
    assert any(line["event"] == "foreign message" for line in lines)
