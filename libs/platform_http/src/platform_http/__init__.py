"""HTTP edge utilities and the ServiceModule contract."""

from platform_http.client import ServiceHttpClient
from platform_http.compose import Wiring, create_application, load_modules
from platform_http.errors import (
    UnhandledErrorMiddleware,
    error_body,
    install_error_handlers,
    status_for,
)
from platform_http.module import (
    ENTRY_POINT_GROUP,
    BaseServiceModule,
    ServiceModule,
    validate_router_prefix,
)

__all__ = [
    "ENTRY_POINT_GROUP",
    "BaseServiceModule",
    "ServiceHttpClient",
    "ServiceModule",
    "UnhandledErrorMiddleware",
    "Wiring",
    "create_application",
    "error_body",
    "install_error_handlers",
    "load_modules",
    "status_for",
    "validate_router_prefix",
]
