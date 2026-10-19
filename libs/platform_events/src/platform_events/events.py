"""Base class for versioned integration events (rules C-6, C-8).

Events live in each service's `*_contracts.events` and subclass `IntegrationEvent`:

    class UserRegistered(IntegrationEvent):
        EVENT_NAME: ClassVar[str] = "auth.user_registered.v1"
        user_id: UUID
"""

import re
from datetime import UTC, datetime
from typing import Any, ClassVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from platform_core.ids import uuid7

# <service>.<noun>_<verb>.v<N>   e.g. auth.user_registered.v1
EVENT_NAME_RE = re.compile(r"^[a-z][a-z0-9]*\.[a-z][a-z0-9]*(?:_[a-z0-9]+)+\.v[1-9][0-9]*$")

_REGISTRY: dict[str, type["IntegrationEvent"]] = {}


class InvalidEventDefinitionError(TypeError):
    pass


class IntegrationEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    EVENT_NAME: ClassVar[str]

    event_id: UUID = Field(default_factory=uuid7)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        name = cls.__dict__.get("EVENT_NAME")
        if name is None:
            return  # intermediate abstract base
        if not EVENT_NAME_RE.match(name):
            raise InvalidEventDefinitionError(
                f"{cls.__name__}.EVENT_NAME={name!r} must match <service>.<noun>_<verb>.v<N>"
            )
        existing = _REGISTRY.get(name)
        if existing is not None and existing.__qualname__ != cls.__qualname__:
            raise InvalidEventDefinitionError(f"Duplicate event name {name!r}")
        _REGISTRY[name] = cls

    @property
    def event_name(self) -> str:
        return type(self).EVENT_NAME


def event_type_for(name: str) -> type[IntegrationEvent]:
    try:
        return _REGISTRY[name]
    except KeyError:
        raise LookupError(
            f"Unknown event type {name!r}; is its contracts package imported?"
        ) from None
