"""Test that all required packages and library components can be imported."""

import pytest


def test_dlt_import():
    """Test that dlt can be imported."""
    import dlt
    assert dlt is not None


def test_duckdb_import():
    """Test that duckdb can be imported."""
    import duckdb
    assert duckdb is not None


def test_binance_client_import():
    """Test that binance client can be imported."""
    from binance.client import Client
    assert Client is not None


def test_binance_async_client_import():
    """Test that binance async client can be imported."""
    from binance import AsyncClient
    assert AsyncClient is not None


def test_websockets_import():
    """Test that websockets can be imported."""
    import websockets
    assert websockets is not None


def test_pydantic_import():
    """Test that pydantic can be imported."""
    import pydantic
    assert pydantic is not None


def test_library_main_import():
    """Test that main library can be imported."""
    import binance_tick_data
    assert binance_tick_data is not None


def test_library_sources_import():
    """Test that library sources can be imported."""
    from binance_tick_data.sources import binance_rest_api, binance_websocket
    assert binance_rest_api is not None
    assert binance_websocket is not None


def test_library_consumers_import():
    """Test that library consumers can be imported."""
    from binance_tick_data.consumers import RealtimeConsumer, ConsumerConfig
    assert RealtimeConsumer is not None
    assert ConsumerConfig is not None


def test_library_analyzers_import():
    """Test that library analyzers can be imported."""
    from binance_tick_data.analyzers import (
        OrderFlowAnalyzer,
        LiquidityAnalyzer,
        VolumeProfileAnalyzer,
    )
    assert OrderFlowAnalyzer is not None
    assert LiquidityAnalyzer is not None
    assert VolumeProfileAnalyzer is not None


def test_library_streaming_import():
    """Test that streaming components can be imported."""
    from binance_tick_data.streaming import RingBuffer, MetricsAggregator
    assert RingBuffer is not None
    assert MetricsAggregator is not None


def test_dollar_volume_sampling_import():
    """Test that dollar volume sampling can be imported."""
    from binance_tick_data import (
        DollarVolumeSampler,
        create_dollar_volume_bars,
        calculate_optimal_threshold,
    )
    assert DollarVolumeSampler is not None
    assert create_dollar_volume_bars is not None
    assert calculate_optimal_threshold is not None
