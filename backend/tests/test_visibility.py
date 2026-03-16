"""Tests for visibility service — field-level profile visibility enforcement."""

from __future__ import annotations

from app.services.visibility_service import (
    ACCESS_LEVELS,
    FORCED_PRIVATE_FIELDS,
    PERSONAL_DEFAULTS,
    VIEWER_LEVELS,
    _can_see,
)


class TestAccessLevelHierarchy:
    """Test access level ordering."""

    def test_public_is_lowest(self):
        assert ACCESS_LEVELS["public"] == 0

    def test_private_is_highest(self):
        assert ACCESS_LEVELS["private"] == 3

    def test_network_between(self):
        assert ACCESS_LEVELS["network_only"] == 1

    def test_circle_between(self):
        assert ACCESS_LEVELS["circle_only"] == 2

    def test_four_levels(self):
        assert len(ACCESS_LEVELS) == 4


class TestViewerLevelHierarchy:
    """Test viewer level ordering."""

    def test_public_is_lowest(self):
        assert VIEWER_LEVELS["public"] == 0

    def test_self_is_highest(self):
        assert VIEWER_LEVELS["self"] == 3

    def test_four_viewer_levels(self):
        assert len(VIEWER_LEVELS) == 4


class TestCanSee:
    """Test visibility check logic."""

    def test_public_sees_public(self):
        assert _can_see("public", "public") is True

    def test_public_cannot_see_network(self):
        assert _can_see("network_only", "public") is False

    def test_network_sees_network(self):
        assert _can_see("network_only", "network") is True

    def test_network_sees_public(self):
        assert _can_see("public", "network") is True

    def test_network_cannot_see_circle(self):
        assert _can_see("circle_only", "network") is False

    def test_circle_sees_circle(self):
        assert _can_see("circle_only", "circle") is True

    def test_circle_sees_network(self):
        assert _can_see("network_only", "circle") is True

    def test_self_sees_everything(self):
        for vis in ACCESS_LEVELS:
            assert _can_see(vis, "self") is True

    def test_unknown_field_vis_defaults_private(self):
        assert _can_see("unknown", "public") is False
        assert _can_see("unknown", "self") is True


class TestPersonalDefaults:
    """Test default visibility settings for personal agents."""

    def test_display_name_network(self):
        assert PERSONAL_DEFAULTS["display_name"] == "network_only"

    def test_bio_network(self):
        assert PERSONAL_DEFAULTS["bio"] == "network_only"

    def test_location_private(self):
        assert PERSONAL_DEFAULTS["location_city"] == "private"
        assert PERSONAL_DEFAULTS["location_country"] == "private"

    def test_looking_for_private(self):
        assert PERSONAL_DEFAULTS["looking_for"] == "private"

    def test_skills_network(self):
        assert PERSONAL_DEFAULTS["skills"] == "network_only"

    def test_can_offer_network(self):
        assert PERSONAL_DEFAULTS["can_offer"] == "network_only"


class TestForcedPrivateFields:
    """Test fields that must remain private."""

    def test_looking_for_forced(self):
        assert "looking_for" in FORCED_PRIVATE_FIELDS

    def test_forced_fields_not_empty(self):
        assert len(FORCED_PRIVATE_FIELDS) >= 1
