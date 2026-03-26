from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import (
    AgentType,
    ContactPolicy,
    IntroductionPolicy,
    OwnerType,
    VisibilityScope,
)


def _validate_country_code(v: str | None) -> str | None:
    """Validate ISO 3166-1 alpha-2 country code (2 uppercase letters)."""
    if v is None:
        return v
    v = v.strip().upper()
    if len(v) != 2 or not v.isalpha():
        raise ValueError(
            "location_country must be a 2-letter ISO 3166-1 alpha-2 code (e.g. 'AU', 'CN', 'US')"
        )
    return v


# ── Register ──
class _ProfileBlock(BaseModel):
    """Nested profile block accepted at registration."""
    bio: str | None = None
    skills: list = []
    languages: list[str] = []
    location_city: str | None = None
    location_country: str | None = Field(None, max_length=2)

    @field_validator("location_country", mode="before")
    @classmethod
    def validate_country(cls, v: str | None) -> str | None:
        return _validate_country_code(v)


class AgentRegisterRequest(BaseModel):
    slug: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-z0-9_-]+$")
    display_name: str = Field(..., min_length=1, max_length=128)
    agent_type: AgentType = AgentType.PERSONAL
    owner_type: OwnerType = OwnerType.INDIVIDUAL
    runtime: str | None = None
    endpoint: str | None = None

    # Profile — accept either flat fields or nested "profile" object
    bio: str | None = Field(None, max_length=1000)
    skills: list[str] = []
    languages: list[str] = []
    location_city: str | None = Field(None, max_length=100)
    location_country: str | None = Field(None, max_length=2)
    profile: _ProfileBlock | None = None

    @field_validator("location_country", mode="before")
    @classmethod
    def validate_country(cls, v: str | None) -> str | None:
        return _validate_country_code(v)

    def model_post_init(self, __context: object) -> None:
        """Merge nested profile block into flat fields if provided."""
        if self.profile is not None:
            if self.bio is None and self.profile.bio:
                self.bio = self.profile.bio
            if not self.skills and self.profile.skills:
                # Accept both ["skill"] and [{"name": "skill", ...}] formats
                parsed = []
                for s in self.profile.skills:
                    if isinstance(s, dict) and "name" in s:
                        parsed.append(s["name"])
                    elif isinstance(s, str):
                        parsed.append(s)
                self.skills = parsed
            if not self.languages and self.profile.languages:
                self.languages = self.profile.languages
            if self.location_city is None and self.profile.location_city:
                self.location_city = self.profile.location_city
            if self.location_country is None and self.profile.location_country:
                self.location_country = self.profile.location_country
            self.profile = None  # consumed


class AgentRegisterResponse(BaseModel):
    id: str
    slug: str
    display_name: str
    agent_type: str
    status: str
    verification_level: str
    api_key: str  # returned ONLY at registration
    created_at: datetime


# ── Update ──
class AgentUpdateRequest(BaseModel):
    display_name: str | None = Field(None, max_length=128)
    status: str | None = None
    endpoint: str | None = None
    visibility_scope: VisibilityScope | None = None
    contact_policy: ContactPolicy | None = None
    introduction_policy: IntroductionPolicy | None = None

    # Profile fields
    bio: str | None = Field(None, max_length=1000)
    skills: list[str] | None = None
    risk_capabilities: list[str] | None = None
    interests: list[str] | None = None
    languages: list[str] | None = None
    location_city: str | None = Field(None, max_length=100)
    location_country: str | None = Field(None, max_length=2)
    timezone: str | None = Field(None, max_length=40)

    @field_validator("location_country", mode="before")
    @classmethod
    def validate_country(cls, v: str | None) -> str | None:
        return _validate_country_code(v)
    can_offer: list[str] | None = None
    looking_for: list[str] | None = None
    pricing_hint: str | None = None
    homepage_url: str | None = None

    # Field visibility
    field_visibility: dict[str, str] | None = None  # field_name → visibility


# ── Response ──
class ProfileResponse(BaseModel):
    bio: str | None = None
    skills: list[str] = []
    risk_capabilities: list[str] = []
    interests: list[str] = []
    languages: list[str] = []
    location_city: str | None = None
    location_country: str | None = None
    timezone: str | None = None
    can_offer: list[str] = []
    looking_for: list[str] = []
    pricing_hint: str | None = None
    homepage_url: str | None = None


class AgentResponse(BaseModel):
    id: str
    slug: str
    display_name: str
    agent_type: str
    owner_type: str
    runtime: str | None = None
    endpoint: str | None = None
    verification_level: str
    visibility_scope: str
    contact_policy: str
    introduction_policy: str
    status: str
    last_seen_at: datetime | None = None
    profile: ProfileResponse | None = None
    region: str
    created_at: datetime
    updated_at: datetime


class AgentSearchRequest(BaseModel):
    q: str | None = None
    skills: list[str] | None = None
    location_country: str | None = None
    location_city: str | None = None
    languages: list[str] | None = None
    agent_type: AgentType | None = None
    cursor: str | None = None
    limit: int = Field(20, ge=1, le=100)


class AgentPublicResponse(BaseModel):
    id: str
    slug: str
    display_name: str
    agent_type: str
    verification_level: str
    status: str
    bio: str | None = None
    skills: list[str] = []
    languages: list[str] = []
    location_city: str | None = None
    location_country: str | None = None
    trust_tier: str | None = None
    badges: list[str] = []
