"""Local access-token verification (rule X-1). Never calls the Auth service per request."""

from typing import Any

import jwt

from platform_core.errors import UnauthenticatedError
from platform_security.keys import KeyProvider
from platform_security.principal import Principal, PrincipalKind

DEFAULT_ALGORITHMS = ("RS256",)


class JwtVerifier:
    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        keys: KeyProvider,
        algorithms: tuple[str, ...] = DEFAULT_ALGORITHMS,
        leeway_seconds: int = 10,
        required_scope: str = "access",
    ) -> None:
        if "none" in (a.lower() for a in algorithms):
            raise ValueError("The 'none' algorithm is never allowed")
        self._issuer = issuer
        self._audience = audience
        self._keys = keys
        self._algorithms = list(algorithms)
        self._leeway = leeway_seconds
        self._scope = required_scope

    async def verify(self, token: str) -> Principal:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise UnauthenticatedError("Malformed token", code="TOKEN_INVALID") from exc
        kid = header.get("kid")
        if not isinstance(kid, str):
            raise UnauthenticatedError("Token has no key id", code="TOKEN_INVALID")

        key = await self._keys.get_key(kid)
        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                key=key,
                algorithms=self._algorithms,
                audience=self._audience,
                issuer=self._issuer,
                leeway=self._leeway,
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise UnauthenticatedError("Token expired", code="TOKEN_EXPIRED") from exc
        except jwt.PyJWTError as exc:
            raise UnauthenticatedError("Invalid token", code="TOKEN_INVALID") from exc

        if claims.get("scope", "access") != self._scope:
            raise UnauthenticatedError("Token has the wrong scope", code="TOKEN_WRONG_SCOPE")

        subject = str(claims["sub"])
        return Principal(
            kind=PrincipalKind.SERVICE if subject.startswith("service:") else PrincipalKind.USER,
            subject=subject,
            session_id=claims.get("sid"),
            org_id=claims.get("org"),
            roles=tuple(claims.get("roles", ())),
            platform_roles=tuple(claims.get("plat_roles", ())),
            amr=tuple(claims.get("amr", ())),
            token_id=claims.get("jti"),
        )
