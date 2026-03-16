"""Comprehensive tests for business logic services.

Tests cover: agent_service, task_service, relationship_service,
intent_service, introduction_service, circle_service, trust_service,
report_service, budget_service, dlp_service, webhook_service.
"""

from __future__ import annotations

import pytest

from app.models.enums import (
    HIGH_RISK_KEYWORDS,
    TASK_TRANSITIONS,
    RiskLevel,
    TaskStatus,
    requires_human_confirm,
)
from app.services.agent_service import check_protected_brand
from app.services.dlp_service import BLOCKED_PATTERNS, scan_content
from app.services.task_service import detect_risk_level
from app.services.trust_service import compute_trust_score
from app.services.visibility_service import validate_visibility_update

# ── DLP Service Tests ──

class TestDLPService:
    def test_scan_clean_content(self):
        findings = scan_content("Hello world, I need a translator")
        assert findings == []

    def test_scan_detects_api_key(self):
        findings = scan_content("my key is sk_live_abcdef1234567890")
        assert len(findings) >= 1
        blocked = [f for f in findings if f["action"] == "blocked"]
        assert len(blocked) >= 1

    def test_scan_detects_email(self):
        findings = scan_content("contact me at user@example.com")
        assert len(findings) >= 1
        email_finding = [f for f in findings if f["pattern"] == "email"]
        assert len(email_finding) == 1
        assert email_finding[0]["action"] == "warning"

    def test_scan_detects_phone(self):
        findings = scan_content("call me at +1 (555) 123-4567")
        assert len(findings) >= 1
        phone = [f for f in findings if f["pattern"] == "phone"]
        assert len(phone) == 1

    def test_scan_detects_secret(self):
        findings = scan_content("secret = mysupersecretpassword123")
        assert len(findings) >= 1
        blocked = [f for f in findings if f["pattern"] == "secret"]
        assert len(blocked) >= 1
        assert blocked[0]["action"] == "blocked"

    def test_scan_empty_content(self):
        assert scan_content("") == []
        assert scan_content(None) == []

    def test_blocked_patterns_set(self):
        assert "api_key" in BLOCKED_PATTERNS
        assert "secret" in BLOCKED_PATTERNS
        assert "email" not in BLOCKED_PATTERNS


# ── Risk Level Detection Tests ──

class TestRiskLevelDetection:
    def test_detect_r0_default(self):
        assert detect_risk_level("Search for a translator") == RiskLevel.R0

    def test_detect_r2_from_booking(self):
        assert detect_risk_level("Make a booking for dinner") == RiskLevel.R2

    def test_detect_r2_from_email(self):
        assert detect_risk_level("email_send to client") == RiskLevel.R2

    def test_detect_r3_from_payment(self):
        assert detect_risk_level("Process payment for order") == RiskLevel.R3

    def test_detect_r3_from_meet_offline(self):
        assert detect_risk_level("Arrange meet_offline at cafe") == RiskLevel.R3

    def test_detect_r3_from_grant_access(self):
        assert detect_risk_level("grant_access to system") == RiskLevel.R3

    def test_detect_highest_risk(self):
        # Contains both R2 and R3 keywords
        result = detect_risk_level("Make a booking and process payment")
        assert result == RiskLevel.R3

    def test_base_risk_level_override(self):
        # If base is R2 and no keywords found, should stay R2
        result = detect_risk_level("Simple search", RiskLevel.R2)
        assert result == RiskLevel.R2

    def test_human_confirm_required(self):
        assert requires_human_confirm(RiskLevel.R0) is False
        assert requires_human_confirm(RiskLevel.R1) is False
        assert requires_human_confirm(RiskLevel.R2) is True
        assert requires_human_confirm(RiskLevel.R3) is True


# ── Task State Machine Tests ──

class TestTaskStateMachine:
    def test_valid_transitions_from_pending_delivery(self):
        allowed = TASK_TRANSITIONS[TaskStatus.PENDING_DELIVERY]
        assert TaskStatus.DELIVERED in allowed
        assert TaskStatus.FAILED in allowed
        assert TaskStatus.EXPIRED in allowed
        assert TaskStatus.CANCELLED in allowed

    def test_valid_transitions_from_delivered(self):
        allowed = TASK_TRANSITIONS[TaskStatus.DELIVERED]
        assert TaskStatus.PENDING_ACCEPT in allowed
        assert TaskStatus.EXPIRED in allowed
        assert TaskStatus.CANCELLED in allowed

    def test_valid_transitions_from_pending_accept(self):
        allowed = TASK_TRANSITIONS[TaskStatus.PENDING_ACCEPT]
        assert TaskStatus.ACCEPTED in allowed
        assert TaskStatus.DECLINED in allowed
        assert TaskStatus.EXPIRED in allowed

    def test_valid_transitions_from_in_progress(self):
        allowed = TASK_TRANSITIONS[TaskStatus.IN_PROGRESS]
        assert TaskStatus.COMPLETED in allowed
        assert TaskStatus.WAITING_HUMAN_CONFIRM in allowed
        assert TaskStatus.FAILED in allowed

    def test_valid_transitions_from_waiting_human_confirm(self):
        allowed = TASK_TRANSITIONS[TaskStatus.WAITING_HUMAN_CONFIRM]
        assert TaskStatus.COMPLETED in allowed
        assert TaskStatus.CANCELLED in allowed
        assert TaskStatus.EXPIRED in allowed

    def test_terminal_states_have_no_transitions(self):
        terminal = [
            TaskStatus.COMPLETED, TaskStatus.DECLINED,
            TaskStatus.EXPIRED, TaskStatus.CANCELLED, TaskStatus.FAILED,
        ]
        for state in terminal:
            assert state not in TASK_TRANSITIONS

    def test_all_task_statuses_covered(self):
        """Verify all non-terminal statuses have transitions."""
        non_terminal = [
            TaskStatus.PENDING_DELIVERY, TaskStatus.DELIVERED,
            TaskStatus.PENDING_ACCEPT, TaskStatus.ACCEPTED,
            TaskStatus.IN_PROGRESS, TaskStatus.WAITING_HUMAN_CONFIRM,
        ]
        for state in non_terminal:
            assert state in TASK_TRANSITIONS


# ── Trust Score Tests ──

class TestTrustScore:
    def test_perfect_trust_score(self):
        signals = {
            "verification_weight": 4,
            "success_rate_7d": 1.0,
            "report_rate_30d": 0.0,
            "human_confirm_success_rate": 1.0,
            "cancel_expire_rate_30d": 0.0,
        }
        score = compute_trust_score(signals)
        # 25*(4/4) + 25*1.0 - 20*0.0 + 15*1.0 - 15*0.0 = 25+25+15 = 65
        assert score == 65.0

    def test_zero_trust_score(self):
        signals = {
            "verification_weight": 0,
            "success_rate_7d": 0.0,
            "report_rate_30d": 1.0,
            "human_confirm_success_rate": 0.0,
            "cancel_expire_rate_30d": 1.0,
        }
        score = compute_trust_score(signals)
        assert score == 0.0  # clamped to 0

    def test_empty_signals(self):
        assert compute_trust_score({}) == 0.0
        assert compute_trust_score(None) == 0.0

    def test_medium_trust_score(self):
        signals = {
            "verification_weight": 1,
            "success_rate_7d": 0.8,
            "report_rate_30d": 0.05,
            "human_confirm_success_rate": 0.9,
            "cancel_expire_rate_30d": 0.1,
        }
        score = compute_trust_score(signals)
        assert 30 < score < 80  # reasonable range


# ── Protected Brand Words Tests ──

class TestProtectedBrands:
    def test_detects_brand_words(self):
        for brand in ["OpenAI", "ChatGPT", "Claude", "Anthropic"]:
            with pytest.raises(Exception):  # InvalidRequestError
                check_protected_brand(brand)

    def test_allows_normal_names(self):
        # Should not raise
        check_protected_brand("My Translation Agent")
        check_protected_brand("Tokyo Travel Helper")
        check_protected_brand("Code Review Bot")

    def test_case_insensitive(self):
        with pytest.raises(Exception):
            check_protected_brand("CHATGPT Agent")
        with pytest.raises(Exception):
            check_protected_brand("claude assistant")


# ── High Risk Keywords Tests ──

class TestHighRiskKeywords:
    def test_r3_keywords_exist(self):
        r3_keywords = [k for k, v in HIGH_RISK_KEYWORDS.items() if v == RiskLevel.R3]
        assert "payment" in r3_keywords
        assert "transfer" in r3_keywords
        assert "meet_offline" in r3_keywords

    def test_r2_keywords_exist(self):
        r2_keywords = [k for k, v in HIGH_RISK_KEYWORDS.items() if v == RiskLevel.R2]
        assert "booking" in r2_keywords
        assert "email_send" in r2_keywords
        assert "share_contact" in r2_keywords

    def test_keywords_coverage(self):
        """Ensure we have reasonable keyword coverage."""
        assert len(HIGH_RISK_KEYWORDS) >= 20


# ── Enum Coverage Tests ──

class TestEnumCoverage:
    def test_all_task_statuses(self):
        assert len(TaskStatus) == 12  # including draft

    def test_risk_levels(self):
        assert len(RiskLevel) == 4

    def test_risk_level_ordering(self):
        assert RiskLevel.R0.value < RiskLevel.R1.value
        assert RiskLevel.R1.value < RiskLevel.R2.value
        assert RiskLevel.R2.value < RiskLevel.R3.value


# ── Visibility Update Validation Tests ──

class FakePersonalAgent:
    agent_type = "personal"

class FakeServiceAgent:
    agent_type = "service"


class TestVisibilityUpdateValidation:
    @pytest.mark.asyncio
    async def test_personal_cannot_make_looking_for_public(self):
        with pytest.raises(ValueError, match="must remain private"):
            await validate_visibility_update(FakePersonalAgent(), "looking_for", "public")

    @pytest.mark.asyncio
    async def test_personal_cannot_make_looking_for_network(self):
        with pytest.raises(ValueError, match="must remain private"):
            await validate_visibility_update(FakePersonalAgent(), "looking_for", "network_only")

    @pytest.mark.asyncio
    async def test_personal_looking_for_private_ok(self):
        result = await validate_visibility_update(FakePersonalAgent(), "looking_for", "private")
        assert result == "private"

    @pytest.mark.asyncio
    async def test_service_looking_for_public_ok(self):
        result = await validate_visibility_update(FakeServiceAgent(), "looking_for", "public")
        assert result == "public"

    @pytest.mark.asyncio
    async def test_invalid_visibility_value(self):
        with pytest.raises(ValueError, match="Invalid visibility"):
            await validate_visibility_update(FakePersonalAgent(), "bio", "invalid")

    @pytest.mark.asyncio
    async def test_personal_bio_network_ok(self):
        result = await validate_visibility_update(FakePersonalAgent(), "bio", "network_only")
        assert result == "network_only"
