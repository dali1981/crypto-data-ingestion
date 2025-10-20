"""
Client Code Examples - Real-world usage patterns for reading Binance tick data.

These examples show how you would use this library in your own projects.
"""

from binance_tick_data.repository import BinanceDataRepository
from datetime import datetime, timedelta
import pandas as pd


# =============================================================================
# Example 1: Simple Price Tracker
# =============================================================================

def price_tracker():
    """Track current price and 24h change for a symbol."""
    print("=" * 70)
    print("Example 1: Simple Price Tracker")
    print("=" * 70)

    with BinanceDataRepository() as repo:
        # Get last 24 hours of data
        df = repo.get_agg_trades(
            symbol="BTCUSDT",
            start_time=datetime.now() - timedelta(hours=24),
            limit=100000
        )

        if df.empty:
            print("No data available. Run the pipeline first!")
            return

        # Convert price to float
        df['price'] = df['price'].astype(float)

        # Calculate metrics
        current_price = df['price'].iloc[-1]
        open_price = df['price'].iloc[0]
        high_24h = df['price'].max()
        low_24h = df['price'].min()
        change_24h = ((current_price / open_price) - 1) * 100

        print(f"\n💰 BTC/USDT")
        print(f"   Current Price: ${current_price:,.2f}")
        print(f"   24h Change: {change_24h:+.2f}%")
        print(f"   24h High: ${high_24h:,.2f}")
        print(f"   24h Low: ${low_24h:,.2f}")
        print(f"   24h Range: ${high_24h - low_24h:,.2f}")


# =============================================================================
# Example 2: Trading Signal Generator
# =============================================================================

def trading_signals():
    """Generate simple trading signals based on moving averages."""
    print("\n" + "=" * 70)
    print("Example 2: Trading Signal Generator")
    print("=" * 70)

    with BinanceDataRepository() as repo:
        # Get 1-hour candles
        ohlcv = repo.get_ohlcv(
            symbol="BTCUSDT",
            interval="1h",
            start_time=datetime.now() - timedelta(days=7)
        )

        if ohlcv.empty:
            print("No data available. Run the pipeline first!")
            return

        # Calculate indicators
        ohlcv['sma_20'] = ohlcv['close'].rolling(window=20).mean()
        ohlcv['sma_50'] = ohlcv['close'].rolling(window=50).mean()

        # Generate signals
        latest = ohlcv.iloc[-1]
        prev = ohlcv.iloc[-2]

        print(f"\n📊 Technical Analysis (1H timeframe)")
        print(f"   Current Price: ${latest['close']:,.2f}")
        print(f"   SMA 20: ${latest['sma_20']:,.2f}")
        print(f"   SMA 50: ${latest['sma_50']:,.2f}")

        # Golden Cross / Death Cross
        if prev['sma_20'] <= prev['sma_50'] and latest['sma_20'] > latest['sma_50']:
            print(f"\n   🟢 GOLDEN CROSS - Bullish signal!")
        elif prev['sma_20'] >= prev['sma_50'] and latest['sma_20'] < latest['sma_50']:
            print(f"\n   🔴 DEATH CROSS - Bearish signal!")
        elif latest['sma_20'] > latest['sma_50']:
            print(f"\n   🟢 Bullish trend (SMA20 > SMA50)")
        else:
            print(f"\n   🔴 Bearish trend (SMA20 < SMA50)")


# =============================================================================
# Example 3: Market Order Flow Analysis
# =============================================================================

def order_flow_analysis():
    """Analyze buy vs sell pressure."""
    print("\n" + "=" * 70)
    print("Example 3: Order Flow Analysis")
    print("=" * 70)

    with BinanceDataRepository() as repo:
        # Get last hour of trades
        df = repo.get_agg_trades(
            symbol="BTCUSDT",
            start_time=datetime.now() - timedelta(hours=1)
        )

        if df.empty:
            print("No data available. Run the pipeline first!")
            return

        # Convert to numeric
        df['price'] = df['price'].astype(float)
        df['quantity'] = df['quantity'].astype(float)
        df['value'] = df['price'] * df['quantity']

        # Separate buy and sell orders
        # is_buyer_maker = True means seller initiated (sell order)
        # is_buyer_maker = False means buyer initiated (buy order)
        buys = df[~df['is_buyer_maker']]
        sells = df[df['is_buyer_maker']]

        buy_volume = buys['quantity'].sum()
        sell_volume = sells['quantity'].sum()
        buy_value = buys['value'].sum()
        sell_value = sells['value'].sum()

        print(f"\n📈 Order Flow (Last 1 hour)")
        print(f"\n   Buy Orders:")
        print(f"      Count: {len(buys):,}")
        print(f"      Volume: {buy_volume:,.2f} BTC")
        print(f"      Value: ${buy_value:,.2f}")

        print(f"\n   Sell Orders:")
        print(f"      Count: {len(sells):,}")
        print(f"      Volume: {sell_volume:,.2f} BTC")
        print(f"      Value: ${sell_value:,.2f}")

        # Calculate pressure
        if sell_volume > 0:
            buy_sell_ratio = buy_volume / sell_volume
            print(f"\n   📊 Buy/Sell Ratio: {buy_sell_ratio:.2f}")

            if buy_sell_ratio > 1.2:
                print(f"   🟢 Strong buying pressure!")
            elif buy_sell_ratio < 0.8:
                print(f"   🔴 Strong selling pressure!")
            else:
                print(f"   ⚪ Balanced market")


# =============================================================================
# Example 4: Multi-Timeframe Analysis
# =============================================================================

def multi_timeframe_analysis():
    """Analyze price action across multiple timeframes."""
    print("\n" + "=" * 70)
    print("Example 4: Multi-Timeframe Analysis")
    print("=" * 70)

    with BinanceDataRepository() as repo:
        timeframes = {
            "15m": ("15m", timedelta(days=2)),
            "1h": ("1h", timedelta(days=7)),
            "4h": ("4h", timedelta(days=30)),
        }

        print(f"\n📊 BTC/USDT Multi-Timeframe Analysis\n")

        for name, (interval, lookback) in timeframes.items():
            ohlcv = repo.get_ohlcv(
                symbol="BTCUSDT",
                interval=interval,
                start_time=datetime.now() - lookback
            )

            if ohlcv.empty:
                continue

            # Calculate metrics
            first_price = ohlcv['open'].iloc[0]
            last_price = ohlcv['close'].iloc[-1]
            change = ((last_price / first_price) - 1) * 100

            # Determine trend
            trend = "🟢 Bullish" if change > 0 else "🔴 Bearish"

            print(f"   {name.upper()}: {trend} ({change:+.2f}%)")


# =============================================================================
# Example 5: Export Data for Analysis
# =============================================================================

def export_for_analysis():
    """Export data for external analysis (Excel, ML models, etc.)."""
    print("\n" + "=" * 70)
    print("Example 5: Export Data for Analysis")
    print("=" * 70)

    with BinanceDataRepository() as repo:
        # Get 30 days of 1-hour candles
        ohlcv = repo.get_ohlcv(
            symbol="BTCUSDT",
            interval="1h",
            start_time=datetime.now() - timedelta(days=30)
        )

        if ohlcv.empty:
            print("No data available. Run the pipeline first!")
            return

        # Add technical indicators
        ohlcv['sma_20'] = ohlcv['close'].rolling(20).mean()
        ohlcv['sma_50'] = ohlcv['close'].rolling(50).mean()
        ohlcv['returns'] = ohlcv['close'].pct_change()
        ohlcv['volatility'] = ohlcv['returns'].rolling(24).std()

        # Export to different formats
        ohlcv.to_csv("btc_analysis.csv", index=False)
        ohlcv.to_parquet("btc_analysis.parquet")
        ohlcv.to_excel("btc_analysis.xlsx", index=False)

        print(f"\n✅ Exported {len(ohlcv)} candles to:")
        print(f"   - btc_analysis.csv")
        print(f"   - btc_analysis.parquet")
        print(f"   - btc_analysis.xlsx")
        print(f"\n💡 Open in Excel or use in your analysis tools!")


# =============================================================================
# Example 6: Real-time Price Alert
# =============================================================================

def price_alert_checker(target_price=50000):
    """Check if price has crossed a threshold."""
    print("\n" + "=" * 70)
    print(f"Example 6: Price Alert (Target: ${target_price:,})")
    print("=" * 70)

    with BinanceDataRepository() as repo:
        # Get recent trades
        df = repo.get_agg_trades(
            symbol="BTCUSDT",
            start_time=datetime.now() - timedelta(minutes=5),
            limit=1000
        )

        if df.empty:
            print("No data available. Run the pipeline first!")
            return

        # Convert price
        df['price'] = df['price'].astype(float)

        current_price = df['price'].iloc[-1]
        high_5m = df['price'].max()
        low_5m = df['price'].min()

        print(f"\n   Current Price: ${current_price:,.2f}")
        print(f"   Target Price: ${target_price:,.2f}")
        print(f"   5m High: ${high_5m:,.2f}")
        print(f"   5m Low: ${low_5m:,.2f}")

        if current_price >= target_price:
            print(f"\n   🔔 ALERT: Price is above target!")
        elif high_5m >= target_price:
            print(f"\n   ⚠️  Price touched target in last 5 minutes!")
        else:
            distance = ((target_price / current_price) - 1) * 100
            print(f"\n   📍 Price is {abs(distance):.2f}% away from target")


# =============================================================================
# Example 7: Volume Profile (Support/Resistance Finder)
# =============================================================================

def find_support_resistance():
    """Find potential support and resistance levels using volume profile."""
    print("\n" + "=" * 70)
    print("Example 7: Support/Resistance Levels")
    print("=" * 70)

    with BinanceDataRepository() as repo:
        # Get volume profile
        profile = repo.get_volume_profile(
            symbol="BTCUSDT",
            price_bins=30,
            start_time=datetime.now() - timedelta(days=7)
        )

        if profile.empty:
            print("No data available. Run the pipeline first!")
            return

        # Sort by volume to find high-volume nodes (HVN)
        profile = profile.sort_values('total_volume', ascending=False)

        # Top 5 high-volume price levels
        top_levels = profile.head(5)

        print(f"\n📊 High Volume Nodes (Potential Support/Resistance)")
        print(f"    Price Range                  Volume         Trades")
        print(f"    " + "-" * 55)

        for _, row in top_levels.iterrows():
            price_low = row['price_low']
            price_high = row['price_high']
            volume = row['total_volume']
            trades = row['trade_count']

            print(f"    ${price_low:,.2f} - ${price_high:,.2f}    {volume:>8.2f} BTC    {trades:>6,}")

        print(f"\n💡 These price levels have high trading activity")
        print(f"   and may act as support or resistance.")


# =============================================================================
# Example 8: Compare Multiple Symbols
# =============================================================================

def compare_symbols():
    """Compare performance across multiple symbols."""
    print("\n" + "=" * 70)
    print("Example 8: Multi-Symbol Comparison")
    print("=" * 70)

    with BinanceDataRepository() as repo:
        symbols = repo.list_symbols()

        if not symbols:
            print("No data available. Run the pipeline first!")
            return

        print(f"\n📊 24h Performance Comparison\n")
        print(f"   Symbol      Current     24h Change    24h Volume")
        print(f"   " + "-" * 55)

        for symbol in symbols:
            stats = repo.get_symbol_stats(
                symbol=symbol,
                start_time=datetime.now() - timedelta(hours=24)
            )

            if stats['trade_count'] == 0:
                continue

            # Get current and starting price
            df = repo.get_agg_trades(
                symbol=symbol,
                start_time=datetime.now() - timedelta(hours=24),
                limit=100000
            )

            if not df.empty:
                df['price'] = df['price'].astype(float)
                current = df['price'].iloc[-1]
                start = df['price'].iloc[0]
                change_24h = ((current / start) - 1) * 100

                indicator = "🟢" if change_24h > 0 else "🔴"

                print(f"   {symbol:<10}  ${current:>9,.2f}   {indicator} {change_24h:>+6.2f}%   {stats['total_volume']:>10,.2f}")


# =============================================================================
# Example 9: Backtest Strategy (Simple Moving Average Crossover)
# =============================================================================

def simple_backtest():
    """Simple backtest of a moving average crossover strategy."""
    print("\n" + "=" * 70)
    print("Example 9: Simple Backtest (SMA Crossover)")
    print("=" * 70)

    with BinanceDataRepository() as repo:
        # Get 4-hour candles for last 30 days
        ohlcv = repo.get_ohlcv(
            symbol="BTCUSDT",
            interval="4h",
            start_time=datetime.now() - timedelta(days=30)
        )

        if ohlcv.empty or len(ohlcv) < 50:
            print("Not enough data available. Run the pipeline first!")
            return

        # Calculate indicators
        ohlcv['sma_20'] = ohlcv['close'].rolling(20).mean()
        ohlcv['sma_50'] = ohlcv['close'].rolling(50).mean()

        # Generate signals
        ohlcv['signal'] = 0
        ohlcv.loc[ohlcv['sma_20'] > ohlcv['sma_50'], 'signal'] = 1  # Buy
        ohlcv.loc[ohlcv['sma_20'] < ohlcv['sma_50'], 'signal'] = -1  # Sell

        # Detect crossovers
        ohlcv['position'] = ohlcv['signal'].diff()

        # Calculate returns
        buy_signals = ohlcv[ohlcv['position'] == 2]  # Crossover up
        sell_signals = ohlcv[ohlcv['position'] == -2]  # Crossover down

        print(f"\n📊 Backtest Results (Last 30 days)")
        print(f"   Period: {ohlcv['time'].iloc[0]} to {ohlcv['time'].iloc[-1]}")
        print(f"   Total Candles: {len(ohlcv)}")
        print(f"   Buy Signals: {len(buy_signals)}")
        print(f"   Sell Signals: {len(sell_signals)}")

        # Simple P&L calculation
        if len(buy_signals) > 0 and len(sell_signals) > 0:
            trades = []
            for i, buy in buy_signals.iterrows():
                # Find next sell signal
                next_sells = sell_signals[sell_signals['time'] > buy['time']]
                if len(next_sells) > 0:
                    sell = next_sells.iloc[0]
                    pnl = ((sell['close'] / buy['close']) - 1) * 100
                    trades.append({
                        'entry': buy['close'],
                        'exit': sell['close'],
                        'pnl': pnl
                    })

            if trades:
                total_pnl = sum(t['pnl'] for t in trades)
                avg_pnl = total_pnl / len(trades)
                wins = sum(1 for t in trades if t['pnl'] > 0)
                win_rate = (wins / len(trades)) * 100

                print(f"\n   Completed Trades: {len(trades)}")
                print(f"   Total P&L: {total_pnl:+.2f}%")
                print(f"   Average P&L: {avg_pnl:+.2f}%")
                print(f"   Win Rate: {win_rate:.1f}%")
                print(f"   Wins: {wins}, Losses: {len(trades) - wins}")


# =============================================================================
# Example 10: Your Custom Analysis Template
# =============================================================================

def custom_analysis_template():
    """Template for your own custom analysis."""
    print("\n" + "=" * 70)
    print("Example 10: Custom Analysis Template")
    print("=" * 70)

    with BinanceDataRepository() as repo:
        # Step 1: Get your data
        symbol = "BTCUSDT"
        df = repo.get_agg_trades(
            symbol=symbol,
            start_time=datetime.now() - timedelta(days=7)
        )

        if df.empty:
            print("No data available. Run the pipeline first!")
            return

        # Step 2: Process it
        df['price'] = df['price'].astype(float)
        df['quantity'] = df['quantity'].astype(float)

        # Step 3: Your custom analysis here
        print(f"\n✨ Your Custom Analysis for {symbol}")
        print(f"   Total Records: {len(df):,}")
        print(f"   Date Range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        print(f"\n   💡 Add your own analysis logic here!")
        print(f"   - Calculate custom indicators")
        print(f"   - Run your trading strategy")
        print(f"   - Generate reports")
        print(f"   - Build ML features")


# =============================================================================
# Main Menu
# =============================================================================

def main():
    """Run all examples or select specific one."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Client code examples for reading Binance tick data"
    )
    parser.add_argument(
        "--example",
        type=int,
        choices=list(range(0, 11)),
        help="Example number to run (0 = all, 1-10 = specific)",
        default=0,
    )

    args = parser.parse_args()

    examples = {
        1: ("Price Tracker", price_tracker),
        2: ("Trading Signals", trading_signals),
        3: ("Order Flow Analysis", order_flow_analysis),
        4: ("Multi-Timeframe Analysis", multi_timeframe_analysis),
        5: ("Export Data", export_for_analysis),
        6: ("Price Alert", lambda: price_alert_checker(50000)),
        7: ("Support/Resistance", find_support_resistance),
        8: ("Compare Symbols", compare_symbols),
        9: ("Simple Backtest", simple_backtest),
        10: ("Custom Template", custom_analysis_template),
    }

    try:
        if args.example == 0:
            # Run all examples
            print("\n🚀 Running all examples...\n")
            for num, (name, func) in examples.items():
                try:
                    func()
                except Exception as e:
                    print(f"\n⚠️  Example {num} failed: {e}")
        else:
            # Run specific example
            name, func = examples[args.example]
            print(f"\n🚀 Running: {name}\n")
            func()

        print("\n" + "=" * 70)
        print("✅ Done!")
        print("=" * 70)

        if args.example == 0:
            print("\n💡 Run a specific example with --example N (1-10)")
            print("   Example: uv run python examples/client_examples.py --example 1")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
