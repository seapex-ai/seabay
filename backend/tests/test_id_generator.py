"""Tests for ID generator — format and uniqueness."""

from __future__ import annotations

from app.core.id_generator import generate_id


class TestIDFormat:
    """Test ID format compliance with spec."""

    def test_agent_id_prefix(self):
        assert generate_id("agent").startswith("agt_")

    def test_task_id_prefix(self):
        assert generate_id("task").startswith("tsk_")

    def test_intent_id_prefix(self):
        assert generate_id("intent").startswith("int_")

    def test_circle_id_prefix(self):
        assert generate_id("circle").startswith("cir_")

    def test_relationship_id_prefix(self):
        assert generate_id("relationship").startswith("rel_")

    def test_verification_id_prefix(self):
        assert generate_id("verification").startswith("vrf_")

    def test_report_id_prefix(self):
        assert generate_id("report").startswith("rpt_")

    def test_introduction_id_prefix(self):
        assert generate_id("introduction").startswith("itr_")

    def test_interaction_id_prefix(self):
        assert generate_id("interaction").startswith("ixn_")

    def test_profile_id_prefix(self):
        assert generate_id("profile").startswith("prf_")

    def test_membership_id_prefix(self):
        assert generate_id("circle_membership").startswith("cmb_")


class TestIDUniqueness:
    """Test ID uniqueness."""

    def test_ids_are_unique(self):
        """100 generated IDs should all be unique."""
        ids = {generate_id("agent") for _ in range(100)}
        assert len(ids) == 100

    def test_ids_across_types_differ(self):
        """IDs for different entity types should differ."""
        agent_id = generate_id("agent")
        task_id = generate_id("task")
        assert agent_id != task_id

    def test_id_has_nanoid_portion(self):
        """ID should have a nanoid portion after the prefix."""
        id_val = generate_id("agent")
        parts = id_val.split("_", 1)
        assert len(parts) == 2
        assert len(parts[1]) >= 10  # nanoid part


class TestIDLength:
    """Test ID total length."""

    def test_id_fits_in_column(self):
        """IDs should fit in String(32) column."""
        for entity in ["agent", "task", "circle", "intent", "report"]:
            id_val = generate_id(entity)
            assert len(id_val) <= 32, f"{entity} ID too long: {len(id_val)}"
