"""Installation model — tracks MCP host connections.

Each installation represents a binding between an external MCP host
(Claude, ChatGPT, etc.) and a Seabay agent identity (linked or proxy).
Created during OAuth first-authorization flow.

See Remote MCP Server v1.0 spec section 4.2.
"""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.agent import Base


class Installation(Base):
    __tablename__ = "installations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)

    # Host type: claude, chatgpt, gemini, grok, openclaw, shell, generic
    host_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # The developer's existing agent (if they have one)
    linked_agent_id: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("agents.id"), nullable=True,
    )

    # Auto-created proxy agent for pure consumers
    proxy_agent_id: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("agents.id"), nullable=True,
    )

    # OAuth subject identifier from the authorization flow
    oauth_subject: Mapped[Optional[str]] = mapped_column(String(256))

    # Granted OAuth scopes
    granted_scopes: Mapped[List[str]] = mapped_column(
        ARRAY(Text), default=list,
    )

    # Region tag for data residency
    region: Mapped[str] = mapped_column(String(10), nullable=False, default="intl")

    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    updated_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("idx_installations_host", "host_type"),
        Index("idx_installations_agent", "linked_agent_id"),
    )
