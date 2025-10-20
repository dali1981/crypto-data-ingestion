"""Test script to verify the Binance tick data library setup."""

import sys


def test_imports():
    """Test that all required packages can be imported."""
    print("Testing imports...")

    try:
        import dlt
        print("  ✓ dlt imported successfully")
    except ImportError as e:
        print(f"  ✗ Failed to import dlt: {e}")
        return False

    try:
        import duckdb
        print("  ✓ duckdb imported successfully")
    except ImportError as e:
        print(f"  ✗ Failed to import duckdb: {e}")
        return False

    try:
        from binance.client import Client
        print("  ✓ binance client imported successfully")
    except ImportError as e:
        print(f"  ✗ Failed to import binance: {e}")
        return False

    try:
        import websockets
        print("  ✓ websockets imported successfully")
    except ImportError as e:
        print(f"  ✗ Failed to import websockets: {e}")
        return False

    try:
        import pydantic
        print("  ✓ pydantic imported successfully")
    except ImportError as e:
        print(f"  ✗ Failed to import pydantic: {e}")
        return False

    return True


def test_library():
    """Test that the binance_tick_data library can be imported."""
    print("\nTesting library...")

    try:
        from binance_tick_data import BinanceConfig, get_config
        print("  ✓ BinanceConfig imported successfully")

        # Test config creation
        config = get_config()
        print(f"  ✓ Config created with symbols: {config.symbols}")

    except ImportError as e:
        print(f"  ✗ Failed to import binance_tick_data: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Error testing config: {e}")
        return False

    try:
        from binance_tick_data.sources import binance_historical_data, binance_realtime_data
        print("  ✓ Data sources imported successfully")
    except ImportError as e:
        print(f"  ✗ Failed to import data sources: {e}")
        return False

    return True


def test_binance_connection():
    """Test connection to Binance API."""
    print("\nTesting Binance API connection...")

    try:
        from binance.client import Client

        client = Client()  # Public API, no credentials needed

        # Test simple API call
        server_time = client.get_server_time()
        print(f"  ✓ Connected to Binance API (server time: {server_time['serverTime']})")

        # Test getting ticker price
        ticker = client.get_symbol_ticker(symbol="BTCUSDT")
        print(f"  ✓ Current BTC/USDT price: ${ticker['price']}")

        return True

    except Exception as e:
        print(f"  ✗ Failed to connect to Binance API: {e}")
        print("  Note: This may be due to network issues or rate limiting")
        return False


def test_duckdb():
    """Test DuckDB functionality."""
    print("\nTesting DuckDB...")

    try:
        import duckdb
        import tempfile
        import os

        # Create temporary database path
        temp_dir = tempfile.mkdtemp()
        temp_db_path = os.path.join(temp_dir, "test.duckdb")

        conn = duckdb.connect(temp_db_path)

        # Create test table
        conn.execute("CREATE TABLE test (id INTEGER, value VARCHAR)")
        conn.execute("INSERT INTO test VALUES (1, 'test')")

        # Query
        result = conn.execute("SELECT * FROM test").fetchall()
        assert result[0] == (1, 'test'), "DuckDB query failed"

        conn.close()

        # Clean up
        import shutil
        shutil.rmtree(temp_dir)

        print("  ✓ DuckDB working correctly")
        return True

    except Exception as e:
        print(f"  ✗ DuckDB test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Binance Tick Data Library - Setup Test")
    print("=" * 60)

    all_passed = True

    # Run tests
    all_passed &= test_imports()
    all_passed &= test_library()
    all_passed &= test_binance_connection()
    all_passed &= test_duckdb()

    # Summary
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All tests passed! Library is ready to use.")
        print("\nNext steps:")
        print("  1. Run historical data download:")
        print("     uv run python pipelines/historical_pipeline.py --symbols BTCUSDT")
        print("\n  2. Or try the examples:")
        print("     uv run python examples/download_historical.py")
        print("     uv run python examples/stream_realtime.py")
    else:
        print("✗ Some tests failed. Please check the errors above.")
        sys.exit(1)

    print("=" * 60)


if __name__ == "__main__":
    main()
