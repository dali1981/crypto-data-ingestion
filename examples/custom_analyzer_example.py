"""
Custom Analyzer Example

Demonstrates how to create custom analyzers for specific market patterns
or trading strategies.

This example implements three custom analyzers:
1. PriceMovementAnalyzer - Tracks price changes and momentum
2. TradeSize Analyzer - Analyzes trade size distribution
3. VolumeClusterAnalyzer - Detects volume clustering patterns

Usage:
    uv run python examples/custom_analyzer_example.py
"""

import asyncio
import logging
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

from binance_tick_data.analyzers import BaseAnalyzer
from binance_tick_data.consumers import RealtimeConsumer, ConsumerConfig
from binance_tick_data.sources.schemas import Trade

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PriceMovementAnalyzer(BaseAnalyzer):
    """
    Analyzes price movement patterns and momentum.

    Tracks:
    - Price change rate
    - Momentum (EMA of price changes)
    - Volatility (rolling std of returns)
    - Trend direction
    """

    def __init__(self, window_size: int = 60, ema_alpha: float = 0.1):
        """
        Initialize analyzer.

        Args:
            window_size: Analysis window in seconds
            ema_alpha: Exponential moving average smoothing factor (0-1)
        """
        super().__init__(name="price_movement", window_size=window_size)
        self.ema_alpha = ema_alpha

        # Price tracking
        self._prices: deque = deque(maxlen=100)
        self._timestamps: deque = deque(maxlen=100)

        # Momentum
        self._momentum = 0.0  # EMA of price changes
        self._prev_price: Optional[float] = None

        # Statistics
        self._price_changes: List[float] = []

    async def on_trade(self, trade: Trade) -> Optional[Dict[str, Any]]:
        """Process individual trade."""
        price = float(trade.price)
        timestamp = datetime.fromtimestamp(trade.time / 1000)

        self._prices.append(price)
        self._timestamps.append(timestamp)

        # Calculate price change
        if self._prev_price is not None:
            price_change = price - self._prev_price
            pct_change = (price_change / self._prev_price) * 100

            # Update momentum (EMA of price changes)
            self._momentum = (
                self.ema_alpha * pct_change + (1 - self.ema_alpha) * self._momentum
            )

            self._price_changes.append(pct_change)

        self._prev_price = price

        return None  # No per-trade metrics

    async def on_window_close(self, window_end: datetime) -> Dict[str, Any]:
        """Compute metrics when window closes."""
        if len(self._prices) < 2:
            return self._empty_metrics()

        prices = np.array(list(self._prices))

        # Calculate metrics
        price_change = prices[-1] - prices[0]
        price_change_pct = (price_change / prices[0]) * 100

        metrics = {
            "start_price": float(prices[0]),
            "end_price": float(prices[-1]),
            "price_change": float(price_change),
            "price_change_pct": float(price_change_pct),
            "momentum": float(self._momentum),
            "price_volatility": float(np.std(prices)),
            "price_range": float(prices.max() - prices.min()),
        }

        # Trend direction
        if self._momentum > 0.01:
            metrics["trend"] = "BULLISH"
        elif self._momentum < -0.01:
            metrics["trend"] = "BEARISH"
        else:
            metrics["trend"] = "NEUTRAL"

        # Volatility level
        if len(self._price_changes) > 10:
            volatility = np.std(self._price_changes)
            metrics["volatility_score"] = float(volatility)

            if volatility > 0.1:
                metrics["volatility_level"] = "HIGH"
            elif volatility > 0.05:
                metrics["volatility_level"] = "MEDIUM"
            else:
                metrics["volatility_level"] = "LOW"

        # Reset
        self._price_changes.clear()

        return metrics

    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current metrics."""
        if len(self._prices) < 2:
            return {"momentum": 0.0, "trend": "NEUTRAL"}

        return {
            "current_price": float(self._prices[-1]),
            "momentum": float(self._momentum),
            "trend": "BULLISH" if self._momentum > 0.01 else "BEARISH" if self._momentum < -0.01 else "NEUTRAL"
        }

    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics."""
        return {
            "price_change": 0.0,
            "momentum": 0.0,
            "trend": "NEUTRAL",
            "volatility_level": "UNKNOWN"
        }


class TradeSizeAnalyzer(BaseAnalyzer):
    """
    Analyzes trade size distribution and detects large trades.

    Tracks:
    - Trade size percentiles
    - Large trade detection (outliers)
    - Average trade sizes by side (buy/sell)
    """

    def __init__(self, window_size: int = 60, large_trade_threshold: float = 2.0):
        """
        Initialize analyzer.

        Args:
            window_size: Analysis window in seconds
            large_trade_threshold: Z-score threshold for large trade detection
        """
        super().__init__(name="trade_size", window_size=window_size)
        self.large_trade_threshold = large_trade_threshold

        # Trade sizes
        self._trade_sizes: List[float] = []
        self._buy_sizes: List[float] = []
        self._sell_sizes: List[float] = []

        # Large trades
        self._large_trades_count = 0

    async def on_trade(self, trade: Trade) -> Optional[Dict[str, Any]]:
        """Process individual trade."""
        size = float(trade.qty)
        is_buy = not trade.isBuyerMaker

        self._trade_sizes.append(size)

        if is_buy:
            self._buy_sizes.append(size)
        else:
            self._sell_sizes.append(size)

        # Detect large trades (outliers)
        if len(self._trade_sizes) > 20:
            mean_size = np.mean(self._trade_sizes)
            std_size = np.std(self._trade_sizes)

            if std_size > 0:
                z_score = (size - mean_size) / std_size
                if abs(z_score) > self.large_trade_threshold:
                    self._large_trades_count += 1

        return None

    async def on_window_close(self, window_end: datetime) -> Dict[str, Any]:
        """Compute metrics when window closes."""
        if not self._trade_sizes:
            return self._empty_metrics()

        sizes_array = np.array(self._trade_sizes)

        metrics = {
            "trade_count": len(self._trade_sizes),
            "total_volume": float(sizes_array.sum()),
            "avg_size": float(sizes_array.mean()),
            "median_size": float(np.median(sizes_array)),
            "size_std": float(sizes_array.std()),
            "min_size": float(sizes_array.min()),
            "max_size": float(sizes_array.max()),
            "p25_size": float(np.percentile(sizes_array, 25)),
            "p75_size": float(np.percentile(sizes_array, 75)),
            "p95_size": float(np.percentile(sizes_array, 95)),
            "large_trades_count": self._large_trades_count,
        }

        # Buy vs sell sizes
        if self._buy_sizes:
            metrics["avg_buy_size"] = float(np.mean(self._buy_sizes))
        if self._sell_sizes:
            metrics["avg_sell_size"] = float(np.mean(self._sell_sizes))

        # Size distribution
        small_trades = sum(1 for s in self._trade_sizes if s < metrics["p25_size"])
        large_trades = sum(1 for s in self._trade_sizes if s > metrics["p75_size"])

        metrics["small_trades_pct"] = (small_trades / len(self._trade_sizes)) * 100
        metrics["large_trades_pct"] = (large_trades / len(self._trade_sizes)) * 100

        # Reset
        self._trade_sizes.clear()
        self._buy_sizes.clear()
        self._sell_sizes.clear()
        self._large_trades_count = 0

        return metrics

    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current metrics."""
        if not self._trade_sizes:
            return {"trade_count": 0}

        return {
            "trade_count": len(self._trade_sizes),
            "avg_size": float(np.mean(self._trade_sizes)),
            "large_trades_count": self._large_trades_count,
        }

    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics."""
        return {
            "trade_count": 0,
            "avg_size": 0.0,
            "large_trades_count": 0,
        }


class VolumeClusterAnalyzer(BaseAnalyzer):
    """
    Detects volume clustering patterns.

    Identifies periods of:
    - High volume activity (bursts)
    - Low volume activity (quiet periods)
    - Volume acceleration/deceleration
    """

    def __init__(self, window_size: int = 60, burst_threshold: float = 2.0):
        """
        Initialize analyzer.

        Args:
            window_size: Analysis window in seconds
            burst_threshold: Z-score threshold for volume burst detection
        """
        super().__init__(name="volume_cluster", window_size=window_size)
        self.burst_threshold = burst_threshold

        # Volume tracking (per second)
        self._volume_per_second: Dict[int, float] = {}
        self._current_second = 0

        # Burst detection
        self._burst_count = 0
        self._quiet_count = 0

    async def on_trade(self, trade: Trade) -> Optional[Dict[str, Any]]:
        """Process individual trade."""
        timestamp_seconds = int(trade.time / 1000)
        volume = float(trade.qty)

        if timestamp_seconds != self._current_second:
            self._current_second = timestamp_seconds

        if timestamp_seconds not in self._volume_per_second:
            self._volume_per_second[timestamp_seconds] = 0.0

        self._volume_per_second[timestamp_seconds] += volume

        return None

    async def on_window_close(self, window_end: datetime) -> Dict[str, Any]:
        """Compute metrics when window closes."""
        if not self._volume_per_second:
            return self._empty_metrics()

        volumes = np.array(list(self._volume_per_second.values()))

        metrics = {
            "periods": len(volumes),
            "total_volume": float(volumes.sum()),
            "avg_volume_per_second": float(volumes.mean()),
            "volume_std": float(volumes.std()),
            "max_volume_burst": float(volumes.max()),
            "min_volume": float(volumes.min()),
        }

        # Detect bursts and quiet periods
        mean_vol = volumes.mean()
        std_vol = volumes.std()

        if std_vol > 0:
            for vol in volumes:
                z_score = (vol - mean_vol) / std_vol

                if z_score > self.burst_threshold:
                    self._burst_count += 1
                elif z_score < -self.burst_threshold:
                    self._quiet_count += 1

            metrics["burst_periods"] = self._burst_count
            metrics["quiet_periods"] = self._quiet_count
            metrics["burst_rate"] = (self._burst_count / len(volumes)) * 100

        # Volume acceleration (trend)
        if len(volumes) > 2:
            first_half = volumes[:len(volumes)//2].mean()
            second_half = volumes[len(volumes)//2:].mean()

            acceleration = ((second_half - first_half) / first_half) * 100
            metrics["volume_acceleration_pct"] = float(acceleration)

            if acceleration > 20:
                metrics["volume_trend"] = "ACCELERATING"
            elif acceleration < -20:
                metrics["volume_trend"] = "DECELERATING"
            else:
                metrics["volume_trend"] = "STABLE"

        # Reset
        self._volume_per_second.clear()
        self._burst_count = 0
        self._quiet_count = 0

        return metrics

    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current metrics."""
        if not self._volume_per_second:
            return {"periods": 0}

        volumes = list(self._volume_per_second.values())
        return {
            "periods": len(volumes),
            "avg_volume_per_second": float(np.mean(volumes)),
            "burst_count": self._burst_count,
        }

    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics."""
        return {
            "periods": 0,
            "total_volume": 0.0,
            "burst_periods": 0,
        }


async def main():
    """Main execution function."""
    logger.info("Starting custom analyzer example...")

    # Configure consumer
    config = ConsumerConfig(
        symbols=["BTCUSDT"],
        buffer_size=10000,
        update_interval=0.1,
    )

    # Create consumer
    consumer = RealtimeConsumer(config)

    # Create custom analyzers
    price_movement = PriceMovementAnalyzer(window_size=60)
    trade_size = TradeSizeAnalyzer(window_size=60, large_trade_threshold=2.0)
    volume_cluster = VolumeClusterAnalyzer(window_size=60, burst_threshold=2.0)

    # Register analyzers
    consumer.register_analyzer(price_movement)
    consumer.register_analyzer(trade_size)
    consumer.register_analyzer(volume_cluster)

    logger.info("Registered 3 custom analyzers")

    try:
        # Start consumer
        await consumer.start()
        logger.info("Consumer started! Collecting data...")

        # Run for 60 seconds and print metrics every 10 seconds
        for i in range(6):
            await asyncio.sleep(10)

            print("\n" + "=" * 80)
            print(f"Metrics at {(i+1)*10} seconds")
            print("=" * 80)

            # Price movement
            pm_metrics = price_movement.get_current_metrics()
            print(f"\n📊 PRICE MOVEMENT:")
            print(f"  Current Price: {pm_metrics.get('current_price', 0):.2f}")
            print(f"  Momentum: {pm_metrics.get('momentum', 0):.4f}")
            print(f"  Trend: {pm_metrics.get('trend', 'N/A')}")

            # Trade size
            ts_metrics = trade_size.get_current_metrics()
            print(f"\n📏 TRADE SIZE:")
            print(f"  Trade Count: {ts_metrics.get('trade_count', 0)}")
            print(f"  Avg Size: {ts_metrics.get('avg_size', 0):.6f}")
            print(f"  Large Trades: {ts_metrics.get('large_trades_count', 0)}")

            # Volume cluster
            vc_metrics = volume_cluster.get_current_metrics()
            print(f"\n💥 VOLUME CLUSTERING:")
            print(f"  Periods Tracked: {vc_metrics.get('periods', 0)}")
            print(f"  Avg Volume/s: {vc_metrics.get('avg_volume_per_second', 0):.4f}")
            print(f"  Bursts Detected: {vc_metrics.get('burst_count', 0)}")

        print("\n" + "=" * 80)
        print("✓ Example complete!")

    except KeyboardInterrupt:
        logger.info("Interrupted by user")

    finally:
        # Cleanup
        await consumer.stop()
        logger.info("Consumer stopped")


if __name__ == "__main__":
    asyncio.run(main())
