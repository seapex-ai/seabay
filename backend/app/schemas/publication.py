from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import PublicationStatus, PublicationType, VisibilityScope


class PublicationCreate(BaseModel):
    publication_type: PublicationType
    title: str = Field(max_length=200)
    description: str = Field(max_length=5000)
    structured_data: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list, max_length=20)
    category: str | None = Field(None, max_length=50)
    price_summary: str | None = Field(None, max_length=128)
    availability_summary: str | None = Field(None, max_length=128)
    location_city: str | None = Field(None, max_length=100)
    location_country: str | None = Field(None, max_length=2)
    visibility_scope: VisibilityScope = VisibilityScope.PUBLIC
    expires_at: datetime | None = None


class PublicationUpdate(BaseModel):
    title: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=5000)
    structured_data: dict | None = None
    tags: list[str] | None = Field(None, max_length=20)
    category: str | None = Field(None, max_length=50)
    price_summary: str | None = Field(None, max_length=128)
    availability_summary: str | None = Field(None, max_length=128)
    location_city: str | None = Field(None, max_length=100)
    location_country: str | None = Field(None, max_length=2)
    status: PublicationStatus | None = None
    visibility_scope: VisibilityScope | None = None
    expires_at: datetime | None = None


class PublicationResponse(BaseModel):
    id: str
    agent_id: str
    publication_type: str
    title: str
    description: str
    structured_data: dict
    tags: list[str]
    category: str | None
    price_summary: str | None
    availability_summary: str | None
    location_city: str | None
    location_country: str | None
    status: str
    visibility_scope: str
    view_count: int
    expires_at: datetime | None
    region: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
