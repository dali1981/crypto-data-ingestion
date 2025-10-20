"""
Tests for dollar volume sampling module.

Run with:
    pytest tests/test_dollar_volume_sampling.py -v
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from binance_tick_data import (
    create_dollar_volume_bars,
    DollarVolumeSampler,
    calculate_optimal_threshold,
    DataError,
    InsufficientDataError,
    DataQualityError,
)


@pytest.fixture
def sample_tick_data():
    """Generate sample tick data for testing."""
    np.random.seed(42)
    n = 1000
    start_time = datetime(2024, 1, 1, 9, 0, 0)

    timestamps = [start_time + timedelta(seconds=i) for i in range(n)]
    prices = 45000 * (1 + np.random.randn(n).cumsum() * 0.001)
    volumes = np.random.lognormal(5, 1, n)

    return pd.DataFrame({
        'timestamp': timestamps,
        'price': prices,
        'volume': volumes
    })


@pytest.fixture
def large_tick_data():
    """Generate larger dataset for performance testing."""
    np.random.seed(123)
    n = 10000
    start_time = datetime(2024, 1, 1, 9, 0, 0)

    timestamps = [start_time + timedelta(seconds=i*0.1) for i in range(n)]
    prices = 45000 * (1 + np.random.randn(n).cumsum() * 0.001)
    volumes = np.random.lognormal(5, 1, n)

    return pd.DataFrame({
        'timestamp': timestamps,
        'price': prices,
        'volume': volumes
    })


class TestCreateDollarVolumeBars:
    """Test the create_dollar_volume_bars convenience function."""

    def test_basic_usage_auto_threshold(self, sample_tick_data):
        """Test basic usage with auto-calculated threshold."""
        bars = create_dollar_volume_bars(sample_tick_data, ticks_per_bar=50)

        assert isinstance(bars, pd.DataFrame)
        assert len(bars) > 0
        assert len(bars) == pytest.approx(len(sample_tick_data) / 50, rel=0.2)

    def test_fixed_threshold(self, sample_tick_data):
        """Test with fixed dollar volume threshold."""
        threshold = 1_000_000
        bars = create_dollar_volume_bars(sample_tick_data, threshold=threshold)

        assert len(bars) > 0
        # Most bars should have dollar_volume >= threshold (allowing some tolerance)
        above_threshold = (bars['dollar_volume'] >= threshold * 0.9).sum()
        assert above_threshold >= len(bars) * 0.8  # At least 80% meet threshold

    def test_adaptive_threshold(self, sample_tick_data):
        """Test adaptive threshold mode."""
        bars = create_dollar_volume_bars(
            sample_tick_data,
            ticks_per_bar=50,
            adaptive=True,
            lookback_bars=10
        )

        assert len(bars) > 0
        assert 'threshold_used' in bars.columns
        # Threshold should vary
        assert bars['threshold_used'].std() > 0

    def test_output_columns(self, sample_tick_data):
        """Test that output contains all expected columns."""
        bars = create_dollar_volume_bars(sample_tick_data, ticks_per_bar=50)

        expected_columns = [
            'bar_id', 'timestamp', 'open', 'high', 'low', 'close',
            'volume', 'dollar_volume', 'tick_count', 'vwap',
            'price_std', 'price_change'
        ]

        for col in expected_columns:
            assert col in bars.columns, f"Missing column: {col}"

    def test_ohlc_consistency(self, sample_tick_data):
        """Test that OHLC values are consistent."""
        bars = create_dollar_volume_bars(sample_tick_data, ticks_per_bar=50)

        # High should be >= Open, Low, Close
        assert (bars['high'] >= bars['open']).all()
        assert (bars['high'] >= bars['low']).all()
        assert (bars['high'] >= bars['close']).all()

        # Low should be <= Open, High, Close
        assert (bars['low'] <= bars['open']).all()
        assert (bars['low'] <= bars['high']).all()
        assert (bars['low'] <= bars['close']).all()

    def test_custom_column_names(self, sample_tick_data):
        """Test with custom column names."""
        # Rename columns
        custom_data = sample_tick_data.rename(columns={
            'price': 'last_price',
            'volume': 'quantity',
            'timestamp': 'trade_time'
        }).copy()

        bars = create_dollar_volume_bars(
            custom_data,
            price_col='last_price',
            volume_col='quantity',
            timestamp_col='trade_time',
            ticks_per_bar=50
        )

        assert len(bars) > 0
        assert 'open' in bars.columns

    def test_vwap_calculation(self, sample_tick_data):
        """Test that VWAP is calculated correctly."""
        bars = create_dollar_volume_bars(sample_tick_data, ticks_per_bar=50)

        # VWAP should be between low and high
        assert (bars['vwap'] >= bars['low']).all()
        assert (bars['vwap'] <= bars['high']).all()

        # VWAP = dollar_volume / volume
        calculated_vwap = bars['dollar_volume'] / bars['volume']
        assert np.allclose(bars['vwap'], calculated_vwap)

    def test_price_change_calculation(self, sample_tick_data):
        """Test price_change is correct."""
        bars = create_dollar_volume_bars(sample_tick_data, ticks_per_bar=50)

        calculated_change = bars['close'] - bars['open']
        assert np.allclose(bars['price_change'], calculated_change)


class TestDollarVolumeSampler:
    """Test the DollarVolumeSampler class."""

    def test_initialization_default(self):
        """Test sampler initialization with defaults."""
        sampler = DollarVolumeSampler()

        assert sampler.threshold is None
        assert sampler.ticks_per_bar == 100
        assert sampler.adaptive is False
        assert sampler.lookback_bars == 20

    def test_initialization_custom(self):
        """Test sampler initialization with custom parameters."""
        sampler = DollarVolumeSampler(
            threshold=500000,
            ticks_per_bar=200,
            adaptive=True,
            lookback_bars=10
        )

        assert sampler.threshold == 500000
        assert sampler.ticks_per_bar == 200
        assert sampler.adaptive is True
        assert sampler.lookback_bars == 10

    def test_initialization_validation(self):
        """Test parameter validation on initialization."""
        with pytest.raises(ValueError, match="Threshold must be positive"):
            DollarVolumeSampler(threshold=-100)

        with pytest.raises(ValueError, match="ticks_per_bar must be at least 1"):
            DollarVolumeSampler(ticks_per_bar=0)

        with pytest.raises(ValueError, match="lookback_bars must be at least 1"):
            DollarVolumeSampler(lookback_bars=0)

    def test_create_bars_basic(self, sample_tick_data):
        """Test basic bar creation."""
        sampler = DollarVolumeSampler(ticks_per_bar=50)
        bars = sampler.create_bars(sample_tick_data)

        assert len(bars) > 0
        assert bars['tick_count'].mean() == pytest.approx(50, rel=0.2)

    def test_get_bar_statistics(self, sample_tick_data):
        """Test bar statistics calculation."""
        sampler = DollarVolumeSampler(ticks_per_bar=50)
        bars = sampler.create_bars(sample_tick_data)
        stats = sampler.get_bar_statistics(bars)

        # Check all expected statistics are present
        expected_stats = [
            'n_bars', 'avg_ticks_per_bar', 'std_ticks_per_bar',
            'avg_volume', 'avg_dollar_volume',
            'returns_mean', 'returns_std', 'returns_skew', 'returns_kurtosis'
        ]

        for stat in expected_stats:
            assert stat in stats, f"Missing statistic: {stat}"

        # Check values are reasonable
        assert stats['n_bars'] == len(bars)
        assert stats['avg_ticks_per_bar'] > 0
        assert stats['avg_volume'] > 0
        assert stats['avg_dollar_volume'] > 0

    def test_get_bar_statistics_adaptive(self, sample_tick_data):
        """Test statistics include threshold info for adaptive mode."""
        sampler = DollarVolumeSampler(ticks_per_bar=50, adaptive=True)
        bars = sampler.create_bars(sample_tick_data)
        stats = sampler.get_bar_statistics(bars)

        assert 'threshold_min' in stats
        assert 'threshold_max' in stats
        assert 'threshold_mean' in stats


class TestCalculateOptimalThreshold:
    """Test the calculate_optimal_threshold function."""

    def test_basic_calculation(self, sample_tick_data):
        """Test optimal threshold calculation."""
        target_bars = 20
        threshold = calculate_optimal_threshold(sample_tick_data, target_bars=target_bars)

        assert threshold > 0

        # Create bars with this threshold
        bars = create_dollar_volume_bars(sample_tick_data, threshold=threshold)

        # Should be close to target
        assert len(bars) == pytest.approx(target_bars, rel=0.1)

    def test_different_targets(self, sample_tick_data):
        """Test with different target bar counts."""
        targets = [10, 20, 50, 100]

        for target in targets:
            threshold = calculate_optimal_threshold(sample_tick_data, target_bars=target)
            bars = create_dollar_volume_bars(sample_tick_data, threshold=threshold)

            # Allow 20% tolerance
            assert len(bars) == pytest.approx(target, rel=0.2)

    def test_custom_columns(self, sample_tick_data):
        """Test with custom column names."""
        custom_data = sample_tick_data.rename(columns={
            'price': 'p',
            'volume': 'v'
        })

        threshold = calculate_optimal_threshold(
            custom_data,
            target_bars=20,
            price_col='p',
            volume_col='v'
        )

        assert threshold > 0


class TestDataValidation:
    """Test data validation and error handling."""

    def test_empty_dataframe(self):
        """Test with empty DataFrame."""
        empty_df = pd.DataFrame()

        with pytest.raises(InsufficientDataError, match="DataFrame is empty"):
            create_dollar_volume_bars(empty_df)

    def test_missing_columns(self, sample_tick_data):
        """Test with missing required columns."""
        # Remove price column
        bad_df = sample_tick_data.drop(columns=['price'])

        with pytest.raises(DataError, match="Missing required columns"):
            create_dollar_volume_bars(bad_df)

    def test_nan_values_in_price(self, sample_tick_data):
        """Test with NaN values in price column."""
        bad_data = sample_tick_data.copy()
        bad_data.loc[10, 'price'] = np.nan

        with pytest.raises(DataQualityError, match="Data contains NaN values"):
            create_dollar_volume_bars(bad_data)

    def test_nan_values_in_volume(self, sample_tick_data):
        """Test with NaN values in volume column."""
        bad_data = sample_tick_data.copy()
        bad_data.loc[10, 'volume'] = np.nan

        with pytest.raises(DataQualityError, match="Data contains NaN values"):
            create_dollar_volume_bars(bad_data)

    def test_negative_prices(self, sample_tick_data):
        """Test with negative prices."""
        bad_data = sample_tick_data.copy()
        bad_data.loc[10, 'price'] = -100

        with pytest.raises(DataQualityError, match="non-positive prices"):
            create_dollar_volume_bars(bad_data)

    def test_negative_volumes(self, sample_tick_data):
        """Test with negative volumes."""
        bad_data = sample_tick_data.copy()
        bad_data.loc[10, 'volume'] = -10

        with pytest.raises(DataQualityError, match="negative volumes"):
            create_dollar_volume_bars(bad_data)

    def test_zero_prices(self, sample_tick_data):
        """Test with zero prices."""
        bad_data = sample_tick_data.copy()
        bad_data.loc[10, 'price'] = 0

        with pytest.raises(DataQualityError, match="non-positive prices"):
            create_dollar_volume_bars(bad_data)

    def test_statistics_empty_bars(self):
        """Test statistics with empty bars DataFrame."""
        sampler = DollarVolumeSampler()
        empty_bars = pd.DataFrame()

        with pytest.raises(InsufficientDataError, match="Bars DataFrame is empty"):
            sampler.get_bar_statistics(empty_bars)


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_single_tick(self):
        """Test with single tick."""
        single_tick = pd.DataFrame({
            'timestamp': [datetime(2024, 1, 1)],
            'price': [45000.0],
            'volume': [1.0]
        })

        bars = create_dollar_volume_bars(single_tick, ticks_per_bar=1)

        assert len(bars) == 1
        assert bars.iloc[0]['open'] == bars.iloc[0]['close']
        assert bars.iloc[0]['high'] == bars.iloc[0]['low']

    def test_very_small_dataset(self):
        """Test with very small dataset."""
        small_data = pd.DataFrame({
            'timestamp': [datetime(2024, 1, 1) + timedelta(seconds=i) for i in range(10)],
            'price': [45000.0 + i for i in range(10)],
            'volume': [1.0] * 10
        })

        bars = create_dollar_volume_bars(small_data, ticks_per_bar=5)

        # Should create approximately 2 bars (10 ticks / 5 per bar)
        assert len(bars) >= 2  # May create slightly more due to rounding
        assert bars['tick_count'].sum() == 10

    def test_constant_prices(self):
        """Test with constant prices (no volatility)."""
        constant_data = pd.DataFrame({
            'timestamp': [datetime(2024, 1, 1) + timedelta(seconds=i) for i in range(100)],
            'price': [45000.0] * 100,
            'volume': np.random.lognormal(5, 1, 100)
        })

        bars = create_dollar_volume_bars(constant_data, ticks_per_bar=10)

        assert len(bars) > 0
        # All prices should be the same
        assert (bars['open'] == bars['close']).all()
        assert (bars['high'] == bars['low']).all()
        assert bars['price_std'].fillna(0).sum() == 0

    def test_constant_volumes(self):
        """Test with constant volumes."""
        constant_vol_data = pd.DataFrame({
            'timestamp': [datetime(2024, 1, 1) + timedelta(seconds=i) for i in range(100)],
            'price': 45000 * (1 + np.random.randn(100).cumsum() * 0.001),
            'volume': [1.0] * 100
        })

        bars = create_dollar_volume_bars(constant_vol_data, ticks_per_bar=10)

        assert len(bars) > 0
        # Volumes per bar should be roughly equal
        assert bars['volume'].std() / bars['volume'].mean() < 0.2

    def test_large_threshold(self, sample_tick_data):
        """Test with threshold larger than total dollar volume."""
        total_dollar_volume = (sample_tick_data['price'] * sample_tick_data['volume']).sum()
        large_threshold = total_dollar_volume * 2

        bars = create_dollar_volume_bars(sample_tick_data, threshold=large_threshold)

        # Should create only 1 bar
        assert len(bars) == 1
        assert bars.iloc[0]['tick_count'] == len(sample_tick_data)

    def test_very_small_threshold(self, sample_tick_data):
        """Test with very small threshold."""
        # Threshold smaller than smallest tick's dollar volume
        min_dollar_vol = (sample_tick_data['price'] * sample_tick_data['volume']).min()
        small_threshold = min_dollar_vol / 2

        bars = create_dollar_volume_bars(sample_tick_data, threshold=small_threshold)

        # Most bars should have 1 tick
        single_tick_bars = (bars['tick_count'] == 1).sum()
        assert single_tick_bars > len(bars) * 0.8  # At least 80% are single tick


class TestPerformance:
    """Test performance with larger datasets."""

    def test_large_dataset(self, large_tick_data):
        """Test with 10,000 ticks."""
        import time

        start = time.time()
        bars = create_dollar_volume_bars(large_tick_data, ticks_per_bar=100)
        elapsed = time.time() - start

        assert len(bars) > 0
        assert elapsed < 1.0  # Should complete in under 1 second

    def test_adaptive_performance(self, large_tick_data):
        """Test adaptive mode performance."""
        import time

        start = time.time()
        bars = create_dollar_volume_bars(large_tick_data, ticks_per_bar=100, adaptive=True)
        elapsed = time.time() - start

        assert len(bars) > 0
        assert elapsed < 5.0  # Adaptive is slower but should still be reasonable


class TestAdaptiveThreshold:
    """Test adaptive threshold functionality."""

    def test_threshold_adaptation(self, large_tick_data):
        """Test that threshold actually adapts."""
        bars = create_dollar_volume_bars(
            large_tick_data,
            ticks_per_bar=100,
            adaptive=True,
            lookback_bars=20
        )

        # Threshold should change over time
        thresholds = bars['threshold_used']
        assert thresholds.std() > 0
        assert thresholds.max() > thresholds.min()

    def test_lookback_parameter(self, large_tick_data):
        """Test different lookback periods."""
        bars_short = create_dollar_volume_bars(
            large_tick_data,
            ticks_per_bar=100,
            adaptive=True,
            lookback_bars=5
        )

        bars_long = create_dollar_volume_bars(
            large_tick_data,
            ticks_per_bar=100,
            adaptive=True,
            lookback_bars=50
        )

        # Both should create bars
        assert len(bars_short) > 0
        assert len(bars_long) > 0

        # Shorter lookback should have more variance in thresholds
        short_var = bars_short['threshold_used'].std() / bars_short['threshold_used'].mean()
        long_var = bars_long['threshold_used'].std() / bars_long['threshold_used'].mean()

        # This may or may not be true depending on data, so just check they're different
        assert short_var != long_var


class TestIntegration:
    """Integration tests with full workflows."""

    def test_full_workflow(self, sample_tick_data):
        """Test complete workflow from data to analysis."""
        # Create bars
        sampler = DollarVolumeSampler(ticks_per_bar=50)
        bars = sampler.create_bars(sample_tick_data)

        # Get statistics
        stats = sampler.get_bar_statistics(bars)

        # Verify workflow
        assert len(bars) > 0
        assert stats['n_bars'] == len(bars)
        assert stats['avg_ticks_per_bar'] > 0

    def test_multiple_symbols_workflow(self, sample_tick_data):
        """Test processing multiple symbols."""
        # Simulate two different symbols
        btc_data = sample_tick_data.copy()
        eth_data = sample_tick_data.copy()
        eth_data['price'] = eth_data['price'] * 0.06  # ETH ~6% of BTC price

        # Process both
        btc_bars = create_dollar_volume_bars(btc_data, ticks_per_bar=50)
        eth_bars = create_dollar_volume_bars(eth_data, ticks_per_bar=50)

        # Both should work
        assert len(btc_bars) > 0
        assert len(eth_bars) > 0

        # Different price levels shouldn't matter for bar count
        assert len(btc_bars) == pytest.approx(len(eth_bars), rel=0.2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
