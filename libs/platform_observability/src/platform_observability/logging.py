"""Structured JSON logging (rules O-2…O-4).

structlog sits on top of stdlib logging so third-party libraries are captured too.
Every line gets: timestamp, severity, event, service identity, request/trace correlation,
and is run through the redaction processor before it is rendered.
"""

import logging
import sys
from typing import Any

import structlog
from opentelemetry import trace

from platform_observability import context
from platform_observability.redaction import redact

_NOISY_LOGGERS = ("uvicorn.access", "httpx", "httpcore", "asyncio")


def _add_identity(service_name: str, version: str, env: str) -> structlog.typing.Processor:
    def processor(
        _: Any, __: str, event_dict: structlog.typing.EventDict
    ) -> structlog.typing.EventDict:
        event_dict["service.name"] = service_name
        event_dict["service.version"] = version
        event_dict["deployment.environment.name"] = env
        return event_dict

    return processor


def _add_context(
    _: Any, __: str, event_dict: structlog.typing.EventDict
) -> structlog.typing.EventDict:
    if (request_id := context.get_request_id()) is not None:
        event_dict.setdefault("request_id", request_id)
    if (app_service := context.get_app_service()) is not None:
        event_dict.setdefault("app.service", app_service)
    if (user_id := context.get_user_id()) is not None:
        event_dict.setdefault("enduser.id", user_id)
    if (org_id := context.get_org_id()) is not None:
        event_dict.setdefault("org.id", org_id)
    span_context = trace.get_current_span().get_span_context()
    if span_context.is_valid:
        event_dict["trace_id"] = format(span_context.trace_id, "032x")
        event_dict["span_id"] = format(span_context.span_id, "016x")
    return event_dict


def _rename_keys(
    _: Any, __: str, event_dict: structlog.typing.EventDict
) -> structlog.typing.EventDict:
    if "level" in event_dict:
        event_dict["severity"] = str(event_dict.pop("level")).upper()
    return event_dict


def _redact(_: Any, __: str, event_dict: structlog.typing.EventDict) -> structlog.typing.EventDict:
    redacted: structlog.typing.EventDict = redact(dict(event_dict))
    return redacted


def configure_logging(
    *, level: str = "INFO", service_name: str, version: str = "dev", env: str = "local"
) -> None:
    """Idempotent: safe to call again (tests, reloads)."""
    shared: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
        _add_identity(service_name, version, env),
        _add_context,
        structlog.processors.format_exc_info,
        _rename_keys,
        _redact,
    ]

    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(sort_keys=False),
        ],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.set_name(STDOUT_HANDLER_NAME)

    root = logging.getLogger()
    root.handlers = [h for h in root.handlers if h.get_name() != STDOUT_HANDLER_NAME]
    root.addHandler(handler)
    root.setLevel(level.upper())
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


STDOUT_HANDLER_NAME = "platform-stdout-json"


def json_formatter() -> logging.Formatter | None:
    """The formatter that renders our JSON lines (looked up by handler NAME, never by position: other tools such as
    pytest add their own root handlers first)."""
    for handler in logging.getLogger().handlers:
        if handler.get_name() == STDOUT_HANDLER_NAME:
            return handler.formatter
    return None


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger
