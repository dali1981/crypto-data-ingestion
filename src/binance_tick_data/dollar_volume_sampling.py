"""
Dollar Volume Sampling Module

This module provides efficient methods for creating dollar volume bars from tick data.
Dollar volume bars are a form of information-driven sampling that aggregates ticks
based on dollar volume traded, rather than fixed time intervals.

Key Benefits:
- Better statistical properties (more normally distributed returns)
- Reduced serial correlation
- Adaptive to market activity
- Information-driven sampling

Author: Binance Tick Data Library
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
import logging

from .errors import DataError, DataQualityError, InsufficientDataError

logger = logging.getLogger(__name__)


class DollarVolumeSampler:
    """
    Creates dollar volume bars from tick data using pandas.

    Dollar volume bars aggregate ticks until a specified dollar volume threshold
    is reached, creating bars that are adaptive to market activity.

    Example:
        >>> sampler = DollarVolumeSampler(threshold=1_000_000)
        >>> bars = sampler.create_bars(tick_data)
        >>> print(bars.head())
    """

    def __init__(self,
                 threshold: Optional[float] = None,
                 ticks_per_bar: int = 100,
                 adaptive: bool = False,
                 lookback_bars: int = 20):
        """
        Initialize the dollar volume sampler.

        Args:
            threshold: Fixed dollar volume threshold per bar. If None, will be
                      calculated from data based on ticks_per_bar.
            ticks_per_bar: Target number of ticks per bar (used to calculate
                          threshold if not provided).
            adaptive: If True, threshold adapts based on recent bar volumes.
            lookback_bars: Number of recent bars to use for adaptive threshold
                          (only used if adaptive=True).

        Raises:
            ValueError: If threshold is negative or ticks_per_bar < 1
        """
        if threshold is not None and threshold <= 0:
            raise ValueError("Threshold must be positive")
        if ticks_per_bar < 1:
            raise ValueError("ticks_per_bar must be at least 1")
        if lookback_bars < 1:
            raise ValueError("lookback_bars must be at least 1")

        self.threshold = threshold
        self.ticks_per_bar = ticks_per_bar
        self.adaptive = adaptive
        self.lookback_bars = lookback_bars
        self._calculated_threshold = None

    def _calculate_threshold(self, df: pd.DataFrame) -> float:
        """
        Calculate threshold from data if not provided.

        Args:
            df: DataFrame with 'price' and 'volume' columns

        Returns:
            Calculated threshold value
        """
        if 'price' not in df.columns or 'volume' not in df.columns:
            raise DataError("DataFrame must contain 'price' and 'volume' columns")

        avg_dollar_volume = (df['price'] * df['volume']).mean()
        threshold = avg_dollar_volume * self.ticks_per_bar

        logger.info(f"Calculated threshold: ${threshold:,.2f} "
                   f"(avg dollar volume: ${avg_dollar_volume:,.2f}, "
                   f"target ticks: {self.ticks_per_bar})")

        return threshold

    def create_bars(self,
                   df: pd.DataFrame,
                   price_col: str = 'price',
                   volume_col: str = 'volume',
                   timestamp_col: str = 'timestamp') -> pd.DataFrame:
        """
        Create dollar volume bars from tick data.

        Args:
            df: DataFrame with tick data
            price_col: Name of price column
            volume_col: Name of volume column
            timestamp_col: Name of timestamp column

        Returns:
            DataFrame with OHLCV dollar volume bars containing:
            - timestamp: First timestamp of the bar
            - open: First price in the bar
            - high: Highest price in the bar
            - low: Lowest price in the bar
            - close: Last price in the bar
            - volume: Total volume in the bar
            - dollar_volume: Total dollar volume in the bar
            - tick_count: Number of ticks in the bar
            - vwap: Volume-weighted average price
            - price_std: Standard deviation of prices
            - price_change: Close - Open

        Raises:
            DataError: If required columns are missing
            InsufficientDataError: If DataFrame is empty
            DataQualityError: If data contains NaN or invalid values
        """
        # Validation
        if df.empty:
            raise InsufficientDataError("DataFrame is empty", required_records=1, available_records=0)

        required_cols = [price_col, volume_col, timestamp_col]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise DataError(f"Missing required columns: {missing_cols}")

        # Check for NaN values
        if df[[price_col, volume_col]].isna().any().any():
            raise DataQualityError("Data contains NaN values in price or volume columns", issues=["NaN values found"])

        # Check for negative values
        if (df[price_col] <= 0).any() or (df[volume_col] < 0).any():
            raise DataQualityError("Data contains non-positive prices or negative volumes", issues=["Invalid price or volume values"])

        # Make a copy to avoid modifying original
        df = df.copy()

        # Determine threshold
        threshold = self.threshold
        if threshold is None:
            # Create a temporary dataframe with standard column names for threshold calculation
            temp_df = pd.DataFrame({
                'price': df[price_col],
                'volume': df[volume_col]
            })
            threshold = self._calculate_threshold(temp_df)
            self._calculated_threshold = threshold

        if not self.adaptive:
            return self._create_fixed_bars(df, threshold, price_col, volume_col, timestamp_col)
        else:
            return self._create_adaptive_bars(df, threshold, price_col, volume_col, timestamp_col)

    def _create_fixed_bars(self,
                          df: pd.DataFrame,
                          threshold: float,
                          price_col: str,
                          volume_col: str,
                          timestamp_col: str) -> pd.DataFrame:
        """
        Create bars with fixed threshold (non-adaptive).

        Args:
            df: DataFrame with tick data
            threshold: Dollar volume threshold
            price_col: Name of price column
            volume_col: Name of volume column
            timestamp_col: Name of timestamp column

        Returns:
            DataFrame with dollar volume bars
        """
        # Calculate dollar volume for each tick
        df['dollar_volume'] = df[price_col] * df[volume_col]

        # Calculate cumulative dollar volume
        df['cum_dollar_volume'] = df['dollar_volume'].cumsum()

        # Identify bar boundaries
        df['bar_id'] = (df['cum_dollar_volume'] // threshold).astype(int)

        # Aggregate to create bars with time metrics
        bars = df.groupby('bar_id').agg({
            timestamp_col: ['first', 'last'],
            price_col: ['first', 'max', 'min', 'last', 'std'],
            volume_col: 'sum',
            'dollar_volume': 'sum'
        })

        # Flatten column names
        bars.columns = ['timestamp', 'timestamp_close', 'open', 'high', 'low', 'close', 'price_std',
                       'volume', 'dollar_volume']

        # Convert timestamps to datetime if they're integers (milliseconds from DuckDB)
        if pd.api.types.is_integer_dtype(bars['timestamp']):
            bars['timestamp'] = pd.to_datetime(bars['timestamp'], unit='ms')
            bars['timestamp_close'] = pd.to_datetime(bars['timestamp_close'], unit='ms')

        # Add additional metrics
        tick_counts = df.groupby('bar_id').size()
        bars['tick_count'] = tick_counts
        bars['price_change'] = bars['close'] - bars['open']
        bars['vwap'] = bars['dollar_volume'] / bars['volume']

        # Calculate time-based metrics
        bars['duration_seconds'] = (bars['timestamp_close'] - bars['timestamp']).dt.total_seconds()
        bars['ticks_per_second'] = bars['tick_count'] / bars['duration_seconds'].replace(0, 1)
        bars['dollar_volume_per_second'] = bars['dollar_volume'] / bars['duration_seconds'].replace(0, 1)

        # Reset index
        bars = bars.reset_index()

        # Calculate time between bars (informative about market activity gaps)
        bars['time_since_last_bar'] = bars['timestamp'].diff().dt.total_seconds()

        # Reorder columns for better readability
        bars = bars[['bar_id', 'timestamp', 'timestamp_close', 'open', 'high', 'low', 'close',
                    'volume', 'dollar_volume', 'tick_count', 'vwap',
                    'price_std', 'price_change', 'duration_seconds',
                    'ticks_per_second', 'dollar_volume_per_second', 'time_since_last_bar']]

        logger.info(f"Created {len(bars)} dollar volume bars with fixed threshold ${threshold:,.2f}")

        return bars

    def _create_adaptive_bars(self,
                             df: pd.DataFrame,
                             initial_threshold: float,
                             price_col: str,
                             volume_col: str,
                             timestamp_col: str) -> pd.DataFrame:
        """
        Create bars with adaptive threshold based on recent activity.

        The threshold adjusts based on exponentially weighted average of recent bar sizes.

        Args:
            df: DataFrame with tick data
            initial_threshold: Starting dollar volume threshold
            price_col: Name of price column
            volume_col: Name of volume column
            timestamp_col: Name of timestamp column

        Returns:
            DataFrame with dollar volume bars including 'threshold_used' column
        """
        bars = []
        current_threshold = initial_threshold
        recent_volumes = []

        cum_dollar_volume = 0
        bar_start_idx = 0

        for i in range(len(df)):
            row = df.iloc[i]
            dollar_volume = row[price_col] * row[volume_col]
            cum_dollar_volume += dollar_volume

            if cum_dollar_volume >= current_threshold:
                # Create bar
                bar_data = df.iloc[bar_start_idx:i+1]

                bar_volume = bar_data[volume_col].sum()
                bar_dollar_volume = cum_dollar_volume
                timestamp_open = bar_data.iloc[0][timestamp_col]
                timestamp_close = bar_data.iloc[-1][timestamp_col]

                # Convert timestamps to datetime if they're integers (milliseconds from DuckDB)
                if isinstance(timestamp_open, (int, np.integer)):
                    timestamp_open = pd.to_datetime(timestamp_open, unit='ms')
                    timestamp_close = pd.to_datetime(timestamp_close, unit='ms')

                # Calculate duration
                duration = (timestamp_close - timestamp_open).total_seconds() if hasattr(timestamp_close - timestamp_open, 'total_seconds') else 0

                bar = {
                    'timestamp': timestamp_open,
                    'timestamp_close': timestamp_close,
                    'open': bar_data.iloc[0][price_col],
                    'high': bar_data[price_col].max(),
                    'low': bar_data[price_col].min(),
                    'close': bar_data.iloc[-1][price_col],
                    'volume': bar_volume,
                    'dollar_volume': bar_dollar_volume,
                    'tick_count': len(bar_data),
                    'vwap': bar_dollar_volume / bar_volume if bar_volume > 0 else 0,
                    'price_std': bar_data[price_col].std(),
                    'price_change': bar_data.iloc[-1][price_col] - bar_data.iloc[0][price_col],
                    'duration_seconds': duration,
                    'ticks_per_second': len(bar_data) / max(duration, 1),
                    'dollar_volume_per_second': bar_dollar_volume / max(duration, 1),
                    'threshold_used': current_threshold
                }
                bars.append(bar)
                recent_volumes.append(cum_dollar_volume)

                # Update adaptive threshold
                if len(recent_volumes) > self.lookback_bars:
                    recent_volumes.pop(0)

                if len(recent_volumes) >= 5:  # Need minimum bars for adaptation
                    # Use exponential weighted average
                    weights = np.exp(np.linspace(-1, 0, len(recent_volumes)))
                    weights /= weights.sum()
                    current_threshold = np.average(recent_volumes, weights=weights)

                # Reset
                cum_dollar_volume = 0
                bar_start_idx = i + 1

        bars_df = pd.DataFrame(bars)

        # Add bar_id
        bars_df.insert(0, 'bar_id', range(len(bars_df)))

        # Calculate time between bars
        bars_df['time_since_last_bar'] = bars_df['timestamp'].diff().dt.total_seconds()

        logger.info(f"Created {len(bars_df)} adaptive dollar volume bars "
                   f"(initial threshold: ${initial_threshold:,.2f}, "
                   f"final threshold: ${current_threshold:,.2f})")

        return bars_df

    def get_bar_statistics(self, bars: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate statistical properties of the dollar volume bars.

        Args:
            bars: DataFrame with dollar volume bars (output from create_bars)

        Returns:
            Dictionary with statistics including:
            - n_bars: Number of bars
            - avg_ticks_per_bar: Average number of ticks per bar
            - std_ticks_per_bar: Standard deviation of ticks per bar
            - avg_volume: Average volume per bar
            - avg_dollar_volume: Average dollar volume per bar
            - returns_mean: Mean return
            - returns_std: Standard deviation of returns
            - returns_skew: Skewness of returns
            - returns_kurtosis: Kurtosis of returns
        """
        if bars.empty:
            raise InsufficientDataError("Bars DataFrame is empty", required_records=1, available_records=0)

        # Calculate returns
        returns = bars['close'].pct_change().dropna()

        stats = {
            'n_bars': len(bars),
            'avg_ticks_per_bar': bars['tick_count'].mean(),
            'std_ticks_per_bar': bars['tick_count'].std(),
            'avg_volume': bars['volume'].mean(),
            'avg_dollar_volume': bars['dollar_volume'].mean(),
            'returns_mean': returns.mean(),
            'returns_std': returns.std(),
            'returns_skew': returns.skew(),
            'returns_kurtosis': returns.kurtosis(),
        }

        # Add adaptive threshold stats if available
        if 'threshold_used' in bars.columns:
            stats['threshold_min'] = bars['threshold_used'].min()
            stats['threshold_max'] = bars['threshold_used'].max()
            stats['threshold_mean'] = bars['threshold_used'].mean()

        return stats


def create_dollar_volume_bars(df: pd.DataFrame,
                              threshold: Optional[float] = None,
                              ticks_per_bar: int = 100,
                              price_col: str = 'price',
                              volume_col: str = 'volume',
                              timestamp_col: str = 'timestamp',
                              adaptive: bool = False,
                              lookback_bars: int = 20) -> pd.DataFrame:
    """
    Convenience function to create dollar volume bars from tick data.

    This is a simpler interface to DollarVolumeSampler for quick usage.

    Args:
        df: DataFrame with tick data
        threshold: Dollar volume threshold per bar. If None, calculated from data.
        ticks_per_bar: Target ticks per bar (used if threshold is None)
        price_col: Name of price column (default: 'price')
        volume_col: Name of volume column (default: 'volume')
        timestamp_col: Name of timestamp column (default: 'timestamp')
        adaptive: If True, threshold adapts based on recent bars
        lookback_bars: Number of recent bars for adaptive threshold

    Returns:
        DataFrame with OHLCV dollar volume bars

    Example:
        >>> import pandas as pd
        >>> from binance_tick_data import create_dollar_volume_bars
        >>>
        >>> # Simple usage with auto-calculated threshold
        >>> bars = create_dollar_volume_bars(tick_data, ticks_per_bar=100)
        >>>
        >>> # With fixed threshold
        >>> bars = create_dollar_volume_bars(tick_data, threshold=1_000_000)
        >>>
        >>> # Adaptive threshold
        >>> bars = create_dollar_volume_bars(tick_data, adaptive=True)
    """
    sampler = DollarVolumeSampler(
        threshold=threshold,
        ticks_per_bar=ticks_per_bar,
        adaptive=adaptive,
        lookback_bars=lookback_bars
    )

    return sampler.create_bars(
        df=df,
        price_col=price_col,
        volume_col=volume_col,
        timestamp_col=timestamp_col
    )


def calculate_optimal_threshold(df: pd.DataFrame,
                                target_bars: int = None,
                                target_bars_per_day: int = None,
                                price_col: str = 'price',
                                volume_col: str = 'volume',
                                timestamp_col: str = 'timestamp') -> float:
    """
    Calculate optimal dollar volume threshold to achieve target number of bars.

    Args:
        df: DataFrame with tick data
        target_bars: Desired total number of bars (mutually exclusive with target_bars_per_day)
        target_bars_per_day: Desired bars per day (requires timestamp column, mutually exclusive with target_bars)
        price_col: Name of price column
        volume_col: Name of volume column
        timestamp_col: Name of timestamp column (required if using target_bars_per_day)

    Returns:
        Calculated threshold value

    Example:
        >>> # Calculate for total number of bars
        >>> threshold = calculate_optimal_threshold(tick_data, target_bars=1000)
        >>> bars = create_dollar_volume_bars(tick_data, threshold=threshold)

        >>> # Calculate for bars per day
        >>> threshold = calculate_optimal_threshold(tick_data, target_bars_per_day=50)
        >>> bars = create_dollar_volume_bars(tick_data, threshold=threshold)
    """
    if df.empty:
        raise InsufficientDataError("DataFrame is empty", required_records=1, available_records=0)

    # Validate arguments
    if target_bars is None and target_bars_per_day is None:
        raise ValueError("Must specify either target_bars or target_bars_per_day")

    if target_bars is not None and target_bars_per_day is not None:
        raise ValueError("Cannot specify both target_bars and target_bars_per_day")

    # Calculate target_bars from target_bars_per_day if needed
    if target_bars_per_day is not None:
        if timestamp_col not in df.columns:
            raise ValueError(f"timestamp_col '{timestamp_col}' not found in DataFrame")

        # Convert timestamps to datetime if needed
        timestamps = df[timestamp_col]
        if pd.api.types.is_integer_dtype(timestamps):
            timestamps = pd.to_datetime(timestamps, unit='ms')
        elif not pd.api.types.is_datetime64_any_dtype(timestamps):
            timestamps = pd.to_datetime(timestamps)

        # Calculate days in data
        time_range = timestamps.max() - timestamps.min()
        days = time_range.total_seconds() / 86400

        if days < 0.01:  # Less than ~15 minutes
            raise InsufficientDataError(
                "Data span is too short for target_bars_per_day calculation",
                required_records=int(target_bars_per_day * days) if days > 0 else 1,
                available_records=len(df)
            )

        target_bars = int(target_bars_per_day * days)
        logger.info(f"Calculated target_bars={target_bars} from {target_bars_per_day} bars/day over {days:.2f} days")

    total_dollar_volume = (df[price_col] * df[volume_col]).sum()
    threshold = total_dollar_volume / target_bars

    logger.info(f"Calculated optimal threshold: ${threshold:,.2f} "
               f"for {target_bars} bars from {len(df)} ticks")

    return threshold
