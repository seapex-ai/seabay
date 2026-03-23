"""Tests for introduction service — mutual introduction protocol (spec §2.3-2.4, §7.4).

Tests create_introduction, accept/decline, auto-edge creation on both_accepted, TTL expiry.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ConflictError, InvalidRequestError, NotFoundError
from app.services.introduction_service import (
    accept_introduction,
    create_introduction,
    decline_introduction,
)


def _make_agent(agent_id: str, introduction_policy: str = "open") -> MagicMock:
    agent = MagicMock()
    agent.id = agent_id
    agent.introduction_policy = introduction_policy
    return agent


def _make_intro(
    intro_id: str = "intro_001",
    introducer_id: str = "agt_intro",
    target_a_id: str = "agt_a",
    target_b_id: str = "agt_b",
    status: str = "pending",
    expires_at: datetime | None = None,
) -> MagicMock:
    intro = MagicMock()
    intro.id = intro_id
    intro.introducer_id = introducer_id
    intro.target_a_id = target_a_id
    intro.target_b_id = target_b_id
    intro.status = status
    intro.a_responded_at = None
    intro.b_responded_at = None
    intro.expires_at = expires_at or (datetime.now(timezone.utc) + timedelta(hours=72))
    return intro


def _mock_db_scalar(return_value):
    """Create a mock for db.execute().scalar_one_or_none()."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = return_value
    return result


class TestCreateIntroduction:
    """Test create_introduction service method."""

    @pytest.mark.asyncio
    async def test_cannot_introduce_same_agent(self):
        """Cannot introduce an agent to themselves."""
        db = AsyncMock()
        introducer = _make_agent("agt_intro")
        with pytest.raises(InvalidRequestError, match="Cannot introduce an agent to themselves"):
            await create_introduction(db, introducer, "agt_a", "agt_a")

    @pytest.mark.asyncio
    async def test_cannot_include_self(self):
        """Cannot include yourself in an introduction."""
        db = AsyncMock()
        introducer = _make_agent("agt_intro")
        with pytest.raises(InvalidRequestError, match="Cannot include yourself"):
            await create_introduction(db, introducer, "agt_intro", "agt_b")

    @pytest.mark.asyncio
    async def test_cannot_include_self_as_target_b(self):
        """Cannot include yourself as target_b."""
        db = AsyncMock()
        introducer = _make_agent("agt_intro")
        with pytest.raises(InvalidRequestError, match="Cannot include yourself"):
            await create_introduction(db, introducer, "agt_a", "agt_intro")

    @pytest.mark.asyncio
    async def test_target_not_found(self):
        """Raise NotFoundError if target agent doesn't exist."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_scalar(None))
        introducer = _make_agent("agt_intro")
        with pytest.raises(NotFoundError):
            await create_introduction(db, introducer, "agt_a", "agt_b")

    @pytest.mark.asyncio
    async def test_target_closed_introduction_policy(self):
        """Raise error if target has introduction_policy=closed."""
        target = _make_agent("agt_a", introduction_policy="closed")
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_scalar(target))
        introducer = _make_agent("agt_intro")
        with pytest.raises(InvalidRequestError, match="does not accept introductions"):
            await create_introduction(db, introducer, "agt_a", "agt_b")

    @pytest.mark.asyncio
    async def test_no_relationship_with_target(self):
        """Raise error if introducer has no relationship with target."""
        target_a = _make_agent("agt_a")
        target_b = _make_agent("agt_b")
        introducer = _make_agent("agt_intro")

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                # First 2 calls: target lookups (both exist)
                if call_count == 1:
                    return _mock_db_scalar(target_a)
                return _mock_db_scalar(target_b)
            return _mock_db_scalar(None)

        db = AsyncMock()
        db.execute = mock_execute

        with patch(
            "app.services.introduction_service.relationship_service.has_any_relationship",
            new_callable=AsyncMock,
            return_value=False,
        ):
            with pytest.raises(InvalidRequestError, match="No active relationship"):
                await create_introduction(db, introducer, "agt_a", "agt_b")

    @pytest.mark.asyncio
    async def test_valid_introduction_creates_object(self):
        """Valid introduction creates and returns Introduction object."""
        target_a = _make_agent("agt_a")
        target_b = _make_agent("agt_b")
        introducer = _make_agent("agt_intro")

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _mock_db_scalar(target_a)
            if call_count == 2:
                return _mock_db_scalar(target_b)
            # Remaining calls: check for existing intro
            return _mock_db_scalar(None)

        db = AsyncMock()
        db.execute = mock_execute
        db.add = MagicMock()
        db.flush = AsyncMock()

        with patch(
            "app.services.introduction_service.relationship_service.has_any_relationship",
            new_callable=AsyncMock,
            return_value=True,
        ):
            intro = await create_introduction(db, introducer, "agt_a", "agt_b", reason="They should meet")

        assert intro.introducer_id == "agt_intro"
        assert intro.target_a_id == "agt_a"
        assert intro.target_b_id == "agt_b"
        assert intro.status == "pending"
        assert intro.reason == "They should meet"
        db.add.assert_called_once()
        db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_duplicate_pending_introduction_rejected(self):
        """Raise ConflictError for duplicate pending introduction."""
        target_a = _make_agent("agt_a")
        target_b = _make_agent("agt_b")
        introducer = _make_agent("agt_intro")
        existing_intro = MagicMock()

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _mock_db_scalar(target_a)
            if call_count == 2:
                return _mock_db_scalar(target_b)
            # Check for existing introduction: return existing
            return _mock_db_scalar(existing_intro)

        db = AsyncMock()
        db.execute = mock_execute

        with patch(
            "app.services.introduction_service.relationship_service.has_any_relationship",
            new_callable=AsyncMock,
            return_value=True,
        ):
            with pytest.raises(ConflictError, match="already pending"):
                await create_introduction(db, introducer, "agt_a", "agt_b")


class TestAcceptIntroduction:
    """Test accept_introduction service method."""

    @pytest.mark.asyncio
    async def test_introduction_not_found(self):
        """Raise NotFoundError for non-existent introduction."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_scalar(None))
        agent = _make_agent("agt_a")
        with pytest.raises(NotFoundError):
            await accept_introduction(db, "nonexistent", agent)

    @pytest.mark.asyncio
    async def test_non_target_cannot_accept(self):
        """Raise error if accepting agent is not a target."""
        intro = _make_intro()
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_scalar(intro))
        outsider = _make_agent("agt_outsider")
        with pytest.raises(InvalidRequestError, match="not a target"):
            await accept_introduction(db, "intro_001", outsider)

    @pytest.mark.asyncio
    async def test_already_accepted_raises_conflict(self):
        """Raise ConflictError for already completed introduction."""
        intro = _make_intro(status="both_accepted")
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_scalar(intro))
        agent_a = _make_agent("agt_a")
        with pytest.raises(ConflictError, match="both_accepted"):
            await accept_introduction(db, "intro_001", agent_a)

    @pytest.mark.asyncio
    async def test_declined_introduction_cannot_be_accepted(self):
        """Raise ConflictError for declined introduction."""
        intro = _make_intro(status="declined")
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_scalar(intro))
        agent_a = _make_agent("agt_a")
        with pytest.raises(ConflictError, match="declined"):
            await accept_introduction(db, "intro_001", agent_a)

    @pytest.mark.asyncio
    async def test_expired_introduction_marked_and_raises(self):
        """Expired introduction is marked as expired and raises ConflictError."""
        expired_at = datetime.now(timezone.utc) - timedelta(hours=1)
        intro = _make_intro(status="pending", expires_at=expired_at)
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_scalar(intro))
        db.flush = AsyncMock()
        agent_a = _make_agent("agt_a")
        with pytest.raises(ConflictError, match="expired"):
            await accept_introduction(db, "intro_001", agent_a)
        assert intro.status == "expired"

    @pytest.mark.asyncio
    async def test_target_a_accepts_pending(self):
        """Target A accepting a pending introduction sets status to a_accepted."""
        intro = _make_intro(status="pending")
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_scalar(intro))
        db.flush = AsyncMock()
        agent_a = _make_agent("agt_a")

        result = await accept_introduction(db, "intro_001", agent_a)
        assert result.status == "a_accepted"
        assert result.a_responded_at is not None

    @pytest.mark.asyncio
    async def test_target_b_accepts_pending(self):
        """Target B accepting a pending introduction sets status to b_accepted."""
        intro = _make_intro(status="pending")
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_scalar(intro))
        db.flush = AsyncMock()
        agent_b = _make_agent("agt_b")

        result = await accept_introduction(db, "intro_001", agent_b)
        assert result.status == "b_accepted"
        assert result.b_responded_at is not None

    @pytest.mark.asyncio
    async def test_both_accepted_triggers_edge_creation(self):
        """When both targets accept, auto-create edges."""
        intro = _make_intro(status="b_accepted")
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_scalar(intro))
        db.flush = AsyncMock()
        agent_a = _make_agent("agt_a")

        with patch(
            "app.services.introduction_service._create_introduction_edges",
            new_callable=AsyncMock,
        ) as mock_edges:
            result = await accept_introduction(db, "intro_001", agent_a)
            assert result.status == "both_accepted"
            mock_edges.assert_awaited_once_with(db, intro)

    @pytest.mark.asyncio
    async def test_a_accepts_after_b_accepted(self):
        """Target A accepting after B accepted results in both_accepted."""
        intro = _make_intro(status="b_accepted")
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_scalar(intro))
        db.flush = AsyncMock()
        agent_a = _make_agent("agt_a")

        with patch(
            "app.services.introduction_service._create_introduction_edges",
            new_callable=AsyncMock,
        ):
            result = await accept_introduction(db, "intro_001", agent_a)
            assert result.status == "both_accepted"

    @pytest.mark.asyncio
    async def test_b_accepts_after_a_accepted(self):
        """Target B accepting after A accepted results in both_accepted."""
        intro = _make_intro(status="a_accepted")
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_scalar(intro))
        db.flush = AsyncMock()
        agent_b = _make_agent("agt_b")

        with patch(
            "app.services.introduction_service._create_introduction_edges",
            new_callable=AsyncMock,
        ):
            result = await accept_introduction(db, "intro_001", agent_b)
            assert result.status == "both_accepted"


class TestDeclineIntroduction:
    """Test decline_introduction service method."""

    @pytest.mark.asyncio
    async def test_introduction_not_found(self):
        """Raise NotFoundError for non-existent introduction."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_scalar(None))
        agent = _make_agent("agt_a")
        with pytest.raises(NotFoundError):
            await decline_introduction(db, "nonexistent", agent)

    @pytest.mark.asyncio
    async def test_non_target_cannot_decline(self):
        """Raise error if declining agent is not a target."""
        intro = _make_intro()
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_scalar(intro))
        outsider = _make_agent("agt_outsider")
        with pytest.raises(InvalidRequestError, match="not a target"):
            await decline_introduction(db, "intro_001", outsider)

    @pytest.mark.asyncio
    async def test_both_accepted_cannot_be_declined(self):
        """Cannot decline an already completed introduction."""
        intro = _make_intro(status="both_accepted")
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_scalar(intro))
        agent_a = _make_agent("agt_a")
        with pytest.raises(ConflictError, match="both_accepted"):
            await decline_introduction(db, "intro_001", agent_a)

    @pytest.mark.asyncio
    async def test_target_a_declines(self):
        """Target A declining sets status to declined."""
        intro = _make_intro(status="pending")
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_scalar(intro))
        db.flush = AsyncMock()
        agent_a = _make_agent("agt_a")

        result = await decline_introduction(db, "intro_001", agent_a)
        assert result.status == "declined"
        assert result.a_responded_at is not None

    @pytest.mark.asyncio
    async def test_target_b_declines(self):
        """Target B declining sets status to declined."""
        intro = _make_intro(status="pending")
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_scalar(intro))
        db.flush = AsyncMock()
        agent_b = _make_agent("agt_b")

        result = await decline_introduction(db, "intro_001", agent_b)
        assert result.status == "declined"
        assert result.b_responded_at is not None

    @pytest.mark.asyncio
    async def test_decline_after_partial_accept(self):
        """Can decline even after the other party accepted."""
        intro = _make_intro(status="a_accepted")
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_scalar(intro))
        db.flush = AsyncMock()
        agent_b = _make_agent("agt_b")

        result = await decline_introduction(db, "intro_001", agent_b)
        assert result.status == "declined"


class TestAutoEdgeCreation:
    """Test that _create_introduction_edges creates bidirectional edges."""

    @pytest.mark.asyncio
    async def test_creates_bidirectional_edges(self):
        """Both directions of edges should be created."""
        from app.services.introduction_service import _create_introduction_edges

        intro = _make_intro()
        db = AsyncMock()

        mock_edge = MagicMock()
        mock_edge.id = "edge_001"

        with patch(
            "app.services.introduction_service.relationship_service.get_or_create_edge",
            new_callable=AsyncMock,
            return_value=mock_edge,
        ) as mock_get_edge, patch(
            "app.services.introduction_service.relationship_service.add_origin",
            new_callable=AsyncMock,
        ) as mock_add_origin:
            await _create_introduction_edges(db, intro)

            # Should be called twice (A->B and B->A)
            assert mock_get_edge.await_count == 2
            assert mock_add_origin.await_count == 2

            # Check that both directions were created
            calls = mock_get_edge.call_args_list
            from_to_pairs = [(c[1].get("from_id") or c[0][1], c[1].get("to_id") or c[0][2]) for c in calls]
            assert ("agt_a", "agt_b") in from_to_pairs
            assert ("agt_b", "agt_a") in from_to_pairs


class TestTTLExpiration:
    """Test TTL-related behavior."""

    def test_introduction_ttl_default(self):
        """Introduction TTL defaults to 72 hours."""
        from app.config import settings
        assert settings.INTRODUCTION_TTL_HOURS == 72

    @pytest.mark.asyncio
    async def test_expired_intro_rejected_on_accept(self):
        """Accepting an expired introduction sets status and raises."""
        expired_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        intro = _make_intro(status="pending", expires_at=expired_at)
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_scalar(intro))
        db.flush = AsyncMock()
        agent_a = _make_agent("agt_a")

        with pytest.raises(ConflictError, match="expired"):
            await accept_introduction(db, "intro_001", agent_a)
        assert intro.status == "expired"

    def test_ttl_seconds_matches_hours(self):
        """ttl_seconds = ttl_hours * 3600."""
        from app.config import settings
        expected_seconds = settings.INTRODUCTION_TTL_HOURS * 3600
        assert expected_seconds == 72 * 3600
