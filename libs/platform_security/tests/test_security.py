import time
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from platform_core.errors import UnauthenticatedError
from platform_http import install_error_handlers
from platform_security import (
    CurrentPrincipal,
    JwtVerifier,
    Principal,
    RolePermissionMap,
    StaticKeyProvider,
    require_org_roles,
    require_permission,
)

ISS, AUD = "https://auth.example", "befastapi"
PRIVATE = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def make_token(key: Any = PRIVATE, *, kid: str = "k1", **overrides: Any) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": ISS,
        "aud": AUD,
        "sub": "user-1",
        "iat": now,
        "exp": now + 600,
        "sid": "s1",
        "org": "org-1",
        "roles": ["org_admin"],
        "plat_roles": [],
        "amr": ["pwd"],
        "jti": "j1",
    }
    claims.update(overrides)
    return jwt.encode(
        {k: v for k, v in claims.items() if v is not None},
        key,
        algorithm="RS256",
        headers={"kid": kid},
    )


def verifier() -> JwtVerifier:
    return JwtVerifier(
        issuer=ISS, audience=AUD, keys=StaticKeyProvider({"k1": PRIVATE.public_key()})
    )


async def test_valid_token_becomes_principal() -> None:
    principal = await verifier().verify(make_token())
    assert principal.user_id == "user-1" and principal.org_id == "org-1"
    assert principal.roles == ("org_admin",) and principal.amr == ("pwd",)


@pytest.mark.parametrize(
    ("token", "code"),
    [
        (make_token(exp=int(time.time()) - 3600), "TOKEN_EXPIRED"),
        (make_token(aud="someone-else"), "TOKEN_INVALID"),
        (make_token(iss="https://evil"), "TOKEN_INVALID"),
        (make_token(OTHER), "TOKEN_INVALID"),  # signed by a different key
        (make_token(kid="unknown"), "TOKEN_UNKNOWN_KEY"),
        (make_token(scope="signup_complete"), "TOKEN_WRONG_SCOPE"),
        ("not-a-jwt", "TOKEN_INVALID"),
    ],
)
async def test_rejects_bad_tokens(token: str, code: str) -> None:
    with pytest.raises(UnauthenticatedError) as info:
        await verifier().verify(token)
    assert info.value.code == code


def test_none_algorithm_is_refused() -> None:
    with pytest.raises(ValueError):
        JwtVerifier(issuer=ISS, audience=AUD, keys=StaticKeyProvider({}), algorithms=("none",))


async def test_dependencies_enforce_authn_and_authz() -> None:
    app = FastAPI()
    install_error_handlers(app)
    app.state.jwt_verifier = verifier()
    app.state.permission_resolver = RolePermissionMap({"org_admin": frozenset({"members:invite"})})

    @app.get("/me")
    async def me(principal: CurrentPrincipal) -> dict[str, str | None]:
        return {"user": principal.user_id}

    @app.get("/admin", dependencies=[Depends(require_org_roles("org_owner"))])
    async def admin() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/invite")
    async def invite(
        principal: Principal = Depends(require_permission("members:invite")),
    ) -> dict[str, bool]:
        return {"ok": True}

    @app.post("/lock")
    async def lock(
        principal: Principal = Depends(require_permission("users:lock")),
    ) -> dict[str, bool]:
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        bearer = {"Authorization": f"Bearer {make_token()}"}
        assert (await client.get("/me")).status_code == 401
        assert (await client.get("/me", headers=bearer)).json() == {"user": "user-1"}
        assert (await client.get("/admin", headers=bearer)).status_code == 403  # wrong role
        assert (await client.post("/invite", headers=bearer)).status_code == 200
        assert (
            await client.post("/lock", headers=bearer)
        ).status_code == 403  # permission not granted
