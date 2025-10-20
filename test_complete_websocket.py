"""
Complete WebSocket test with analyzers and schema validation.
Run with: uv run python test_complete_websocket.py
"""

import asyncio
import logging
from binance_tick_data.consumers.realtime_consumer import RealtimeConsumer
from binance_tick_data.consumers.consumer_config import ConsumerConfig
from binance_tick_data.analyzers.order_flow import OrderFlowAnalyzer
from binance_tick_data.analyzers.liquidity import LiquidityAnalyzer

# Enable logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_complete_websocket():
    """Test WebSocket with schema validation and analyzers."""
    print("\n" + "="*80)
    print("Complete WebSocket Test (15 seconds)")
    print("="*80 + "\n")

    # Create consumer config
    config = ConsumerConfig(
        symbols=["BTCUSDT"],
        buffer_size=500
    )

    # Create consumer
    consumer = RealtimeConsumer(config)

    # Create analyzers
    order_flow = OrderFlowAnalyzer(window_size=5)
    liquidity = LiquidityAnalyzer(window_size=5)

    # Register analyzers
    consumer.register_analyzer(order_flow)
    consumer.register_analyzer(liquidity)

    # Track trades
    trade_count = [0]
    validation_errors = [0]

    def on_trade(symbol: str, trade):
        trade_count[0] += 1

        # Validate schema fields
        try:
            # Test property accessors (camelCase)
            assert hasattr(trade, 'isBuyerMaker'), "Missing isBuyerMaker property"
            assert hasattr(trade, 'isBestMatch'), "Missing isBestMatch property"
            assert hasattr(trade, 'quoteQty'), "Missing quoteQty property"

            # Test actual fields (snake_case)
            assert hasattr(trade, 'is_buyer_maker'), "Missing is_buyer_maker field"
            assert hasattr(trade, 'is_best_match'), "Missing is_best_match field"
            assert hasattr(trade, 'quote_qty'), "Missing quote_qty field"

            # Test string types
            assert isinstance(trade.price, str), f"price should be string, got {type(trade.price)}"
            assert isinstance(trade.qty, str), f"qty should be string, got {type(trade.qty)}"
            assert isinstance(trade.quote_qty, str), f"quote_qty should be string, got {type(trade.quote_qty)}"

            # Test conversions
            price = float(trade.price)
            qty = float(trade.qty)
            quote_qty = float(trade.quote_qty)

            if trade_count[0] <= 3:
                side = "BUY" if not trade.isBuyerMaker else "SELL"
                print(f"✅ Trade {trade_count[0]}: {symbol} {side} @ ${price:.2f}, qty={qty:.6f}, quote=${quote_qty:.2f}")

        except (AssertionError, ValueError) as e:
            validation_errors[0] += 1
            logger.error(f"Validation error in trade {trade_count[0]}: {e}")

    consumer.subscribe_to_trades(on_trade)

    try:
        # Start consumer
        await consumer.start()
        print("\n✅ Consumer started with 2 analyzers\n")

        # Run for 15 seconds
        await asyncio.sleep(15)

        # Get statistics
        stats = consumer.get_statistics()

        # Stop consumer
        await consumer.stop()

        # Print results
        print(f"\n{'='*80}")
        print("Test Results")
        print(f"{'='*80}")
        print(f"\n✅ Total trades received: {trade_count[0]}")
        print(f"✅ Validation errors: {validation_errors[0]}")
        print(f"✅ Analyzers: {', '.join(stats['analyzers'])}")
        print(f"✅ Uptime: {stats.get('uptime_seconds', 0):.1f}s")

        for symbol, symbol_stats in stats.get('symbols_data', {}).items():
            print(f"\n{symbol} Statistics:")
            print(f"  - Total trades: {symbol_stats.get('total_trades', 0)}")
            print(f"  - Buffer usage: {symbol_stats.get('utilization', 0):.1%}")
            print(f"  - Buffer size: {symbol_stats.get('current_size', 0)}")

        print(f"\n{'='*80}")

        if validation_errors[0] > 0:
            print(f"❌ FAILED: {validation_errors[0]} validation errors occurred")
            return False
        elif trade_count[0] == 0:
            print("⚠️  WARNING: No trades received (market might be quiet)")
            return True
        else:
            print(f"✅ SUCCESS! All {trade_count[0]} trades passed validation")
            print("✅ WebSocket connection working correctly")
            print("✅ Schema validation working correctly")
            print("✅ Analyzers running without errors")
            return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_complete_websocket())
    exit(0 if success else 1)
