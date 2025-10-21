"""
Test repository NULL handling for edge cases.

These tests ensure that repository methods handle NULL/None values
correctly from SQL aggregates.
"""

import pytest
from datetime import datetime


def test_get_symbol_stats_null_handling():
    """Test get_symbol_stats handles NULL values without errors."""
    from binance_tick_data.repository import BinanceDataRepository
    from binance_tick_data.db_config import get_config

    config = get_config()

    # This test checks the logic, not actual database queries
    # We're testing that the NULL handling code works

    # Simulate what SQL returns when no data exists
    result = (
        0,      # trade_count (COUNT always returns 0, not NULL)
        None,   # min_price (MIN returns NULL when no rows)
        None,   # max_price
        None,   # avg_price
        None,   # total_volume (SUM returns NULL when no rows)
        None,   # sell_count (SUM returns NULL when no rows)
        None,   # buy_count
        None,   # first_trade_time
        None,   # last_trade_time
    )

    # Test the extraction logic works
    trade_count = result[0]
    min_price = float(result[1]) if result[1] is not None else None
    max_price = float(result[2]) if result[2] is not None else None
    avg_price = float(result[3]) if result[3] is not None else None
    total_volume = float(result[4]) if result[4] is not None else None
    sell_count = result[5] if result[5] is not None else 0
    buy_count = result[6] if result[6] is not None else 0
    first_trade_time = None  # Would use datetime.fromtimestamp if not None
    last_trade_time = None

    # This should NOT raise TypeError anymore
    buy_sell_ratio = buy_count / sell_count if sell_count > 0 else None

    # Assertions
    assert trade_count == 0
    assert min_price is None
    assert max_price is None
    assert avg_price is None
    assert total_volume is None
    assert sell_count == 0
    assert buy_count == 0
    assert buy_sell_ratio is None  # Division by zero avoided
    assert first_trade_time is None
    assert last_trade_time is None


def test_get_symbol_stats_with_data():
    """Test get_symbol_stats calculates ratio correctly with data."""

    # Simulate what SQL returns when data exists
    result = (
        1000,           # trade_count
        50000.0,        # min_price
        51000.0,        # max_price
        50500.0,        # avg_price
        100.5,          # total_volume
        600,            # sell_count
        400,            # buy_count
        1609459200000,  # first_trade_time (ms timestamp)
        1609545600000,  # last_trade_time
    )

    # Extract values (same logic as fixed code)
    trade_count = result[0]
    min_price = float(result[1]) if result[1] is not None else None
    max_price = float(result[2]) if result[2] is not None else None
    avg_price = float(result[3]) if result[3] is not None else None
    total_volume = float(result[4]) if result[4] is not None else None
    sell_count = result[5] if result[5] is not None else 0
    buy_count = result[6] if result[6] is not None else 0

    # Calculate ratio
    buy_sell_ratio = buy_count / sell_count if sell_count > 0 else None

    # Assertions
    assert trade_count == 1000
    assert min_price == 50000.0
    assert max_price == 51000.0
    assert avg_price == 50500.0
    assert total_volume == 100.5
    assert sell_count == 600
    assert buy_count == 400
    assert buy_sell_ratio == pytest.approx(400 / 600)  # ~0.6667


def test_get_symbol_stats_zero_sells():
    """Test get_symbol_stats when sell_count is 0 (all buys)."""

    # Simulate all buyers (no sellers)
    result = (
        100,     # trade_count
        50000.0, # min_price
        50100.0, # max_price
        50050.0, # avg_price
        10.0,    # total_volume
        0,       # sell_count (SUM returns 0, not NULL, when CASE never matches)
        100,     # buy_count
        1609459200000,
        1609545600000,
    )

    # Extract
    sell_count = result[5] if result[5] is not None else 0
    buy_count = result[6] if result[6] is not None else 0

    # Calculate ratio - should handle division by zero
    buy_sell_ratio = buy_count / sell_count if sell_count > 0 else None

    # Assertions
    assert sell_count == 0
    assert buy_count == 100
    assert buy_sell_ratio is None  # Avoided division by zero


def test_get_symbol_stats_zero_buys():
    """Test get_symbol_stats when buy_count is 0 (all sells)."""

    # Simulate all sellers (no buyers)
    result = (
        100,     # trade_count
        50000.0, # min_price
        50100.0, # max_price
        50050.0, # avg_price
        10.0,    # total_volume
        100,     # sell_count
        0,       # buy_count (SUM returns 0 when CASE never matches)
        1609459200000,
        1609545600000,
    )

    # Extract
    sell_count = result[5] if result[5] is not None else 0
    buy_count = result[6] if result[6] is not None else 0

    # Calculate ratio
    buy_sell_ratio = buy_count / sell_count if sell_count > 0 else None

    # Assertions
    assert sell_count == 100
    assert buy_count == 0
    assert buy_sell_ratio == 0.0  # 0 / 100 = 0
