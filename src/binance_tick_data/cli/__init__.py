"""CLI business logic layer - clean separation from presentation."""

from .models import (
    DownloadParams,
    DownloadResult,
    StreamParams,
    StreamResult,
    ValidateParams,
    ValidationResult,
    DataSummary,
)
from .download import execute_download
from .stream import execute_stream, request_shutdown, reset_shutdown_flag

__all__ = [
    # Models
    "DownloadParams",
    "DownloadResult",
    "StreamParams",
    "StreamResult",
    "ValidateParams",
    "ValidationResult",
    "DataSummary",
    # Business logic
    "execute_download",
    "execute_stream",
    "request_shutdown",
    "reset_shutdown_flag",
]
