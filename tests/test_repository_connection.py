"""
Test script to verify the fix works before running in notebook.
Run this first: uv run python test_notebook_fix.py
"""

from binance_tick_data import BinanceDataRepository, get_config
from datetime import datetime

print("="*80)
print("Testing Notebook Fix")
print("="*80)

# 1. Show configuration
config = get_config()
print(f"\n1. Configuration:")
print(f"   Database: {config.database.db_path}")
print(f"   Catalog: '{config.database.catalog_name}' (empty = no catalog prefix)")
print(f"   Schema: {config.database.schema_name}")
print(f"   Full path: {config.database.full_schema_path}.agg_trades")

# 2. Test connection
print(f"\n2. Testing database connection...")
try:
    with BinanceDataRepository() as repo:
        # Test query
        df = repo.get_agg_trades(
            symbol="BTCUSDT",
            start_time=datetime(2025, 10, 1),
            limit=10
        )
        print(f"   ✅ Success! Retrieved {len(df)} rows")
        print(f"\n3. Sample data:")
        print(df[['timestamp', 'price', 'quantity']].head(3))

        print(f"\n{'='*80}")
        print("✅ ALL TESTS PASSED")
        print("="*80)
        print("\nThe notebook should work now!")
        print("\nIn your Jupyter notebook:")
        print("1. Restart the kernel: Kernel → Restart Kernel")
        print("2. Run the import cell")
        print("3. Run the data loading cell")

except Exception as e:
    print(f"   ❌ Failed: {e}")
    print("\nIf this fails, the notebook will also fail.")
    import traceback
    traceback.print_exc()
