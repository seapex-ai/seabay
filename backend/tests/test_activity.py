"""Tests for activity service — counters and stats."""

from __future__ import annotations

from app.services.activity_service import (
    get_profile_views,
    get_search_appearances,
    record_profile_view,
    record_search_appearance,
    reset_counters,
)


class TestProfileViewCounters:
    """Test in-memory profile view tracking."""

    def setup_method(self):
        """Reset counters before each test."""
        reset_counters()

    def test_initial_count_is_zero(self):
        assert get_profile_views("agt_test") == 0

    def test_record_increments_count(self):
        record_profile_view("agt_test")
        assert get_profile_views("agt_test") == 1

    def test_multiple_views(self):
        for _ in range(5):
            record_profile_view("agt_test")
        assert get_profile_views("agt_test") == 5

    def test_separate_agents(self):
        record_profile_view("agt_1")
        record_profile_view("agt_1")
        record_profile_view("agt_2")
        assert get_profile_views("agt_1") == 2
        assert get_profile_views("agt_2") == 1


class TestSearchAppearanceCounters:
    """Test in-memory search appearance tracking."""

    def setup_method(self):
        reset_counters()

    def test_initial_count_is_zero(self):
        assert get_search_appearances("agt_test") == 0

    def test_record_increments_count(self):
        record_search_appearance("agt_test")
        assert get_search_appearances("agt_test") == 1

    def test_multiple_appearances(self):
        for _ in range(3):
            record_search_appearance("agt_test")
        assert get_search_appearances("agt_test") == 3


class TestCounterReset:
    """Test counter reset functionality."""

    def test_reset_clears_all(self):
        record_profile_view("agt_1")
        record_search_appearance("agt_2")
        reset_counters()
        assert get_profile_views("agt_1") == 0
        assert get_search_appearances("agt_2") == 0
