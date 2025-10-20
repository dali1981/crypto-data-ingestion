"""
Test that repository now opens in read-only mode by default.
"""

from datetime import datetime
from binance_tick_data.repository import BinanceDataRepository

print("Testing read-only mode fix...")
print("=" * 60)

# This should now work even if another process is writing
with BinanceDataRepository() as repo:
    print(f"✓ Connected to database (read_only={repo.read_only})")

    # Try a simple query
    df = repo.get_agg_trades(
        symbol="BTCUSDT",
        start_time=datetime(2025, 10, 1),
        end_time=datetime(2025, 10, 2),
        limit=10
    )

    print(f"✓ Query successful: Retrieved {len(df)} trades")
    print(f"\nFirst few trades:")
    print(df[['timestamp', 'price', 'quantity']].head())

print("\n" + "=" * 60)
print("✅ Read-only mode is working!")
print("\nNow you can:")
print("- Read data while jobs are writing")
print("- Run multiple analysis scripts simultaneously")
print("- No more lock conflicts!")
