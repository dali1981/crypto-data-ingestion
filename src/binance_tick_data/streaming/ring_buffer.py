"""
Ring buffer implementation for efficient in-memory storage of streaming trade data.

Provides O(1) append and retrieval operations with fixed memory footprint.
Thread-safe for single writer, multiple readers scenario.
"""

import threading
from collections import deque
from datetime import datetime
from typing import Any, Deque, Generic, List, Optional, TypeVar

import numpy as np

T = TypeVar("T")


class RingBuffer(Generic[T]):
    """
    Thread-safe ring buffer with fixed capacity.

    Efficiently stores the most recent N items with O(1) append and O(N) retrieval.
    Automatically overwrites oldest items when capacity is reached.

    Examples:
        >>> buffer = RingBuffer[dict](capacity=1000)
        >>> buffer.append({"price": 100.5, "qty": 1.5})
        >>> recent = buffer.get_recent(100)  # Get last 100 items
        >>> all_items = buffer.get_all()     # Get all items
    """

    def __init__(self, capacity: int):
        """
        Initialize ring buffer with fixed capacity.

        Args:
            capacity: Maximum number of items to store

        Raises:
            ValueError: If capacity is not positive
        """
        if capacity <= 0:
            raise ValueError(f"Capacity must be positive, got {capacity}")

        self._capacity = capacity
        self._buffer: Deque[T] = deque(maxlen=capacity)
        self._lock = threading.RLock()
        self._total_added = 0

    def append(self, item: T) -> None:
        """
        Append item to buffer.

        If buffer is full, oldest item is automatically removed.
        Thread-safe operation.

        Args:
            item: Item to append
        """
        with self._lock:
            self._buffer.append(item)
            self._total_added += 1

    def extend(self, items: List[T]) -> None:
        """
        Append multiple items to buffer.

        More efficient than calling append() repeatedly.

        Args:
            items: List of items to append
        """
        with self._lock:
            self._buffer.extend(items)
            self._total_added += len(items)

    def get_recent(self, n: int) -> List[T]:
        """
        Get the last N items from buffer.

        Returns fewer items if buffer contains less than N items.

        Args:
            n: Number of recent items to retrieve

        Returns:
            List of recent items (oldest to newest)
        """
        with self._lock:
            if n >= len(self._buffer):
                return list(self._buffer)

            # Get last n items efficiently
            return list(self._buffer)[-n:]

    def get_all(self) -> List[T]:
        """
        Get all items currently in buffer.

        Returns:
            List of all items (oldest to newest)
        """
        with self._lock:
            return list(self._buffer)

    def get_since_time(self, timestamp: datetime, time_field: str = "timestamp") -> List[T]:
        """
        Get all items since specified timestamp.

        Assumes items have a time field (datetime or Unix timestamp).

        Args:
            timestamp: Cutoff timestamp
            time_field: Name of the time field in items

        Returns:
            List of items after timestamp
        """
        with self._lock:
            result = []
            for item in reversed(self._buffer):
                # Handle both dict and object attribute access
                if isinstance(item, dict):
                    item_time = item.get(time_field)
                else:
                    item_time = getattr(item, time_field, None)

                if item_time is None:
                    continue

                # Convert Unix timestamp to datetime if needed
                if isinstance(item_time, (int, float)):
                    item_time = datetime.fromtimestamp(item_time / 1000)  # Assuming ms

                if item_time < timestamp:
                    break

                result.append(item)

            return list(reversed(result))

    def clear(self) -> None:
        """
        Clear all items from buffer.

        Thread-safe operation.
        """
        with self._lock:
            self._buffer.clear()

    def __len__(self) -> int:
        """Get current number of items in buffer."""
        return len(self._buffer)

    @property
    def capacity(self) -> int:
        """Get maximum capacity of buffer."""
        return self._capacity

    @property
    def is_full(self) -> bool:
        """Check if buffer is at capacity."""
        return len(self._buffer) >= self._capacity

    @property
    def total_added(self) -> int:
        """Get total number of items added since creation."""
        return self._total_added

    def get_stats(self) -> dict:
        """
        Get buffer statistics.

        Returns:
            Dictionary with buffer statistics
        """
        with self._lock:
            return {
                "capacity": self._capacity,
                "current_size": len(self._buffer),
                "is_full": self.is_full,
                "total_added": self._total_added,
                "utilization": len(self._buffer) / self._capacity,
            }

    def __repr__(self) -> str:
        """String representation of buffer."""
        return (
            f"RingBuffer(capacity={self._capacity}, "
            f"size={len(self._buffer)}, "
            f"total_added={self._total_added})"
        )


class NumericRingBuffer:
    """
    Specialized ring buffer for numeric data with efficient numpy operations.

    Optimized for time-series numeric data with built-in statistical methods.
    Uses numpy arrays for fast vectorized operations.

    Examples:
        >>> buffer = NumericRingBuffer(capacity=1000)
        >>> buffer.append(100.5)
        >>> buffer.extend([101.0, 102.5, 103.0])
        >>> stats = buffer.get_stats()  # mean, std, min, max, etc.
    """

    def __init__(self, capacity: int):
        """
        Initialize numeric ring buffer.

        Args:
            capacity: Maximum number of values to store

        Raises:
            ValueError: If capacity is not positive
        """
        if capacity <= 0:
            raise ValueError(f"Capacity must be positive, got {capacity}")

        self._capacity = capacity
        self._buffer = np.full(capacity, np.nan, dtype=np.float64)
        self._head = 0  # Next write position
        self._size = 0  # Current number of elements
        self._lock = threading.RLock()
        self._total_added = 0

    def append(self, value: float) -> None:
        """
        Append value to buffer.

        Args:
            value: Numeric value to append
        """
        with self._lock:
            self._buffer[self._head] = value
            self._head = (self._head + 1) % self._capacity
            self._size = min(self._size + 1, self._capacity)
            self._total_added += 1

    def extend(self, values: List[float]) -> None:
        """
        Append multiple values to buffer.

        Args:
            values: List of numeric values
        """
        if not values:
            return

        values_array = np.array(values, dtype=np.float64)

        with self._lock:
            n = len(values)

            if n >= self._capacity:
                # If adding more than capacity, just keep the last capacity items
                self._buffer[:] = values_array[-self._capacity :]
                self._head = 0
                self._size = self._capacity
            else:
                # Add values in chunks if wrapping around
                remaining_space = self._capacity - self._head

                if n <= remaining_space:
                    # No wrap-around needed
                    self._buffer[self._head : self._head + n] = values_array
                    self._head = (self._head + n) % self._capacity
                else:
                    # Wrap-around needed
                    self._buffer[self._head :] = values_array[:remaining_space]
                    wrap_size = n - remaining_space
                    self._buffer[:wrap_size] = values_array[remaining_space:]
                    self._head = wrap_size

                self._size = min(self._size + n, self._capacity)

            self._total_added += n

    def get_array(self) -> np.ndarray:
        """
        Get all values as numpy array in chronological order.

        Returns:
            Numpy array of values (oldest to newest)
        """
        with self._lock:
            if self._size == 0:
                return np.array([])

            if self._size < self._capacity:
                # Buffer not full yet
                return self._buffer[: self._size].copy()

            # Buffer is full, need to reorder
            return np.concatenate([self._buffer[self._head :], self._buffer[: self._head]])

    def get_recent(self, n: int) -> np.ndarray:
        """
        Get last N values.

        Args:
            n: Number of recent values to retrieve

        Returns:
            Numpy array of recent values
        """
        with self._lock:
            if n >= self._size:
                return self.get_array()

            if self._size < self._capacity:
                # Buffer not full
                start = max(0, self._size - n)
                return self._buffer[start : self._size].copy()

            # Buffer is full, get last n values
            start_idx = (self._head - n) % self._capacity
            if start_idx < self._head:
                return self._buffer[start_idx : self._head].copy()
            else:
                return np.concatenate([self._buffer[start_idx:], self._buffer[: self._head]])

    def get_stats(self) -> dict:
        """
        Calculate statistics for current buffer contents.

        Returns:
            Dictionary with statistical metrics
        """
        with self._lock:
            if self._size == 0:
                return {
                    "count": 0,
                    "mean": np.nan,
                    "std": np.nan,
                    "min": np.nan,
                    "max": np.nan,
                    "sum": np.nan,
                }

            data = self.get_array()

            return {
                "count": len(data),
                "mean": np.mean(data),
                "std": np.std(data),
                "min": np.min(data),
                "max": np.max(data),
                "sum": np.sum(data),
                "median": np.median(data),
                "p25": np.percentile(data, 25),
                "p75": np.percentile(data, 75),
            }

    def clear(self) -> None:
        """Clear all values from buffer."""
        with self._lock:
            self._buffer[:] = np.nan
            self._head = 0
            self._size = 0

    def __len__(self) -> int:
        """Get current number of values in buffer."""
        return self._size

    @property
    def capacity(self) -> int:
        """Get maximum capacity."""
        return self._capacity

    @property
    def is_full(self) -> bool:
        """Check if buffer is at capacity."""
        return self._size >= self._capacity

    def __repr__(self) -> str:
        """String representation."""
        return f"NumericRingBuffer(capacity={self._capacity}, size={self._size})"
