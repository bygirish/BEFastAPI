"""Standalone entrypoint: ``uvicorn --factory notifications_api.main:create_app``.

Ports owned by other services are bound to fakes via the module's `bind_standalone_defaults`
(or to HTTP clients once those services are really remote)."""

import os

from fastapi import FastAPI

from notifications_service.module import NotificationsModule
from platform_core.settings import PlatformSettings
from platform_http import create_application
from platform_observability import setup
from platform_security import JwksKeyProvider, JwtVerifier


def create_app() -> FastAPI:
    settings = PlatformSettings()
    handle = setup(
        settings, service_name="notifications-service"
    )  # before engines exist, so DB spans work
    verifier = None
    if (
        (jwks := os.environ.get("JWT_JWKS_URL"))
        and (iss := os.environ.get("JWT_ISSUER"))
        and (aud := os.environ.get("JWT_AUDIENCE"))
    ):
        verifier = JwtVerifier(issuer=iss, audience=aud, keys=JwksKeyProvider(jwks))
    return create_application(
        title="notifications",
        service_name="notifications-service",
        modules=[NotificationsModule()],
        standalone=True,
        platform_settings=settings,
        observability=handle,
        jwt_verifier=verifier,
    )
