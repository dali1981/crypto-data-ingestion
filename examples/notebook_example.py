"""
Jupyter Notebook Style Example

Copy these code blocks into your Jupyter notebook!
Run them cell by cell.
"""

# =============================================================================
# CELL 1: Setup and imports
# =============================================================================

from binance_tick_data.repository import BinanceDataRepository
from datetime import datetime, timedelta
import pandas as pd

# Initialize repository
repo = BinanceDataRepository()
repo.connect()

print("✅ Connected to database")


# =============================================================================
# CELL 2: Load data
# =============================================================================

# Get last 7 days of BTC trades
df = repo.get_agg_trades_by_date_range("BTCUSDT", days=7)

# Convert to numeric
df['price'] = df['price'].astype(float)
df['quantity'] = df['quantity'].astype(float)
df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')

print(f"Loaded {len(df):,} trades")
df.head()


# =============================================================================
# CELL 3: Basic statistics
# =============================================================================

print("Basic Statistics:")
print(f"  Price range: ${df['price'].min():.2f} - ${df['price'].max():.2f}")
print(f"  Average price: ${df['price'].mean():.2f}")
print(f"  Total volume: {df['quantity'].sum():.2f} BTC")
print(f"  Total trades: {len(df):,}")


# =============================================================================
# CELL 4: Generate OHLCV candlesticks
# =============================================================================

# Get 1-hour candles
ohlcv = repo.get_ohlcv(
    symbol="BTCUSDT",
    interval="1h",
    start_time=datetime.now() - timedelta(days=7)
)

print(f"Generated {len(ohlcv)} hourly candles")
ohlcv.tail(10)


# =============================================================================
# CELL 5: Plot price chart (requires matplotlib)
# =============================================================================

import matplotlib.pyplot as plt

plt.figure(figsize=(14, 7))
plt.plot(ohlcv['time'], ohlcv['close'], label='Close Price')
plt.title('BTC/USDT Price (1H)')
plt.xlabel('Time')
plt.ylabel('Price (USD)')
plt.legend()
plt.grid(True, alpha=0.3)
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()


# =============================================================================
# CELL 6: Calculate technical indicators
# =============================================================================

# Moving averages
ohlcv['SMA_20'] = ohlcv['close'].rolling(window=20).mean()
ohlcv['SMA_50'] = ohlcv['close'].rolling(window=50).mean()

# RSI
delta = ohlcv['close'].diff()
gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
rs = gain / loss
ohlcv['RSI'] = 100 - (100 / (1 + rs))

# Bollinger Bands
ohlcv['BB_middle'] = ohlcv['close'].rolling(window=20).mean()
bb_std = ohlcv['close'].rolling(window=20).std()
ohlcv['BB_upper'] = ohlcv['BB_middle'] + (bb_std * 2)
ohlcv['BB_lower'] = ohlcv['BB_middle'] - (bb_std * 2)

ohlcv[['time', 'close', 'SMA_20', 'SMA_50', 'RSI']].tail(10)


# =============================================================================
# CELL 7: Plot with indicators
# =============================================================================

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)

# Price and MAs
ax1.plot(ohlcv['time'], ohlcv['close'], label='Close', linewidth=2)
ax1.plot(ohlcv['time'], ohlcv['SMA_20'], label='SMA 20', alpha=0.7)
ax1.plot(ohlcv['time'], ohlcv['SMA_50'], label='SMA 50', alpha=0.7)
ax1.fill_between(ohlcv['time'], ohlcv['BB_upper'], ohlcv['BB_lower'], alpha=0.2)
ax1.set_ylabel('Price (USD)')
ax1.set_title('BTC/USDT with Technical Indicators')
ax1.legend()
ax1.grid(True, alpha=0.3)

# RSI
ax2.plot(ohlcv['time'], ohlcv['RSI'], color='purple', linewidth=2)
ax2.axhline(y=70, color='r', linestyle='--', alpha=0.5, label='Overbought')
ax2.axhline(y=30, color='g', linestyle='--', alpha=0.5, label='Oversold')
ax2.fill_between(ohlcv['time'], 30, 70, alpha=0.1)
ax2.set_ylabel('RSI')
ax2.set_xlabel('Time')
ax2.set_ylim([0, 100])
ax2.legend()
ax2.grid(True, alpha=0.3)

plt.xticks(rotation=45)
plt.tight_layout()
plt.show()


# =============================================================================
# CELL 8: Order flow analysis
# =============================================================================

# Separate buy and sell orders
buys = df[~df['is_buyer_maker']]  # Buyer initiated
sells = df[df['is_buyer_maker']]   # Seller initiated

buy_volume = buys['quantity'].sum()
sell_volume = sells['quantity'].sum()

print(f"Order Flow Analysis:")
print(f"  Buy Volume: {buy_volume:.2f} BTC ({len(buys):,} trades)")
print(f"  Sell Volume: {sell_volume:.2f} BTC ({len(sells):,} trades)")
print(f"  Buy/Sell Ratio: {buy_volume / sell_volume:.2f}")

# Plot volume distribution
fig, ax = plt.subplots(figsize=(10, 6))
ax.bar(['Buy Orders', 'Sell Orders'], [buy_volume, sell_volume],
       color=['green', 'red'], alpha=0.7)
ax.set_ylabel('Volume (BTC)')
ax.set_title('Buy vs Sell Volume (Last 7 Days)')
ax.grid(True, alpha=0.3, axis='y')
plt.tight_layout()
plt.show()


# =============================================================================
# CELL 9: Volume profile (support/resistance)
# =============================================================================

volume_profile = repo.get_volume_profile(
    symbol="BTCUSDT",
    price_bins=50,
    start_time=datetime.now() - timedelta(days=7)
)

# Plot volume profile
fig, ax = plt.subplots(figsize=(12, 8))
ax.barh(volume_profile['price_avg'], volume_profile['total_volume'],
        height=(volume_profile['price_high'] - volume_profile['price_low']),
        alpha=0.6)
ax.set_xlabel('Volume (BTC)')
ax.set_ylabel('Price (USD)')
ax.set_title('Volume Profile - Potential Support/Resistance Levels')
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()

# Show top volume levels
print("\nTop 5 High Volume Price Levels:")
top_levels = volume_profile.nlargest(5, 'total_volume')
for _, row in top_levels.iterrows():
    print(f"  ${row['price_avg']:.2f}: {row['total_volume']:.2f} BTC ({row['trade_count']:,} trades)")


# =============================================================================
# CELL 10: Export results
# =============================================================================

# Export to CSV for further analysis
ohlcv.to_csv("btc_ohlcv_analysis.csv", index=False)
df.to_csv("btc_trades_raw.csv", index=False)

# Or export to Parquet (more efficient)
ohlcv.to_parquet("btc_ohlcv_analysis.parquet")

print("✅ Data exported!")
print("  - btc_ohlcv_analysis.csv")
print("  - btc_trades_raw.csv")
print("  - btc_ohlcv_analysis.parquet")


# =============================================================================
# CELL 11: Cleanup (run at end of notebook)
# =============================================================================

# Close the database connection
repo.close()
print("✅ Connection closed")


# =============================================================================
# BONUS: Quick helper functions for your notebook
# =============================================================================

def get_latest_price(symbol="BTCUSDT"):
    """Get the latest price for a symbol."""
    with BinanceDataRepository() as r:
        df = r.get_agg_trades(symbol=symbol, limit=1)
        if not df.empty:
            return float(df['price'].iloc[-1])
    return None


def get_24h_change(symbol="BTCUSDT"):
    """Get 24h price change percentage."""
    with BinanceDataRepository() as r:
        df = r.get_agg_trades(
            symbol=symbol,
            start_time=datetime.now() - timedelta(hours=24)
        )
        if not df.empty:
            df['price'] = df['price'].astype(float)
            first = df['price'].iloc[0]
            last = df['price'].iloc[-1]
            return ((last / first) - 1) * 100
    return None


def quick_stats(symbol="BTCUSDT", days=7):
    """Get quick statistics for a symbol."""
    with BinanceDataRepository() as r:
        return r.get_symbol_stats(
            symbol=symbol,
            start_time=datetime.now() - timedelta(days=days)
        )


# Test helper functions
print("\n🔧 Helper Functions:")
print(f"  Latest BTC price: ${get_latest_price('BTCUSDT'):,.2f}")
print(f"  24h change: {get_24h_change('BTCUSDT'):+.2f}%")
