"""
Order Flow Analyzer for market microstructure analysis.

Analyzes the direction and intensity of trading activity, computing metrics like:
- Buy vs sell pressure
- Order imbalance
- Trade direction persistence
- Order flow toxicity

References:
- Easley, D., & O'Hara, M. (2012). "Flow toxicity and liquidity in a high-frequency world"
- Cont, R., Kukanov, A., & Stoikov, S. (2014). "The price impact of order book events"
"""

from collections import deque
from datetime import datetime
from typing import Any, Dict, Optional

import numpy as np

from .base_analyzer import BaseAnalyzer
from ..sources.schemas import Trade


class OrderFlowAnalyzer(BaseAnalyzer):
    """
    Analyzes order flow dynamics and trade direction.

    Tracks buy/sell pressure, order imbalance, and trade direction
    persistence over configurable time windows.

    Metrics computed:
    - Buy/sell trade counts and volumes
    - Order imbalance (buy - sell) / (buy + sell)
    - Trade direction persistence (runs test)
    - Order flow toxicity (adverse selection metric)
    - Cumulative order imbalance

    Examples:
        >>> from binance_tick_data.consumers import ConsumerConfig, OrderFlowConfig
        >>> analyzer = OrderFlowAnalyzer(OrderFlowConfig(
        ...     window_size=60,
        ...     compute_toxicity=True
        ... ))
        >>> consumer.register_analyzer(analyzer)
    """

    def __init__(
        self,
        window_size: int = 60,
        compute_toxicity: bool = True,
        persistence_test: bool = True,
        imbalance_threshold: float = 0.1,
    ):
        """
        Initialize order flow analyzer.

        Args:
            window_size: Analysis window in seconds
            compute_toxicity: Whether to compute flow toxicity metrics
            persistence_test: Whether to perform runs test for direction persistence
            imbalance_threshold: Threshold for significant imbalance alerts
        """
        super().__init__(name="order_flow", window_size=window_size)

        self.compute_toxicity = compute_toxicity
        self.persistence_test = persistence_test
        self.imbalance_threshold = imbalance_threshold

        # Trade tracking
        self._trades: deque = deque()  # (timestamp, is_buy, price, quantity)

        # Cumulative metrics
        self._buy_count = 0
        self._sell_count = 0
        self._buy_volume = 0.0
        self._sell_volume = 0.0
        self._buy_dollar_volume = 0.0
        self._sell_dollar_volume = 0.0

        # For toxicity calculation
        self._price_changes: deque = deque(maxlen=100)  # Recent price changes
        self._trade_directions: deque = deque(maxlen=100)  # Recent directions (1=buy, -1=sell)

        # For persistence test
        self._direction_sequence: list = []  # Sequence of trade directions

    async def on_trade(self, trade: Trade) -> Optional[Dict[str, Any]]:
        """
        Process individual trade.

        Args:
            trade: Trade object

        Returns:
            None (metrics computed at window close)
        """
        timestamp = datetime.fromtimestamp(trade.time / 1000)
        is_buy = not trade.isBuyerMaker  # Buyer is aggressor = buy trade
        price = float(trade.price)
        quantity = float(trade.qty)

        # Add to trade buffer
        self._trades.append((timestamp, is_buy, price, quantity))

        # Update counters
        if is_buy:
            self._buy_count += 1
            self._buy_volume += quantity
            self._buy_dollar_volume += price * quantity
        else:
            self._sell_count += 1
            self._sell_volume += quantity
            self._sell_dollar_volume += price * quantity

        # Track direction for toxicity/persistence
        direction = 1 if is_buy else -1
        self._trade_directions.append(direction)
        self._direction_sequence.append(direction)

        # Track price changes for toxicity
        if len(self._price_changes) > 0:
            prev_price = self._trades[-2][2] if len(self._trades) > 1 else price
            price_change = price - prev_price
            self._price_changes.append(price_change)

        return None  # No per-trade metrics

    async def on_window_close(self, window_end: datetime) -> Dict[str, Any]:
        """
        Compute order flow metrics for the window.

        Args:
            window_end: Window end timestamp

        Returns:
            Dictionary of order flow metrics
        """
        total_trades = self._buy_count + self._sell_count

        if total_trades == 0:
            return self._empty_metrics()

        # Basic order flow metrics
        metrics = {
            "buy_count": self._buy_count,
            "sell_count": self._sell_count,
            "total_trades": total_trades,
            "buy_volume": self._buy_volume,
            "sell_volume": self._sell_volume,
            "total_volume": self._buy_volume + self._sell_volume,
            "buy_dollar_volume": self._buy_dollar_volume,
            "sell_dollar_volume": self._sell_dollar_volume,
            "total_dollar_volume": self._buy_dollar_volume + self._sell_dollar_volume,
        }

        # Order imbalance (normalized)
        if total_trades > 0:
            metrics["order_imbalance"] = (self._buy_count - self._sell_count) / total_trades
            metrics["volume_imbalance"] = (
                (self._buy_volume - self._sell_volume) / (self._buy_volume + self._sell_volume)
                if (self._buy_volume + self._sell_volume) > 0
                else 0.0
            )
            metrics["dollar_imbalance"] = (
                (self._buy_dollar_volume - self._sell_dollar_volume)
                / (self._buy_dollar_volume + self._sell_dollar_volume)
                if (self._buy_dollar_volume + self._sell_dollar_volume) > 0
                else 0.0
            )
        else:
            metrics["order_imbalance"] = 0.0
            metrics["volume_imbalance"] = 0.0
            metrics["dollar_imbalance"] = 0.0

        # Trade size metrics
        if self._buy_count > 0:
            metrics["avg_buy_size"] = self._buy_volume / self._buy_count
            metrics["avg_buy_dollar_size"] = self._buy_dollar_volume / self._buy_count
        else:
            metrics["avg_buy_size"] = 0.0
            metrics["avg_buy_dollar_size"] = 0.0

        if self._sell_count > 0:
            metrics["avg_sell_size"] = self._sell_volume / self._sell_count
            metrics["avg_sell_dollar_size"] = self._sell_dollar_volume / self._sell_count
        else:
            metrics["avg_sell_size"] = 0.0
            metrics["avg_sell_dollar_size"] = 0.0

        # Ratios
        metrics["buy_sell_ratio"] = (
            self._buy_count / self._sell_count if self._sell_count > 0 else float("inf")
        )
        metrics["volume_buy_sell_ratio"] = (
            self._buy_volume / self._sell_volume if self._sell_volume > 0 else float("inf")
        )

        # Alert flag for significant imbalance
        metrics["significant_imbalance"] = (
            abs(metrics["order_imbalance"]) > self.imbalance_threshold
        )

        # Optional: Trade direction persistence (runs test)
        if self.persistence_test and len(self._direction_sequence) > 10:
            metrics["direction_persistence"] = self._compute_persistence()
        else:
            metrics["direction_persistence"] = None

        # Optional: Order flow toxicity
        if self.compute_toxicity and len(self._price_changes) > 10:
            metrics["flow_toxicity"] = self._compute_toxicity_metric()
        else:
            metrics["flow_toxicity"] = None

        # Reset for next window
        self._reset_window()

        return metrics

    def get_current_metrics(self) -> Dict[str, Any]:
        """
        Get current order flow metrics (mid-window).

        Returns:
            Dictionary of current metrics
        """
        total_trades = self._buy_count + self._sell_count

        if total_trades == 0:
            return self._empty_metrics()

        return {
            "buy_count": self._buy_count,
            "sell_count": self._sell_count,
            "total_trades": total_trades,
            "buy_volume": self._buy_volume,
            "sell_volume": self._sell_volume,
            "order_imbalance": (
                (self._buy_count - self._sell_count) / total_trades if total_trades > 0 else 0.0
            ),
            "volume_imbalance": (
                (self._buy_volume - self._sell_volume) / (self._buy_volume + self._sell_volume)
                if (self._buy_volume + self._sell_volume) > 0
                else 0.0
            ),
            "buy_sell_ratio": (
                self._buy_count / self._sell_count if self._sell_count > 0 else float("inf")
            ),
        }

    def _reset_window(self) -> None:
        """Reset all counters for new window."""
        self._buy_count = 0
        self._sell_count = 0
        self._buy_volume = 0.0
        self._sell_volume = 0.0
        self._buy_dollar_volume = 0.0
        self._sell_dollar_volume = 0.0
        self._trades.clear()
        self._direction_sequence.clear()

    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics structure."""
        return {
            "buy_count": 0,
            "sell_count": 0,
            "total_trades": 0,
            "buy_volume": 0.0,
            "sell_volume": 0.0,
            "total_volume": 0.0,
            "order_imbalance": 0.0,
            "volume_imbalance": 0.0,
            "dollar_imbalance": 0.0,
            "buy_sell_ratio": 0.0,
            "significant_imbalance": False,
            "direction_persistence": None,
            "flow_toxicity": None,
        }

    def _compute_persistence(self) -> float:
        """
        Compute trade direction persistence using runs test.

        Tests whether trade directions are random or show persistence
        (clustering of buys or sells).

        Returns:
            Z-score (positive = persistence, negative = alternation)
        """
        if len(self._direction_sequence) < 10:
            return 0.0

        # Count runs (sequences of same direction)
        runs = 1
        for i in range(1, len(self._direction_sequence)):
            if self._direction_sequence[i] != self._direction_sequence[i - 1]:
                runs += 1

        n = len(self._direction_sequence)
        n_buys = sum(1 for d in self._direction_sequence if d == 1)
        n_sells = n - n_buys

        if n_buys == 0 or n_sells == 0:
            return 0.0

        # Expected runs under randomness
        expected_runs = (2 * n_buys * n_sells / n) + 1

        # Standard deviation of runs
        variance = (2 * n_buys * n_sells * (2 * n_buys * n_sells - n)) / (n * n * (n - 1))
        std = np.sqrt(variance)

        if std == 0:
            return 0.0

        # Z-score (negative = persistence, positive = alternation)
        z_score = (runs - expected_runs) / std

        # Return negative to make positive = persistence
        return -z_score

    def _compute_toxicity_metric(self) -> float:
        """
        Compute order flow toxicity.

        Measures adverse selection: correlation between trade direction
        and subsequent price changes. High toxicity = informed trading.

        Returns:
            Toxicity score (0-1, higher = more toxic flow)
        """
        if len(self._price_changes) < 10 or len(self._trade_directions) < 10:
            return 0.0

        # Align arrays (price change after trade direction)
        min_len = min(len(self._price_changes), len(self._trade_directions) - 1)
        if min_len < 10:
            return 0.0

        directions = np.array(list(self._trade_directions)[:min_len])
        price_changes = np.array(list(self._price_changes)[:min_len])

        # Correlation between direction and price change
        if np.std(directions) == 0 or np.std(price_changes) == 0:
            return 0.0

        correlation = np.corrcoef(directions, price_changes)[0, 1]

        # Normalize to 0-1 range
        toxicity = (correlation + 1) / 2

        return float(toxicity)

    def reset(self) -> None:
        """Reset all analyzer state."""
        super().reset()
        self._reset_window()
        self._price_changes.clear()
        self._trade_directions.clear()
