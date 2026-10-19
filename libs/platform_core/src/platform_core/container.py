"""Tiny dependency container used by the composition root (rule B-4).

Ports (Protocol classes) are bound to providers in `apps/*/wiring`; services resolve
what they need through constructor injection, never by importing a provider.
"""

from typing import Any, cast


class NotBoundError(LookupError):
    """Raised when a port is resolved but nothing has been bound to it."""


class Container:
    def __init__(self) -> None:
        self._providers: dict[type[Any], Any] = {}

    def bind[T](self, port: type[T], provider: T, *, override: bool = False) -> None:
        if port in self._providers and not override:
            raise ValueError(f"{port.__name__} is already bound; pass override=True to replace it")
        self._providers[port] = provider

    def bind_default[T](self, port: type[T], provider: T) -> None:
        """Bind only if nothing is bound yet (used for standalone fakes)."""
        self._providers.setdefault(port, provider)

    def resolve[T](self, port: type[T]) -> T:
        try:
            return cast(T, self._providers[port])
        except KeyError:
            raise NotBoundError(f"No provider bound for {port.__name__}") from None

    def is_bound(self, port: type[Any]) -> bool:
        return port in self._providers
