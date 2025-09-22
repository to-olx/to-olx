"""
Logging configuration module using structlog for structured logging.
"""

import logging
import sys
from typing import Any, Dict

import structlog
from structlog.contextvars import merge_contextvars

from app.core.config import settings


def setup_logging() -> None:
    """
    Configure structured logging for the application.
    """
    # Set up standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper()),
    )
    
    # Configure structlog
    processors = [
        merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    if settings.log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get a logger instance with the given name.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        structlog.BoundLogger: Configured logger instance
    """
    return structlog.get_logger(name)


class LogContext:
    """Context manager for adding temporary context to logs."""
    
    def __init__(self, **kwargs: Any):
        self.context = kwargs
        self._tokens = []
    
    def __enter__(self):
        for key, value in self.context.items():
            token = structlog.contextvars.bind_contextvars(**{key: value})
            self._tokens.append(token)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        for token in self._tokens:
            structlog.contextvars.clear_contextvars()


def log_error(logger: structlog.BoundLogger, error: Exception, **context: Any) -> None:
    """
    Log an error with context.
    
    Args:
        logger: Logger instance
        error: Exception to log
        **context: Additional context to include in the log
    """
    logger.error(
        "error_occurred",
        error_type=type(error).__name__,
        error_message=str(error),
        **context,
        exc_info=True,
    )


def log_request(
    logger: structlog.BoundLogger,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    **context: Any,
) -> None:
    """
    Log an HTTP request.
    
    Args:
        logger: Logger instance
        method: HTTP method
        path: Request path
        status_code: Response status code
        duration_ms: Request duration in milliseconds
        **context: Additional context to include in the log
    """
    logger.info(
        "http_request",
        method=method,
        path=path,
        status_code=status_code,
        duration_ms=duration_ms,
        **context,
    )