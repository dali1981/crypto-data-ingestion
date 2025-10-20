"""
Simple Streaming Example - Market Microstructure Analysis

Demonstrates basic usage of the streaming platform with real-time analyzers.

This example:
1. Connects to Binance WebSocket
2. Streams BTCUSDT trades
3. Runs order flow, liquidity, and volume profile analyzers
4. Prints metrics every 10 seconds
5. Runs for 60 seconds then exits

Usage:
    uv run python examples/simple_streaming_example.py
"""

import asyncio
import logging
from datetime import datetime

from binance_tick_data.consumers import RealtimeConsumer, ConsumerConfig
from binance_tick_data.analyzers import (
    OrderFlowAnalyzer,
    LiquidityAnalyzer,
    VolumeProfileAnalyzer,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def print_analyzer_metrics(analyzers: list, interval: int = 10):
    """
    Periodically print metrics from analyzers.

    Args:
        analyzers: List of analyzer instances
        interval: Print interval in seconds
    """
    while True:
        await asyncio.sleep(interval)

        print("\n" + "=" * 80)
        print(f"Metrics Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)

        for analyzer in analyzers:
            if not analyzer.enabled:
                continue

            print(f"\n{analyzer.name.upper()} ANALYZER")
            print("-" * 40)

            metrics = analyzer.get_current_metrics()

            for key, value in metrics.items():
                if isinstance(value, float):
                    print(f"  {key:30s}: {value:12.4f}")
                elif isinstance(value, int):
                    print(f"  {key:30s}: {value:12,d}")
                else:
                    print(f"  {key:30s}: {value}")


async def main():
    """Main execution function."""
    logger.info("Starting simple streaming example...")

    # Configure consumer
    config = ConsumerConfig(
        symbols=["BTCUSDT"],  # Single symbol for simplicity
        buffer_size=10000,
        update_interval=0.1,
        reconnect_delay=5,
    )

    # Create consumer
    consumer = RealtimeConsumer(config)

    # Create analyzers
    order_flow = OrderFlowAnalyzer(
        window_size=60,
        compute_toxicity=True,
        persistence_test=True,
        imbalance_threshold=0.1,
    )

    liquidity = LiquidityAnalyzer(
        window_size=60,
        spread_method="mid",
    )

    volume_profile = VolumeProfileAnalyzer(
        window_size=60,
        price_bins=50,
        vwap_decay=0.99,
    )

    # Register analyzers
    consumer.register_analyzer(order_flow)
    consumer.register_analyzer(liquidity)
    consumer.register_analyzer(volume_profile)

    analyzers = [order_flow, liquidity, volume_profile]

    logger.info(f"Registered {len(analyzers)} analyzers")

    # Subscribe to trade events (optional - for live feed)
    def trade_callback(symbol: str, trade):
        # Uncomment to see live trades (very verbose!)
        # print(f"[{symbol}] Trade: {trade.price} @ {trade.qty}")
        pass

    consumer.subscribe_to_trades(trade_callback)

    try:
        # Start consumer
        logger.info("Starting consumer...")
        await consumer.start()
        logger.info("Consumer started! Receiving trades...")

        # Start metrics reporter
        reporter_task = asyncio.create_task(
            print_analyzer_metrics(analyzers, interval=10)
        )

        # Run for 60 seconds
        logger.info("Running for 60 seconds...")
        await asyncio.sleep(60)

        # Cancel reporter
        reporter_task.cancel()
        try:
            await reporter_task
        except asyncio.CancelledError:
            pass

        # Get final statistics
        print("\n" + "=" * 80)
        print("FINAL STATISTICS")
        print("=" * 80)

        stats = consumer.get_statistics()

        print(f"\nConsumer Status: {'Running' if stats['running'] else 'Stopped'}")
        print(f"Uptime: {stats.get('uptime_seconds', 0):.1f} seconds")
        print(f"Symbols: {', '.join(stats['symbols'])}")
        print(f"Analyzers: {', '.join(stats['analyzers'])}")

        for symbol, symbol_stats in stats['symbols_data'].items():
            print(f"\n{symbol} Statistics:")
            print(f"  Total trades processed: {symbol_stats['total_trades']:,}")
            print(f"  Buffer utilization: {symbol_stats['utilization']:.1%}")
            print(f"  Current buffer size: {symbol_stats['current_size']:,}")

        # Get recent trades from buffer
        print(f"\nRecent trades in buffer:")
        recent = consumer.get_recent_trades("BTCUSDT", n=5)
        for trade in recent[-5:]:
            side = "BUY" if not trade.isBuyerMaker else "SELL"
            # Convert string price/qty to float for display
            price = float(trade.price)
            qty = float(trade.qty)
            print(f"  {side:4s} {price:12.2f} @ {qty:10.6f}")

    except KeyboardInterrupt:
        logger.info("Interrupted by user")

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)

    finally:
        # Cleanup
        logger.info("Stopping consumer...")
        await consumer.stop()
        logger.info("Consumer stopped. Example complete!")


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
