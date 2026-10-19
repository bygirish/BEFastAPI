"""The authenticated caller, decoded from a verified JWT (docs/architecture §8)."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class PrincipalKind(StrEnum):
    USER = "user"
    SERVICE = "service"


class Principal(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: PrincipalKind = PrincipalKind.USER
    subject: str  # user id, or "service:<name>"
    session_id: str | None = None
    org_id: str | None = None  # active org (token `org` claim)
    roles: tuple[str, ...] = ()  # roles in the active org
    platform_roles: tuple[str, ...] = ()
    amr: tuple[str, ...] = ()
    token_id: str | None = None

    @property
    def user_id(self) -> str | None:
        return self.subject if self.kind is PrincipalKind.USER else None

    def has_org_role(self, *roles: str) -> bool:
        return any(r in self.roles for r in roles)

    def has_platform_role(self, *roles: str) -> bool:
        return any(r in self.platform_roles for r in roles)
