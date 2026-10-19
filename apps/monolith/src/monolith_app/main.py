"""ASGI entrypoint: ``uvicorn --factory monolith_app.main:create_app``."""

from fastapi import FastAPI

from monolith_app.settings import MonolithSettings
from monolith_app.wiring import wire
from platform_core.settings import PlatformSettings
from platform_http import create_application, load_modules
from platform_observability import setup
from platform_security import JwksKeyProvider, JwtVerifier


def create_app(settings: MonolithSettings | None = None) -> FastAPI:
    settings = settings or MonolithSettings()
    platform_settings = PlatformSettings()
    handle = setup(
        platform_settings, service_name=settings.service_name
    )  # before engines are built
    modules = load_modules(settings.enabled_services or None)

    verifier: JwtVerifier | None = None
    if settings.jwt_issuer and settings.jwt_audience and settings.jwt_jwks_url:
        verifier = JwtVerifier(
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            keys=JwksKeyProvider(settings.jwt_jwks_url),
        )

    return create_application(
        title="BEFastAPI",
        service_name=settings.service_name,
        modules=modules,
        wiring=wire,
        platform_settings=platform_settings,
        observability=handle,
        jwt_verifier=verifier,
    )
