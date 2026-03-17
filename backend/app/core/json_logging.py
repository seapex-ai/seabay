"""Structured JSON logging for production environments.

Provides JSON-formatted log output suitable for log aggregation services
(ELK, Datadog, CloudWatch, etc.).

Usage:
    from app.core.json_logging import setup_json_logging
    setup_json_logging()

Configuration:
    - SEABAY_LOG_FORMAT=json → enables JSON logging
    - SEABAY_LOG_FORMAT=text → plain text logging (default)
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Optional

from app.config import settings


class JSONFormatter(logging.Formatter):
    """Format log records as JSON lines."""

    def __init__(
        self,
        service_name: str = "seabay",
        region: Optional[str] = None,
        version: Optional[str] = None,
    ):
        super().__init__()
        self.service_name = service_name
        self.region = region or settings.REGION
        self.version = version or settings.APP_VERSION

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self.service_name,
            "region": self.region,
            "version": self.version,
        }

        # Add location info
        if record.pathname:
            log_entry["source"] = {
                "file": record.pathname,
                "line": record.lineno,
                "function": record.funcName,
            }

        # Add exception info
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = {
                "type": type(record.exc_info[1]).__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        # Add extra fields from record
        standard_attrs = {
            "name", "msg", "args", "created", "relativeCreated", "exc_info",
            "exc_text", "stack_info", "lineno", "funcName", "pathname",
            "filename", "module", "thread", "threadName", "process",
            "processName", "levelname", "levelno", "message", "msecs",
            "taskName",
        }
        extra = {
            k: v for k, v in record.__dict__.items()
            if k not in standard_attrs and not k.startswith("_")
        }
        if extra:
            log_entry["extra"] = extra

        return json.dumps(log_entry, default=str)


class RequestLogFormatter(JSONFormatter):
    """Extended JSON formatter with request context."""

    def format(self, record: logging.LogRecord) -> str:
        base = json.loads(super().format(record))

        # Add request context if available
        request_id = getattr(record, "request_id", None)
        if request_id:
            base["request_id"] = request_id

        agent_id = getattr(record, "agent_id", None)
        if agent_id:
            base["agent_id"] = agent_id

        return json.dumps(base, default=str)


def setup_json_logging(
    level: Optional[str] = None,
    service_name: str = "seabay",
) -> None:
    """Configure structured JSON logging.

    Call this at application startup to replace the default text formatter.
    """
    log_level = level or ("DEBUG" if settings.DEBUG else "INFO")

    # Clear existing handlers
    root = logging.getLogger()
    root.handlers.clear()

    # Create JSON handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(RequestLogFormatter(
        service_name=service_name,
        region=settings.REGION,
        version=settings.APP_VERSION,
    ))

    root.addHandler(handler)
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Quiet down noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_request_logger(
    name: str,
    request_id: Optional[str] = None,
    agent_id: Optional[str] = None,
) -> logging.LoggerAdapter:
    """Get a logger with request context attached."""
    logger = logging.getLogger(name)
    extra = {}
    if request_id:
        extra["request_id"] = request_id
    if agent_id:
        extra["agent_id"] = agent_id
    return logging.LoggerAdapter(logger, extra)
