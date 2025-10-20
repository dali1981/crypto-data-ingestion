"""
Quick test to verify WebSocket fix works.
Run with: uv run python test_websocket_fix.py
"""

import asyncio
import logging
from binance_tick_data.consumers.realtime_consumer import RealtimeConsumer
from binance_tick_data.consumers.consumer_config import ConsumerConfig

# Enable logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_websocket():
    """Test WebSocket connection for 10 seconds."""
    print("\n" + "="*80)
    print("Testing WebSocket Connection (10 seconds)")
    print("="*80 + "\n")

    # Create consumer config
    config = ConsumerConfig(
        symbols=["BTCUSDT"],
        buffer_size=100
    )

    # Create consumer
    consumer = RealtimeConsumer(config)

    # Track trades
    trade_count = [0]

    def on_trade(symbol: str, trade):
        trade_count[0] += 1
        if trade_count[0] <= 5:
            # Convert string price/qty to float for display
            price = float(trade.price)
            qty = float(trade.qty)
            quote_qty = float(trade.quote_qty)
            print(f"✅ Trade {trade_count[0]}: {symbol} @ ${price:.2f}, qty={qty:.6f}, quote=${quote_qty:.2f}")

    consumer.subscribe_to_trades(on_trade)

    try:
        # Start consumer
        await consumer.start()
        print("Consumer started, waiting for trades...\n")

        # Run for 10 seconds
        await asyncio.sleep(10)

        # Stop consumer
        await consumer.stop()

        print(f"\n{'='*80}")
        print(f"✅ SUCCESS! Received {trade_count[0]} trades in 10 seconds")
        print(f"{'='*80}\n")

        if trade_count[0] == 0:
            print("⚠️  Warning: No trades received. Check if market is active.")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_websocket())
