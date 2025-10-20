"""
Volume Profile Analyzer for market microstructure analysis.

Analyzes volume distribution across price levels, VWAP calculation,
and volume clustering patterns.

Key metrics:
- Real-time VWAP (Volume Weighted Average Price)
- Volume distribution by price bins
- POC (Point of Control - price with most volume)
- Value Area (price range containing X% of volume)
- Volume delta (buy volume - sell volume)

References:
- Dalton, J. F., Jones, E. T., & Dalton, R. B. (2007). "Mind Over Markets"
- Steidlmayer, J. P. (1984). "Market Profile"
"""

from collections import defaultdict, deque
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .base_analyzer import BaseAnalyzer
from ..sources.schemas import Trade


class VolumeProfileAnalyzer(BaseAnalyzer):
    """
    Analyzes volume distribution across price levels.

    Computes VWAP, volume profile histogram, POC, value area, and
    volume delta for market microstructure analysis.

    Metrics computed:
    - Real-time VWAP with optional decay
    - Volume histogram by price bins
    - POC (Point of Control)
    - Value Area (70% volume range by default)
    - Volume delta (buy - sell volume)
    - Volume-weighted price range

    Examples:
        >>> from binance_tick_data.consumers import VolumeProfileConfig
        >>> analyzer = VolumeProfileAnalyzer(VolumeProfileConfig(
        ...     window_size=60,
        ...     price_bins=50,
        ...     vwap_decay=0.99
        ... ))
        >>> consumer.register_analyzer(analyzer)
    """

    def __init__(
        self,
        window_size: int = 60,
        price_bins: int = 50,
        vwap_decay: float = 0.99,
        value_area_percent: float = 0.70,
    ):
        """
        Initialize volume profile analyzer.

        Args:
            window_size: Analysis window in seconds
            price_bins: Number of price bins for volume histogram
            vwap_decay: Exponential decay factor for VWAP (0-1, higher = slower decay)
            value_area_percent: Percentage of volume for value area (typically 0.70)
        """
        super().__init__(name="volume_profile", window_size=window_size)

        self.price_bins = price_bins
        self.vwap_decay = vwap_decay
        self.value_area_percent = value_area_percent

        # VWAP tracking
        self._vwap_numerator = 0.0  # Sum of (price * volume)
        self._vwap_denominator = 0.0  # Sum of volume

        # Volume profile (price -> volume mapping)
        self._volume_by_price: Dict[float, float] = defaultdict(float)
        self._buy_volume_by_price: Dict[float, float] = defaultdict(float)
        self._sell_volume_by_price: Dict[float, float] = defaultdict(float)

        # Trade tracking for binning
        self._trades: deque = deque()  # (price, volume, is_buy)

        # Price range tracking
        self._min_price: Optional[float] = None
        self._max_price: Optional[float] = None

    async def on_trade(self, trade: Trade) -> Optional[Dict[str, Any]]:
        """
        Process individual trade.

        Args:
            trade: Trade object

        Returns:
            None (metrics computed at window close)
        """
        price = float(trade.price)
        volume = float(trade.qty)
        is_buy = not trade.isBuyerMaker
        dollar_volume = price * volume

        # Update VWAP with exponential decay
        self._vwap_numerator = self._vwap_numerator * self.vwap_decay + dollar_volume
        self._vwap_denominator = self._vwap_denominator * self.vwap_decay + volume

        # Track price range
        if self._min_price is None or price < self._min_price:
            self._min_price = price
        if self._max_price is None or price > self._max_price:
            self._max_price = price

        # Add to trade buffer
        self._trades.append((price, volume, is_buy))

        # Update volume profile
        self._volume_by_price[price] += volume
        if is_buy:
            self._buy_volume_by_price[price] += volume
        else:
            self._sell_volume_by_price[price] += volume

        return None

    async def on_window_close(self, window_end: datetime) -> Dict[str, Any]:
        """
        Compute volume profile metrics for the window.

        Args:
            window_end: Window end timestamp

        Returns:
            Dictionary of volume profile metrics
        """
        if len(self._trades) == 0:
            return self._empty_metrics()

        metrics = {}

        # VWAP
        if self._vwap_denominator > 0:
            metrics["vwap"] = self._vwap_numerator / self._vwap_denominator
        else:
            metrics["vwap"] = 0.0

        # Total volumes
        total_volume = sum(t[1] for t in self._trades)
        buy_volume = sum(t[1] for t in self._trades if t[2])
        sell_volume = sum(t[1] for t in self._trades if not t[2])

        metrics["total_volume"] = total_volume
        metrics["buy_volume"] = buy_volume
        metrics["sell_volume"] = sell_volume
        metrics["volume_delta"] = buy_volume - sell_volume
        metrics["volume_delta_pct"] = (
            (buy_volume - sell_volume) / total_volume if total_volume > 0 else 0.0
        )

        # Price range
        if self._min_price and self._max_price:
            metrics["price_min"] = self._min_price
            metrics["price_max"] = self._max_price
            metrics["price_range"] = self._max_price - self._min_price
        else:
            metrics["price_min"] = 0.0
            metrics["price_max"] = 0.0
            metrics["price_range"] = 0.0

        # Create binned volume profile
        if self._min_price and self._max_price and self._max_price > self._min_price:
            bin_edges, volume_histogram, buy_histogram, sell_histogram = self._create_histogram()

            metrics["bin_edges"] = bin_edges.tolist()
            metrics["volume_histogram"] = volume_histogram.tolist()
            metrics["buy_histogram"] = buy_histogram.tolist()
            metrics["sell_histogram"] = sell_histogram.tolist()

            # Find POC (Point of Control) - price level with most volume
            poc_idx = np.argmax(volume_histogram)
            poc_price = (bin_edges[poc_idx] + bin_edges[poc_idx + 1]) / 2
            metrics["poc_price"] = float(poc_price)
            metrics["poc_volume"] = float(volume_histogram[poc_idx])

            # Calculate Value Area (price range containing value_area_percent of volume)
            value_area = self._calculate_value_area(bin_edges, volume_histogram)
            metrics["value_area_low"] = value_area[0]
            metrics["value_area_high"] = value_area[1]
            metrics["value_area_range"] = value_area[1] - value_area[0]

            # Volume concentration (Herfindahl index)
            if total_volume > 0:
                volume_shares = volume_histogram / total_volume
                herfindahl = np.sum(volume_shares**2)
                metrics["volume_concentration"] = float(herfindahl)
            else:
                metrics["volume_concentration"] = 0.0

        else:
            metrics["bin_edges"] = []
            metrics["volume_histogram"] = []
            metrics["poc_price"] = None
            metrics["value_area_low"] = None
            metrics["value_area_high"] = None

        # Volume-weighted price statistics
        prices = np.array([t[0] for t in self._trades])
        volumes = np.array([t[1] for t in self._trades])

        if total_volume > 0:
            metrics["volume_weighted_std"] = float(
                np.sqrt(np.sum(volumes * (prices - metrics["vwap"]) ** 2) / total_volume)
            )
        else:
            metrics["volume_weighted_std"] = 0.0

        # Trade count
        metrics["trade_count"] = len(self._trades)

        # Reset for next window
        self._reset_window()

        return metrics

    def get_current_metrics(self) -> Dict[str, Any]:
        """
        Get current volume profile metrics (mid-window).

        Returns:
            Dictionary of current metrics
        """
        if len(self._trades) == 0:
            return self._empty_metrics()

        vwap = (
            self._vwap_numerator / self._vwap_denominator if self._vwap_denominator > 0 else 0.0
        )

        total_volume = sum(t[1] for t in self._trades)
        buy_volume = sum(t[1] for t in self._trades if t[2])
        sell_volume = sum(t[1] for t in self._trades if not t[2])

        return {
            "vwap": vwap,
            "total_volume": total_volume,
            "buy_volume": buy_volume,
            "sell_volume": sell_volume,
            "volume_delta": buy_volume - sell_volume,
            "trade_count": len(self._trades),
        }

    def _create_histogram(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Create volume histogram across price bins.

        Returns:
            Tuple of (bin_edges, volume_histogram, buy_histogram, sell_histogram)
        """
        # Create price bins
        bin_edges = np.linspace(self._min_price, self._max_price, self.price_bins + 1)

        # Initialize histograms
        volume_histogram = np.zeros(self.price_bins)
        buy_histogram = np.zeros(self.price_bins)
        sell_histogram = np.zeros(self.price_bins)

        # Bin each trade
        for price, volume, is_buy in self._trades:
            # Find bin index
            bin_idx = np.searchsorted(bin_edges, price, side="right") - 1
            bin_idx = max(0, min(bin_idx, self.price_bins - 1))  # Clamp to valid range

            volume_histogram[bin_idx] += volume
            if is_buy:
                buy_histogram[bin_idx] += volume
            else:
                sell_histogram[bin_idx] += volume

        return bin_edges, volume_histogram, buy_histogram, sell_histogram

    def _calculate_value_area(
        self, bin_edges: np.ndarray, volume_histogram: np.ndarray
    ) -> Tuple[float, float]:
        """
        Calculate Value Area (price range containing value_area_percent of volume).

        Args:
            bin_edges: Price bin edges
            volume_histogram: Volume in each bin

        Returns:
            Tuple of (value_area_low, value_area_high)
        """
        total_volume = np.sum(volume_histogram)
        target_volume = total_volume * self.value_area_percent

        if total_volume == 0:
            return (0.0, 0.0)

        # Find POC (starting point)
        poc_idx = np.argmax(volume_histogram)

        # Expand from POC until we reach target volume
        accumulated_volume = volume_histogram[poc_idx]
        low_idx = poc_idx
        high_idx = poc_idx

        while accumulated_volume < target_volume and (low_idx > 0 or high_idx < len(volume_histogram) - 1):
            # Decide whether to expand low or high
            can_expand_low = low_idx > 0
            can_expand_high = high_idx < len(volume_histogram) - 1

            if not can_expand_low:
                # Can only expand high
                high_idx += 1
                accumulated_volume += volume_histogram[high_idx]
            elif not can_expand_high:
                # Can only expand low
                low_idx -= 1
                accumulated_volume += volume_histogram[low_idx]
            else:
                # Choose direction with more volume
                low_volume = volume_histogram[low_idx - 1]
                high_volume = volume_histogram[high_idx + 1]

                if low_volume >= high_volume:
                    low_idx -= 1
                    accumulated_volume += volume_histogram[low_idx]
                else:
                    high_idx += 1
                    accumulated_volume += volume_histogram[high_idx]

        # Convert indices to prices
        value_area_low = bin_edges[low_idx]
        value_area_high = bin_edges[high_idx + 1]

        return (float(value_area_low), float(value_area_high))

    def _reset_window(self) -> None:
        """Reset all counters for new window."""
        self._trades.clear()
        self._volume_by_price.clear()
        self._buy_volume_by_price.clear()
        self._sell_volume_by_price.clear()
        self._min_price = None
        self._max_price = None
        # Keep VWAP running (don't reset due to decay factor)

    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics structure."""
        return {
            "vwap": 0.0,
            "total_volume": 0.0,
            "buy_volume": 0.0,
            "sell_volume": 0.0,
            "volume_delta": 0.0,
            "trade_count": 0,
            "poc_price": None,
            "value_area_low": None,
            "value_area_high": None,
        }

    def reset(self) -> None:
        """Reset all analyzer state."""
        super().reset()
        self._vwap_numerator = 0.0
        self._vwap_denominator = 0.0
        self._reset_window()
