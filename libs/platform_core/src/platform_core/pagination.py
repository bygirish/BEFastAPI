"""Cursor pagination types used in contracts and HTTP APIs (rule C-3)."""

from pydantic import BaseModel, Field


class PageRequest(BaseModel):
    limit: int = Field(default=50, ge=1, le=200)
    cursor: str | None = None


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None = None
