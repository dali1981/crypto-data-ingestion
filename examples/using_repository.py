"""Examples of using the BinanceDataRepository for data access."""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from binance_tick_data.repository import BinanceDataRepository


def example_1_basic_queries():
    """Example 1: Basic data queries."""
    print("=" * 70)
    print("Example 1: Basic Data Queries")
    print("=" * 70)

    with BinanceDataRepository() as repo:
        # Get last 7 days of BTCUSDT trades
        print("\n1. Getting last 7 days of BTC trades...")
        df = repo.get_agg_trades_by_date_range("BTCUSDT", days=7)
        print(f"   Retrieved {len(df):,} trades")
        print(f"   Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        print("\nFirst 5 rows:")
        print(df.head())


def example_2_ohlcv_candlesticks():
    """Example 2: Generate OHLCV candlestick data."""
    print("\n" + "=" * 70)
    print("Example 2: OHLCV Candlestick Data")
    print("=" * 70)

    with BinanceDataRepository() as repo:
        # Get 1-hour candles for the last 24 hours
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=24)

        print(f"\nGenerating 1-hour candles for BTCUSDT...")
        df = repo.get_ohlcv(
            symbol="BTCUSDT",
            interval="1h",
            start_time=start_time,
            end_time=end_time
        )

        print(f"Retrieved {len(df)} candles")
        print("\nCandles:")
        print(df.to_string())

        # Get 5-minute candles
        print(f"\n\nGenerating 5-minute candles for BTCUSDT...")
        df_5m = repo.get_ohlcv(
            symbol="BTCUSDT",
            interval="5m",
            start_time=start_time,
            end_time=end_time
        )
        print(f"Retrieved {len(df_5m)} candles")
        print("\nLast 10 candles:")
        print(df_5m.tail(10).to_string())


def example_3_market_statistics():
    """Example 3: Market statistics and analysis."""
    print("\n" + "=" * 70)
    print("Example 3: Market Statistics")
    print("=" * 70)

    with BinanceDataRepository() as repo:
        # Get statistics for BTCUSDT
        print("\nBTCUSDT Statistics (last 7 days):")
        end_time = datetime.now()
        start_time = end_time - timedelta(days=7)

        stats = repo.get_symbol_stats("BTCUSDT", start_time, end_time)

        print(f"  Trade Count: {stats['trade_count']:,}")
        print(f"  Price Range: ${stats['min_price']:.2f} - ${stats['max_price']:.2f}")
        print(f"  Average Price: ${stats['avg_price']:.2f}")
        print(f"  Total Volume: {stats['total_volume']:.2f}")
        print(f"  Buy/Sell Ratio: {stats['buy_sell_ratio']:.2f}")
        print(f"  Buy Orders: {stats['buy_count']:,}")
        print(f"  Sell Orders: {stats['sell_count']:,}")
        print(f"  First Trade: {stats['first_trade_time']}")
        print(f"  Last Trade: {stats['last_trade_time']}")


def example_4_volume_profile():
    """Example 4: Volume profile analysis."""
    print("\n" + "=" * 70)
    print("Example 4: Volume Profile")
    print("=" * 70)

    with BinanceDataRepository() as repo:
        # Get volume profile for the last 24 hours
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=24)

        print("\nCalculating volume profile for BTCUSDT (last 24 hours)...")
        df = repo.get_volume_profile(
            symbol="BTCUSDT",
            price_bins=20,
            start_time=start_time,
            end_time=end_time
        )

        print(f"\nVolume by Price Level:")
        print(df.to_string())


def example_5_data_export():
    """Example 5: Export data to files."""
    print("\n" + "=" * 70)
    print("Example 5: Data Export")
    print("=" * 70)

    with BinanceDataRepository() as repo:
        # Export last 7 days to Parquet
        end_time = datetime.now()
        start_time = end_time - timedelta(days=7)

        print("\n1. Exporting to Parquet...")
        repo.export_to_parquet(
            symbol="BTCUSDT",
            output_path="btc_last_7days.parquet",
            start_time=start_time,
            end_time=end_time
        )

        print("\n2. Exporting to CSV...")
        repo.export_to_csv(
            symbol="BTCUSDT",
            output_path="btc_last_7days.csv",
            start_time=start_time,
            end_time=end_time
        )

        # Check file sizes
        import os
        parquet_size = os.path.getsize("btc_last_7days.parquet") / (1024 * 1024)
        csv_size = os.path.getsize("btc_last_7days.csv") / (1024 * 1024)

        print(f"\nFile sizes:")
        print(f"  Parquet: {parquet_size:.2f} MB")
        print(f"  CSV: {csv_size:.2f} MB")
        print(f"  Compression ratio: {csv_size/parquet_size:.1f}x")


def example_6_custom_queries():
    """Example 6: Custom SQL queries."""
    print("\n" + "=" * 70)
    print("Example 6: Custom SQL Queries")
    print("=" * 70)

    with BinanceDataRepository() as repo:
        # Custom query: Price changes per hour
        query = """
            SELECT
                DATE_TRUNC('hour', to_timestamp(timestamp / 1000)) as hour,
                FIRST(CAST(price AS DECIMAL)) as open,
                LAST(CAST(price AS DECIMAL)) as close,
                ((LAST(CAST(price AS DECIMAL)) - FIRST(CAST(price AS DECIMAL))) /
                 FIRST(CAST(price AS DECIMAL)) * 100) as pct_change
            FROM binance_historical.agg_trades
            WHERE symbol = 'BTCUSDT'
            GROUP BY hour
            ORDER BY hour DESC
            LIMIT 24
        """

        print("\nPrice changes per hour (last 24 hours):")
        df = repo.execute_query(query)
        print(df.to_string())


def example_7_data_summary():
    """Example 7: Get data summary."""
    print("\n" + "=" * 70)
    print("Example 7: Data Summary")
    print("=" * 70)

    with BinanceDataRepository() as repo:
        # List all symbols
        print("\nAvailable symbols:")
        symbols = repo.list_symbols()
        for symbol in symbols:
            print(f"  - {symbol}")

        # Get data summary
        print("\n\nData Summary:")
        summary = repo.get_data_summary()

        for table, info in summary.items():
            if info:
                print(f"\n{table}:")
                print(f"  Total Records: {info['total_records']:,}")
                print(f"  Symbols: {info['symbol_count']}")
                print(f"  Date Range: {info['first_timestamp']} to {info['last_timestamp']}")
            else:
                print(f"\n{table}: No data")


def example_8_time_series_analysis():
    """Example 8: Time series analysis."""
    print("\n" + "=" * 70)
    print("Example 8: Time Series Analysis")
    print("=" * 70)

    with BinanceDataRepository() as repo:
        # Get 1-minute data for analysis
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=1)

        df = repo.get_ohlcv(
            symbol="BTCUSDT",
            interval="1m",
            start_time=start_time,
            end_time=end_time
        )

        print(f"\nAnalyzing last hour of BTCUSDT data ({len(df)} minutes)...")

        # Calculate returns
        df['returns'] = df['close'].pct_change()

        # Statistics
        print(f"\nPrice Statistics:")
        print(f"  Current Price: ${df['close'].iloc[-1]:.2f}")
        print(f"  High: ${df['high'].max():.2f}")
        print(f"  Low: ${df['low'].min():.2f}")
        print(f"  Price Change: ${df['close'].iloc[-1] - df['open'].iloc[0]:.2f}")
        print(f"  % Change: {((df['close'].iloc[-1] / df['open'].iloc[0]) - 1) * 100:.2f}%")

        print(f"\nVolume Statistics:")
        print(f"  Total Volume: {df['volume'].sum():.2f}")
        print(f"  Average Volume per Minute: {df['volume'].mean():.2f}")
        print(f"  Max Volume Minute: {df['volume'].max():.2f}")

        print(f"\nVolatility:")
        print(f"  Returns Std Dev: {df['returns'].std():.6f}")
        print(f"  Annualized Volatility: {df['returns'].std() * (252 * 24 * 60) ** 0.5:.2%}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Data repository examples")
    parser.add_argument(
        "--example",
        type=int,
        choices=list(range(1, 9)),
        help="Example number to run (1-8)",
        default=1,
    )

    args = parser.parse_args()

    examples = {
        1: example_1_basic_queries,
        2: example_2_ohlcv_candlesticks,
        3: example_3_market_statistics,
        4: example_4_volume_profile,
        5: example_5_data_export,
        6: example_6_custom_queries,
        7: example_7_data_summary,
        8: example_8_time_series_analysis,
    }

    try:
        examples[args.example]()
        print("\n" + "=" * 70)
        print("✓ Example completed successfully!")
        print("=" * 70)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
