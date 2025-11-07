"""Tests for stream business logic."""

import pytest
from unittest.mock import Mock, MagicMock, patch
import time

from binance_tick_data.cli.stream import (
    execute_stream,
    request_shutdown,
    reset_shutdown_flag,
    shutdown_requested,
)
from binance_tick_data.cli.models import StreamParams, StreamResult


class TestExecuteStream:
    """Tests for execute_stream function."""

    def setup_method(self):
        """Reset shutdown flag before each test."""
        reset_shutdown_flag()

    def test_successful_stream_with_limited_batches(self, sample_stream_params, mock_pipeline):
        """Test successful stream with max_batches limit."""

        def mock_config_factory(params):
            config = Mock()
            config.symbols = params.symbols
            config.stream_buffer_size = params.buffer_size
            return config

        def mock_pipeline_factory(config):
            return mock_pipeline

        result = execute_stream(
            sample_stream_params,
            config_factory=mock_config_factory,
            pipeline_factory=mock_pipeline_factory,
            setup_signal_handlers=False,
        )

        # Verify result
        assert isinstance(result, StreamResult)
        assert result.success is True
        assert result.batches_processed == 10  # max_batches from fixture
        assert result.records_count >= 0
        assert result.duration_seconds > 0
        assert result.error is None

    def test_stream_continuous_mode_with_shutdown(self, mock_pipeline):
        """Test continuous streaming that stops on shutdown signal."""
        params = StreamParams(
            symbols=["BTCUSDT"],
            max_batches=None,  # Continuous mode
            buffer_size=100,
        )

        def mock_config_factory(params):
            config = Mock()
            config.symbols = params.symbols
            config.stream_buffer_size = params.buffer_size
            return config

        batch_count = 0

        def mock_pipeline_factory(config):
            nonlocal batch_count
            pipeline = MagicMock()

            def mock_run_side_effect(source):
                nonlocal batch_count
                batch_count += 1
                # Request shutdown after 3 batches
                if batch_count >= 3:
                    request_shutdown()
                # Simulate some processing time
                time.sleep(0.01)
                return Mock(loads_ids=["load_123"])

            pipeline.run.side_effect = mock_run_side_effect
            return pipeline

        result = execute_stream(
            params,
            config_factory=mock_config_factory,
            pipeline_factory=mock_pipeline_factory,
            setup_signal_handlers=False,
        )

        # Should have stopped after shutdown request
        assert result.success is True
        assert result.batches_processed == 3
        assert not shutdown_requested()  # Should be reset after execution

    def test_stream_handles_pipeline_exception(self, sample_stream_params):
        """Test that stream handles pipeline exceptions gracefully."""

        def mock_config_factory(params):
            config = Mock()
            config.symbols = params.symbols
            return config

        def failing_pipeline_factory(config):
            pipeline = MagicMock()
            pipeline.run.side_effect = RuntimeError("WebSocket connection failed")
            return pipeline

        result = execute_stream(
            sample_stream_params,
            config_factory=mock_config_factory,
            pipeline_factory=failing_pipeline_factory,
            setup_signal_handlers=False,
        )

        # Should return failed result, not raise exception
        assert result.success is False
        assert "WebSocket connection failed" in result.error
        assert result.batches_processed >= 0

    def test_stream_handles_config_exception(self, sample_stream_params):
        """Test that stream handles config creation exceptions."""

        def failing_config_factory(params):
            raise ValueError("Invalid stream configuration")

        result = execute_stream(
            sample_stream_params,
            config_factory=failing_config_factory,
            setup_signal_handlers=False,
        )

        assert result.success is False
        assert "Invalid stream configuration" in result.error

    def test_stream_measures_duration(self, sample_stream_params, mock_pipeline):
        """Test that stream accurately measures execution duration."""

        def mock_config_factory(params):
            config = Mock()
            config.symbols = params.symbols
            return config

        def mock_pipeline_factory(config):
            # Add artificial delay
            time.sleep(0.05)
            return mock_pipeline

        result = execute_stream(
            sample_stream_params,
            config_factory=mock_config_factory,
            pipeline_factory=mock_pipeline_factory,
            setup_signal_handlers=False,
        )

        # Should have measured duration >= 0.05 seconds
        assert result.duration_seconds >= 0.05

    def test_stream_with_multiple_symbols(self, mock_pipeline):
        """Test stream with multiple symbols."""
        params = StreamParams(
            symbols=["BTCUSDT", "ETHUSDT", "BNBUSDT"],
            max_batches=5,
            buffer_size=200,
        )

        def mock_config_factory(params):
            config = Mock()
            config.symbols = params.symbols
            config.stream_buffer_size = params.buffer_size
            return config

        def mock_pipeline_factory(config):
            return mock_pipeline

        result = execute_stream(
            params,
            config_factory=mock_config_factory,
            pipeline_factory=mock_pipeline_factory,
            setup_signal_handlers=False,
        )

        assert result.success is True
        assert result.batches_processed == 5

    def test_stream_respects_buffer_size(self, mock_pipeline):
        """Test that stream respects buffer_size parameter."""
        params = StreamParams(
            symbols=["BTCUSDT"],
            max_batches=3,
            buffer_size=500,
        )

        def mock_config_factory(params):
            config = Mock()
            config.symbols = params.symbols
            config.stream_buffer_size = params.buffer_size
            return config

        def mock_pipeline_factory(config):
            # Verify buffer size is passed through
            assert config.stream_buffer_size == 500
            return mock_pipeline

        result = execute_stream(
            params,
            config_factory=mock_config_factory,
            pipeline_factory=mock_pipeline_factory,
            setup_signal_handlers=False,
        )

        assert result.success is True

    def test_stream_result_includes_metadata(self, sample_stream_params, mock_pipeline):
        """Test that result includes metadata about the stream."""

        def mock_config_factory(params):
            config = Mock()
            config.symbols = params.symbols
            return config

        def mock_pipeline_factory(config):
            return mock_pipeline

        result = execute_stream(
            sample_stream_params,
            config_factory=mock_config_factory,
            pipeline_factory=mock_pipeline_factory,
            setup_signal_handlers=False,
        )

        # Check metadata
        assert result.pipeline_name == "binance_realtime"
        assert isinstance(result.metadata, dict)

    def test_stream_with_warnings(self, sample_stream_params, mock_pipeline):
        """Test that stream can return warnings."""

        def mock_config_factory(params):
            config = Mock()
            config.symbols = params.symbols
            return config

        def mock_pipeline_factory(config):
            return mock_pipeline

        result = execute_stream(
            sample_stream_params,
            config_factory=mock_config_factory,
            pipeline_factory=mock_pipeline_factory,
            setup_signal_handlers=False,
        )

        assert result.success is True
        # Warnings list should exist (may be empty)
        assert isinstance(result.warnings, list)


class TestShutdownSignaling:
    """Tests for shutdown signaling mechanism."""

    def setup_method(self):
        """Reset shutdown flag before each test."""
        reset_shutdown_flag()

    def test_shutdown_flag_starts_false(self):
        """Test that shutdown flag starts as False."""
        assert shutdown_requested() is False

    def test_request_shutdown_sets_flag(self):
        """Test that request_shutdown sets the flag to True."""
        request_shutdown()
        assert shutdown_requested() is True

    def test_reset_shutdown_flag_clears_flag(self):
        """Test that reset_shutdown_flag clears the flag."""
        request_shutdown()
        assert shutdown_requested() is True

        reset_shutdown_flag()
        assert shutdown_requested() is False

    def test_multiple_shutdown_requests(self):
        """Test that multiple shutdown requests are idempotent."""
        request_shutdown()
        request_shutdown()
        request_shutdown()

        assert shutdown_requested() is True

        reset_shutdown_flag()
        assert shutdown_requested() is False

    def test_shutdown_stops_continuous_stream(self, mock_pipeline):
        """Integration test: shutdown signal stops continuous streaming."""
        params = StreamParams(
            symbols=["BTCUSDT"],
            max_batches=None,  # Continuous
        )

        batches = 0

        def mock_config_factory(params):
            config = Mock()
            config.symbols = params.symbols
            return config

        def mock_pipeline_factory(config):
            nonlocal batches
            pipeline = MagicMock()

            def run_side_effect(source):
                nonlocal batches
                batches += 1
                if batches >= 5:
                    request_shutdown()
                time.sleep(0.01)
                return Mock(loads_ids=[f"load_{batches}"])

            pipeline.run.side_effect = run_side_effect
            return pipeline

        result = execute_stream(
            params,
            config_factory=mock_config_factory,
            pipeline_factory=mock_pipeline_factory,
            setup_signal_handlers=False,
        )

        # Should stop at 5 batches
        assert result.batches_processed == 5
        assert result.success is True
