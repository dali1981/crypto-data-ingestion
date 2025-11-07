"""Shared fixtures for CLI tests."""

import pytest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import Mock, MagicMock
from typing import Any, Dict

from binance_tick_data.cli.models import (
    DownloadParams,
    StreamParams,
    ValidateParams,
    DataSummary,
)


@pytest.fixture
def sample_download_params():
    """Fixture providing valid download parameters."""
    return DownloadParams(
        symbols=["BTCUSDT"],
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31),
        batch_size=1000,
        destination="duckdb",
    )


@pytest.fixture
def large_download_params():
    """Fixture providing parameters for a large download (>30 days)."""
    return DownloadParams(
        symbols=["BTCUSDT", "ETHUSDT"],
        start_date=date(2024, 1, 1),
        end_date=date(2024, 3, 15),  # 74 days
        batch_size=1000,
        destination="duckdb",
    )


@pytest.fixture
def sample_stream_params():
    """Fixture providing valid stream parameters."""
    return StreamParams(
        symbols=["BTCUSDT", "ETHUSDT"],
        max_batches=10,
        buffer_size=100,
        destination="duckdb",
    )


@pytest.fixture
def sample_validate_params():
    """Fixture providing valid validate parameters."""
    return ValidateParams(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31),
        symbol="BTCUSDT",
    )


@pytest.fixture
def sample_data_summary():
    """Fixture providing a sample data summary."""
    return DataSummary(
        symbol="BTCUSDT",
        record_count=100000,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31),
        size_bytes=10485760,  # 10 MB
    )


@pytest.fixture
def mock_pipeline():
    """Fixture providing a mock dlt pipeline."""
    pipeline = MagicMock()
    pipeline.pipeline_name = "test_pipeline"

    # Mock successful load_info
    load_info = Mock()
    load_info.loads_ids = ["load_123"]
    load_info.has_failed_jobs = False
    pipeline.run.return_value = load_info

    return pipeline


@pytest.fixture
def mock_config():
    """Fixture providing a mock BinanceConfig."""
    config = Mock()
    config.symbols = ["BTCUSDT"]
    config.historical_start_date = "2024-01-01"
    config.historical_end_date = "2024-01-31"
    config.historical_max_records = None
    config.historical_batch_size = 1000
    config.database.db_path = Path("/tmp/test.duckdb")
    config.database.schema_name = "test_schema"
    return config


@pytest.fixture
def mock_duckdb_connection(tmp_path):
    """Fixture providing a mock DuckDB connection."""
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = []
    conn.execute.return_value.fetchone.return_value = None
    conn.close.return_value = None
    return conn


@pytest.fixture
def temp_db_path(tmp_path):
    """Fixture providing a temporary database path."""
    return tmp_path / "test_binance.duckdb"
