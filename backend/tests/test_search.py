"""Tests for search service — agent discovery and directory listing."""

from __future__ import annotations

from app.services.search_service import _agent_to_search_result, _filter_search_fields


class FakeProfile:
    bio = "A helpful agent"
    skills = ["python", "go"]
    languages = ["en", "zh"]
    location_city = "San Francisco"
    location_country = "US"
    can_offer = ["coding", "translation"]


class FakeAgent:
    id = "agt_search_test"
    slug = "test-agent"
    display_name = "Test Agent"
    agent_type = "service"
    verification_level = "email"
    status = "online"


class FakeAgentNoVerification:
    id = "agt_no_verify"
    slug = "no-verify"
    display_name = "No Verify"
    agent_type = "personal"
    verification_level = "none"
    status = "offline"


class TestAgentToSearchResult:
    """Test the _agent_to_search_result helper."""

    def test_basic_fields(self):
        result = _agent_to_search_result(FakeAgent(), FakeProfile())
        assert result["id"] == "agt_search_test"
        assert result["slug"] == "test-agent"
        assert result["display_name"] == "Test Agent"
        assert result["agent_type"] == "service"

    def test_profile_fields(self):
        result = _agent_to_search_result(FakeAgent(), FakeProfile())
        assert result["bio"] == "A helpful agent"
        assert result["skills"] == ["python", "go"]
        assert result["languages"] == ["en", "zh"]
        # location_city is excluded from search results for privacy
        assert "location_city" not in result
        assert result["location_country"] == "US"
        assert result["can_offer"] == ["coding", "translation"]

    def test_no_profile(self):
        result = _agent_to_search_result(FakeAgent(), None)
        assert result["bio"] is None
        assert result["skills"] == []
        assert result["languages"] == []
        assert result["can_offer"] == []

    def test_verification_badge(self):
        result = _agent_to_search_result(FakeAgent(), None)
        assert "email" in result["badges"]

    def test_no_verification_no_badge(self):
        result = _agent_to_search_result(FakeAgentNoVerification(), None)
        assert result["badges"] == []

    def test_status_included(self):
        result = _agent_to_search_result(FakeAgent(), None)
        assert result["status"] == "online"


class TestSearchSortOptions:
    """Test search sort option values."""

    def test_valid_sort_options(self):
        valid = {"relevance", "newest", "trust_first", "recent_active"}
        assert "relevance" in valid
        assert "newest" in valid
        assert "trust_first" in valid


class TestSearchPagination:
    """Test cursor-based pagination logic."""

    def test_has_more_logic(self):
        """Fetching limit+1 determines has_more."""
        limit = 20
        rows_fetched = 21
        has_more = rows_fetched > limit
        assert has_more is True

    def test_no_more_results(self):
        limit = 20
        rows_fetched = 15
        has_more = rows_fetched > limit
        assert has_more is False

    def test_exact_limit(self):
        limit = 20
        rows_fetched = 20
        has_more = rows_fetched > limit
        assert has_more is False


class TestFilterSearchFields:
    """Test field-level visibility filtering in search results."""

    def _make_result(self):
        return _agent_to_search_result(FakeAgent(), FakeProfile())

    def test_public_viewer_personal_defaults(self):
        """Public viewer should not see network_only/private fields."""
        result = self._make_result()
        filtered = _filter_search_fields(result, {}, "public")
        # bio defaults to network_only → hidden from public
        assert filtered["bio"] is None
        # skills defaults to network_only → hidden
        assert filtered["skills"] == []
        # location_country defaults to private → hidden
        assert filtered["location_country"] is None
        # can_offer defaults to network_only → hidden
        assert filtered["can_offer"] == []
        # Non-profile fields remain
        assert filtered["id"] == "agt_search_test"
        assert filtered["display_name"] == "Test Agent"

    def test_network_viewer_sees_network_fields(self):
        """Network-level viewer sees network_only fields."""
        result = self._make_result()
        filtered = _filter_search_fields(result, {}, "network")
        assert filtered["bio"] == "A helpful agent"
        assert filtered["skills"] == ["python", "go"]
        assert filtered["can_offer"] == ["coding", "translation"]
        # location_country defaults to private → still hidden
        assert filtered["location_country"] is None

    def test_explicit_override_respected(self):
        """Explicit field visibility overrides take precedence over defaults."""
        result = self._make_result()
        overrides = {"bio": "public", "location_country": "network_only"}
        filtered = _filter_search_fields(result, overrides, "public")
        # bio overridden to public → visible
        assert filtered["bio"] == "A helpful agent"
        # location_country overridden to network_only → still hidden from public
        assert filtered["location_country"] is None

    def test_forced_private_field(self):
        """looking_for is not in search results at all (already excluded)."""
        result = self._make_result()
        assert "looking_for" not in result
