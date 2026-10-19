"""Request-scoped context shared by logs, spans and metrics (rule O-7)."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_app_service: ContextVar[str | None] = ContextVar("app_service", default=None)
_user_id: ContextVar[str | None] = ContextVar("user_id", default=None)
_org_id: ContextVar[str | None] = ContextVar("org_id", default=None)


def get_request_id() -> str | None:
    return _request_id.get()


def get_app_service() -> str | None:
    return _app_service.get()


def get_user_id() -> str | None:
    return _user_id.get()


def get_org_id() -> str | None:
    return _org_id.get()


def set_request_id(value: str | None) -> Token[str | None]:
    return _request_id.set(value)


def reset_request_id(token: Token[str | None]) -> None:
    _request_id.reset(token)


def bind_principal(user_id: str | None, org_id: str | None) -> None:
    """Record the authenticated caller for log correlation (IDs only, never PII)."""
    _user_id.set(user_id)
    _org_id.set(org_id)


@contextmanager
def app_service_scope(name: str) -> Iterator[None]:
    """Mark code as running on behalf of logical service `name` (jobs, handlers, tests)."""
    token = _app_service.set(name)
    try:
        yield
    finally:
        _app_service.reset(token)


def set_app_service(name: str | None) -> Token[str | None]:
    return _app_service.set(name)


def reset_app_service(token: Token[str | None]) -> None:
    _app_service.reset(token)
