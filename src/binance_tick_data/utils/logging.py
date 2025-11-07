"""Centralized logging configuration with structured logging support.

This module provides:
- Structured logging with structlog
- JSON output for production monitoring
- File logging with rotation
- Suppression of noisy third-party loggers
- Consistent formatting across the codebase

Example usage:
    from binance_tick_data.utils.logging import setup_logging, get_logger

    # Configure logging
    setup_logging(verbose=True, log_file="app.log")

    # Get logger
    logger = get_logger(__name__)

    # Use structured logging
    logger.info("download_started", symbol="BTCUSDT", records=1000)
    logger.error("download_failed", error=str(e), exc_info=True)
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler

import structlog


def setup_logging(
    verbose: bool = False,
    quiet: bool = False,
    log_file: Optional[Path] = None,
    json_logs: bool = False,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
) -> None:
    """
    Configure structured logging for the application.

    Args:
        verbose: Enable DEBUG level logging
        quiet: Enable WARNING level logging only
        log_file: Optional file path for log output
        json_logs: Output logs in JSON format (for production)
        max_bytes: Maximum log file size before rotation (default: 10MB)
        backup_count: Number of backup log files to keep (default: 5)

    Example:
        >>> setup_logging(verbose=True, log_file=Path("app.log"))
        >>> logger = get_logger(__name__)
        >>> logger.info("application_started")
    """
    # Determine log level
    if verbose:
        level = logging.DEBUG
    elif quiet:
        level = logging.WARNING
    else:
        level = logging.INFO

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        level=level,
        stream=sys.stdout,
    )

    # Suppress noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("dlt").setLevel(logging.WARNING)
    logging.getLogger("dagster").setLevel(logging.WARNING)
    logging.getLogger("binance").setLevel(logging.WARNING)

    # Configure structlog processors
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    # Add exception formatting
    if verbose:
        processors.append(structlog.processors.format_exc_info)
    else:
        # In non-verbose mode, format exceptions more compactly
        processors.append(structlog.processors.ExceptionPrettyPrinter())

    # Choose renderer based on output format
    if json_logs:
        # JSON output for production/monitoring
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Colorized console output for development
        processors.append(
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.plain_traceback,
            )
        )

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Add file handler if log_file specified
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)

        # Create rotating file handler
        file_handler = RotatingFileHandler(
            filename=log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(level)

        # Use JSON format for file logs (easier to parse)
        file_formatter = logging.Formatter(
            "%(message)s"  # structlog will handle formatting
        )
        file_handler.setFormatter(file_formatter)

        # Add to root logger
        logging.root.addHandler(file_handler)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a configured structured logger.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured structlog BoundLogger

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("operation_started", user_id=123, action="download")
        >>> logger.error("operation_failed", error="Connection timeout", retry_count=3)
    """
    return structlog.get_logger(name)


# Convenience functions for common logging patterns

def log_operation_start(logger: structlog.stdlib.BoundLogger, operation: str, **kwargs) -> None:
    """
    Log the start of an operation with context.

    Args:
        logger: Structured logger instance
        operation: Operation name (e.g., "download", "stream")
        **kwargs: Additional context (symbol, date_range, etc.)

    Example:
        >>> logger = get_logger(__name__)
        >>> log_operation_start(logger, "download", symbols=["BTCUSDT"], days=30)
    """
    logger.info(f"{operation}_started", **kwargs)


def log_operation_complete(
    logger: structlog.stdlib.BoundLogger,
    operation: str,
    duration_seconds: float,
    **kwargs
) -> None:
    """
    Log the completion of an operation with metrics.

    Args:
        logger: Structured logger instance
        operation: Operation name
        duration_seconds: Operation duration
        **kwargs: Additional metrics (records_count, etc.)

    Example:
        >>> logger = get_logger(__name__)
        >>> log_operation_complete(
        ...     logger, "download",
        ...     duration_seconds=125.5,
        ...     records_count=10000
        ... )
    """
    logger.info(
        f"{operation}_completed",
        duration_seconds=duration_seconds,
        **kwargs
    )


def log_operation_failed(
    logger: structlog.stdlib.BoundLogger,
    operation: str,
    error: str,
    **kwargs
) -> None:
    """
    Log operation failure with error details.

    Args:
        logger: Structured logger instance
        operation: Operation name
        error: Error message or exception string
        **kwargs: Additional context

    Example:
        >>> logger = get_logger(__name__)
        >>> try:
        ...     # some operation
        ...     pass
        ... except Exception as e:
        ...     log_operation_failed(logger, "download", str(e), symbol="BTCUSDT")
    """
    logger.error(
        f"{operation}_failed",
        error=error,
        **kwargs
    )
