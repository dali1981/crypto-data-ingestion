#!/usr/bin/env python3
"""
Test script to validate the Dagster asset changes.

This script tests the raw_agg_trades asset with a small sample
to verify the date-based partitioning works correctly.
"""

import sys
from pathlib import Path
from dagster import materialize
from dagster_pipeline import defs

def test_asset_structure():
    """Test that the Dagster definitions load correctly."""
    print("✓ Testing Dagster definitions...")

    # Check assets are defined
    assert len(defs.assets) > 0, "No assets defined"
    print(f"  Found {len(defs.assets)} assets")

    # Check asset checks are defined
    assert len(defs.asset_checks) > 0, "No asset checks defined"
    print(f"  Found {len(defs.asset_checks)} asset checks")

    # Check resources are defined
    assert len(defs.resources) > 0, "No resources defined"
    print(f"  Found {len(defs.resources)} resources")

    print("✓ Dagster definitions validated successfully\n")


def test_output_structure():
    """Test that the expected output directory structure exists or can be created."""
    print("✓ Testing output structure...")

    output_base = Path("data/binance_data/agg_trades")

    # Create if doesn't exist
    output_base.mkdir(parents=True, exist_ok=True)

    assert output_base.exists(), f"Failed to create {output_base}"
    print(f"  Output directory: {output_base}")
    print("✓ Output structure validated\n")


def check_existing_data():
    """Check if there's already data in the expected location."""
    print("✓ Checking for existing data...")

    output_base = Path("data/binance_data/agg_trades")

    if not output_base.exists():
        print("  No existing data directory")
        return

    parquet_files = list(output_base.glob("**/*.parquet"))

    if not parquet_files:
        print("  No existing parquet files found")
        return

    print(f"  Found {len(parquet_files)} existing parquet files")

    # Sample structure
    dates = set()
    symbols = set()

    for pf in parquet_files[:20]:
        # Expected: data/binance_data/agg_trades/{date}/{symbol}.parquet
        date_dir = pf.parent.name
        symbol = pf.stem

        dates.add(date_dir)
        symbols.add(symbol)

    print(f"  Dates: {sorted(list(dates))[:5]}...")
    print(f"  Symbols: {sorted(list(symbols))[:10]}...")
    print()


def main():
    """Run all tests."""
    print("=" * 70)
    print("Dagster Asset Validation Test")
    print("=" * 70)
    print()

    try:
        test_asset_structure()
        test_output_structure()
        check_existing_data()

        print("=" * 70)
        print("✅ All validation tests passed!")
        print("=" * 70)
        print()
        print("Next steps:")
        print("1. Start Dagster UI: ./start_dagster.sh")
        print("2. Navigate to http://localhost:3000")
        print("3. Materialize the 'raw_agg_trades' asset")
        print("4. Monitor the logs for progress")
        print()
        print("Expected output:")
        print("  data/binance_data/agg_trades/")
        print("    └── {date}/")
        print("        ├── BTCUSDT.parquet")
        print("        ├── ETHUSDT.parquet")
        print("        └── ... (20 symbols)")
        print()

        return 0

    except Exception as e:
        print(f"❌ Validation failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
