"""Token verification and authorization helpers. Verifies tokens; issuing is Auth's job."""

from platform_security.fastapi_deps import (
    CurrentPrincipal,
    PermissionResolver,
    RolePermissionMap,
    get_principal,
    require_org_roles,
    require_permission,
    require_platform_roles,
)
from platform_security.keys import JwksKeyProvider, KeyProvider, StaticKeyProvider
from platform_security.principal import Principal, PrincipalKind
from platform_security.verifier import JwtVerifier

__all__ = [
    "CurrentPrincipal",
    "JwksKeyProvider",
    "JwtVerifier",
    "KeyProvider",
    "PermissionResolver",
    "Principal",
    "PrincipalKind",
    "RolePermissionMap",
    "StaticKeyProvider",
    "get_principal",
    "require_org_roles",
    "require_permission",
    "require_platform_roles",
]
