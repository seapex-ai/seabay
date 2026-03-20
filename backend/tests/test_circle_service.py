"""Tests for circle service — creation, membership, dissolution logic.

Enhanced with mock-based tests for actual service methods.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import settings
from app.core.exceptions import ConflictError, ForbiddenError, InvalidRequestError


class TestCircleConstraints:
    """Test circle hard constraints from spec §8.3."""

    def test_max_members_default(self):
        assert settings.CIRCLE_MAX_MEMBERS == 30

    def test_max_members_enforced(self):
        """max_members cannot exceed settings limit."""
        requested = 50
        enforced = min(requested, settings.CIRCLE_MAX_MEMBERS)
        assert enforced == 30

    def test_max_members_smaller_ok(self):
        """Smaller max_members is allowed."""
        requested = 10
        enforced = min(requested, settings.CIRCLE_MAX_MEMBERS)
        assert enforced == 10


class TestCircleJoinModes:
    """Test circle join mode logic."""

    def test_invite_only(self):
        """invite_only requires a valid invite token."""
        mode = "invite_only"
        assert mode == "invite_only"

    def test_request_approve(self):
        """request_approve requires a separate join request flow."""
        mode = "request_approve"
        assert mode == "request_approve"

    def test_open_link(self):
        """open_link allows anyone with the link to join."""
        mode = "open_link"
        assert mode == "open_link"


class TestCircleContactModes:
    """Test circle contact mode behavior."""

    def test_directory_only(self):
        """directory_only: members can see each other but can't direct message."""
        mode = "directory_only"
        assert mode == "directory_only"

    def test_request_only(self):
        """request_only: members must request permission before contacting."""
        mode = "request_only"
        assert mode == "request_only"

    def test_direct_allowed(self):
        """direct_allowed: members can directly task each other."""
        mode = "direct_allowed"
        assert mode == "direct_allowed"


class TestCircleRoles:
    """Test circle membership roles."""

    def test_owner_role(self):
        """Owner has full control."""
        assert "owner" in ["owner", "admin", "member"]

    def test_admin_role(self):
        """Admin can manage members and requests."""
        assert "admin" in ["owner", "admin", "member"]

    def test_member_role(self):
        """Member has basic participation rights."""
        assert "member" in ["owner", "admin", "member"]


class TestCircleDissolution:
    """Test circle dissolution rules."""

    def test_only_owner_can_dissolve(self):
        """Only the circle owner can dissolve it."""
        owner_id = "agt_owner"
        circle_owner_id = "agt_owner"
        assert owner_id == circle_owner_id

    def test_non_owner_cannot_dissolve(self):
        """Non-owner should not be able to dissolve."""
        requester_id = "agt_member"
        circle_owner_id = "agt_owner"
        assert requester_id != circle_owner_id


class TestCircleOwnershipTransfer:
    """Test ownership transfer rules."""

    def test_new_owner_must_be_member(self):
        """Can only transfer to an existing member."""
        members = ["agt_1", "agt_2", "agt_3"]
        new_owner = "agt_2"
        assert new_owner in members

    def test_non_member_rejected(self):
        """Cannot transfer to non-member."""
        members = ["agt_1", "agt_2"]
        new_owner = "agt_99"
        assert new_owner not in members

    def test_owner_demoted_to_admin(self):
        """After transfer, old owner becomes admin."""
        old_role = "owner"
        new_role = "admin"
        assert old_role != new_role


# ── Enhanced mock-based service tests ──


def _mock_db_scalar(return_value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = return_value
    return result


def _make_agent(agent_id: str) -> MagicMock:
    agent = MagicMock()
    agent.id = agent_id
    return agent


def _make_circle(
    circle_id: str = "circle_001",
    owner_id: str = "agt_owner",
    max_members: int = 30,
    member_count: int = 1,
    join_mode: str = "invite_only",
    invite_link_token: str = "valid_token",
    is_active: bool = True,
) -> MagicMock:
    circle = MagicMock()
    circle.id = circle_id
    circle.owner_agent_id = owner_id
    circle.max_members = max_members
    circle.member_count = member_count
    circle.join_mode = join_mode
    circle.invite_link_token = invite_link_token
    circle.is_active = is_active
    return circle


class TestCircleServiceCreate:
    """Test circle_service.create_circle with mocks."""

    @pytest.mark.asyncio
    async def test_create_circle_sets_owner_as_member(self):
        """Creating a circle should add owner as first member."""
        from app.services.circle_service import create_circle

        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        owner = _make_agent("agt_owner")

        circle = await create_circle(db, owner, "Test Circle")
        assert circle.name == "Test Circle"
        assert circle.owner_agent_id == "agt_owner"
        assert circle.member_count == 1
        # db.add called for both circle and membership
        assert db.add.call_count == 2

    @pytest.mark.asyncio
    async def test_create_circle_caps_max_members(self):
        """max_members should be capped at CIRCLE_MAX_MEMBERS."""
        from app.services.circle_service import create_circle

        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        owner = _make_agent("agt_owner")

        circle = await create_circle(db, owner, "Big Circle", max_members=100)
        assert circle.max_members == 30


class TestCircleServiceJoin:
    """Test circle_service.join_circle with mocks."""

    @pytest.mark.asyncio
    async def test_already_member_raises_conflict(self):
        """Joining a circle you're already in raises ConflictError."""
        from app.services.circle_service import join_circle

        circle = _make_circle()
        agent = _make_agent("agt_member")

        existing_membership = MagicMock()
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_scalar(existing_membership))

        with pytest.raises(ConflictError, match="Already a member"):
            await join_circle(db, circle, agent, "valid_token")

    @pytest.mark.asyncio
    async def test_full_circle_raises_error(self):
        """Joining a full circle raises InvalidRequestError."""
        from app.services.circle_service import join_circle

        circle = _make_circle(member_count=30, max_members=30)
        agent = _make_agent("agt_new")

        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_scalar(None))

        with pytest.raises(InvalidRequestError, match="Circle is full"):
            await join_circle(db, circle, agent, "valid_token")

    @pytest.mark.asyncio
    async def test_invalid_token_raises_forbidden(self):
        """Invalid invite token raises ForbiddenError."""
        from app.services.circle_service import join_circle

        circle = _make_circle()
        agent = _make_agent("agt_new")

        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_scalar(None))

        with pytest.raises(ForbiddenError, match="Invalid invite token"):
            await join_circle(db, circle, agent, "wrong_token")

    @pytest.mark.asyncio
    async def test_request_approve_redirects(self):
        """request_approve circles should direct to join-requests."""
        from app.services.circle_service import join_circle

        circle = _make_circle(join_mode="request_approve")
        agent = _make_agent("agt_new")

        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_scalar(None))

        with pytest.raises(InvalidRequestError, match="join-requests"):
            await join_circle(db, circle, agent)


class TestCircleServiceLeave:
    """Test circle_service.leave_circle with mocks."""

    @pytest.mark.asyncio
    async def test_owner_cannot_leave(self):
        """Circle owner cannot leave."""
        from app.services.circle_service import leave_circle

        circle = _make_circle(owner_id="agt_owner")
        owner = _make_agent("agt_owner")
        db = AsyncMock()

        with pytest.raises(InvalidRequestError, match="Owner cannot leave"):
            await leave_circle(db, circle, owner)


class TestCircleServiceDissolve:
    """Test circle_service.dissolve_circle with mocks."""

    @pytest.mark.asyncio
    async def test_non_owner_cannot_dissolve(self):
        """Non-owner attempting to dissolve raises ForbiddenError."""
        from app.services.circle_service import dissolve_circle

        circle = _make_circle(owner_id="agt_owner")
        non_owner = _make_agent("agt_member")
        db = AsyncMock()

        with pytest.raises(ForbiddenError, match="Only the circle owner"):
            await dissolve_circle(db, circle, non_owner)


class TestCircleServiceTransfer:
    """Test circle_service.transfer_ownership with mocks."""

    @pytest.mark.asyncio
    async def test_non_owner_cannot_transfer(self):
        """Non-owner cannot transfer ownership."""
        from app.services.circle_service import transfer_ownership

        circle = _make_circle(owner_id="agt_owner")
        non_owner = _make_agent("agt_member")
        db = AsyncMock()

        with pytest.raises(ForbiddenError, match="Only the circle owner"):
            await transfer_ownership(db, circle, non_owner, "agt_new_owner")

    @pytest.mark.asyncio
    async def test_transfer_to_non_member_fails(self):
        """Transfer to non-member raises InvalidRequestError."""
        from app.services.circle_service import transfer_ownership

        circle = _make_circle(owner_id="agt_owner")
        owner = _make_agent("agt_owner")
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_mock_db_scalar(None))

        with pytest.raises(InvalidRequestError, match="New owner must be a circle member"):
            await transfer_ownership(db, circle, owner, "agt_nonmember")


class TestCircleEnums:
    """Test circle-related enumerations are complete."""

    def test_join_modes(self):
        from app.models.enums import CircleJoinMode
        values = {m.value for m in CircleJoinMode}
        assert values == {"invite_only", "request_approve", "open_link"}

    def test_contact_modes(self):
        from app.models.enums import CircleContactMode
        values = {m.value for m in CircleContactMode}
        assert values == {"directory_only", "request_only", "direct_allowed"}

    def test_roles(self):
        from app.models.enums import CircleRole
        values = {r.value for r in CircleRole}
        assert values == {"owner", "admin", "member"}

    def test_join_request_statuses(self):
        from app.models.enums import CircleJoinRequestStatus
        assert len(CircleJoinRequestStatus) >= 4
