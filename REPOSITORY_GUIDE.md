# Data Repository & Access Guide

Complete guide to accessing and querying your Binance tick data.

## Quick Start

```python
from binance_tick_data.repository import BinanceDataRepository

# Context manager (recommended - auto-closes connection)
with BinanceDataRepository() as repo:
    # Get last 7 days of trades
    df = repo.get_agg_trades_by_date_range("BTCUSDT", days=7)
    print(f"Retrieved {len(df):,} trades")
```

## Installation Check

```bash
# Make sure you have pandas and pyarrow
uv add pandas pyarrow

# Test the repository
uv run python examples/using_repository.py --example 1
```

## Repository Features

The `BinanceDataRepository` provides a clean, Pythonic interface to your data:

### 1. Trade Data Access

```python
with BinanceDataRepository() as repo:
    # Get trades for a specific time range
    df = repo.get_agg_trades(
        symbol="BTCUSDT",
        start_time=datetime(2024, 1, 1),
        end_time=datetime(2024, 1, 31),
        limit=10000
    )

    # Get last N days (convenient helper)
    df = repo.get_agg_trades_by_date_range("BTCUSDT", days=7)

    # Returns pandas DataFrame by default
    print(df.head())
    #   agg_trade_id    symbol      price  quantity  timestamp
    # 0        123456  BTCUSDT  43250.50     0.125  1704067200000
```

### 2. OHLCV Candlestick Data

```python
with BinanceDataRepository() as repo:
    # Generate candlesticks from trades
    ohlcv = repo.get_ohlcv(
        symbol="BTCUSDT",
        interval="1h",  # 1m, 5m, 15m, 1h, 4h, 1d
        start_time=datetime.now() - timedelta(days=7)
    )

    print(ohlcv.tail())
    #         time             open      high       low     close    volume  trades
    # 2024-01-01 00:00:00  43250.50  43500.00  43200.00  43450.00  125.45   1250
```

### 3. Market Statistics

```python
with BinanceDataRepository() as repo:
    stats = repo.get_symbol_stats(
        symbol="BTCUSDT",
        start_time=datetime.now() - timedelta(days=7)
    )

    print(stats)
    # {
    #     'symbol': 'BTCUSDT',
    #     'trade_count': 125000,
    #     'min_price': 42000.00,
    #     'max_price': 45000.00,
    #     'avg_price': 43500.00,
    #     'total_volume': 1250.50,
    #     'buy_count': 62500,
    #     'sell_count': 62500,
    #     'buy_sell_ratio': 1.0,
    #     'first_trade_time': datetime(...),
    #     'last_trade_time': datetime(...)
    # }
```

### 4. Volume Profile Analysis

```python
with BinanceDataRepository() as repo:
    # Get volume distribution across price levels
    profile = repo.get_volume_profile(
        symbol="BTCUSDT",
        price_bins=50,
        start_time=datetime.now() - timedelta(hours=24)
    )

    # Useful for finding support/resistance levels
    print(profile.sort_values('total_volume', ascending=False).head())
```

### 5. Order Book Data

```python
with BinanceDataRepository() as repo:
    # Get latest order book snapshot
    ob = repo.get_order_book_snapshot("BTCUSDT")

    print(f"Bids: {ob['bids'][:5]}")  # Top 5 bid levels
    print(f"Asks: {ob['asks'][:5]}")  # Top 5 ask levels
```

### 6. Real-time Data

```python
with BinanceDataRepository() as repo:
    # Get latest real-time trades
    recent = repo.get_realtime_trades("BTCUSDT", limit=100)
    print(f"Last 100 trades: {recent}")
```

### 7. Data Export

```python
with BinanceDataRepository() as repo:
    # Export to Parquet (highly compressed)
    repo.export_to_parquet(
        symbol="BTCUSDT",
        output_path="btc_data.parquet",
        start_time=datetime(2024, 1, 1),
        end_time=datetime(2024, 12, 31)
    )

    # Export to CSV
    repo.export_to_csv(
        symbol="BTCUSDT",
        output_path="btc_data.csv"
    )
```

### 8. Metadata & Discovery

```python
with BinanceDataRepository() as repo:
    # List all available symbols
    symbols = repo.list_symbols()
    print(f"Available: {symbols}")

    # Get data summary
    summary = repo.get_data_summary()
    print(summary)
    # {
    #     'agg_trades': {
    #         'total_records': 1250000,
    #         'symbol_count': 3,
    #         'first_timestamp': datetime(...),
    #         'last_timestamp': datetime(...)
    #     }
    # }
```

### 9. Custom SQL Queries

```python
with BinanceDataRepository() as repo:
    # Execute any SQL query
    df = repo.execute_query("""
        SELECT
            DATE_TRUNC('day', to_timestamp(timestamp / 1000)) as day,
            AVG(CAST(price AS DECIMAL)) as avg_price,
            SUM(CAST(quantity AS DECIMAL)) as volume
        FROM binance_historical.agg_trades
        WHERE symbol = 'BTCUSDT'
        GROUP BY day
        ORDER BY day DESC
        LIMIT 30
    """)
```

## Complete Examples

### Example 1: Basic Price Analysis

```python
from binance_tick_data.repository import BinanceDataRepository
from datetime import datetime, timedelta

with BinanceDataRepository() as repo:
    # Get last 24 hours
    df = repo.get_agg_trades(
        symbol="BTCUSDT",
        start_time=datetime.now() - timedelta(hours=24)
    )

    # Convert price to float
    df['price'] = df['price'].astype(float)

    # Basic statistics
    print(f"24h High: ${df['price'].max():,.2f}")
    print(f"24h Low: ${df['price'].min():,.2f}")
    print(f"Current: ${df['price'].iloc[-1]:,.2f}")
    print(f"24h Change: {(df['price'].iloc[-1] / df['price'].iloc[0] - 1) * 100:.2f}%")
```

### Example 2: Technical Analysis

```python
with BinanceDataRepository() as repo:
    # Get 1-hour candles
    ohlcv = repo.get_ohlcv("BTCUSDT", interval="1h")

    # Calculate simple moving averages
    ohlcv['sma_20'] = ohlcv['close'].rolling(20).mean()
    ohlcv['sma_50'] = ohlcv['close'].rolling(50).mean()

    # Calculate RSI
    delta = ohlcv['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    ohlcv['rsi'] = 100 - (100 / (1 + rs))

    print(ohlcv[['time', 'close', 'sma_20', 'sma_50', 'rsi']].tail())
```

### Example 3: Multi-Symbol Comparison

```python
with BinanceDataRepository() as repo:
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]

    for symbol in symbols:
        stats = repo.get_symbol_stats(
            symbol=symbol,
            start_time=datetime.now() - timedelta(days=7)
        )

        print(f"\n{symbol}:")
        print(f"  Price Range: ${stats['min_price']:.2f} - ${stats['max_price']:.2f}")
        print(f"  Volume: {stats['total_volume']:.2f}")
        print(f"  Buy/Sell: {stats['buy_sell_ratio']:.2f}")
```

### Example 4: Export for Machine Learning

```python
with BinanceDataRepository() as repo:
    # Get features for ML model
    ohlcv = repo.get_ohlcv("BTCUSDT", interval="5m")

    # Feature engineering
    ohlcv['returns'] = ohlcv['close'].pct_change()
    ohlcv['volatility'] = ohlcv['returns'].rolling(20).std()
    ohlcv['volume_ma'] = ohlcv['volume'].rolling(20).mean()

    # Export for training
    ohlcv.to_parquet("btc_features.parquet")
    print(f"Exported {len(ohlcv)} samples for ML training")
```

### Example 5: Real-time Monitoring

```python
import time

with BinanceDataRepository() as repo:
    while True:
        # Get latest stats
        recent = repo.get_realtime_trades("BTCUSDT", limit=100)

        if not recent.empty:
            latest_price = float(recent['price'].iloc[0])
            print(f"BTC/USDT: ${latest_price:,.2f}")

        time.sleep(5)  # Update every 5 seconds
```

## Running the Examples

```bash
# Example 1: Basic queries
uv run python examples/using_repository.py --example 1

# Example 2: OHLCV candlesticks
uv run python examples/using_repository.py --example 2

# Example 3: Market statistics
uv run python examples/using_repository.py --example 3

# Example 4: Volume profile
uv run python examples/using_repository.py --example 4

# Example 5: Data export
uv run python examples/using_repository.py --example 5

# Example 6: Custom SQL
uv run python examples/using_repository.py --example 6

# Example 7: Data summary
uv run python examples/using_repository.py --example 7

# Example 8: Time series analysis
uv run python examples/using_repository.py --example 8
```

## Best Practices

### 1. Always Use Context Manager

```python
# ✅ Good - auto-closes connection
with BinanceDataRepository() as repo:
    df = repo.get_agg_trades("BTCUSDT")

# ❌ Bad - might leave connection open
repo = BinanceDataRepository()
df = repo.get_agg_trades("BTCUSDT")
# Need to manually call repo.close()
```

### 2. Filter Early

```python
# ✅ Good - filter in database
df = repo.get_agg_trades(
    symbol="BTCUSDT",
    start_time=start,
    end_time=end
)

# ❌ Bad - load everything then filter
df = repo.execute_query("SELECT * FROM binance_historical.agg_trades")
df = df[df['symbol'] == 'BTCUSDT']  # Slow!
```

### 3. Use Appropriate Intervals

```python
# For day trading
ohlcv_1m = repo.get_ohlcv("BTCUSDT", interval="1m")

# For swing trading
ohlcv_1h = repo.get_ohlcv("BTCUSDT", interval="1h")

# For long-term analysis
ohlcv_1d = repo.get_ohlcv("BTCUSDT", interval="1d")
```

### 4. Limit Large Queries

```python
# ✅ Good - use limit
df = repo.get_agg_trades("BTCUSDT", limit=10000)

# ⚠️  Careful - might load millions of rows
df = repo.get_agg_trades("BTCUSDT")  # No limit!
```

## Advanced Usage

### Combining Multiple Queries

```python
with BinanceDataRepository() as repo:
    # Get data
    trades = repo.get_agg_trades_by_date_range("BTCUSDT", days=30)
    ohlcv = repo.get_ohlcv("BTCUSDT", interval="1h")
    stats = repo.get_symbol_stats("BTCUSDT")

    # Combine for analysis
    print(f"Loaded {len(trades):,} trades")
    print(f"Generated {len(ohlcv)} candles")
    print(f"Average price: ${stats['avg_price']:.2f}")
```

### Working with Timestamps

```python
# The repository handles timestamp conversions
from datetime import datetime

# Use datetime objects (easiest)
df = repo.get_agg_trades(
    symbol="BTCUSDT",
    start_time=datetime(2024, 1, 1),
    end_time=datetime(2024, 1, 31)
)

# Or use millisecond timestamps
df = repo.get_agg_trades(
    symbol="BTCUSDT",
    start_time=1704067200000,  # ms since epoch
    end_time=1706745600000
)
```

### Batch Processing

```python
with BinanceDataRepository() as repo:
    symbols = repo.list_symbols()

    for symbol in symbols:
        print(f"Processing {symbol}...")

        # Export each symbol
        repo.export_to_parquet(
            symbol=symbol,
            output_path=f"exports/{symbol}_data.parquet"
        )
```

## Troubleshooting

### "Table does not exist"

Make sure you've downloaded data first:

```bash
uv run python pipelines/historical_pipeline.py --symbols BTCUSDT --max-records 10000
```

### "Database is locked"

Only one writer at a time. Close other connections:

```python
# Make sure to close connections
with BinanceDataRepository() as repo:
    # ... your code ...
# Connection auto-closed here
```

### Slow queries

Add indexes or filter early:

```python
# Filter at query time, not after loading
df = repo.get_agg_trades(
    symbol="BTCUSDT",
    start_time=recent_date,  # Filter early
    limit=10000
)
```

## See Also

- **STORAGE_COMPARISON.md** - DuckDB vs Parquet comparison
- **DATA_MANAGEMENT.md** - Data management guide
- **examples/using_repository.py** - Complete working examples
- **examples/stream_realtime.py** - Real-time data examples

---

**Ready to query your data?**

```bash
uv run python examples/using_repository.py --example 1
```
