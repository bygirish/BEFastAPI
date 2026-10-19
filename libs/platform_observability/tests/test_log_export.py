"""The OTLP log handler must (a) send our JSON line as the body and (b) never raise into the caller (rule O-11)."""

import json
import logging

import pytest
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import InMemoryLogExporter, SimpleLogRecordProcessor

from platform_observability import app_service_scope, configure_logging, get_logger
from platform_observability.logging import json_formatter
from platform_observability.setup import build_log_handler


def test_json_line_is_exported_as_the_log_body_and_secrets_stay_redacted() -> None:
    configure_logging(level="INFO", service_name="export-test", env="test")
    root = logging.getLogger()
    exporter = InMemoryLogExporter()
    provider = LoggerProvider()
    provider.add_log_record_processor(SimpleLogRecordProcessor(exporter))
    handler = build_log_handler(provider, json_formatter())
    root.addHandler(handler)
    try:
        with app_service_scope("auth"):
            get_logger("t").info("login_failed", password="hunter2", reason="locked")
    finally:
        root.removeHandler(handler)

    bodies = [json.loads(r.log_record.body) for r in exporter.get_finished_logs()]
    assert all(
        not b["event"].startswith("Invalid type") for b in bodies
    )  # no per-line attribute warnings
    ours = next(b for b in bodies if b["event"] == "login_failed")
    assert ours["app.service"] == "auth"
    assert ours["password"] == "[REDACTED]"


def test_a_failing_exporter_never_raises_into_business_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import opentelemetry.sdk._logs as sdk_logs

    def boom(self: object, record: object) -> None:
        raise RuntimeError("collector exploded")

    monkeypatch.setattr(sdk_logs.LoggingHandler, "emit", boom)
    monkeypatch.setattr(logging, "raiseExceptions", False)  # keep the test output quiet
    handler = build_log_handler(LoggerProvider(), None)
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "msg", (), None)
    handler.emit(record)  # must not raise
