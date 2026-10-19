"""HTTP-only models for the development endpoints (rule L-5)."""

from pydantic import BaseModel, Field


class DevSendRequest(BaseModel):
    channel: str = Field(examples=["email"])
    recipient: str = Field(examples=["dev@example.com"])
    template: str = Field(default="otp", examples=["otp"])
    variables: dict[str, str] | None = Field(
        default=None, description="Omit to get sample values for the built-in templates."
    )
    idempotency_key: str | None = None


class DevSendResponse(BaseModel):
    delivery_id: str
    status: str
    provider: str | None
    attempts: int


class DevMessage(BaseModel):
    channel: str
    to: str
    subject: str | None
    body: str
