"""Tests for CLI Pydantic models."""

import pytest
from datetime import date, datetime, timedelta
from pydantic import ValidationError

from binance_tick_data.cli.models import (
    DownloadParams,
    DownloadResult,
    StreamParams,
    StreamResult,
    ValidateParams,
    ValidationResult,
    DataSummary,
)


class TestDownloadParams:
    """Tests for DownloadParams model."""

    def test_valid_params(self):
        """Test creating valid download parameters."""
        params = DownloadParams(
            symbols=["BTCUSDT"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            batch_size=1000,
            destination="duckdb",
        )
        assert params.symbols == ["BTCUSDT"]
        assert params.start_date == date(2024, 1, 1)
        assert params.end_date == date(2024, 1, 31)
        assert params.batch_size == 1000
        assert params.destination == "duckdb"

    def test_symbols_uppercased(self):
        """Test that symbols are automatically uppercased."""
        params = DownloadParams(
            symbols=["btcusdt", "ethusdt"],
            start_date=date(2024, 1, 1),
        )
        assert params.symbols == ["BTCUSDT", "ETHUSDT"]

    def test_symbols_whitespace_stripped(self):
        """Test that symbols have whitespace stripped."""
        params = DownloadParams(
            symbols=[" BTCUSDT ", " ETHUSDT "],
            start_date=date(2024, 1, 1),
        )
        assert params.symbols == ["BTCUSDT", "ETHUSDT"]

    def test_empty_symbols_raises_error(self):
        """Test that empty symbols list raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            DownloadParams(
                symbols=[],
                start_date=date(2024, 1, 1),
            )
        assert "at least 1 item" in str(exc_info.value).lower()

    def test_end_before_start_raises_error(self):
        """Test that end_date before start_date raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            DownloadParams(
                symbols=["BTCUSDT"],
                start_date=date(2024, 1, 31),
                end_date=date(2024, 1, 1),
            )
        # Check error mentions both dates
        error_str = str(exc_info.value).lower()
        assert "end_date" in error_str and ("must be after" in error_str or "value error" in error_str)

    def test_end_date_defaults_to_none(self):
        """Test that end_date is None if not provided."""
        params = DownloadParams(
            symbols=["BTCUSDT"],
            start_date=date(2024, 1, 1),
        )
        # end_date remains None - business logic handles the default
        assert params.end_date is None

    def test_days_to_download_property(self):
        """Test days_to_download computed property."""
        params = DownloadParams(
            symbols=["BTCUSDT"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
        )
        # Inclusive: Jan 1 to Jan 31 = 31 days
        assert params.days_to_download == 31

    def test_days_to_download_with_none_end_date(self):
        """Test days_to_download when end_date is None (defaults to today)."""
        params = DownloadParams(
            symbols=["BTCUSDT"],
            start_date=date.today() - timedelta(days=10),
        )
        # Should calculate days from start_date to today
        assert params.days_to_download >= 10

    def test_is_large_download_true(self):
        """Test is_large_download returns True for >30 days."""
        params = DownloadParams(
            symbols=["BTCUSDT"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 15),  # 74 days
        )
        assert params.is_large_download is True

    def test_is_large_download_false(self):
        """Test is_large_download returns False for <=30 days."""
        params = DownloadParams(
            symbols=["BTCUSDT"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 15),  # 14 days
        )
        assert params.is_large_download is False

    def test_batch_size_validation(self):
        """Test batch_size must be between 100 and 10000."""
        # Too small
        with pytest.raises(ValidationError):
            DownloadParams(
                symbols=["BTCUSDT"],
                start_date=date(2024, 1, 1),
                batch_size=50,
            )

        # Too large
        with pytest.raises(ValidationError):
            DownloadParams(
                symbols=["BTCUSDT"],
                start_date=date(2024, 1, 1),
                batch_size=20000,
            )

        # Valid range
        params = DownloadParams(
            symbols=["BTCUSDT"],
            start_date=date(2024, 1, 1),
            batch_size=5000,
        )
        assert params.batch_size == 5000

    def test_max_records_validation(self):
        """Test max_records must be >= 1000 if provided."""
        # Too small
        with pytest.raises(ValidationError):
            DownloadParams(
                symbols=["BTCUSDT"],
                start_date=date(2024, 1, 1),
                max_records=500,
            )

        # Valid
        params = DownloadParams(
            symbols=["BTCUSDT"],
            start_date=date(2024, 1, 1),
            max_records=10000,
        )
        assert params.max_records == 10000

        # None is valid
        params = DownloadParams(
            symbols=["BTCUSDT"],
            start_date=date(2024, 1, 1),
            max_records=None,
        )
        assert params.max_records is None

    def test_params_immutable(self):
        """Test that params are frozen (immutable)."""
        params = DownloadParams(
            symbols=["BTCUSDT"],
            start_date=date(2024, 1, 1),
        )
        with pytest.raises(ValidationError):
            params.symbols = ["ETHUSDT"]


class TestDownloadResult:
    """Tests for DownloadResult model."""

    def test_successful_result(self):
        """Test creating a successful result."""
        result = DownloadResult(
            success=True,
            records_count=100000,
            symbols_processed=["BTCUSDT"],
            duration_seconds=45.5,
            pipeline_name="binance_historical",
            output_path="/tmp/test.duckdb",
        )
        assert result.success is True
        assert result.records_count == 100000
        assert result.error is None

    def test_failed_result(self):
        """Test creating a failed result."""
        result = DownloadResult(
            success=False,
            duration_seconds=5.0,
            pipeline_name="binance_historical",
            output_path="",
            error="API rate limit exceeded",
        )
        assert result.success is False
        assert result.error == "API rate limit exceeded"
        assert result.records_count == 0

    def test_records_per_second_property(self):
        """Test records_per_second computed property."""
        result = DownloadResult(
            success=True,
            records_count=100000,
            symbols_processed=["BTCUSDT"],
            duration_seconds=50.0,
            pipeline_name="test",
            output_path="/tmp/test.duckdb",
        )
        assert result.records_per_second == 2000.0

    def test_records_per_second_zero_duration(self):
        """Test records_per_second with zero duration."""
        result = DownloadResult(
            success=True,
            records_count=100,
            symbols_processed=["BTCUSDT"],
            duration_seconds=0.0,
            pipeline_name="test",
            output_path="/tmp/test.duckdb",
        )
        assert result.records_per_second == 0.0


class TestStreamParams:
    """Tests for StreamParams model."""

    def test_valid_params(self):
        """Test creating valid stream parameters."""
        params = StreamParams(
            symbols=["BTCUSDT", "ETHUSDT"],
            max_batches=10,
            buffer_size=100,
            destination="duckdb",
        )
        assert params.symbols == ["BTCUSDT", "ETHUSDT"]
        assert params.max_batches == 10
        assert params.buffer_size == 100

    def test_symbols_uppercased(self):
        """Test symbols are uppercased."""
        params = StreamParams(
            symbols=["btcusdt"],
            destination="duckdb",
        )
        assert params.symbols == ["BTCUSDT"]

    def test_empty_symbols_raises_error(self):
        """Test empty symbols list raises error."""
        with pytest.raises(ValidationError):
            StreamParams(symbols=[], destination="duckdb")

    def test_buffer_size_validation(self):
        """Test buffer_size must be >= 10."""
        with pytest.raises(ValidationError):
            StreamParams(symbols=["BTCUSDT"], buffer_size=5)

        params = StreamParams(symbols=["BTCUSDT"], buffer_size=100)
        assert params.buffer_size == 100

    def test_max_batches_validation(self):
        """Test max_batches must be >= 1 if provided."""
        with pytest.raises(ValidationError):
            StreamParams(symbols=["BTCUSDT"], max_batches=0)

        params = StreamParams(symbols=["BTCUSDT"], max_batches=None)
        assert params.max_batches is None

    def test_continuous_mode_check(self):
        """Test determining continuous vs limited mode."""
        # Continuous mode (no max_batches)
        params = StreamParams(symbols=["BTCUSDT"])
        assert params.max_batches is None

        # Limited mode (with max_batches)
        params = StreamParams(symbols=["BTCUSDT"], max_batches=10)
        assert params.max_batches == 10


class TestStreamResult:
    """Tests for StreamResult model."""

    def test_successful_result(self):
        """Test creating a successful stream result."""
        result = StreamResult(
            success=True,
            batches_processed=10,
            records_count=5000,
            duration_seconds=120.0,
            pipeline_name="binance_realtime",
            output_path="/tmp/test.duckdb",
        )
        assert result.success is True
        assert result.batches_processed == 10
        assert result.records_count == 5000

    def test_failed_result(self):
        """Test creating a failed stream result."""
        result = StreamResult(
            success=False,
            batches_processed=2,
            duration_seconds=15.0,
            pipeline_name="binance_realtime",
            output_path="",
            error="WebSocket connection lost",
        )
        assert result.success is False
        assert result.error == "WebSocket connection lost"


class TestValidateParams:
    """Tests for ValidateParams model."""

    def test_valid_params(self):
        """Test creating valid validate parameters."""
        params = ValidateParams(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            symbol="BTCUSDT",
        )
        assert params.start_date == date(2024, 1, 1)
        assert params.end_date == date(2024, 1, 31)
        assert params.symbol == "BTCUSDT"

    def test_all_optional(self):
        """Test all parameters are optional."""
        params = ValidateParams()
        assert params.start_date is None
        assert params.end_date is None
        assert params.symbol is None

    def test_symbol_uppercased(self):
        """Test symbol is uppercased."""
        params = ValidateParams(symbol="btcusdt")
        assert params.symbol == "BTCUSDT"


class TestValidationResult:
    """Tests for ValidationResult model."""

    def test_successful_validation_no_issues(self):
        """Test successful validation with no issues."""
        result = ValidationResult(
            success=True,
            symbols_checked=["BTCUSDT", "ETHUSDT"],
            total_records=200000,
            duplicate_count=0,
            gap_count=0,
            quality_score=100.0,
            duration_seconds=5.0,
        )
        assert result.success is True
        assert result.has_issues is False
        assert result.quality_score == 100.0

    def test_validation_with_issues(self):
        """Test validation with issues found."""
        result = ValidationResult(
            success=True,
            symbols_checked=["BTCUSDT"],
            total_records=100000,
            duplicate_count=150,
            gap_count=2,
            quality_score=95.5,
            duration_seconds=3.0,
            issues=[
                {"type": "duplicates", "symbol": "BTCUSDT", "message": "150 duplicates found"},
                {"type": "gap", "symbol": "BTCUSDT", "message": "Gap of 2.5 hours"},
            ],
        )
        assert result.success is True
        assert result.has_issues is True
        assert result.duplicate_count == 150
        assert result.gap_count == 2
        assert len(result.issues) == 2

    def test_failed_validation(self):
        """Test failed validation."""
        result = ValidationResult(
            success=False,
            symbols_checked=[],
            total_records=0,
            duplicate_count=0,
            gap_count=0,
            quality_score=0.0,
            duration_seconds=0.5,
            issues=[{"type": "error", "message": "Database not found"}],
        )
        assert result.success is False
        assert len(result.issues) == 1

    def test_has_issues_property(self):
        """Test has_issues computed property."""
        # No issues
        result = ValidationResult(
            success=True,
            symbols_checked=["BTCUSDT"],
            total_records=100000,
            duplicate_count=0,
            gap_count=0,
            anomaly_count=0,
            quality_score=100.0,
            duration_seconds=3.0,
        )
        assert result.has_issues is False

        # Has issues (duplicate_count > 0)
        result = ValidationResult(
            success=True,
            symbols_checked=["BTCUSDT"],
            total_records=100000,
            duplicate_count=5,
            gap_count=0,
            anomaly_count=0,
            quality_score=99.0,
            duration_seconds=3.0,
        )
        assert result.has_issues is True

        # Has issues (gap_count > 0)
        result = ValidationResult(
            success=True,
            symbols_checked=["BTCUSDT"],
            total_records=100000,
            duplicate_count=0,
            gap_count=1,
            anomaly_count=0,
            quality_score=98.0,
            duration_seconds=3.0,
        )
        assert result.has_issues is True

        # Has issues (anomaly_count > 0)
        result = ValidationResult(
            success=True,
            symbols_checked=["BTCUSDT"],
            total_records=100000,
            duplicate_count=0,
            gap_count=0,
            anomaly_count=2,
            quality_score=95.0,
            duration_seconds=3.0,
        )
        assert result.has_issues is True


class TestDataSummary:
    """Tests for DataSummary model."""

    def test_valid_summary(self):
        """Test creating valid data summary."""
        summary = DataSummary(
            symbol="BTCUSDT",
            record_count=100000,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            size_bytes=10485760,
        )
        assert summary.symbol == "BTCUSDT"
        assert summary.record_count == 100000
        assert summary.size_bytes == 10485760

    def test_size_mb_property(self):
        """Test size_mb computed property."""
        summary = DataSummary(
            symbol="BTCUSDT",
            record_count=100000,
            size_bytes=10485760,  # 10 MB
        )
        assert summary.size_mb == 10.0

    def test_days_of_data_property(self):
        """Test days_of_data computed property."""
        summary = DataSummary(
            symbol="BTCUSDT",
            record_count=100000,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            size_bytes=10485760,
        )
        # Inclusive: Jan 1 to Jan 31 = 31 days
        assert summary.days_of_data == 31

    def test_days_of_data_with_none_dates(self):
        """Test days_of_data returns 0 when dates are None."""
        summary = DataSummary(
            symbol="BTCUSDT",
            record_count=100000,
            size_bytes=10485760,
        )
        assert summary.days_of_data == 0
