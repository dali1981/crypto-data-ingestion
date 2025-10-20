"""
Liquidity Analyzer for market microstructure analysis.

Analyzes market liquidity through bid-ask spreads, order book depth,
and liquidity scores.

Key metrics:
- Bid-ask spread (absolute and relative)
- Market depth at multiple levels
- Liquidity score
- Spread volatility
- Depth imbalance

References:
- Amihud, Y. (2002). "Illiquidity and stock returns"
- Kyle, A. S. (1985). "Continuous auctions and insider trading"
"""

from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .base_analyzer import BaseAnalyzer
from ..sources.schemas import Trade


class LiquidityAnalyzer(BaseAnalyzer):
    """
    Analyzes market liquidity metrics.

    Tracks bid-ask spreads, market depth, and liquidity conditions
    using trade data and order book snapshots.

    IMPORTANT LIMITATION:
    Without real-time order book data, the "spread" estimated from trades
    is NOT the true bid-ask spread. Instead, it measures the price difference
    between recent buy and sell trades, which includes:
    - True bid-ask spread (typically 1-2 ticks)
    - Price drift/movement between trades
    - Market impact of trades

    For BTCUSDT at $110k:
    - True spread: ~$0.01-0.02 (0.0009-0.0018 bps)
    - Our estimate: ~0.01-0.1 bps (10-100x higher due to price movement)

    For TRUE spread measurement, use OrderBookLiquidityAnalyzer with depth stream.

    Metrics computed:
    - Effective spread estimate (from trades) - INCLUDES PRICE DRIFT
    - Spread volatility
    - Trade price dispersion
    - Liquidity score (trade frequency / volatility)
    - Average trade size (proxy for depth)

    Examples:
        >>> from binance_tick_data.consumers import LiquidityConfig
        >>> analyzer = LiquidityAnalyzer(LiquidityConfig(
        ...     window_size=60,
        ...     spread_method="effective"
        ... ))
        >>> consumer.register_analyzer(analyzer)
    """

    def __init__(
        self,
        window_size: int = 60,
        depth_levels: int = 10,
        spread_method: str = "mid",
        min_spread_threshold: float = 0.0001,
    ):
        """
        Initialize liquidity analyzer.

        Args:
            window_size: Analysis window in seconds
            depth_levels: Order book depth levels to analyze (when available)
            spread_method: Method for spread calculation ('mid', 'best', 'effective')
            min_spread_threshold: Minimum valid spread threshold
        """
        super().__init__(name="liquidity", window_size=window_size)

        self.depth_levels = depth_levels
        self.spread_method = spread_method
        self.min_spread_threshold = min_spread_threshold

        # Trade tracking
        self._trades: deque = deque()  # (timestamp, price, quantity, is_buy)
        self._prices: deque = deque(maxlen=1000)  # Recent prices

        # Spread tracking (estimated from trades)
        self._spreads: deque = deque(maxlen=100)  # Recent spread estimates

        # Price levels (for estimating depth)
        self._buy_prices: deque = deque(maxlen=100)
        self._sell_prices: deque = deque(maxlen=100)

    async def on_trade(self, trade: Trade) -> Optional[Dict[str, Any]]:
        """
        Process individual trade.

        Args:
            trade: Trade object

        Returns:
            None (metrics computed at window close)
        """
        timestamp = datetime.fromtimestamp(trade.time / 1000)
        price = float(trade.price)
        quantity = float(trade.qty)
        is_buy = not trade.isBuyerMaker

        # Add to trade buffer
        self._trades.append((timestamp, price, quantity, is_buy))
        self._prices.append(price)

        # Track buy/sell prices separately for spread estimation
        if is_buy:
            self._buy_prices.append(price)
        else:
            self._sell_prices.append(price)

        # Estimate spread if we have recent buys and sells
        if len(self._buy_prices) >= 2 and len(self._sell_prices) >= 2:
            # Effective spread: difference between recent buy and sell prices
            # Use multiple recent prices for better estimation
            buy_prices = list(self._buy_prices)[-5:]  # Last 5 buys
            sell_prices = list(self._sell_prices)[-5:]  # Last 5 sells

            # Average recent buy/sell prices
            avg_buy = sum(buy_prices) / len(buy_prices)
            avg_sell = sum(sell_prices) / len(sell_prices)

            # Buys execute at ask (higher), sells execute at bid (lower)
            # So we expect avg_buy > avg_sell
            if avg_buy > avg_sell:
                spread = avg_buy - avg_sell
                mid_price = (avg_buy + avg_sell) / 2
                relative_spread = spread / mid_price if mid_price > 0 else 0.0

                if relative_spread >= self.min_spread_threshold:
                    self._spreads.append(relative_spread)
            else:
                # If avg_sell >= avg_buy, market is very tight or inverted
                # Use absolute price difference as minimum spread estimate
                spread = abs(avg_buy - avg_sell)
                mid_price = (avg_buy + avg_sell) / 2
                relative_spread = spread / mid_price if mid_price > 0 else 0.0

                if relative_spread >= self.min_spread_threshold:
                    self._spreads.append(relative_spread)

        return None

    async def on_window_close(self, window_end: datetime) -> Dict[str, Any]:
        """
        Compute liquidity metrics for the window.

        Args:
            window_end: Window end timestamp

        Returns:
            Dictionary of liquidity metrics
        """
        if len(self._trades) == 0:
            return self._empty_metrics()

        metrics = {}

        # Trade statistics
        metrics["trade_count"] = len(self._trades)
        prices = [t[1] for t in self._trades]
        quantities = [t[2] for t in self._trades]

        # Price statistics
        metrics["avg_price"] = float(np.mean(prices))
        metrics["price_std"] = float(np.std(prices))
        metrics["price_min"] = float(np.min(prices))
        metrics["price_max"] = float(np.max(prices))
        metrics["price_range"] = metrics["price_max"] - metrics["price_min"]
        metrics["price_range_pct"] = (
            metrics["price_range"] / metrics["avg_price"] if metrics["avg_price"] > 0 else 0.0
        )

        # Trade size statistics
        metrics["avg_trade_size"] = float(np.mean(quantities))
        metrics["trade_size_std"] = float(np.std(quantities))
        metrics["total_volume"] = float(np.sum(quantities))

        # Spread metrics (estimated from trades)
        # NOTE: These include price drift, not just true spread!
        if len(self._spreads) > 0:
            spreads_array = np.array(list(self._spreads))
            metrics["effective_spread_mean"] = float(np.mean(spreads_array))
            metrics["effective_spread_std"] = float(np.std(spreads_array))
            metrics["effective_spread_median"] = float(np.median(spreads_array))
            metrics["effective_spread_min"] = float(np.min(spreads_array))
            metrics["effective_spread_max"] = float(np.max(spreads_array))

            # Spread volatility (higher = less liquid)
            metrics["spread_volatility"] = float(np.std(spreads_array))

            # Add interpretation help
            metrics["spread_note"] = "Includes price drift - not true bid-ask spread"
        else:
            metrics["effective_spread_mean"] = None
            metrics["effective_spread_std"] = None
            metrics["effective_spread_median"] = None
            metrics["effective_spread_min"] = None
            metrics["effective_spread_max"] = None
            metrics["spread_volatility"] = None
            metrics["spread_note"] = "Insufficient buy/sell trades for estimation"

        # Liquidity score (Amihud-inspired)
        # Higher trade frequency + lower volatility = more liquid
        if metrics["price_std"] > 0:
            metrics["liquidity_score"] = metrics["trade_count"] / metrics["price_std"]
        else:
            metrics["liquidity_score"] = float("inf")

        # Price impact estimate (std / avg_size)
        if metrics["avg_trade_size"] > 0:
            metrics["price_impact_estimate"] = metrics["price_std"] / metrics["avg_trade_size"]
        else:
            metrics["price_impact_estimate"] = 0.0

        # Trade arrival rate (trades per second)
        if len(self._trades) > 1:
            first_time = self._trades[0][0]
            last_time = self._trades[-1][0]
            duration = (last_time - first_time).total_seconds()
            if duration > 0:
                metrics["trade_arrival_rate"] = len(self._trades) / duration
            else:
                metrics["trade_arrival_rate"] = 0.0
        else:
            metrics["trade_arrival_rate"] = 0.0

        # Relative tick frequency (price changes)
        if len(self._prices) > 1:
            price_list = list(self._prices)
            tick_count = sum(
                1 for i in range(1, len(price_list)) if price_list[i] != price_list[i - 1]
            )
            metrics["tick_frequency"] = tick_count / len(price_list)
        else:
            metrics["tick_frequency"] = 0.0

        # Reset for next window
        self._reset_window()

        return metrics

    def get_current_metrics(self) -> Dict[str, Any]:
        """
        Get current liquidity metrics (mid-window).

        Returns:
            Dictionary of current metrics
        """
        if len(self._trades) == 0:
            return self._empty_metrics()

        prices = [t[1] for t in self._trades]
        quantities = [t[2] for t in self._trades]

        metrics = {
            "trade_count": len(self._trades),
            "avg_price": float(np.mean(prices)),
            "price_std": float(np.std(prices)),
            "avg_trade_size": float(np.mean(quantities)),
            "total_volume": float(np.sum(quantities)),
        }

        if len(self._spreads) > 0:
            metrics["effective_spread_mean"] = float(np.mean(list(self._spreads)))
        else:
            metrics["effective_spread_mean"] = None

        return metrics

    def _reset_window(self) -> None:
        """Reset all counters for new window."""
        self._trades.clear()
        # Keep recent prices and spreads for continuity
        # Don't clear _prices, _spreads, _buy_prices, _sell_prices

    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics structure."""
        return {
            "trade_count": 0,
            "avg_price": 0.0,
            "price_std": 0.0,
            "price_range": 0.0,
            "avg_trade_size": 0.0,
            "effective_spread_mean": None,
            "liquidity_score": 0.0,
            "trade_arrival_rate": 0.0,
        }

    def reset(self) -> None:
        """Reset all analyzer state."""
        super().reset()
        self._trades.clear()
        self._prices.clear()
        self._spreads.clear()
        self._buy_prices.clear()
        self._sell_prices.clear()


class OrderBookLiquidityAnalyzer(BaseAnalyzer):
    """
    Advanced liquidity analyzer using order book depth.

    Requires order book snapshot data for accurate liquidity analysis.
    Provides deeper insights into market microstructure.

    Metrics computed:
    - Bid-ask spread at multiple levels
    - Cumulative depth at each level
    - Depth imbalance (bid vs ask)
    - Weighted average spread
    - Liquidity density

    Note: This analyzer requires order book data to function.
    Use LiquidityAnalyzer if only trade data is available.
    """

    def __init__(self, window_size: int = 60, depth_levels: int = 10):
        """
        Initialize order book liquidity analyzer.

        Args:
            window_size: Analysis window in seconds
            depth_levels: Number of order book levels to analyze
        """
        super().__init__(name="orderbook_liquidity", window_size=window_size)
        self.depth_levels = depth_levels

        # Order book snapshots
        self._snapshots: deque = deque()  # (timestamp, bids, asks)

    def process_orderbook_snapshot(
        self, timestamp: datetime, bids: List[Tuple[float, float]], asks: List[Tuple[float, float]]
    ):
        """
        Process order book snapshot.

        Args:
            timestamp: Snapshot timestamp
            bids: List of (price, quantity) tuples
            asks: List of (price, quantity) tuples
        """
        self._snapshots.append((timestamp, bids, asks))

    async def on_trade(self, trade: Trade) -> Optional[Dict[str, Any]]:
        """Process trade (not used for order book analysis)."""
        return None

    async def on_window_close(self, window_end: datetime) -> Dict[str, Any]:
        """
        Compute order book liquidity metrics.

        Args:
            window_end: Window end timestamp

        Returns:
            Dictionary of liquidity metrics
        """
        if len(self._snapshots) == 0:
            return {"error": "No order book snapshots available"}

        # Analyze most recent snapshot
        timestamp, bids, asks = self._snapshots[-1]

        if not bids or not asks:
            return {"error": "Empty order book"}

        metrics = {}

        # Best bid/ask
        best_bid = bids[0][0]
        best_ask = asks[0][0]

        # Spread metrics
        spread = best_ask - best_bid
        mid_price = (best_bid + best_ask) / 2
        metrics["spread_absolute"] = spread
        metrics["spread_relative"] = spread / mid_price if mid_price > 0 else 0.0
        metrics["spread_bps"] = (spread / mid_price * 10000) if mid_price > 0 else 0.0

        # Depth at multiple levels
        levels = min(self.depth_levels, len(bids), len(asks))

        for i in range(levels):
            level = i + 1
            cum_bid_volume = sum(b[1] for b in bids[: level])
            cum_ask_volume = sum(a[1] for a in asks[: level])

            metrics[f"bid_volume_L{level}"] = cum_bid_volume
            metrics[f"ask_volume_L{level}"] = cum_ask_volume
            metrics[f"total_volume_L{level}"] = cum_bid_volume + cum_ask_volume

            # Depth imbalance at each level
            total = cum_bid_volume + cum_ask_volume
            if total > 0:
                metrics[f"depth_imbalance_L{level}"] = (cum_bid_volume - cum_ask_volume) / total
            else:
                metrics[f"depth_imbalance_L{level}"] = 0.0

        # Overall depth imbalance
        total_bid_volume = sum(b[1] for b in bids[:levels])
        total_ask_volume = sum(a[1] for a in asks[:levels])
        total_volume = total_bid_volume + total_ask_volume

        if total_volume > 0:
            metrics["depth_imbalance"] = (total_bid_volume - total_ask_volume) / total_volume
        else:
            metrics["depth_imbalance"] = 0.0

        # Weighted average spread
        weights = []
        spreads = []
        for i in range(min(5, len(bids), len(asks))):
            level_spread = asks[i][0] - bids[i][0]
            level_volume = bids[i][1] + asks[i][1]
            weights.append(level_volume)
            spreads.append(level_spread)

        if sum(weights) > 0:
            metrics["weighted_spread"] = (
                sum(s * w for s, w in zip(spreads, weights)) / sum(weights)
            )
        else:
            metrics["weighted_spread"] = spread

        # Reset for next window
        self._snapshots.clear()

        return metrics

    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current order book metrics."""
        if len(self._snapshots) == 0:
            return {"snapshot_count": 0}

        return {"snapshot_count": len(self._snapshots)}

    def reset(self) -> None:
        """Reset analyzer state."""
        super().reset()
        self._snapshots.clear()
