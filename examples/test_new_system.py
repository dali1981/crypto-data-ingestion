"""
Test script for the new configuration and error handling system.

This script demonstrates:
1. Loading configuration from config.yaml
2. Proper error handling with actionable messages
3. Creating dollar-volume bars
4. Validation and diagnostics
"""

from binance_tick_data import (
    BinanceDataRepository,
    get_config,
    NoDataFoundError,
    TableNotFoundError,
    DatabaseNotFoundError,
)
from datetime import datetime, timedelta
import sys


def print_section(title: str):
    """Print a section header."""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def test_configuration():
    """Test configuration loading and validation."""
    print_section("1. Configuration System")

    # Load configuration
    config = get_config()

    print("✓ Configuration loaded successfully")
    print(f"\nDatabase Settings:")
    print(f"  Path: {config.database.db_path}")
    print(f"  Schema: {config.database.full_schema_path}")
    print(f"  Read-only: {config.database.read_only}")

    print(f"\nPipeline Settings:")
    print(f"  Batch size: {config.pipeline.default_batch_size:,}")

    print(f"\nDollar Bar Thresholds:")
    for symbol in ["BTCUSDT", "ETHUSDT", "BNBUSDT"]:
        threshold = config.pipeline.bar_thresholds.get_dollar_threshold(symbol)
        print(f"  {symbol}: ${threshold:,.0f}")

    # Validate setup
    print(f"\n\nValidating Configuration...")
    status = config.validate_setup()

    if status["warnings"]:
        print("\n⚠️  Warnings:")
        for warning in status["warnings"]:
            print(f"  • {warning}")

    if status["errors"]:
        print("\n❌ Errors:")
        for error in status["errors"]:
            print(f"  • {error}")
        return False

    print("\n✓ Configuration is valid")

    if status["info"]:
        print(f"\n📊 Info:")
        for key, value in status["info"].items():
            print(f"  • {key}: {value}")

    return True


def test_database_connection():
    """Test database connection with error handling."""
    print_section("2. Database Connection")

    try:
        with BinanceDataRepository() as repo:
            print("✓ Connected to database successfully")

            # Get data summary
            print("\nFetching data summary...")
            summary = repo.get_data_summary()

            print("\nAvailable Tables:")
            for table_name, info in summary.items():
                if info.get("exists"):
                    print(f"\n  {table_name}:")
                    print(f"    Records: {info['total_records']:,}")
                    print(f"    Symbols: {info['symbol_count']}")
                    if info['first_timestamp']:
                        print(f"    From: {info['first_timestamp']}")
                    if info['last_timestamp']:
                        print(f"    To: {info['last_timestamp']}")
                else:
                    print(f"\n  {table_name}: (not found)")

            return True

    except DatabaseNotFoundError as e:
        print(f"\n{e}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return False


def test_data_queries():
    """Test data queries with error handling."""
    print_section("3. Data Queries with Error Handling")

    try:
        with BinanceDataRepository() as repo:
            # List available symbols
            print("Fetching available symbols...")
            try:
                symbols = repo.list_available_symbols()
                print(f"✓ Found {len(symbols)} symbols: {', '.join(symbols[:5])}")
                if len(symbols) > 5:
                    print(f"  (and {len(symbols) - 5} more)")

                test_symbol = symbols[0] if symbols else "BTCUSDT"
            except Exception as e:
                print(f"⚠️  Could not list symbols: {e}")
                test_symbol = "BTCUSDT"

            # Query tick data
            print(f"\n\nQuerying tick data for {test_symbol}...")
            try:
                df = repo.get_agg_trades(
                    symbol=test_symbol,
                    start_time=datetime(2025, 10, 1),
                    limit=10000
                )

                print(f"✓ Retrieved {len(df):,} trades")
                print(f"\nFirst trade: {datetime.fromtimestamp(df['timestamp'].iloc[0] / 1000)}")
                print(f"Last trade:  {datetime.fromtimestamp(df['timestamp'].iloc[-1] / 1000)}")

                # Show sample
                print(f"\nSample trades:")
                df_display = df.head(3).copy()
                df_display['price'] = df_display['price'].astype(float)
                df_display['quantity'] = df_display['quantity'].astype(float)
                print(df_display[['timestamp', 'price', 'quantity', 'is_buyer_maker']])

                return df, test_symbol

            except NoDataFoundError as e:
                print(f"\n{e}")
                return None, test_symbol
            except TableNotFoundError as e:
                print(f"\n{e}")
                return None, test_symbol

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return None, None


def test_dollar_bars(df, symbol):
    """Test dollar-volume bar creation."""
    print_section("4. Dollar-Volume Bar Sampling")

    if df is None:
        print("⚠️  Skipping dollar bar test (no tick data available)")
        return

    try:
        with BinanceDataRepository() as repo:
            print(f"Creating dollar-volume bars for {symbol}...")

            # Get threshold from config
            config = get_config()
            threshold = config.pipeline.bar_thresholds.get_dollar_threshold(symbol)
            print(f"Using threshold: ${threshold:,.0f} per bar")

            # Create dollar bars
            dollar_bars = repo.create_dollar_bars(
                symbol=symbol,
                start_time=datetime(2025, 10, 1),
                dollar_threshold=threshold
            )

            # Convert to pandas for display if Polars
            if hasattr(dollar_bars, 'to_pandas'):
                dollar_bars = dollar_bars.to_pandas()

            print(f"\n✓ Created {len(dollar_bars)} dollar bars from {len(df)} ticks")
            print(f"  Average ticks per bar: {len(df) / len(dollar_bars):.1f}")

            # Show statistics
            print(f"\n\nDollar Bar Statistics:")
            print(f"  Average tick count: {dollar_bars['tick_count'].mean():.1f}")
            print(f"  Min tick count: {dollar_bars['tick_count'].min()}")
            print(f"  Max tick count: {dollar_bars['tick_count'].max()}")
            print(f"  Average dollar volume: ${dollar_bars['dollar_volume'].mean():,.0f}")

            # Show sample bars
            print(f"\n\nSample Dollar Bars:")
            sample = dollar_bars.head(3)
            print(f"\n{sample[['timestamp', 'open', 'high', 'low', 'close', 'volume', 'tick_count']]}")

            return True

    except Exception as e:
        print(f"\n❌ Error creating dollar bars: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_error_messages():
    """Test error message quality."""
    print_section("5. Error Message Examples")

    print("Testing error messages (these should fail gracefully)...\n")

    # Test 1: Invalid symbol
    print("Test 1: Invalid symbol")
    print("-" * 40)
    try:
        with BinanceDataRepository() as repo:
            df = repo.get_agg_trades(symbol="INVALID_SYMBOL")
    except NoDataFoundError as e:
        print(f"✓ Caught expected error:\n{e}\n")

    # Test 2: No data in range
    print("\nTest 2: No data in date range")
    print("-" * 40)
    try:
        with BinanceDataRepository() as repo:
            df = repo.get_agg_trades(
                symbol="BTCUSDT",
                start_time=datetime(2020, 1, 1),
                end_time=datetime(2020, 1, 2)
            )
    except NoDataFoundError as e:
        print(f"✓ Caught expected error:\n{e}\n")


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("  Binance Tick Data - New System Test Suite")
    print("=" * 80)

    results = {}

    # Test 1: Configuration
    results["config"] = test_configuration()

    if not results["config"]:
        print("\n❌ Configuration test failed. Cannot continue.")
        return False

    # Test 2: Database connection
    results["connection"] = test_database_connection()

    if not results["connection"]:
        print("\n⚠️  Database not available. Some tests will be skipped.")

    # Test 3: Data queries
    df, symbol = test_data_queries()
    results["queries"] = df is not None

    # Test 4: Dollar bars
    if df is not None:
        results["dollar_bars"] = test_dollar_bars(df, symbol)
    else:
        results["dollar_bars"] = None

    # Test 5: Error messages
    if results["connection"]:
        test_error_messages()

    # Summary
    print_section("Test Summary")

    print("Results:")
    for test_name, result in results.items():
        if result is True:
            print(f"  ✓ {test_name}: PASSED")
        elif result is False:
            print(f"  ✗ {test_name}: FAILED")
        else:
            print(f"  ⊘ {test_name}: SKIPPED")

    all_passed = all(r for r in results.values() if r is not None)

    if all_passed:
        print("\n✅ All tests passed!")
        return True
    else:
        print("\n⚠️  Some tests failed or were skipped")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
