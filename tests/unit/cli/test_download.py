"""Tests for download business logic."""

import pytest
from datetime import date
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import time

from binance_tick_data.cli.download import execute_download
from binance_tick_data.cli.models import DownloadParams, DownloadResult


class TestExecuteDownload:
    """Tests for execute_download function."""

    def test_successful_download_with_mock_pipeline(self, sample_download_params, mock_pipeline):
        """Test successful download with injected mock pipeline."""

        def mock_pipeline_factory(config):
            return mock_pipeline

        def mock_config_factory(params):
            config = Mock()
            config.symbols = params.symbols
            config.database.db_path = Path("/tmp/test.duckdb")
            return config

        result = execute_download(
            sample_download_params,
            config_factory=mock_config_factory,
            pipeline_factory=mock_pipeline_factory,
        )

        # Verify result
        assert isinstance(result, DownloadResult)
        assert result.success is True
        assert result.records_count > 0
        assert result.duration_seconds > 0
        assert result.symbols_processed == ["BTCUSDT"]
        assert result.error is None
        assert result.pipeline_name == "binance_historical"

        # Verify pipeline was called
        mock_pipeline.run.assert_called_once()

    def test_download_with_multiple_symbols(self, mock_pipeline):
        """Test download with multiple symbols."""
        params = DownloadParams(
            symbols=["BTCUSDT", "ETHUSDT", "BNBUSDT"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 2),
        )

        def mock_pipeline_factory(config):
            return mock_pipeline

        def mock_config_factory(params):
            config = Mock()
            config.symbols = params.symbols
            config.database.db_path = Path("/tmp/test.duckdb")
            return config

        result = execute_download(
            params,
            config_factory=mock_config_factory,
            pipeline_factory=mock_pipeline_factory,
        )

        assert result.success is True
        assert result.symbols_processed == ["BTCUSDT", "ETHUSDT", "BNBUSDT"]

    def test_download_with_max_records_limit(self, mock_pipeline):
        """Test download with max_records limit."""
        params = DownloadParams(
            symbols=["BTCUSDT"],
            start_date=date(2024, 1, 1),
            max_records=10000,
        )

        def mock_config_factory(params):
            config = Mock()
            config.symbols = params.symbols
            config.historical_max_records = params.max_records
            config.database.db_path = Path("/tmp/test.duckdb")
            return config

        def mock_pipeline_factory(config):
            # Verify config has max_records set
            assert config.historical_max_records == 10000
            return mock_pipeline

        result = execute_download(
            params,
            config_factory=mock_config_factory,
            pipeline_factory=mock_pipeline_factory,
        )

        assert result.success is True

    def test_download_handles_pipeline_exception(self, sample_download_params):
        """Test that download handles pipeline exceptions gracefully."""

        def mock_config_factory(params):
            config = Mock()
            config.symbols = params.symbols
            config.database.db_path = Path("/tmp/test.duckdb")
            return config

        def failing_pipeline_factory(config):
            pipeline = MagicMock()
            pipeline.run.side_effect = RuntimeError("API rate limit exceeded")
            return pipeline

        result = execute_download(
            sample_download_params,
            config_factory=mock_config_factory,
            pipeline_factory=failing_pipeline_factory,
        )

        # Should return failed result, not raise exception
        assert result.success is False
        assert "API rate limit exceeded" in result.error
        assert result.records_count == 0
        assert result.duration_seconds > 0

    def test_download_handles_config_exception(self, sample_download_params):
        """Test that download handles config creation exceptions."""

        def failing_config_factory(params):
            raise ValueError("Invalid configuration")

        result = execute_download(
            sample_download_params,
            config_factory=failing_config_factory,
        )

        assert result.success is False
        assert "Invalid configuration" in result.error

    def test_download_measures_duration(self, sample_download_params, mock_pipeline):
        """Test that download accurately measures execution duration."""

        def mock_pipeline_factory(config):
            # Add artificial delay
            time.sleep(0.1)
            return mock_pipeline

        def mock_config_factory(params):
            config = Mock()
            config.symbols = params.symbols
            config.database.db_path = Path("/tmp/test.duckdb")
            return config

        result = execute_download(
            sample_download_params,
            config_factory=mock_config_factory,
            pipeline_factory=mock_pipeline_factory,
        )

        # Should have measured duration >= 0.1 seconds
        assert result.duration_seconds >= 0.1

    def test_download_uses_default_factories_when_none_provided(self, sample_download_params):
        """Test that download can use default factories."""
        # This test would call real factories - skip in unit tests
        # Just verify it doesn't crash with None factories
        with patch("binance_tick_data.cli.download.BinanceConfig") as mock_config_class:
            with patch("binance_tick_data.cli.download.dlt") as mock_dlt:
                mock_config = Mock()
                mock_config.database.db_path = Path("/tmp/test.duckdb")
                mock_config_class.from_params.return_value = mock_config

                mock_pipeline = MagicMock()
                mock_dlt.pipeline.return_value = mock_pipeline

                # Provide None factories - should use defaults
                result = execute_download(
                    sample_download_params,
                    config_factory=None,
                    pipeline_factory=None,
                )

                # Verify defaults were used
                mock_config_class.from_params.assert_called_once()
                mock_dlt.pipeline.assert_called_once()

    def test_download_result_includes_metadata(self, sample_download_params, mock_pipeline):
        """Test that result includes metadata about the download."""

        def mock_config_factory(params):
            config = Mock()
            config.symbols = params.symbols
            config.database.db_path = Path("/tmp/test.duckdb")
            return config

        def mock_pipeline_factory(config):
            return mock_pipeline

        result = execute_download(
            sample_download_params,
            config_factory=mock_config_factory,
            pipeline_factory=mock_pipeline_factory,
        )

        # Check metadata
        assert result.pipeline_name == "binance_historical"
        assert "/tmp/test.duckdb" in result.output_path
        assert isinstance(result.metadata, dict)

    def test_download_with_warnings(self, sample_download_params, mock_pipeline):
        """Test that download can return warnings."""

        def mock_config_factory(params):
            config = Mock()
            config.symbols = params.symbols
            config.database.db_path = Path("/tmp/test.duckdb")
            return config

        def mock_pipeline_factory(config):
            # Simulate a partial success with warnings
            pipeline = MagicMock()
            load_info = Mock()
            load_info.loads_ids = ["load_123"]
            load_info.has_failed_jobs = False
            pipeline.run.return_value = load_info
            return pipeline

        result = execute_download(
            sample_download_params,
            config_factory=mock_config_factory,
            pipeline_factory=mock_pipeline_factory,
        )

        assert result.success is True
        # Warnings list should exist (may be empty)
        assert isinstance(result.warnings, list)

    def test_download_with_custom_batch_size(self, mock_pipeline):
        """Test download respects custom batch_size parameter."""
        params = DownloadParams(
            symbols=["BTCUSDT"],
            start_date=date(2024, 1, 1),
            batch_size=5000,
        )

        def mock_config_factory(params):
            config = Mock()
            config.symbols = params.symbols
            config.historical_batch_size = params.batch_size
            config.database.db_path = Path("/tmp/test.duckdb")
            return config

        def mock_pipeline_factory(config):
            # Verify batch size is passed through
            assert config.historical_batch_size == 5000
            return mock_pipeline

        result = execute_download(
            params,
            config_factory=mock_config_factory,
            pipeline_factory=mock_pipeline_factory,
        )

        assert result.success is True

    def test_download_with_date_range(self, mock_pipeline):
        """Test download with specific date range."""
        params = DownloadParams(
            symbols=["BTCUSDT"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 15),
        )

        def mock_config_factory(params):
            config = Mock()
            config.symbols = params.symbols
            config.historical_start_date = str(params.start_date)
            config.historical_end_date = str(params.end_date)
            config.database.db_path = Path("/tmp/test.duckdb")
            return config

        def mock_pipeline_factory(config):
            # Verify date range is set
            assert config.historical_start_date == "2024-01-01"
            assert config.historical_end_date == "2024-01-15"
            return mock_pipeline

        result = execute_download(
            params,
            config_factory=mock_config_factory,
            pipeline_factory=mock_pipeline_factory,
        )

        assert result.success is True

    def test_download_with_failed_pipeline_jobs(self, sample_download_params):
        """Test download when pipeline has failed jobs."""

        def mock_config_factory(params):
            config = Mock()
            config.symbols = params.symbols
            config.database.db_path = Path("/tmp/test.duckdb")
            return config

        def mock_pipeline_factory(config):
            pipeline = MagicMock()
            load_info = Mock()
            load_info.loads_ids = []
            load_info.has_failed_jobs = True
            pipeline.run.return_value = load_info
            return pipeline

        result = execute_download(
            sample_download_params,
            config_factory=mock_config_factory,
            pipeline_factory=mock_pipeline_factory,
        )

        # Should report as failed or with warnings
        if not result.success:
            assert result.error is not None
        else:
            assert len(result.warnings) > 0
