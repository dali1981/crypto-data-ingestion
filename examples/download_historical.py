"""Example: Download historical Binance tick data."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from binance_tick_data.pipelines.historical_pipeline import run_historical_pipeline


def example_basic():
    """Basic example: Download historical data with default settings."""
    print("Example 1: Basic historical data download")
    print("-" * 60)

    run_historical_pipeline()


def example_custom_symbols():
    """Example: Download data for specific symbols."""
    print("\nExample 2: Custom symbols")
    print("-" * 60)

    run_historical_pipeline(
        symbols=["BTCUSDT", "ETHUSDT"],
        start_date="2024-10-01",
    )


def example_single_symbol():
    """Example: Download data for a single symbol with specific date range."""
    print("\nExample 3: Single symbol with date range")
    print("-" * 60)

    run_historical_pipeline(
        symbols=["SOLUSDT"],
        start_date="2024-10-15",
        dataset_name="binance_sol",
    )


def example_query_data():
    """Example: Query the downloaded data using DuckDB."""
    import duckdb

    print("\nExample 4: Query downloaded data")
    print("-" * 60)

    # Connect to the DuckDB database
    conn = duckdb.connect("dlt_binance.duckdb")

    # Example queries
    queries = [
        ("Total trades", "SELECT COUNT(*) as total_trades FROM binance_historical.trades"),
        ("Trades by symbol", "SELECT symbol, COUNT(*) as count FROM binance_historical.trades GROUP BY symbol"),
        ("Average trade price (BTC)", "SELECT symbol, AVG(CAST(price AS DECIMAL)) as avg_price FROM binance_historical.trades WHERE symbol = 'BTCUSDT' GROUP BY symbol"),
        ("Latest 5 trades", "SELECT symbol, price, qty, time FROM binance_historical.trades ORDER BY time DESC LIMIT 5"),
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

    parser = argparse.ArgumentParser(description="Historical data download examples")
    parser.add_argument(
        "--example",
        type=int,
        choices=[1, 2, 3, 4],
        help="Example number to run (1-4)",
        default=1,
    )

    args = parser.parse_args()

    examples = {
        1: example_basic,
        2: example_custom_symbols,
        3: example_single_symbol,
        4: example_query_data,
    }

    examples[args.example]()
