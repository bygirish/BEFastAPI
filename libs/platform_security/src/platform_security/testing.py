"""Test helpers: a throwaway RSA key pair, a matching verifier and a token factory."""

import time
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from platform_security.keys import StaticKeyProvider
from platform_security.verifier import JwtVerifier

TEST_ISSUER = "https://auth.test"
TEST_AUDIENCE = "befastapi"


class TestAuth:
    __test__ = False  # not a pytest class

    def __init__(self, kid: str = "test-key") -> None:
        self._private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.kid = kid
        self.verifier = JwtVerifier(
            issuer=TEST_ISSUER,
            audience=TEST_AUDIENCE,
            keys=StaticKeyProvider({kid: self._private.public_key()}),
        )

    def token(self, subject: str = "user-1", **claims: Any) -> str:
        now = int(time.time())
        payload: dict[str, Any] = {
            "iss": TEST_ISSUER,
            "aud": TEST_AUDIENCE,
            "sub": subject,
            "iat": now,
            "exp": now + 600,
            "jti": "test-jti",
            "roles": [],
            "plat_roles": [],
            "amr": ["pwd"],
        }
        payload.update(claims)
        return jwt.encode(payload, self._private, algorithm="RS256", headers={"kid": self.kid})

    def service_token(self, name: str = "tests") -> str:
        return self.token(f"service:{name}")

    def headers(self, subject: str = "user-1", **claims: Any) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token(subject, **claims)}"}

    def service_headers(self, name: str = "tests") -> dict[str, str]:
        return {"Authorization": f"Bearer {self.service_token(name)}"}
