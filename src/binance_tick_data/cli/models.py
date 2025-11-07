"""Pydantic models for CLI parameters and results.

These models provide:
- Type safety throughout the codebase
- Automatic validation of parameters
- Self-documenting code with Field descriptions
- Immutable parameter objects (frozen=True)
- JSON serialization for result objects
"""

from typing import List, Optional, Dict, Any
from datetime import date, datetime
from pathlib import Path
from pydantic import BaseModel, Field, field_validator, ConfigDict


# ============================================================================
# Download Models
# ============================================================================

class DownloadParams(BaseModel):
    """Parameters for historical data download operation.

    All parameters are validated on construction. Invalid parameters
    raise ValidationError with clear error messages.
    """
    model_config = ConfigDict(frozen=True)  # Immutable after creation

    symbols: List[str] = Field(
        ...,
        min_length=1,
        description="Trading pair symbols (e.g., BTCUSDT, ETHUSDT)"
    )
    start_date: date = Field(
        ...,
        description="Start date for historical data"
    )
    end_date: Optional[date] = Field(
        None,
        description="End date for historical data (default: today)"
    )
    max_records: Optional[int] = Field(
        None,
        ge=1000,
        description="Maximum records to download (for testing)"
    )
    batch_size: int = Field(
        1000,
        ge=100,
        le=10000,
        description="Records per API batch (Binance limit: 1000)"
    )
    destination: str = Field(
        "duckdb",
        description="Destination type (duckdb, postgres, etc.)"
    )

    @field_validator('symbols')
    @classmethod
    def validate_symbols(cls, v: List[str]) -> List[str]:
        """Ensure symbols are uppercase."""
        return [s.upper().strip() for s in v]

    @field_validator('end_date')
    @classmethod
    def validate_date_range(cls, v: Optional[date], info) -> Optional[date]:
        """Ensure end_date is after start_date."""
        if v is None:
            return date.today()

        start_date = info.data.get('start_date')
        if start_date and v < start_date:
            raise ValueError(f'end_date ({v}) must be after start_date ({start_date})')

        return v

    @field_validator('end_date')
    @classmethod
    def warn_future_date(cls, v: Optional[date]) -> Optional[date]:
        """Warn if end_date is in the future."""
        if v and v > date.today():
            # Note: This is a warning, not an error
            # The validation passes but caller should check warnings
            pass
        return v

    @property
    def days_to_download(self) -> int:
        """Calculate number of days in date range."""
        end = self.end_date or date.today()
        return (end - self.start_date).days + 1

    @property
    def is_large_download(self) -> bool:
        """Check if download is large (>30 days)."""
        return self.days_to_download > 30

    @property
    def has_future_date(self) -> bool:
        """Check if end_date is in the future."""
        end = self.end_date or date.today()
        return end > date.today()


class DownloadResult(BaseModel):
    """Result of historical data download operation.

    Provides structured result with metrics for logging and display.
    """
    success: bool = Field(..., description="Whether download succeeded")
    records_count: int = Field(
        0,
        ge=0,
        description="Total records downloaded"
    )
    symbols_processed: List[str] = Field(
        default_factory=list,
        description="Symbols successfully processed"
    )
    symbols_failed: List[str] = Field(
        default_factory=list,
        description="Symbols that failed to download"
    )
    duration_seconds: float = Field(
        ...,
        ge=0,
        description="Total duration in seconds"
    )
    pipeline_name: str = Field(..., description="DLT pipeline name")
    output_path: str = Field(..., description="Database or output path")
    error: Optional[str] = Field(
        None,
        description="Error message if failed"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Warning messages"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (load IDs, etc.)"
    )

    @property
    def records_per_second(self) -> float:
        """Calculate download throughput."""
        if self.duration_seconds > 0:
            return self.records_count / self.duration_seconds
        return 0.0


# ============================================================================
# Stream Models
# ============================================================================

class StreamParams(BaseModel):
    """Parameters for real-time streaming operation."""
    model_config = ConfigDict(frozen=True)

    symbols: List[str] = Field(
        ...,
        min_length=1,
        description="Trading pair symbols to stream"
    )
    max_batches: Optional[int] = Field(
        None,
        ge=1,
        description="Maximum batches to process (for testing)"
    )
    buffer_size: int = Field(
        100,
        ge=10,
        le=1000,
        description="Buffer size before flushing to database"
    )
    destination: str = Field(
        "duckdb",
        description="Destination type"
    )

    @field_validator('symbols')
    @classmethod
    def validate_symbols(cls, v: List[str]) -> List[str]:
        """Ensure symbols are uppercase."""
        return [s.upper().strip() for s in v]


class StreamResult(BaseModel):
    """Result of streaming operation."""
    success: bool = Field(..., description="Whether stream succeeded")
    records_count: int = Field(
        0,
        ge=0,
        description="Total records streamed"
    )
    batches_processed: int = Field(
        0,
        ge=0,
        description="Number of batches processed"
    )
    duration_seconds: float = Field(
        ...,
        ge=0,
        description="Total duration in seconds"
    )
    pipeline_name: str = Field(..., description="DLT pipeline name")
    output_path: str = Field(..., description="Database or output path")
    error: Optional[str] = Field(
        None,
        description="Error message if failed"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Warning messages"
    )


# ============================================================================
# Validation Models
# ============================================================================

class ValidateParams(BaseModel):
    """Parameters for data validation operation."""
    model_config = ConfigDict(frozen=True)

    start_date: Optional[date] = Field(
        None,
        description="Start date for validation window"
    )
    end_date: Optional[date] = Field(
        None,
        description="End date for validation window"
    )
    symbol: Optional[str] = Field(
        None,
        description="Specific symbol to validate (all if None)"
    )

    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v: Optional[str]) -> Optional[str]:
        """Ensure symbol is uppercase."""
        return v.upper().strip() if v else None


class ValidationResult(BaseModel):
    """Result of data validation operation."""
    success: bool = Field(..., description="Whether validation succeeded")
    total_records: int = Field(0, ge=0, description="Total records checked")
    duplicate_count: int = Field(0, ge=0, description="Number of duplicates found")
    gap_count: int = Field(0, ge=0, description="Number of gaps found")
    anomaly_count: int = Field(0, ge=0, description="Number of anomalies found")
    symbols_checked: List[str] = Field(
        default_factory=list,
        description="Symbols that were validated"
    )
    issues: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of detected issues with details"
    )
    duration_seconds: float = Field(
        ...,
        ge=0,
        description="Validation duration"
    )

    @property
    def has_issues(self) -> bool:
        """Check if any issues were found."""
        return (
            self.duplicate_count > 0 or
            self.gap_count > 0 or
            self.anomaly_count > 0
        )

    @property
    def quality_score(self) -> float:
        """Calculate data quality score (0-100)."""
        if self.total_records == 0:
            return 100.0

        issues_total = self.duplicate_count + self.gap_count + self.anomaly_count
        return max(0.0, 100.0 * (1.0 - issues_total / self.total_records))


# ============================================================================
# List Data Models
# ============================================================================

class DataSummary(BaseModel):
    """Summary of available data for a symbol."""
    symbol: str = Field(..., description="Trading pair symbol")
    record_count: int = Field(0, ge=0, description="Total records")
    start_date: Optional[date] = Field(None, description="Earliest data date")
    end_date: Optional[date] = Field(None, description="Latest data date")
    size_bytes: int = Field(0, ge=0, description="Approximate data size")
    last_updated: Optional[datetime] = Field(
        None,
        description="Last update timestamp"
    )

    @property
    def days_of_data(self) -> int:
        """Calculate number of days covered."""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return 0

    @property
    def size_mb(self) -> float:
        """Get size in megabytes."""
        return self.size_bytes / (1024 * 1024)
