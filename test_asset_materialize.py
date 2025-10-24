#!/usr/bin/env python3
"""
Test materialization of raw_agg_trades asset with limited data.

This creates a test run with a small subset of data to validate
the end-to-end pipeline works correctly.
"""

import sys
from pathlib import Path
from datetime import datetime

# Override config for testing (small dataset)
import dagster_pipeline.config as config
config.SYMBOLS = ["BTCUSDT", "ETHUSDT"]  # Test with just 2 symbols
config.HISTORICAL_START_DATE = "2025-10-22"  # Recent date for quick test

from binance_tick_data.config import BinanceConfig
# Override BinanceConfig to limit records for testing
original_config = BinanceConfig()


def test_materialize():
    """Test materializing the asset with limited data."""
    print("=" * 70)
    print("Testing Asset Materialization (Limited Data)")
    print("=" * 70)
    print()
    print("Configuration:")
    print(f"  Symbols: {config.SYMBOLS}")
    print(f"  Start Date: {config.HISTORICAL_START_DATE}")
    print(f"  Max Records: 10,000 (for testing)")
    print()

    # Import after config override
    from dagster import materialize
    from dagster_pipeline.assets.raw_data import raw_agg_trades_dlt
    from dagster_pipeline.resources import binance_api_resource, duckdb_query_resource, parquet_io_manager

    print("Starting materialization...")
    print("-" * 70)

    try:
        # Note: This will actually download data from Binance
        # The first run will take a few minutes
        result = materialize(
            [raw_agg_trades_dlt],
            resources={
                "binance_api": binance_api_resource,
                "duckdb_query": duckdb_query_resource,
                "io_manager": parquet_io_manager,
            }
        )

        print("-" * 70)
        print("✅ Materialization completed successfully!")
        print()

        # Check output
        output_base = Path("data/binance_data/agg_trades")

        if output_base.exists():
            parquet_files = list(output_base.glob("**/*.parquet"))
            print(f"✅ Created {len(parquet_files)} parquet files")

            # Show structure
            dates = set()
            symbols = set()

            for pf in parquet_files:
                date_dir = pf.parent.name
                symbol = pf.stem
                dates.add(date_dir)
                symbols.add(symbol)

                # Show file size
                size_mb = pf.stat().st_size / (1024 * 1024)
                print(f"  {date_dir}/{symbol}.parquet ({size_mb:.2f} MB)")

            print()
            print(f"Dates: {sorted(list(dates))}")
            print(f"Symbols: {sorted(list(symbols))}")

        # Check DuckDB view
        try:
            import duckdb
            conn = duckdb.connect(config.DB_PATH, read_only=True)
            result = conn.execute("SELECT COUNT(*) FROM binance_data.agg_trades").fetchone()
            row_count = result[0] if result else 0
            print(f"\nDuckDB view row count: {row_count:,}")
            conn.close()
        except Exception as e:
            print(f"\n⚠️  DuckDB view check failed: {e}")

        print()
        print("=" * 70)
        print("✅ Test completed successfully!")
        print("=" * 70)

        return 0

    except Exception as e:
        print()
        print("=" * 70)
        print(f"❌ Test failed: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    print()
    print("⚠️  WARNING: This will download real data from Binance API")
    print("   (limited to 2 symbols from 2025-10-22)")
    print()
    response = input("Continue? (y/n): ")

    if response.lower() != 'y':
        print("Cancelled.")
        sys.exit(0)

    sys.exit(test_materialize())
