"""
Simple example: Read data from your Binance database

Copy this file and modify it for your needs!
"""

from binance_tick_data import BinanceDataRepository
from datetime import datetime, timedelta

# =============================================================================
# Basic Example: Read last 24 hours of BTC trades
# =============================================================================

print("Reading BTC/USDT data from last 24 hours...\n")

try:
    with BinanceDataRepository() as repo:
        # Get aggregated trades (recommended - smaller, faster)
        df = repo.get_agg_trades(
            symbol="BTCUSDT",
            start_time=datetime.now() - timedelta(hours=24),
        )

except Exception as e:
    if "does not exist" in str(e):
        print("❌ No data found! Database is empty.\n")
        print("💡 First, download some data:")
        print("   uv run binance-download-safe --symbols BTCUSDT --max-records 10000 --start-date 2025-10-19")
        print("\n   This will download 10k records with incremental writes.")
        print("   You can query the data while it's downloading!")
        exit(0)
    else:
        raise

with BinanceDataRepository() as repo:
    # Query from October 1st onwards (where we have data)
    df = repo.get_agg_trades(
        symbol="BTCUSDT",
        start_time=datetime(2025, 10, 1),
    )

    if df.empty:
        print("❌ No data found!")
        print("\n💡 First, download some data:")
        print("   uv run binance-download --symbols BTCUSDT --max-records 10000")
    else:
        # Convert price and quantity to float
        df['price'] = df['price'].astype(float)
        df['quantity'] = df['quantity'].astype(float)

        # Show basic info
        print(f"✅ Retrieved {len(df):,} trades")
        print(f"📅 From: {datetime.fromtimestamp(df['timestamp'].min() / 1000)}")
        print(f"📅 To: {datetime.fromtimestamp(df['timestamp'].max() / 1000)}")

        # Current price
        current_price = df['price'].iloc[-1]
        print(f"\n💰 Current Price: ${current_price:,.2f}")

        # 24h stats
        high_24h = df['price'].max()
        low_24h = df['price'].min()
        print(f"📊 24h High: ${high_24h:,.2f}")
        print(f"📊 24h Low: ${low_24h:,.2f}")

        # Show first few trades
        print(f"\n📋 First 5 trades:")
        print(df[['timestamp', 'price', 'quantity', 'is_buyer_maker']].head())

        # You can now use this DataFrame for whatever you need!
        # - Technical analysis
        # - Machine learning features
        # - Export to CSV
        # - Build trading strategies
        # etc.

print("\n✅ Done!")
