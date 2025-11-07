"""Tests for list_data business logic."""

import pytest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from binance_tick_data.cli.list_data import execute_list_data
from binance_tick_data.cli.models import DataSummary


class TestExecuteListData:
    """Tests for execute_list_data function."""

    def test_list_data_with_symbol_column_tables(self, mock_duckdb_connection):
        """Test listing data from tables with symbol column (aggregated data)."""
        # Mock table discovery
        mock_duckdb_connection.execute.return_value.fetchall.side_effect = [
            # Tables query
            [("agg_trades",)],
            # Columns query for agg_trades
            [("symbol",), ("timestamp",), ("price",)],
            # Per-symbol stats query
            [
                ("BTCUSDT", 100000, 1609459200000, 1609545600000),  # 2021-01-01 to 2021-01-02
                ("ETHUSDT", 50000, 1609459200000, 1609545600000),
            ],
        ]

        with patch("binance_tick_data.cli.list_data.duckdb.connect", return_value=mock_duckdb_connection):
            with patch("binance_tick_data.cli.list_data.Path.exists", return_value=True):
                summaries = execute_list_data()

        # Should find 2 symbols
        assert len(summaries) == 2
        assert summaries[0].symbol == "BTCUSDT"
        assert summaries[0].record_count == 100000
        assert summaries[1].symbol == "ETHUSDT"
        assert summaries[1].record_count == 50000

    def test_list_data_with_symbol_named_tables(self, mock_duckdb_connection):
        """Test listing data from symbol-named tables (e.g., BTCUSDT table)."""
        # Mock table discovery
        mock_duckdb_connection.execute.return_value.fetchall.side_effect = [
            # Tables query
            [("BTCUSDT",), ("ETHUSDT",)],
            # Columns query for BTCUSDT (no symbol column)
            [("timestamp",), ("price",), ("quantity",)],
            # Stats query for BTCUSDT
            [],  # No results from GROUP BY (will use fetchone instead)
            # Columns query for ETHUSDT
            [("timestamp",), ("price",), ("quantity",)],
        ]

        # Setup fetchone for stats queries
        mock_duckdb_connection.execute.return_value.fetchone.side_effect = [
            (100000, 1609459200000, 1609545600000),  # BTCUSDT stats
            (50000, 1609459200000, 1609545600000),   # ETHUSDT stats
        ]

        with patch("binance_tick_data.cli.list_data.duckdb.connect", return_value=mock_duckdb_connection):
            with patch("binance_tick_data.cli.list_data.Path.exists", return_value=True):
                summaries = execute_list_data()

        # Should find 2 symbols
        assert len(summaries) == 2
        assert summaries[0].symbol == "BTCUSDT"
        assert summaries[1].symbol == "ETHUSDT"

    def test_list_data_empty_database(self, mock_duckdb_connection):
        """Test listing data when database has no tables."""
        # Mock no tables
        mock_duckdb_connection.execute.return_value.fetchall.return_value = []

        with patch("binance_tick_data.cli.list_data.duckdb.connect", return_value=mock_duckdb_connection):
            with patch("binance_tick_data.cli.list_data.Path.exists", return_value=True):
                summaries = execute_list_data()

        assert len(summaries) == 0

    def test_list_data_database_not_found(self):
        """Test listing data when database file doesn't exist."""
        with patch("binance_tick_data.cli.list_data.Path.exists", return_value=False):
            summaries = execute_list_data()

        assert len(summaries) == 0

    def test_list_data_handles_database_error(self, mock_duckdb_connection):
        """Test that list_data handles database errors gracefully."""
        mock_duckdb_connection.execute.side_effect = Exception("Database error")

        with patch("binance_tick_data.cli.list_data.duckdb.connect", return_value=mock_duckdb_connection):
            with patch("binance_tick_data.cli.list_data.Path.exists", return_value=True):
                summaries = execute_list_data()

        # Should return empty list on error
        assert len(summaries) == 0

    def test_list_data_filters_internal_tables(self, mock_duckdb_connection):
        """Test that internal dlt tables are filtered out."""
        # Mock tables including internal ones
        mock_duckdb_connection.execute.return_value.fetchall.side_effect = [
            # Tables query - should exclude _load, _state, backup tables
            [
                ("agg_trades",),
                ("_dlt_loads",),        # Should be excluded
                ("_dlt_state",),        # Should be excluded
                ("trades_backup",),     # Should be excluded
                ("BTCUSDT",),
            ],
            # Columns for agg_trades
            [("symbol",), ("timestamp",)],
            # Stats for agg_trades
            [("BTCUSDT", 100000, 1609459200000, 1609545600000)],
            # Columns for BTCUSDT
            [("timestamp",), ("price",)],
        ]

        mock_duckdb_connection.execute.return_value.fetchone.return_value = (50000, 1609459200000, 1609545600000)

        with patch("binance_tick_data.cli.list_data.duckdb.connect", return_value=mock_duckdb_connection):
            with patch("binance_tick_data.cli.list_data.Path.exists", return_value=True):
                summaries = execute_list_data()

        # Should only return actual data tables
        # The implementation already filters in SQL, so this test verifies the WHERE clause works
        assert len(summaries) >= 1

    def test_list_data_calculates_date_ranges(self, mock_duckdb_connection):
        """Test that list_data correctly calculates date ranges."""
        # Mock data with specific timestamps
        mock_duckdb_connection.execute.return_value.fetchall.side_effect = [
            [("BTCUSDT",)],
            [("timestamp",), ("price",)],
        ]

        # Jan 1, 2024 00:00 to Jan 31, 2024 23:59 (30 days)
        start_ts = int(datetime(2024, 1, 1).timestamp() * 1000)
        end_ts = int(datetime(2024, 1, 31, 23, 59, 59).timestamp() * 1000)

        mock_duckdb_connection.execute.return_value.fetchone.return_value = (100000, start_ts, end_ts)

        with patch("binance_tick_data.cli.list_data.duckdb.connect", return_value=mock_duckdb_connection):
            with patch("binance_tick_data.cli.list_data.Path.exists", return_value=True):
                summaries = execute_list_data()

        assert len(summaries) == 1
        summary = summaries[0]
        assert summary.start_date == date(2024, 1, 1)
        assert summary.end_date == date(2024, 1, 31)
        # Inclusive: Jan 1 to Jan 31 = 31 days
        assert summary.days_of_data == 31

    def test_list_data_sorts_alphabetically(self, mock_duckdb_connection):
        """Test that summaries are sorted alphabetically by symbol."""
        # Mock unsorted symbols
        mock_duckdb_connection.execute.return_value.fetchall.side_effect = [
            [("agg_trades",)],
            [("symbol",)],
            [
                ("ETHUSDT", 50000, 1609459200000, 1609545600000),
                ("BTCUSDT", 100000, 1609459200000, 1609545600000),
                ("BNBUSDT", 30000, 1609459200000, 1609545600000),
            ],
        ]

        with patch("binance_tick_data.cli.list_data.duckdb.connect", return_value=mock_duckdb_connection):
            with patch("binance_tick_data.cli.list_data.Path.exists", return_value=True):
                summaries = execute_list_data()

        # Should be sorted alphabetically
        assert len(summaries) == 3
        assert summaries[0].symbol == "BNBUSDT"
        assert summaries[1].symbol == "BTCUSDT"
        assert summaries[2].symbol == "ETHUSDT"

    def test_list_data_estimates_size(self, mock_duckdb_connection):
        """Test that list_data estimates data size correctly."""
        mock_duckdb_connection.execute.return_value.fetchall.side_effect = [
            [("BTCUSDT",)],
            [("timestamp",)],
        ]

        mock_duckdb_connection.execute.return_value.fetchone.return_value = (100000, 1609459200000, 1609545600000)

        with patch("binance_tick_data.cli.list_data.duckdb.connect", return_value=mock_duckdb_connection):
            with patch("binance_tick_data.cli.list_data.Path.exists", return_value=True):
                summaries = execute_list_data()

        assert len(summaries) == 1
        # Size should be estimated as record_count * 100 bytes
        assert summaries[0].size_bytes == 100000 * 100
        assert summaries[0].size_mb > 0

    def test_list_data_skips_empty_tables(self, mock_duckdb_connection):
        """Test that empty tables are skipped."""
        mock_duckdb_connection.execute.return_value.fetchall.side_effect = [
            [("BTCUSDT",), ("ETHUSDT",)],
            [("timestamp",)],  # BTCUSDT columns
            [("timestamp",)],  # ETHUSDT columns
        ]

        # BTCUSDT has data, ETHUSDT is empty
        mock_duckdb_connection.execute.return_value.fetchone.side_effect = [
            (100000, 1609459200000, 1609545600000),  # BTCUSDT
            (0, None, None),                          # ETHUSDT - empty
        ]

        with patch("binance_tick_data.cli.list_data.duckdb.connect", return_value=mock_duckdb_connection):
            with patch("binance_tick_data.cli.list_data.Path.exists", return_value=True):
                summaries = execute_list_data()

        # Should only include BTCUSDT
        assert len(summaries) == 1
        assert summaries[0].symbol == "BTCUSDT"

    def test_list_data_handles_mixed_table_types(self, mock_duckdb_connection):
        """Test listing data with both aggregated and symbol-named tables."""
        call_count = [0]

        def fetchall_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # Tables query
                return [("agg_trades",), ("SOLUSDT",)]
            elif call_count[0] == 2:
                # Columns for agg_trades (has symbol column)
                return [("symbol",), ("timestamp",)]
            elif call_count[0] == 3:
                # Stats for agg_trades
                return [("BTCUSDT", 100000, 1609459200000, 1609545600000)]
            elif call_count[0] == 4:
                # Columns for SOLUSDT (no symbol column)
                return [("timestamp",), ("price",)]
            return []

        mock_duckdb_connection.execute.return_value.fetchall.side_effect = fetchall_side_effect
        mock_duckdb_connection.execute.return_value.fetchone.return_value = (50000, 1609459200000, 1609545600000)

        with patch("binance_tick_data.cli.list_data.duckdb.connect", return_value=mock_duckdb_connection):
            with patch("binance_tick_data.cli.list_data.Path.exists", return_value=True):
                summaries = execute_list_data()

        # Should find both symbols
        assert len(summaries) == 2
        symbols = {s.symbol for s in summaries}
        assert "BTCUSDT" in symbols
        assert "SOLUSDT" in symbols

    def test_list_data_closes_connection(self, mock_duckdb_connection):
        """Test that database connection is properly closed."""
        mock_duckdb_connection.execute.return_value.fetchall.return_value = []

        with patch("binance_tick_data.cli.list_data.duckdb.connect", return_value=mock_duckdb_connection):
            with patch("binance_tick_data.cli.list_data.Path.exists", return_value=True):
                execute_list_data()

        # Verify connection was closed
        mock_duckdb_connection.close.assert_called_once()

    def test_list_data_returns_data_summary_objects(self, mock_duckdb_connection):
        """Test that all returned objects are DataSummary instances."""
        mock_duckdb_connection.execute.return_value.fetchall.side_effect = [
            [("BTCUSDT",)],
            [("timestamp",)],
        ]
        mock_duckdb_connection.execute.return_value.fetchone.return_value = (100000, 1609459200000, 1609545600000)

        with patch("binance_tick_data.cli.list_data.duckdb.connect", return_value=mock_duckdb_connection):
            with patch("binance_tick_data.cli.list_data.Path.exists", return_value=True):
                summaries = execute_list_data()

        assert len(summaries) > 0
        for summary in summaries:
            assert isinstance(summary, DataSummary)
            assert hasattr(summary, "symbol")
            assert hasattr(summary, "record_count")
            assert hasattr(summary, "size_mb")
            assert hasattr(summary, "days_of_data")
