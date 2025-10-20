"""
Test liquidity analyzer with improved spread estimation.
Run with: uv run python test_liquidity_analyzer.py
"""

import asyncio
import logging
from binance_tick_data.consumers.realtime_consumer import RealtimeConsumer
from binance_tick_data.consumers.consumer_config import ConsumerConfig
from binance_tick_data.analyzers.liquidity import LiquidityAnalyzer

# Enable logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_liquidity():
    """Test liquidity analyzer spread estimation."""
    print("\n" + "="*80)
    print("Liquidity Analyzer Test (20 seconds)")
    print("="*80 + "\n")

    # Create consumer config
    config = ConsumerConfig(
        symbols=["BTCUSDT"],
        buffer_size=1000
    )

    # Create consumer
    consumer = RealtimeConsumer(config)

    # Create liquidity analyzer
    liquidity = LiquidityAnalyzer(
        window_size=10,  # 10 second windows
        spread_method="effective",
        min_spread_threshold=0.00001  # Very low threshold to capture data
    )

    # Register analyzer
    consumer.register_analyzer(liquidity)

    # Track metrics updates
    metrics_count = [0]
    last_metrics = [None]

    # Monitor spread estimation progress
    trade_count = [0]

    def on_trade(symbol: str, trade):
        trade_count[0] += 1

        # Show progress every 50 trades
        if trade_count[0] % 50 == 0:
            # Get current metrics
            current = liquidity.get_current_metrics()
            spread = current.get('effective_spread_mean')

            if spread is not None:
                print(f"✅ {trade_count[0]} trades | Spread: {spread:.6f} ({spread*10000:.2f} bps)")
            else:
                print(f"⏳ {trade_count[0]} trades | Spread: Computing...")

    consumer.subscribe_to_trades(on_trade)

    try:
        # Start consumer
        await consumer.start()
        print("Consumer started with liquidity analyzer\n")

        # Run for 20 seconds
        await asyncio.sleep(20)

        # Get final metrics
        final_metrics = liquidity.get_current_metrics()

        # Stop consumer
        await consumer.stop()

        # Print results
        print(f"\n{'='*80}")
        print("Liquidity Analyzer Results")
        print(f"{'='*80}\n")

        print(f"Total trades processed: {trade_count[0]}")
        print(f"\nFinal Metrics:")
        for key, value in final_metrics.items():
            if isinstance(value, float):
                if 'spread' in key and value is not None:
                    bps = value * 10000
                    print(f"  {key:30s}: {value:.8f} ({bps:.2f} bps)")
                else:
                    print(f"  {key:30s}: {value:.4f}")
            else:
                print(f"  {key:30s}: {value}")

        print(f"\n{'='*80}")

        if final_metrics.get('effective_spread_mean') is None:
            print("⚠️  WARNING: Spread still None - needs more diverse trades")
            print("   (This can happen if all trades are one-sided)")
        else:
            spread_bps = final_metrics['effective_spread_mean'] * 10000
            print(f"✅ SUCCESS! Spread estimated at {spread_bps:.2f} basis points")

        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_liquidity())
    exit(0 if success else 1)
