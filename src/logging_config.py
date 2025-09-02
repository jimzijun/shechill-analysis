#!/usr/bin/env python3
"""
Centralized Logging Configuration for SheChill Analysis
=======================================================

Provides unified logging configuration for all application components:
- Structured JSON logging for Docker/production environments
- Human-readable console logging for development
- Request correlation tracking
- Component-specific loggers with consistent formatting
- Environment-based configuration switching

Usage:
    from src.logging_config import get_logger

    logger = get_logger("component_name")
    logger.info("Operation completed", extra={"duration": 1.23, "items_processed": 42})
"""

import json
import logging
import logging.config
import os
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union

# Context variables for thread-safe correlation tracking
_correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)
_request_id: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_user_session: ContextVar[Optional[str]] = ContextVar("user_session", default=None)


class CorrelationFilter(logging.Filter):
    """Filter to add correlation ID and component metadata to log records"""

    def filter(self, record):
        # Add correlation ID if available
        record.correlation_id = _correlation_id.get() or ""
        record.request_id = _request_id.get() or ""
        record.user_session = _user_session.get() or ""

        # Add process info
        record.component = getattr(record, "component", record.name)
        record.hostname = os.getenv("HOSTNAME", "localhost")
        record.process_id = os.getpid()

        return True


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging in Docker/production environments"""

    def format(self, record):
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "component": getattr(record, "component", record.name),
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "process_id": getattr(record, "process_id", os.getpid()),
            "hostname": getattr(record, "hostname", "localhost"),
        }

        # Add correlation tracking if available
        if hasattr(record, "correlation_id") and record.correlation_id:
            log_data["correlation_id"] = record.correlation_id
        if hasattr(record, "request_id") and record.request_id:
            log_data["request_id"] = record.request_id
        if hasattr(record, "user_session") and record.user_session:
            log_data["user_session"] = record.user_session

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add any extra fields from log calls
        for key, value in record.__dict__.items():
            if key not in [
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "exc_info",
                "exc_text",
                "stack_info",
                "getMessage",
                "component",
                "correlation_id",
                "request_id",
                "user_session",
                "process_id",
                "hostname",
            ] and not key.startswith("_"):
                log_data[key] = value

        return json.dumps(log_data, default=str)


def get_logging_config() -> Dict[str, Any]:
    """Get simplified logging configuration for all environments"""

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "correlation": {
                "()": CorrelationFilter,
            }
        },
        "formatters": {
            "structured": {
                "()": StructuredFormatter,
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": sys.stdout,
                "formatter": "structured",
                "filters": ["correlation"],
                "level": log_level,
            },
            "error_console": {
                "class": "logging.StreamHandler",
                "stream": sys.stderr,
                "formatter": "structured",
                "filters": ["correlation"],
                "level": "ERROR",
            },
        },
        "loggers": {},
        "root": {"level": log_level, "handlers": ["console", "error_console"]},
    }

    return config


def setup_logging():
    """Initialize logging configuration for the application"""
    config = get_logging_config()
    logging.config.dictConfig(config)

    # Set appropriate levels for third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("prophet").setLevel(logging.WARNING)
    logging.getLogger("cmdstanpy").setLevel(logging.WARNING)

    # Log the setup completion
    logger = logging.getLogger("logging_config")
    logger.info("Logging configured", extra={"log_level": os.getenv("LOG_LEVEL", "INFO")})


def get_logger(name: str, component: Optional[str] = None) -> Union[logging.Logger, logging.LoggerAdapter]:
    """
    Get a logger instance with optional component name

    Args:
        name: Logger name (usually module name)
        component: Component name for grouping (defaults to name)

    Returns:
        Logger instance configured with correlation tracking
    """
    logger = logging.getLogger(name)

    # Add component info to logger
    if component:
        # Create a custom LoggerAdapter that adds component info
        class ComponentAdapter(logging.LoggerAdapter):
            def process(self, msg, kwargs):
                kwargs.setdefault("extra", {})["component"] = component
                return msg, kwargs

        return ComponentAdapter(logger, {})

    return logger


def set_correlation_context(
    correlation_id: Optional[str] = None, request_id: Optional[str] = None, user_session: Optional[str] = None
):
    """
    Set correlation context for request tracing

    Args:
        correlation_id: Unique ID for correlating related operations
        request_id: Unique ID for this specific request
        user_session: User session identifier
    """
    if correlation_id:
        _correlation_id.set(correlation_id)
    if request_id:
        _request_id.set(request_id)
    if user_session:
        _user_session.set(user_session)


def clear_correlation_context():
    """Clear correlation context"""
    _correlation_id.set(None)
    _request_id.set(None)
    _user_session.set(None)


def generate_correlation_id() -> str:
    """Generate a new correlation ID"""
    return str(uuid.uuid4())


def generate_request_id() -> str:
    """Generate a new request ID"""
    return str(uuid.uuid4())


# Performance monitoring helpers
class PerformanceLogger:
    """Context manager for logging operation performance"""

    def __init__(self, logger: Union[logging.Logger, logging.LoggerAdapter], operation: str, **extra_fields):
        self.logger = logger
        self.operation = operation
        self.extra_fields = extra_fields
        self.start_time = None

    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.info(f"Starting {self.operation}", extra=self.extra_fields)
        return self

    def __exit__(self, exc_type, exc_val, _exc_tb):
        duration = (datetime.now() - self.start_time).total_seconds()

        if exc_type:
            self.logger.error(
                f"Failed {self.operation}",
                extra={**self.extra_fields, "duration_seconds": duration, "error": str(exc_val)},
                exc_info=True,
            )
        else:
            self.logger.info(f"Completed {self.operation}", extra={**self.extra_fields, "duration_seconds": duration})
        # Return None to not suppress exceptions
        return None


# Initialize logging when module is imported
if __name__ != "__main__":
    setup_logging()


if __name__ == "__main__":
    # Test the logging configuration
    setup_logging()

    # Test different components
    test_logger = get_logger("test_component", "TestSuite")

    test_logger.debug("Debug message with extra data", extra={"test_value": 123})
    test_logger.info("Info message", extra={"operation": "test", "items": 5})
    test_logger.warning("Warning message")
    test_logger.error("Error message", extra={"error_code": "E001"})

    # Test correlation context
    set_correlation_context(
        correlation_id=generate_correlation_id(), request_id=generate_request_id(), user_session="test_session"
    )

    test_logger.info("Message with correlation context")

    # Test performance logging
    with PerformanceLogger(test_logger, "test operation", items=10):
        import time

        time.sleep(0.1)  # Simulate work

    print("Logging test completed!")
