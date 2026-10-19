"""Base for outbound HTTP clients used by `*_contracts.http_client` implementations (rules C-3, C-4).

Handles what every remote call needs: timeouts, bounded retries with jittered backoff
(only for idempotent requests), request-id propagation, and mapping transport failures to
contract-level errors. Trace context (`traceparent`) is injected by the httpx instrumentation.
"""

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from platform_core.errors import DependencyTimeoutError, UnavailableError
from platform_observability import get_logger, get_request_id

_IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "PUT", "DELETE"})
_RETRYABLE_STATUS = frozenset({502, 503, 504})

TokenProvider = Callable[[], Awaitable[str]]


class ServiceHttpClient:
    def __init__(
        self,
        base_url: str,
        *,
        target: str,
        timeout_seconds: float = 3.0,
        max_retries: int = 2,
        backoff_seconds: float = 0.1,
        token_provider: TokenProvider | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._target = target
        self._max_retries = max_retries
        self._backoff = backoff_seconds
        self._token_provider = token_provider
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=timeout_seconds, transport=transport, follow_redirects=False
        )
        self._log = get_logger("http.client")

    async def aclose(self) -> None:
        await self._client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> httpx.Response:
        method = method.upper()
        headers: dict[str, str] = {}
        if (request_id := get_request_id()) is not None:
            headers["X-Request-ID"] = request_id
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        if self._token_provider is not None:
            headers["Authorization"] = f"Bearer {await self._token_provider()}"

        retryable = method in _IDEMPOTENT_METHODS or idempotency_key is not None
        attempts = (self._max_retries + 1) if retryable else 1
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                response = await self._client.request(
                    method, path, json=json, params=params, headers=headers
                )
            except httpx.TimeoutException as exc:
                last_error = DependencyTimeoutError(
                    f"{self._target} timed out", details={"target": self._target}
                )
                last_error.__cause__ = exc
            except httpx.TransportError as exc:
                last_error = UnavailableError(
                    f"{self._target} is unreachable", details={"target": self._target}
                )
                last_error.__cause__ = exc
            else:
                if response.status_code not in _RETRYABLE_STATUS:
                    return response
                last_error = UnavailableError(
                    f"{self._target} returned {response.status_code}",
                    details={"target": self._target},
                )
            if attempt < attempts:
                self._log.warning(
                    "remote_call_retry",
                    target=self._target,
                    attempt=attempt,
                    method=method,
                    path=path,
                )
                await asyncio.sleep(self._backoff * (2 ** (attempt - 1)) * (0.5 + random.random()))  # noqa: S311
        assert last_error is not None
        raise last_error
