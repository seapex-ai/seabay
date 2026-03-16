"""Tests for structured JSON logging."""

from __future__ import annotations

import json
import logging

from app.core.json_logging import JSONFormatter, get_request_logger


class TestJSONFormatter:
    """Test JSON log formatting."""

    def test_format_basic(self):
        formatter = JSONFormatter(service_name="test")
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "INFO"
        assert parsed["message"] == "Test message"
        assert parsed["service"] == "test"

    def test_format_includes_timestamp(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.WARNING,
            pathname="", lineno=0, msg="msg", args=(), exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "timestamp" in parsed

    def test_format_includes_source(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="app/main.py", lineno=10, msg="hello", args=(), exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["source"]["file"] == "app/main.py"
        assert parsed["source"]["line"] == 10

    def test_format_valid_json(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.ERROR,
            pathname="", lineno=0, msg="error occurred", args=(), exc_info=None,
        )
        output = formatter.format(record)
        # Should not raise
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_format_with_exception(self):
        formatter = JSONFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys
            record = logging.LogRecord(
                name="test", level=logging.ERROR,
                pathname="", lineno=0, msg="failed",
                args=(), exc_info=sys.exc_info(),
            )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "exception" in parsed
        assert parsed["exception"]["type"] == "ValueError"
        assert "test error" in parsed["exception"]["message"]


class TestRequestLogger:
    """Test request-scoped logger."""

    def test_get_logger_with_request_id(self):
        adapter = get_request_logger("test", request_id="req_123")
        assert adapter.extra["request_id"] == "req_123"

    def test_get_logger_with_agent_id(self):
        adapter = get_request_logger("test", agent_id="agt_456")
        assert adapter.extra["agent_id"] == "agt_456"

    def test_get_logger_no_context(self):
        adapter = get_request_logger("test")
        assert adapter.extra == {}
