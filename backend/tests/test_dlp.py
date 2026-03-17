"""Tests for DLP (Data Loss Prevention) service."""

from __future__ import annotations

from app.services.dlp_service import has_blocked, has_warning, scan_content


class TestDLPScan:
    """Test DLP content scanning rules."""

    def test_clean_content(self):
        """Clean content should return no findings."""
        findings = scan_content("Please translate this document for me.")
        assert len(findings) == 0

    def test_detect_api_key(self):
        """API keys should be blocked."""
        findings = scan_content("Here is my api_key: sk-abc123456")
        assert has_blocked(findings)

    def test_detect_secret(self):
        """Secrets should be blocked."""
        findings = scan_content("My secret=SuperSecretKey12345 here")
        assert has_blocked(findings)

    def test_detect_password(self):
        """Passwords should be blocked."""
        findings = scan_content("Use password=mypassword123")
        assert has_blocked(findings)

    def test_detect_private_key(self):
        """Private keys should be blocked."""
        findings = scan_content("Copy the private_key to the file")
        assert has_blocked(findings)

    def test_detect_email_warning(self):
        """Email addresses should generate a warning, not a block."""
        findings = scan_content("Contact me at user@example.com")
        assert has_warning(findings)
        assert not has_blocked(findings)

    def test_detect_phone_warning(self):
        """Phone numbers should generate a warning."""
        findings = scan_content("Call me at 555-123-4567")
        assert has_warning(findings)

    def test_no_false_positive_on_normal_text(self):
        """Normal task descriptions should not trigger DLP."""
        texts = [
            "Book a restaurant for 2 people at 7pm",
            "Translate this PDF from English to Chinese",
            "Find me a flight from NYC to LAX",
            "Summarize this research paper",
        ]
        for text in texts:
            findings = scan_content(text)
            assert not has_blocked(findings), f"False positive on: {text}"

    def test_blocked_takes_priority(self):
        """If both blocked and warning patterns found, has_blocked should be True."""
        findings = scan_content("Send to user@example.com with api_key=abcdef12345678")
        assert has_blocked(findings)
        assert has_warning(findings)

    def test_empty_content(self):
        """Empty content should have no findings."""
        assert len(scan_content("")) == 0
        assert len(scan_content("   ")) == 0

    def test_url_warning(self):
        """URLs should generate a warning."""
        findings = scan_content("Visit https://example.com for details")
        assert has_warning(findings)
