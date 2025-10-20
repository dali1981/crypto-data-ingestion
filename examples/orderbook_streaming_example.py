"""
Example: Real-time order book streaming with TRUE spread calculation.

Demonstrates:
- Streaming order book depth from Binance
- Calculating TRUE bid-ask spread
- Monitoring spread changes in real-time
- Comparing true spread vs trade-based estimate

Run with: uv run python examples/orderbook_streaming_example.py
"""

import asyncio
import logging
from datetime import datetime
from binance_tick_data.consumers.realtime_consumer import RealtimeConsumer
from binance_tick_data.consumers.consumer_config import ConsumerConfig

# Enable logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Stream order book and calculate true spread."""
    print("\n" + "="*80)
    print("Order Book Streaming - TRUE Spread Calculation")
    print("="*80 + "\n")

    # Create consumer with order book streaming enabled
    config = ConsumerConfig(
        symbols=["BTCUSDT"],
        buffer_size=1000,
        stream_orderbook=True,  # ✅ Enable order book streaming
        orderbook_update_speed="100ms",  # Fast updates
        orderbook_depth_levels=20,  # Track top 20 levels
    )

    consumer = RealtimeConsumer(config)

    # Track spread statistics
    spread_history = []
    update_count = [0]

    def on_depth_update(symbol: str, depth_data):
        """Process each order book update."""
        update_count[0] += 1

        bids = depth_data["bids"]
        asks = depth_data["asks"]

        if not bids or not asks:
            return

        # Calculate TRUE spread
        best_bid = bids[0][0]  # Highest bid price
        best_ask = asks[0][0]  # Lowest ask price

        spread_absolute = best_ask - best_bid
        mid_price = (best_bid + best_ask) / 2
        spread_relative = spread_absolute / mid_price if mid_price > 0 else 0
        spread_bps = spread_relative * 10000  # Basis points

        # Track spreads
        spread_history.append(spread_bps)
        if len(spread_history) > 1000:
            spread_history.pop(0)

        # Display every update for real-time view
        if update_count[0] % 1 == 0:
            # Calculate stats
            avg_spread = sum(spread_history) / len(spread_history)
            min_spread = min(spread_history)
            max_spread = max(spread_history)

            # Clear screen for live update effect (optional)
            import os
            os.system('clear' if os.name != 'nt' else 'cls')

            print(f"\n{'='*80}")
            print(f"BTCUSDT Order Book - Live Stream | Update #{update_count[0]:,}")
            print(f"Time: {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
            print(f"{'='*80}\n")

            # Display order book side by side
            print(f"{'BIDS (Buy Orders)':^38} | {'ASKS (Sell Orders)':^38}")
            print(f"{'-'*38}-+-{'-'*38}")
            print(f"{'Price':>15} {'Size (BTC)':>10} {'Total $':>12} | {'Price':>15} {'Size (BTC)':>10} {'Total $':>12}")
            print(f"{'-'*38}-+-{'-'*38}")

            for i in range(5):
                if i < len(bids):
                    bid_price, bid_qty = bids[i]
                    bid_total = bid_price * bid_qty
                    bid_str = f"${bid_price:>13,.2f} {bid_qty:>10.4f} ${bid_total:>11,.0f}"
                else:
                    bid_str = f"{'':38}"

                if i < len(asks):
                    ask_price, ask_qty = asks[i]
                    ask_total = ask_price * ask_qty
                    ask_str = f"${ask_price:>13,.2f} {ask_qty:>10.4f} ${ask_total:>11,.0f}"
                else:
                    ask_str = f"{'':38}"

                # Highlight best bid/ask
                if i == 0:
                    print(f"\033[92m{bid_str}\033[0m | \033[91m{ask_str}\033[0m")  # Green bid, Red ask
                else:
                    print(f"{bid_str} | {ask_str}")

            print(f"{'-'*38}-+-{'-'*38}")

            # Spread info
            print(f"\n{'SPREAD ANALYSIS':^80}")
            print(f"{'='*80}")
            print(f"  Spread: ${spread_absolute:.4f}  ({spread_bps:.4f} bps)  |  Mid: ${mid_price:,.2f}")
            print(f"  Avg: {avg_spread:.4f} bps  |  Min: {min_spread:.4f} bps  |  Max: {max_spread:.4f} bps")
            print(f"  Updates: {len(spread_history):,}  |  Range: {max_spread - min_spread:.4f} bps")

    # Subscribe to depth updates
    consumer.subscribe_to_depth(on_depth_update)

    try:
        # Start consumer
        await consumer.start()
        print("\n✅ Order book streaming started!")
        print("   Receiving 100ms updates from Binance...\n")

        # Run for 30 seconds
        await asyncio.sleep(30)

        # Stop consumer
        await consumer.stop()

        # Final summary
        print(f"\n{'='*80}")
        print("Final Summary")
        print(f"{'='*80}\n")

        stats = consumer.get_statistics()

        for symbol, symbol_stats in stats.get('symbols_data', {}).items():
            print(f"{symbol} Statistics:")
            print(f"  Total trades: {symbol_stats.get('total_trades', 0):,}")
            print(f"  Depth updates: {symbol_stats.get('depth_updates', 0):,}")
            print(f"  Order book levels: {symbol_stats.get('orderbook_levels', {})}")

        if spread_history:
            avg_spread = sum(spread_history) / len(spread_history)
            min_spread = min(spread_history)
            max_spread = max(spread_history)

            print(f"\nSpread Analysis:")
            print(f"  Average spread: {avg_spread:.4f} bps")
            print(f"  Min spread: {min_spread:.4f} bps")
            print(f"  Max spread: {max_spread:.4f} bps")
            print(f"  Range: {max_spread - min_spread:.4f} bps")

            # Interpretation
            print(f"\nInterpretation:")
            if avg_spread < 0.001:
                print(f"  ✅ Extremely tight spread - highly liquid market")
            elif avg_spread < 0.01:
                print(f"  ✅ Very tight spread - liquid market")
            elif avg_spread < 0.1:
                print(f"  ⚠️  Moderate spread - decent liquidity")
            else:
                print(f"  ❌ Wide spread - low liquidity")

            # Convert to dollars at ~$110k
            mid_price_estimate = 110000
            spread_dollars = (avg_spread / 10000) * mid_price_estimate
            print(f"\n  At ${mid_price_estimate:,} BTC:")
            print(f"    Average spread ≈ ${spread_dollars:.2f}")
            print(f"    Min spread ≈ ${(min_spread / 10000) * mid_price_estimate:.2f}")
            print(f"    Max spread ≈ ${(max_spread / 10000) * mid_price_estimate:.2f}")

        print(f"\n{'='*80}")
        print("✅ Order book streaming demonstration complete!")
        print(f"{'='*80}\n")

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        await consumer.stop()

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        await consumer.stop()


if __name__ == "__main__":
    asyncio.run(main())
