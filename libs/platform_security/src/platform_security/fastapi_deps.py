"""FastAPI dependencies for authentication/authorization. Only `api/` layers use these (rule L-6).

The composition root stores a `JwtVerifier` on ``app.state.jwt_verifier`` and optionally a
`PermissionResolver` on ``app.state.permission_resolver``.
"""

from collections.abc import Awaitable, Callable
from typing import Annotated, Protocol

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from platform_core.errors import ForbiddenError, UnauthenticatedError, UnavailableError
from platform_observability import bind_principal
from platform_security.principal import Principal
from platform_security.verifier import JwtVerifier

_bearer = HTTPBearer(auto_error=False)


class PermissionResolver(Protocol):
    async def has_permission(self, principal: Principal, permission: str) -> bool: ...


class RolePermissionMap:
    """Static role→permission resolver (tests, early phases). Auth's permission catalog replaces it."""

    def __init__(
        self,
        mapping: dict[str, frozenset[str]],
        platform_mapping: dict[str, frozenset[str]] | None = None,
    ) -> None:
        self._org = mapping
        self._platform = platform_mapping or {}

    async def has_permission(self, principal: Principal, permission: str) -> bool:
        org_perms = set().union(*(self._org.get(r, frozenset()) for r in principal.roles))
        plat_perms = set().union(
            *(self._platform.get(r, frozenset()) for r in principal.platform_roles)
        )
        return permission in org_perms or permission in plat_perms


async def get_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal:
    if credentials is None:
        raise UnauthenticatedError("Missing bearer token", code="TOKEN_MISSING")
    verifier: JwtVerifier | None = getattr(request.app.state, "jwt_verifier", None)
    if verifier is None:
        raise UnavailableError("Token verification is not configured", code="AUTH_NOT_CONFIGURED")
    principal = await verifier.verify(credentials.credentials)
    bind_principal(principal.subject, principal.org_id)
    return principal


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]


def require_org_roles(*roles: str) -> Callable[[Principal], Awaitable[Principal]]:
    async def dependency(principal: CurrentPrincipal) -> Principal:
        if principal.org_id is None:
            raise ForbiddenError("No active organization", code="NO_ACTIVE_ORG")
        if not principal.has_org_role(*roles):
            raise ForbiddenError()
        return principal

    return dependency


def require_platform_roles(*roles: str) -> Callable[[Principal], Awaitable[Principal]]:
    async def dependency(principal: CurrentPrincipal) -> Principal:
        if not principal.has_platform_role(*roles):
            raise ForbiddenError()
        return principal

    return dependency


def require_permission(permission: str) -> Callable[[Request, Principal], Awaitable[Principal]]:
    async def dependency(request: Request, principal: CurrentPrincipal) -> Principal:
        resolver: PermissionResolver | None = getattr(
            request.app.state, "permission_resolver", None
        )
        if resolver is None:
            raise UnavailableError("Authorization is not configured", code="AUTHZ_NOT_CONFIGURED")
        if not await resolver.has_permission(principal, permission):
            raise ForbiddenError()
        return principal

    return dependency
