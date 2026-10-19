"""Signing-key providers for JWT verification: static (tests/dev) and JWKS URL (production)."""

import time
from typing import Any, Protocol

import httpx
import jwt
from jwt import PyJWK

from platform_core.errors import UnauthenticatedError, UnavailableError


class KeyProvider(Protocol):
    async def get_key(self, kid: str) -> Any: ...


class StaticKeyProvider:
    def __init__(self, keys: dict[str, Any]) -> None:
        self._keys = keys

    async def get_key(self, kid: str) -> Any:
        try:
            return self._keys[kid]
        except KeyError:
            raise UnauthenticatedError("Unknown signing key", code="TOKEN_UNKNOWN_KEY") from None


class JwksKeyProvider:
    """Fetches and caches the issuer's JWKS. Refetches (rate-limited) when an unknown kid appears,
    which is how key rotation propagates without restarts."""

    def __init__(
        self,
        jwks_url: str,
        *,
        ttl_seconds: float = 300,
        min_refresh_seconds: float = 30,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._url = jwks_url
        self._ttl = ttl_seconds
        self._min_refresh = min_refresh_seconds
        self._client = client or httpx.AsyncClient(timeout=3.0)
        self._keys: dict[str, PyJWK] = {}
        self._fetched_at = 0.0

    async def _refresh(self) -> None:
        try:
            response = await self._client.get(self._url)
            response.raise_for_status()
            jwks = jwt.PyJWKSet.from_dict(response.json())
        except (httpx.HTTPError, ValueError, jwt.PyJWKSetError) as exc:
            raise UnavailableError("Unable to load signing keys", code="JWKS_UNAVAILABLE") from exc
        self._keys = {k.key_id: k for k in jwks.keys if k.key_id}
        self._fetched_at = time.monotonic()

    async def get_key(self, kid: str) -> Any:
        now = time.monotonic()
        stale = now - self._fetched_at > self._ttl
        unknown = kid not in self._keys
        can_refresh = now - self._fetched_at > self._min_refresh
        if (stale or unknown) and (can_refresh or not self._keys):
            await self._refresh()
        key = self._keys.get(kid)
        if key is None:
            raise UnauthenticatedError("Unknown signing key", code="TOKEN_UNKNOWN_KEY")
        return key.key
