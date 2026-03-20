from __future__ import annotations

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict = {}


class ErrorResponse(BaseModel):
    error: ErrorDetail


class PaginatedResponse(BaseModel):
    data: list
    next_cursor: str | None = None
    has_more: bool = False
