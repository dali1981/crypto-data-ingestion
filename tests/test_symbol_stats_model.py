"""
Test SymbolStats Pydantic model.

Tests the SymbolStats model display methods, computed fields,
and integration with the repository.
"""

import pytest
from datetime import datetime
from binance_tick_data.models import SymbolStats


def test_symbol_stats_creation():
    """Test creating a SymbolStats object."""
    stats = SymbolStats(
        symbol="BTCUSDT",
        trade_count=1000,
        min_price=50000.0,
        max_price=51000.0,
        avg_price=50500.0,
        total_volume=100.5,
        sell_count=600,
        buy_count=400,
        buy_sell_ratio=0.6667,
        first_trade_time=datetime(2021, 1, 1, 0, 0, 0),
        last_trade_time=datetime(2021, 1, 1, 23, 59, 59),
    )

    assert stats.symbol == "BTCUSDT"
    assert stats.trade_count == 1000
    assert stats.min_price == 50000.0
    assert stats.max_price == 51000.0


def test_computed_fields():
    """Test computed fields calculate correctly."""
    stats = SymbolStats(
        symbol="BTCUSDT",
        trade_count=1000,
        min_price=50000.0,
        max_price=51000.0,
        avg_price=50500.0,
        total_volume=100.5,
        sell_count=600,
        buy_count=400,
    )

    # Test price_range
    assert stats.price_range == 1000.0

    # Test price_change_pct
    assert stats.price_change_pct == pytest.approx(2.0)  # (51000-50000)/50000 * 100

    # Test net_order_flow
    assert stats.net_order_flow == -200  # 400 - 600

    # Test order_imbalance
    assert stats.order_imbalance == pytest.approx(-0.2)  # (400-600)/1000


def test_str_method():
    """Test __str__ returns formatted output."""
    stats = SymbolStats(
        symbol="BTCUSDT",
        trade_count=1000,
        min_price=50000.0,
        max_price=51000.0,
        avg_price=50500.0,
        total_volume=100.5,
        sell_count=600,
        buy_count=400,
        buy_sell_ratio=0.6667,
    )

    output = str(stats)
    assert "Symbol Statistics: BTCUSDT" in output
    assert "Total trades: 1,000" in output
    assert "$50,000.00" in output
    assert "$51,000.00" in output


def test_repr_method():
    """Test __repr__ returns developer-friendly output."""
    stats = SymbolStats(
        symbol="BTCUSDT",
        trade_count=1000,
        min_price=50000.0,
        max_price=51000.0,
    )

    output = repr(stats)
    assert "SymbolStats" in output
    assert "BTCUSDT" in output
    assert "trades=1,000" in output


def test_repr_html_method():
    """Test _repr_html_ returns HTML table."""
    stats = SymbolStats(
        symbol="BTCUSDT",
        trade_count=1000,
        min_price=50000.0,
        max_price=51000.0,
        avg_price=50500.0,
        total_volume=100.5,
        sell_count=600,
        buy_count=400,
    )

    html = stats._repr_html_()
    assert "<table" in html
    assert "BTCUSDT" in html
    assert "Trading Activity" in html
    assert "Price Statistics" in html


def test_from_dict():
    """Test creating SymbolStats from dictionary."""
    data = {
        "symbol": "BTCUSDT",
        "trade_count": 1000,
        "min_price": 50000.0,
        "max_price": 51000.0,
        "avg_price": 50500.0,
        "total_volume": 100.5,
        "sell_count": 600,
        "buy_count": 400,
        "buy_sell_ratio": 0.6667,
    }

    stats = SymbolStats.from_dict(data)
    assert stats.symbol == "BTCUSDT"
    assert stats.trade_count == 1000


def test_to_dict():
    """Test converting SymbolStats to dictionary."""
    stats = SymbolStats(
        symbol="BTCUSDT",
        trade_count=1000,
        min_price=50000.0,
        max_price=51000.0,
        avg_price=50500.0,
        total_volume=100.5,
        sell_count=600,
        buy_count=400,
        buy_sell_ratio=0.6667,
    )

    data = stats.to_dict()
    assert data["symbol"] == "BTCUSDT"
    assert data["trade_count"] == 1000
    assert data["price_range"] == 1000.0  # Computed field
    assert "net_order_flow" in data  # Computed field


def test_null_handling():
    """Test SymbolStats handles NULL/None values gracefully."""
    stats = SymbolStats(
        symbol="BTCUSDT",
        trade_count=0,
        min_price=None,
        max_price=None,
        avg_price=None,
        total_volume=None,
        sell_count=0,
        buy_count=0,
        buy_sell_ratio=None,
    )

    # Should not raise errors
    assert stats.price_range is None
    assert stats.price_change_pct is None
    assert stats.net_order_flow == 0
    assert stats.order_imbalance is None

    # Should display without errors
    str(stats)
    repr(stats)
    stats._repr_html_()


def test_zero_division_handling():
    """Test SymbolStats handles zero counts correctly."""
    # All sells, no buys
    stats = SymbolStats(
        symbol="BTCUSDT",
        trade_count=100,
        min_price=50000.0,
        max_price=50100.0,
        sell_count=100,
        buy_count=0,
    )

    assert stats.net_order_flow == -100
    assert stats.order_imbalance == -1.0  # (0-100)/100

    # All buys, no sells
    stats2 = SymbolStats(
        symbol="BTCUSDT",
        trade_count=100,
        min_price=50000.0,
        max_price=50100.0,
        sell_count=0,
        buy_count=100,
    )

    assert stats2.net_order_flow == 100
    assert stats2.order_imbalance == 1.0  # (100-0)/100
