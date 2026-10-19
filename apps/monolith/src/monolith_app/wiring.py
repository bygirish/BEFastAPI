"""Binds consumer ports to provider implementations (rule B-4: the ONLY place that may do this).

Pattern (docs/architecture §6.1). When `users` needs `files`, its `application/ports.py` defines
`AvatarStore`; its `infrastructure/clients/` has the adapter that wraps `files_contracts.FilesApi`.
Here we bind the contract port to a provider:

    container.bind(FilesApi, container.resolve(FilesApi))                    # provided by the files module itself

Extraction later = replace the provider with the HTTP client — nothing else changes:

    container.bind(FilesApi, FilesHttpClient(ServiceHttpClient(settings.files_base_url, target="files")),
                   override=True)
"""

from collections.abc import Sequence

from platform_core.container import Container
from platform_http import ServiceModule


def wire(container: Container, modules: Sequence[ServiceModule]) -> None:
    """Cross-service bindings go here. Intentionally empty until a service depends on another."""
    return None
