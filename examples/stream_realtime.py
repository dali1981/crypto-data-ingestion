"""Example: Stream real-time Binance tick data."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipelines.realtime_pipeline import run_realtime_pipeline


def example_basic():
    """Basic example: Stream real-time data with default settings."""
    print("Example 1: Basic real-time streaming (Ctrl+C to stop)")
    print("-" * 60)

    run_realtime_pipeline()


def example_custom_symbols():
    """Example: Stream data for specific symbols."""
    print("\nExample 2: Stream custom symbols")
    print("-" * 60)

    run_realtime_pipeline(
        symbols=["BTCUSDT", "ETHUSDT"],
    )


def example_limited_batches():
    """Example: Stream for a limited number of batches (useful for testing)."""
    print("\nExample 3: Stream with batch limit")
    print("-" * 60)

    run_realtime_pipeline(
        symbols=["BTCUSDT"],
        max_batches=10,  # Stop after 10 batches
    )


def example_monitor_stream():
    """Example: Monitor streaming data in real-time."""
    import duckdb
    import time
    from threading import Thread

    print("\nExample 4: Real-time monitoring")
    print("-" * 60)

    # Function to monitor data
    def monitor_data():
        """Monitor incoming data every 5 seconds."""
        conn = duckdb.connect("dlt_binance.duckdb")
        print("\nStarting real-time monitoring (will print every 5 seconds)...\n")

        while True:
            try:
                time.sleep(5)

                # Query recent data
                query = """
                SELECT
                    symbol,
                    COUNT(*) as count,
                    MAX(event_time) as latest_event
                FROM binance_realtime.realtime_trades
                GROUP BY symbol
                ORDER BY symbol
                """

                result = conn.execute(query).fetchall()

                print("\n" + "=" * 60)
                print(f"Real-time Trade Count (as of {time.strftime('%H:%M:%S')})")
                print("=" * 60)

                for row in result:
                    symbol, count, latest = row
                    print(f"  {symbol}: {count:,} trades (latest: {latest})")

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Monitor error: {e}")

        conn.close()

    # Start monitoring in a separate thread
    monitor_thread = Thread(target=monitor_data, daemon=True)
    monitor_thread.start()

    # Start streaming
    run_realtime_pipeline(symbols=["BTCUSDT", "ETHUSDT"])


def example_query_realtime_data():
    """Example: Query real-time data after streaming."""
    import duckdb

    print("\nExample 5: Query real-time data")
    print("-" * 60)

    # Connect to the DuckDB database
    conn = duckdb.connect("dlt_binance.duckdb")

    # Example queries
    queries = [
        ("Total real-time trades", "SELECT COUNT(*) as total FROM binance_realtime.realtime_trades"),
        ("Trades per symbol", "SELECT symbol, COUNT(*) as count FROM binance_realtime.realtime_trades GROUP BY symbol"),
        ("Buy vs Sell pressure", """
            SELECT
                symbol,
                SUM(CASE WHEN is_buyer_maker THEN 1 ELSE 0 END) as sells,
                SUM(CASE WHEN NOT is_buyer_maker THEN 1 ELSE 0 END) as buys,
                ROUND(SUM(CASE WHEN NOT is_buyer_maker THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as buy_percentage
            FROM binance_realtime.realtime_trades
            GROUP BY symbol
        """),
        ("Latest 10 trades", """
            SELECT
                symbol,
                price,
                quantity,
                is_buyer_maker,
                event_time
            FROM binance_realtime.realtime_trades
            ORDER BY event_time DESC
            LIMIT 10
        """),
    ]

    for title, query in queries:
        print(f"\n{title}:")
        try:
            result = conn.execute(query).fetchall()
            for row in result:
                print(f"  {row}")
        except Exception as e:
            print(f"  Error: {e}")

    conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Real-time streaming examples")
    parser.add_argument(
        "--example",
        type=int,
        choices=[1, 2, 3, 4, 5],
        help="Example number to run (1-5)",
        default=1,
    )

    args = parser.parse_args()

    examples = {
        1: example_basic,
        2: example_custom_symbols,
        3: example_limited_batches,
        4: example_monitor_stream,
        5: example_query_realtime_data,
    }

    print("\nNote: Examples 1-4 require active streaming. Press Ctrl+C to stop.")
    print("Example 5 queries existing data without starting a new stream.\n")

    examples[args.example]()
