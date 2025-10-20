"""
Tests for time-based metrics in dollar volume sampling.

Run with:
    pytest tests/test_time_metrics.py -v
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from binance_tick_data import (
    create_dollar_volume_bars,
    DollarVolumeSampler,
)


@pytest.fixture
def tick_data_with_timestamps():
    """Generate tick data with realistic timestamps."""
    np.random.seed(42)
    n = 500

    # Create timestamps with variable intervals
    start_time = datetime(2024, 1, 1, 9, 0, 0)
    timestamps = []
    current_time = start_time

    for i in range(n):
        # Variable interval (0.5 to 2 seconds)
        interval = np.random.uniform(0.5, 2.0)
        current_time += timedelta(seconds=interval)
        timestamps.append(current_time)

    prices = 45000 * (1 + np.random.randn(n).cumsum() * 0.001)
    volumes = np.random.lognormal(5, 1, n)

    return pd.DataFrame({
        'timestamp': timestamps,
        'price': prices,
        'volume': volumes
    })


class TestTimeMetricsPresence:
    """Test that time metrics are present in bars."""

    def test_timestamp_close_exists(self, tick_data_with_timestamps):
        """Test timestamp_close column exists."""
        bars = create_dollar_volume_bars(tick_data_with_timestamps, ticks_per_bar=50)
        assert 'timestamp_close' in bars.columns

    def test_duration_seconds_exists(self, tick_data_with_timestamps):
        """Test duration_seconds column exists."""
        bars = create_dollar_volume_bars(tick_data_with_timestamps, ticks_per_bar=50)
        assert 'duration_seconds' in bars.columns

    def test_ticks_per_second_exists(self, tick_data_with_timestamps):
        """Test ticks_per_second column exists."""
        bars = create_dollar_volume_bars(tick_data_with_timestamps, ticks_per_bar=50)
        assert 'ticks_per_second' in bars.columns

    def test_dollar_volume_per_second_exists(self, tick_data_with_timestamps):
        """Test dollar_volume_per_second column exists."""
        bars = create_dollar_volume_bars(tick_data_with_timestamps, ticks_per_bar=50)
        assert 'dollar_volume_per_second' in bars.columns

    def test_time_since_last_bar_exists(self, tick_data_with_timestamps):
        """Test time_since_last_bar column exists."""
        bars = create_dollar_volume_bars(tick_data_with_timestamps, ticks_per_bar=50)
        assert 'time_since_last_bar' in bars.columns

    def test_all_time_metrics_present(self, tick_data_with_timestamps):
        """Test all time metrics are present."""
        bars = create_dollar_volume_bars(tick_data_with_timestamps, ticks_per_bar=50)

        expected_time_metrics = [
            'timestamp_close',
            'duration_seconds',
            'ticks_per_second',
            'dollar_volume_per_second',
            'time_since_last_bar'
        ]

        for metric in expected_time_metrics:
            assert metric in bars.columns, f"Missing time metric: {metric}"


class TestTimeMetricsValues:
    """Test that time metrics have correct values."""

    def test_timestamp_close_after_timestamp(self, tick_data_with_timestamps):
        """Test that close timestamp is after or equal to open timestamp."""
        bars = create_dollar_volume_bars(tick_data_with_timestamps, ticks_per_bar=50)

        assert (bars['timestamp_close'] >= bars['timestamp']).all()

    def test_duration_positive(self, tick_data_with_timestamps):
        """Test that duration is non-negative."""
        bars = create_dollar_volume_bars(tick_data_with_timestamps, ticks_per_bar=50)

        assert (bars['duration_seconds'] >= 0).all()

    def test_ticks_per_second_positive(self, tick_data_with_timestamps):
        """Test that tick rate is positive."""
        bars = create_dollar_volume_bars(tick_data_with_timestamps, ticks_per_bar=50)

        assert (bars['ticks_per_second'] > 0).all()

    def test_dollar_volume_per_second_positive(self, tick_data_with_timestamps):
        """Test that dollar volume velocity is positive."""
        bars = create_dollar_volume_bars(tick_data_with_timestamps, ticks_per_bar=50)

        assert (bars['dollar_volume_per_second'] > 0).all()

    def test_time_since_last_bar_first_is_nan(self, tick_data_with_timestamps):
        """Test that first bar has NaN for time_since_last_bar."""
        bars = create_dollar_volume_bars(tick_data_with_timestamps, ticks_per_bar=50)

        assert pd.isna(bars['time_since_last_bar'].iloc[0])

    def test_time_since_last_bar_rest_positive(self, tick_data_with_timestamps):
        """Test that time gaps are positive after first bar."""
        bars = create_dollar_volume_bars(tick_data_with_timestamps, ticks_per_bar=50)

        assert (bars['time_since_last_bar'].iloc[1:] > 0).all()


class TestDurationCalculation:
    """Test duration calculation accuracy."""

    def test_duration_matches_timestamps(self, tick_data_with_timestamps):
        """Test that duration matches timestamp difference."""
        bars = create_dollar_volume_bars(tick_data_with_timestamps, ticks_per_bar=50)

        # Calculate expected duration
        expected_duration = (bars['timestamp_close'] - bars['timestamp']).dt.total_seconds()

        # Should match within floating point precision
        assert np.allclose(bars['duration_seconds'], expected_duration)

    def test_single_tick_bar_zero_duration(self):
        """Test that single-tick bars have zero duration."""
        single_tick = pd.DataFrame({
            'timestamp': [datetime(2024, 1, 1)],
            'price': [45000.0],
            'volume': [1.0]
        })

        bars = create_dollar_volume_bars(single_tick, ticks_per_bar=1)

        assert bars['duration_seconds'].iloc[0] == 0

    def test_duration_increases_with_tick_spread(self):
        """Test that bars with spread-out ticks have longer duration."""
        # Create data with varying tick spacing
        n = 100
        timestamps_tight = [datetime(2024, 1, 1) + timedelta(seconds=i*0.1) for i in range(n)]
        timestamps_spread = [datetime(2024, 1, 1) + timedelta(seconds=i*1.0) for i in range(n)]

        data_tight = pd.DataFrame({
            'timestamp': timestamps_tight,
            'price': [45000.0] * n,
            'volume': [1.0] * n
        })

        data_spread = pd.DataFrame({
            'timestamp': timestamps_spread,
            'price': [45000.0] * n,
            'volume': [1.0] * n
        })

        bars_tight = create_dollar_volume_bars(data_tight, ticks_per_bar=10)
        bars_spread = create_dollar_volume_bars(data_spread, ticks_per_bar=10)

        # Spread-out bars should have longer average duration
        assert bars_spread['duration_seconds'].mean() > bars_tight['duration_seconds'].mean()


class TestTicksPerSecond:
    """Test tick rate calculation."""

    def test_tick_rate_calculation(self, tick_data_with_timestamps):
        """Test that tick rate is calculated correctly."""
        bars = create_dollar_volume_bars(tick_data_with_timestamps, ticks_per_bar=50)

        # Calculate expected tick rate
        expected_rate = bars['tick_count'] / bars['duration_seconds'].replace(0, 1)

        assert np.allclose(bars['ticks_per_second'], expected_rate)

    def test_high_frequency_high_tick_rate(self):
        """Test that high-frequency data has high tick rate."""
        n = 1000
        # Very frequent ticks (0.1 second intervals)
        timestamps = [datetime(2024, 1, 1) + timedelta(seconds=i*0.1) for i in range(n)]

        data = pd.DataFrame({
            'timestamp': timestamps,
            'price': 45000 * (1 + np.random.randn(n).cumsum() * 0.001),
            'volume': np.random.lognormal(5, 1, n)
        })

        bars = create_dollar_volume_bars(data, ticks_per_bar=100)

        # Should have high tick rate (multiple ticks per second)
        assert bars['ticks_per_second'].mean() > 1.0

    def test_low_frequency_low_tick_rate(self):
        """Test that low-frequency data has low tick rate."""
        n = 100
        # Infrequent ticks (10 second intervals)
        timestamps = [datetime(2024, 1, 1) + timedelta(seconds=i*10) for i in range(n)]

        data = pd.DataFrame({
            'timestamp': timestamps,
            'price': 45000 * (1 + np.random.randn(n).cumsum() * 0.001),
            'volume': np.random.lognormal(5, 1, n)
        })

        bars = create_dollar_volume_bars(data, ticks_per_bar=10)

        # Should have low tick rate (less than 1 tick per second)
        assert bars['ticks_per_second'].mean() < 1.0


class TestDollarVolumeVelocity:
    """Test dollar volume per second calculation."""

    def test_velocity_calculation(self, tick_data_with_timestamps):
        """Test that dollar volume velocity is calculated correctly."""
        bars = create_dollar_volume_bars(tick_data_with_timestamps, ticks_per_bar=50)

        # Calculate expected velocity
        expected_velocity = bars['dollar_volume'] / bars['duration_seconds'].replace(0, 1)

        assert np.allclose(bars['dollar_volume_per_second'], expected_velocity)

    def test_velocity_correlates_with_volume(self, tick_data_with_timestamps):
        """Test that velocity correlates with total dollar volume."""
        bars = create_dollar_volume_bars(tick_data_with_timestamps, ticks_per_bar=50)

        # Higher dollar volume should generally mean higher velocity
        # (though correlation can be weak due to duration variation)
        correlation = bars['dollar_volume'].corr(bars['dollar_volume_per_second'])

        # Just verify positive correlation exists
        assert correlation > 0  # Positive correlation


class TestTimeSinceLastBar:
    """Test inter-bar time gap calculation."""

    def test_gap_calculation(self, tick_data_with_timestamps):
        """Test that time gaps are calculated correctly."""
        bars = create_dollar_volume_bars(tick_data_with_timestamps, ticks_per_bar=50)

        # Calculate expected gaps
        expected_gaps = bars['timestamp'].diff().dt.total_seconds()

        # Skip first (NaN) and compare rest
        assert np.allclose(
            bars['time_since_last_bar'].iloc[1:],
            expected_gaps.iloc[1:]
        )

    def test_gaps_detect_pauses(self):
        """Test that gaps detect trading pauses."""
        # Create data with deliberate pause
        timestamps = []
        current = datetime(2024, 1, 1)

        # First 50 ticks (frequent)
        for i in range(50):
            timestamps.append(current)
            current += timedelta(seconds=1)

        # Pause (5 minute gap)
        current += timedelta(minutes=5)

        # Next 50 ticks (frequent)
        for i in range(50):
            timestamps.append(current)
            current += timedelta(seconds=1)

        data = pd.DataFrame({
            'timestamp': timestamps,
            'price': [45000.0] * 100,
            'volume': [1.0] * 100
        })

        bars = create_dollar_volume_bars(data, ticks_per_bar=10)

        # Should detect a large gap
        max_gap = bars['time_since_last_bar'].max()
        assert max_gap > 60  # At least 1 minute gap detected


class TestAdaptiveTimeMetrics:
    """Test time metrics in adaptive mode."""

    def test_adaptive_has_time_metrics(self, tick_data_with_timestamps):
        """Test that adaptive bars include time metrics."""
        bars = create_dollar_volume_bars(
            tick_data_with_timestamps,
            ticks_per_bar=50,
            adaptive=True
        )

        assert 'timestamp_close' in bars.columns
        assert 'duration_seconds' in bars.columns
        assert 'ticks_per_second' in bars.columns
        assert 'dollar_volume_per_second' in bars.columns
        assert 'time_since_last_bar' in bars.columns

    def test_adaptive_time_metrics_valid(self, tick_data_with_timestamps):
        """Test that adaptive time metrics are valid."""
        bars = create_dollar_volume_bars(
            tick_data_with_timestamps,
            ticks_per_bar=50,
            adaptive=True
        )

        # All validations
        assert (bars['timestamp_close'] >= bars['timestamp']).all()
        assert (bars['duration_seconds'] >= 0).all()
        assert (bars['ticks_per_second'] > 0).all()
        assert (bars['dollar_volume_per_second'] > 0).all()


class TestTimeMetricsIntegration:
    """Integration tests for time metrics."""

    def test_time_metrics_with_sampler_class(self, tick_data_with_timestamps):
        """Test time metrics with DollarVolumeSampler class."""
        sampler = DollarVolumeSampler(ticks_per_bar=50)
        bars = sampler.create_bars(tick_data_with_timestamps)

        # All time metrics should be present
        assert 'timestamp_close' in bars.columns
        assert 'duration_seconds' in bars.columns
        assert 'ticks_per_second' in bars.columns
        assert 'dollar_volume_per_second' in bars.columns
        assert 'time_since_last_bar' in bars.columns

    def test_time_metrics_with_custom_columns(self, tick_data_with_timestamps):
        """Test time metrics work with custom column names."""
        custom_data = tick_data_with_timestamps.rename(columns={
            'timestamp': 'time',
            'price': 'p',
            'volume': 'v'
        })

        bars = create_dollar_volume_bars(
            custom_data,
            timestamp_col='time',
            price_col='p',
            volume_col='v',
            ticks_per_bar=50
        )

        assert 'timestamp_close' in bars.columns
        assert 'duration_seconds' in bars.columns

    def test_time_metrics_large_dataset(self):
        """Test time metrics with larger dataset."""
        n = 5000
        timestamps = [datetime(2024, 1, 1) + timedelta(seconds=i*0.5) for i in range(n)]

        data = pd.DataFrame({
            'timestamp': timestamps,
            'price': 45000 * (1 + np.random.randn(n).cumsum() * 0.001),
            'volume': np.random.lognormal(5, 1, n)
        })

        bars = create_dollar_volume_bars(data, ticks_per_bar=100)

        # Should work without errors
        assert len(bars) > 0
        assert 'duration_seconds' in bars.columns
        assert not bars['duration_seconds'].isna().any()


class TestTimeMetricsEdgeCases:
    """Test edge cases for time metrics."""

    def test_zero_duration_handling(self):
        """Test handling of zero duration bars."""
        # Create simultaneous ticks
        timestamp = datetime(2024, 1, 1)
        data = pd.DataFrame({
            'timestamp': [timestamp] * 10,
            'price': [45000.0] * 10,
            'volume': [1.0] * 10
        })

        bars = create_dollar_volume_bars(data, ticks_per_bar=5)

        # Should handle zero duration without errors
        assert (bars['duration_seconds'] == 0).all()
        # Tick rate should still be calculated (avoiding divide by zero)
        assert not bars['ticks_per_second'].isna().any()
        assert not np.isinf(bars['ticks_per_second']).any()

    def test_microsecond_precision(self):
        """Test that microsecond timestamps are handled."""
        n = 100
        timestamps = [
            datetime(2024, 1, 1) + timedelta(microseconds=i*1000)
            for i in range(n)
        ]

        data = pd.DataFrame({
            'timestamp': timestamps,
            'price': [45000.0] * n,
            'volume': [1.0] * n
        })

        bars = create_dollar_volume_bars(data, ticks_per_bar=10)

        # Should handle microsecond precision
        assert bars['duration_seconds'].min() < 1.0
        assert bars['ticks_per_second'].mean() > 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
