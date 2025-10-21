"""
Integration test for SymbolStats with repository.

Tests that the repository returns SymbolStats objects correctly
when querying an actual database.
"""

import pytest
from pathlib import Path
from binance_tick_data.repository import BinanceDataRepository
from binance_tick_data.models import SymbolStats
from binance_tick_data.db_config import get_config


@pytest.fixture
def repo():
    """Create repository instance if database exists."""
    config = get_config()
    db_path = Path(config.database.db_path)

    if not db_path.exists():
        pytest.skip("Database does not exist - skipping integration test")

    repo = BinanceDataRepository(
        db_path=str(db_path),
        dataset_name=config.database.schema_name,
        read_only=True,
    )
    repo.connect()
    yield repo
    repo.close()


def test_get_symbol_stats_returns_symbol_stats_object(repo):
    """Test that get_symbol_stats returns SymbolStats object."""
    # Try to get stats for BTCUSDT (most common symbol in test data)
    try:
        stats = repo.get_symbol_stats("BTCUSDT")

        # Verify it's a SymbolStats object
        assert isinstance(stats, SymbolStats)

        # Verify it has expected attributes
        assert stats.symbol == "BTCUSDT"
        assert isinstance(stats.trade_count, int)

        # Verify computed fields are accessible
        assert hasattr(stats, "price_range")
        assert hasattr(stats, "price_change_pct")
        assert hasattr(stats, "net_order_flow")
        assert hasattr(stats, "order_imbalance")

        # Verify display methods work
        str_output = str(stats)
        assert "Symbol Statistics: BTCUSDT" in str_output

        repr_output = repr(stats)
        assert "SymbolStats" in repr_output

        html_output = stats._repr_html_()
        assert "<table" in html_output

    except Exception as e:
        # If BTCUSDT doesn't exist, skip the test
        if "no data" in str(e).lower():
            pytest.skip("No BTCUSDT data in database")
        else:
            raise


def test_symbol_stats_to_dict_conversion(repo):
    """Test that SymbolStats can be converted to dict for DataFrame."""
    try:
        stats = repo.get_symbol_stats("BTCUSDT")

        # Convert to dict
        stats_dict = stats.to_dict()

        # Verify it's a dict
        assert isinstance(stats_dict, dict)

        # Verify expected keys
        assert "symbol" in stats_dict
        assert "trade_count" in stats_dict

        # Verify computed fields are included
        assert "price_range" in stats_dict
        assert "net_order_flow" in stats_dict

    except Exception as e:
        if "no data" in str(e).lower():
            pytest.skip("No BTCUSDT data in database")
        else:
            raise


def test_symbol_stats_handles_no_data(repo):
    """Test that SymbolStats handles symbols with no data gracefully."""
    # Use a symbol that definitely doesn't exist
    stats = repo.get_symbol_stats("FAKESYMBOL")

    assert isinstance(stats, SymbolStats)
    assert stats.symbol == "FAKESYMBOL"
    assert stats.trade_count == 0

    # Should handle NULL values gracefully
    assert stats.min_price is None
    assert stats.max_price is None
    assert stats.price_range is None

    # Should not raise errors when displaying
    str(stats)
    repr(stats)
    stats._repr_html_()
