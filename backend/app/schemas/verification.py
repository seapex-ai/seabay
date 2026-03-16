"""Verification request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class EmailStartRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=254)


class EmailCompleteRequest(BaseModel):
    verification_id: str
    code: str = Field(..., min_length=4, max_length=12)


class DomainStartRequest(BaseModel):
    domain: str = Field(..., min_length=3, max_length=253)


class DomainCompleteRequest(BaseModel):
    verification_id: str


class VerificationResponse(BaseModel):
    verification_id: str
    method: str
    status: str
    identifier: Optional[str] = None
    message: Optional[str] = None
    verified_at: Optional[datetime] = None

    # DNS domain verification details
    dns_record_type: Optional[str] = None
    dns_record_name: Optional[str] = None
    dns_record_value: Optional[str] = None

    # Dev-only fields (remove in production)
    dev_code: Optional[str] = Field(None, alias="_dev_code")
    dev_state: Optional[str] = Field(None, alias="_dev_state")

    model_config = {"populate_by_name": True}
