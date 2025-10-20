"""
Metrics Aggregator for real-time streaming data.

Aggregates metrics from multiple analyzers across different time windows,
providing rolling statistics and time-series views.

Features:
- Multiple time window support (1s, 5s, 30s, 1m, etc.)
- Rolling statistics (mean, std, min, max, percentiles)
- Efficient ring buffer storage
- Automatic cleanup of old data
"""

from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from .ring_buffer import NumericRingBuffer


class MetricsAggregator:
    """
    Aggregates metrics across multiple time windows.

    Maintains rolling windows of metrics from analyzers, computing
    statistics and providing time-series access.

    Examples:
        >>> aggregator = MetricsAggregator(
        ...     window_sizes=[1, 5, 30, 60],
        ...     publish_interval=1.0
        ... )
        >>> aggregator.add_metric("vwap", 50123.45, datetime.now())
        >>> stats = aggregator.get_window_statistics("vwap", window_size=60)
    """

    def __init__(
        self,
        window_sizes: List[int] = [1, 5, 30, 60],
        publish_interval: float = 1.0,
        max_history: int = 3600,
    ):
        """
        Initialize metrics aggregator.

        Args:
            window_sizes: List of window sizes in seconds
            publish_interval: How often to compute aggregations (seconds)
            max_history: Maximum history to keep per metric (seconds)
        """
        self.window_sizes = sorted(window_sizes)
        self.publish_interval = publish_interval
        self.max_history = max_history

        # Metric storage: metric_name -> list of (timestamp, value)
        self._metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))

        # Cached aggregations to avoid recomputation
        self._cache: Dict[str, Dict[int, Dict]] = defaultdict(dict)
        self._cache_timestamps: Dict[str, Dict[int, datetime]] = defaultdict(dict)

        # Last publication time
        self._last_publish: Optional[datetime] = None

    def add_metric(self, metric_name: str, value: float, timestamp: Optional[datetime] = None):
        """
        Add a metric value.

        Args:
            metric_name: Name of the metric
            value: Metric value
            timestamp: Timestamp (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.now()

        # Add to storage
        self._metrics[metric_name].append((timestamp, value))

        # Clean up old data
        self._cleanup_old_data(metric_name)

        # Invalidate cache for this metric
        if metric_name in self._cache:
            self._cache[metric_name].clear()
            self._cache_timestamps[metric_name].clear()

    def add_metrics_dict(self, metrics: Dict[str, Any], timestamp: Optional[datetime] = None):
        """
        Add multiple metrics from dictionary.

        Args:
            metrics: Dictionary of metric_name -> value
            timestamp: Timestamp (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.now()

        for metric_name, value in metrics.items():
            # Only add numeric values
            if isinstance(value, (int, float)) and not np.isnan(value) and not np.isinf(value):
                self.add_metric(metric_name, float(value), timestamp)

    def get_window_statistics(
        self, metric_name: str, window_size: int, use_cache: bool = True
    ) -> Dict[str, float]:
        """
        Get statistics for a metric over a time window.

        Args:
            metric_name: Name of the metric
            window_size: Window size in seconds
            use_cache: Whether to use cached results

        Returns:
            Dictionary with statistics (mean, std, min, max, etc.)
        """
        # Check cache
        if use_cache and metric_name in self._cache and window_size in self._cache[metric_name]:
            cache_time = self._cache_timestamps[metric_name][window_size]
            if (datetime.now() - cache_time).total_seconds() < self.publish_interval:
                return self._cache[metric_name][window_size]

        # Get data for window
        values = self._get_window_values(metric_name, window_size)

        if len(values) == 0:
            stats = {
                "count": 0,
                "mean": np.nan,
                "std": np.nan,
                "min": np.nan,
                "max": np.nan,
                "median": np.nan,
                "p25": np.nan,
                "p75": np.nan,
                "p95": np.nan,
            }
        else:
            values_array = np.array(values)
            stats = {
                "count": len(values),
                "mean": float(np.mean(values_array)),
                "std": float(np.std(values_array)),
                "min": float(np.min(values_array)),
                "max": float(np.max(values_array)),
                "median": float(np.median(values_array)),
                "p25": float(np.percentile(values_array, 25)),
                "p75": float(np.percentile(values_array, 75)),
                "p95": float(np.percentile(values_array, 95)),
            }

            # Add range and rate of change
            stats["range"] = stats["max"] - stats["min"]

            if len(values) > 1:
                stats["first"] = float(values[0])
                stats["last"] = float(values[-1])
                stats["change"] = stats["last"] - stats["first"]
                stats["change_pct"] = (
                    (stats["change"] / stats["first"] * 100) if stats["first"] != 0 else 0.0
                )
            else:
                stats["first"] = float(values[0])
                stats["last"] = float(values[0])
                stats["change"] = 0.0
                stats["change_pct"] = 0.0

        # Cache results
        self._cache[metric_name][window_size] = stats
        self._cache_timestamps[metric_name][window_size] = datetime.now()

        return stats

    def get_all_window_statistics(
        self, metric_name: str, use_cache: bool = True
    ) -> Dict[int, Dict[str, float]]:
        """
        Get statistics for all configured windows.

        Args:
            metric_name: Name of the metric
            use_cache: Whether to use cached results

        Returns:
            Dictionary mapping window_size -> statistics
        """
        result = {}
        for window_size in self.window_sizes:
            result[window_size] = self.get_window_statistics(
                metric_name, window_size, use_cache=use_cache
            )
        return result

    def get_latest_value(self, metric_name: str) -> Optional[float]:
        """
        Get the most recent value for a metric.

        Args:
            metric_name: Name of the metric

        Returns:
            Latest value or None if no data
        """
        if metric_name not in self._metrics or len(self._metrics[metric_name]) == 0:
            return None

        return self._metrics[metric_name][-1][1]

    def get_time_series(
        self, metric_name: str, window_size: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Get time series data for a metric.

        Args:
            metric_name: Name of the metric
            window_size: Window size in seconds (None = all data)

        Returns:
            DataFrame with timestamp and value columns
        """
        if metric_name not in self._metrics or len(self._metrics[metric_name]) == 0:
            return pd.DataFrame(columns=["timestamp", "value"])

        # Get data
        if window_size is None:
            data = list(self._metrics[metric_name])
        else:
            cutoff = datetime.now() - timedelta(seconds=window_size)
            data = [(ts, val) for ts, val in self._metrics[metric_name] if ts >= cutoff]

        if len(data) == 0:
            return pd.DataFrame(columns=["timestamp", "value"])

        timestamps, values = zip(*data)
        return pd.DataFrame({"timestamp": timestamps, "value": values})

    def get_available_metrics(self) -> List[str]:
        """
        Get list of available metrics.

        Returns:
            List of metric names
        """
        return list(self._metrics.keys())

    def get_metrics_summary(self) -> Dict[str, Dict[str, Any]]:
        """
        Get summary of all metrics.

        Returns:
            Dictionary with metric summaries
        """
        summary = {}

        for metric_name in self._metrics.keys():
            if len(self._metrics[metric_name]) == 0:
                continue

            latest_value = self._metrics[metric_name][-1][1]
            oldest_time = self._metrics[metric_name][0][0]
            latest_time = self._metrics[metric_name][-1][0]
            duration = (latest_time - oldest_time).total_seconds()

            summary[metric_name] = {
                "count": len(self._metrics[metric_name]),
                "latest_value": latest_value,
                "duration_seconds": duration,
                "oldest_timestamp": oldest_time,
                "latest_timestamp": latest_time,
            }

        return summary

    def clear_metric(self, metric_name: str):
        """
        Clear data for a specific metric.

        Args:
            metric_name: Name of the metric to clear
        """
        if metric_name in self._metrics:
            self._metrics[metric_name].clear()
        if metric_name in self._cache:
            self._cache[metric_name].clear()
        if metric_name in self._cache_timestamps:
            self._cache_timestamps[metric_name].clear()

    def clear_all(self):
        """Clear all metrics data."""
        self._metrics.clear()
        self._cache.clear()
        self._cache_timestamps.clear()

    def _get_window_values(self, metric_name: str, window_size: int) -> List[float]:
        """
        Get metric values for a specific time window.

        Args:
            metric_name: Name of the metric
            window_size: Window size in seconds

        Returns:
            List of values within the window
        """
        if metric_name not in self._metrics:
            return []

        cutoff = datetime.now() - timedelta(seconds=window_size)
        values = [value for timestamp, value in self._metrics[metric_name] if timestamp >= cutoff]

        return values

    def _cleanup_old_data(self, metric_name: str):
        """
        Remove data older than max_history.

        Args:
            metric_name: Name of the metric to clean up
        """
        if metric_name not in self._metrics or len(self._metrics[metric_name]) == 0:
            return

        cutoff = datetime.now() - timedelta(seconds=self.max_history)

        # Remove old entries from the left side of deque
        while len(self._metrics[metric_name]) > 0:
            timestamp, _ = self._metrics[metric_name][0]
            if timestamp < cutoff:
                self._metrics[metric_name].popleft()
            else:
                break

    def should_publish(self) -> bool:
        """
        Check if enough time has passed to publish aggregations.

        Returns:
            True if should publish now
        """
        if self._last_publish is None:
            return True

        elapsed = (datetime.now() - self._last_publish).total_seconds()
        return elapsed >= self.publish_interval

    def mark_published(self):
        """Mark that aggregations have been published."""
        self._last_publish = datetime.now()

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"MetricsAggregator("
            f"metrics={len(self._metrics)}, "
            f"windows={self.window_sizes}, "
            f"interval={self.publish_interval}s)"
        )
