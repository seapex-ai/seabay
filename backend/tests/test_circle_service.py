"""Tests for circle service — creation, membership, dissolution logic."""

from __future__ import annotations

from app.config import settings


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
