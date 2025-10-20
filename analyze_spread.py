"""
Analyze spread estimation in detail to understand why it seems high.
Run with: uv run python analyze_spread.py
"""

import asyncio
import logging
from datetime import datetime
from binance_tick_data.consumers.realtime_consumer import RealtimeConsumer
from binance_tick_data.consumers.consumer_config import ConsumerConfig

# Enable logging
logging.basicConfig(
    level=logging.WARNING,  # Reduce noise
    format='%(asctime)s - %(levelname)s - %(message)s'
)


async def analyze_spread():
    """Analyze actual spread from trades."""
    print("\n" + "="*80)
    print("Spread Analysis - Direct from Trade Data")
    print("="*80 + "\n")

    # Create consumer
    config = ConsumerConfig(symbols=["BTCUSDT"], buffer_size=1000)
    consumer = RealtimeConsumer(config)

    # Track buy/sell prices
    buy_prices = []
    sell_prices = []
    all_prices = []

    trade_count = [0]

    def on_trade(symbol: str, trade):
        trade_count[0] += 1
        price = float(trade.price)
        is_buy = not trade.isBuyerMaker  # Buyer is aggressor = buy

        all_prices.append(price)

        if is_buy:
            buy_prices.append(price)
        else:
            sell_prices.append(price)

        # Show first few trades
        if trade_count[0] <= 10:
            side = "BUY " if is_buy else "SELL"
            qty = float(trade.qty)
            print(f"  Trade {trade_count[0]:3d}: {side} @ ${price:.2f}, qty={qty:.6f}")

    consumer.subscribe_to_trades(on_trade)

    try:
        await consumer.start()
        print("Collecting 20 seconds of trade data...\n")

        # Collect for 20 seconds
        await asyncio.sleep(20)

        await consumer.stop()

        # Analysis
        print(f"\n{'='*80}")
        print("Analysis Results")
        print(f"{'='*80}\n")

        print(f"Total trades: {trade_count[0]}")
        print(f"  Buy trades:  {len(buy_prices)} ({len(buy_prices)/trade_count[0]*100:.1f}%)")
        print(f"  Sell trades: {len(sell_prices)} ({len(sell_prices)/trade_count[0]*100:.1f}%)")

        if len(all_prices) > 1:
            min_price = min(all_prices)
            max_price = max(all_prices)
            price_range = max_price - min_price
            avg_price = sum(all_prices) / len(all_prices)

            print(f"\nPrice Statistics:")
            print(f"  Min price:   ${min_price:.2f}")
            print(f"  Max price:   ${max_price:.2f}")
            print(f"  Range:       ${price_range:.2f} ({price_range/avg_price*10000:.2f} bps)")
            print(f"  Avg price:   ${avg_price:.2f}")

        if len(buy_prices) > 0 and len(sell_prices) > 0:
            # Average prices
            avg_buy = sum(buy_prices) / len(buy_prices)
            avg_sell = sum(sell_prices) / len(sell_prices)

            # Recent prices (last 10)
            recent_buys = buy_prices[-10:] if len(buy_prices) >= 10 else buy_prices
            recent_sells = sell_prices[-10:] if len(sell_prices) >= 10 else sell_prices

            avg_recent_buy = sum(recent_buys) / len(recent_buys)
            avg_recent_sell = sum(recent_sells) / len(recent_sells)

            print(f"\nBuy/Sell Price Analysis:")
            print(f"  Avg buy price (all):     ${avg_buy:.2f}")
            print(f"  Avg sell price (all):    ${avg_sell:.2f}")
            print(f"  Difference (all):        ${abs(avg_buy - avg_sell):.2f}")

            print(f"\n  Avg buy price (last 10): ${avg_recent_buy:.2f}")
            print(f"  Avg sell price (last 10): ${avg_recent_sell:.2f}")
            print(f"  Difference (last 10):     ${abs(avg_recent_buy - avg_recent_sell):.2f}")

            # Spread estimates
            if avg_buy > avg_sell:
                spread_all = avg_buy - avg_sell
                mid_all = (avg_buy + avg_sell) / 2
                rel_spread_all = spread_all / mid_all
                print(f"\nEstimated Spread (all trades):")
                print(f"  Absolute: ${spread_all:.4f}")
                print(f"  Relative: {rel_spread_all:.8f} ({rel_spread_all*10000:.2f} bps)")
            else:
                print(f"\n⚠️  Warning: avg_buy <= avg_sell")
                print(f"     This suggests the market is extremely tight or we need more data")

            if avg_recent_buy > avg_recent_sell:
                spread_recent = avg_recent_buy - avg_recent_sell
                mid_recent = (avg_recent_buy + avg_recent_sell) / 2
                rel_spread_recent = spread_recent / mid_recent
                print(f"\nEstimated Spread (last 10 trades):")
                print(f"  Absolute: ${spread_recent:.4f}")
                print(f"  Relative: {rel_spread_recent:.8f} ({rel_spread_recent*10000:.2f} bps)")

            # Show tick size
            print(f"\nBinance BTCUSDT:")
            print(f"  Typical tick size: $0.01")
            print(f"  Expected spread: 1-2 ticks = $0.01-$0.02")
            print(f"  Expected spread (bps): ~0.01-0.02 bps at $110k")

            # Min tick spread
            min_tick_spread = 0.01 / avg_price
            print(f"\n  Minimum 1-tick spread: {min_tick_spread:.8f} ({min_tick_spread*10000:.4f} bps)")

            if rel_spread_all > min_tick_spread * 10:
                print(f"\n⚠️  ALERT: Estimated spread is {rel_spread_all/min_tick_spread:.1f}x the minimum tick!")
                print(f"     This suggests the estimation method is capturing price drift,")
                print(f"     not just the bid-ask spread.")

        print(f"\n{'='*80}")

        # Show raw price sequence
        print(f"\nLast 20 prices (newest first):")
        for i, p in enumerate(all_prices[-20:][::-1]):
            side = "BUY " if p in buy_prices[-20:] else "SELL"
            print(f"  {i+1:2d}. {side} ${p:.2f}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(analyze_spread())
