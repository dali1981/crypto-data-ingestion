# Client API Reference

Complete reference for the `BinanceDataRepository` client API - the primary interface for accessing Binance tick data in your applications.

---

## Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [Core API](#core-api)
5. [Advanced Features](#advanced-features)
6. [Examples](#examples)
7. [Error Handling](#error-handling)

---

## Overview

The `BinanceDataRepository` provides a clean, Pythonic interface for querying historical Binance tick data stored in DuckDB. It abstracts SQL complexity and provides convenient methods for common trading analysis tasks.

### Key Features

✅ **Simple API** - Clean Python methods, no SQL required
✅ **Type Safety** - Full type hints for IDE support
✅ **Flexible Formats** - Return as Pandas DataFrames or raw tuples
✅ **Time Conversion** - Automatic handling of timestamps and datetimes
✅ **OHLCV Generation** - Compute candlesticks from tick data
✅ **Analytics Built-in** - Volume profiles, statistics, order flow
✅ **Export Tools** - Save to CSV, Parquet, Excel

### Files

**Main API**: `src/binance_tick_data/repository.py`
- Primary client interface
- 585 lines, 19 public methods
- Battle-tested and stable

**Enhanced Version**: `src/binance_tick_data/repository_v2.py`
- Config-based initialization
- Better error messages
- 873 lines, additional validation

**Examples**: `examples/client_examples.py`
- 10 real-world usage patterns
- Copy-paste ready code

---

## Installation

The repository is already available if you have the package installed:

```bash
# Install package (if not already installed)
uv sync

# Import in your code
from binance_tick_data.repository import BinanceDataRepository
```

---

## Quick Start

### Basic Usage Pattern

```python
from binance_tick_data.repository import BinanceDataRepository
from datetime import datetime, timedelta

# Open repository (context manager handles connection)
with BinanceDataRepository() as repo:
    # Get last 24 hours of trades
    df = repo.get_agg_trades(
        symbol="BTCUSDT",
        start_time=datetime.now() - timedelta(hours=24)
    )

    print(f"Fetched {len(df)} trades")
    print(df.head())
```

### Alternative: Manual Connection Management

```python
# Create repository
repo = BinanceDataRepository()

# Connect
repo.connect()

# Use it
df = repo.get_agg_trades("BTCUSDT")

# Close when done
repo.close()
```

**Recommendation**: Use context manager (`with` statement) for automatic cleanup.

---

## Core API

### Constructor

#### `BinanceDataRepository(db_path, dataset_name, read_only)`

Initialize the repository.

**Parameters:**
- `db_path` (str, optional): Path to DuckDB database file
  - Default: `"binance_pipeline.duckdb"`
  - Can be absolute or relative path

- `dataset_name` (str, optional): Schema/dataset name in database
  - Default: `"binance_data"`
  - Must match your pipeline configuration

- `read_only` (bool, optional): Open database in read-only mode
  - Default: `True`
  - Recommended for concurrent access
  - Set to `False` only if writing data

**Returns:** `BinanceDataRepository` instance

**Example:**
```python
# Use defaults
repo = BinanceDataRepository()

# Custom database
repo = BinanceDataRepository(db_path="my_data.duckdb")

# Enable writes
repo = BinanceDataRepository(read_only=False)
```

---

### Trade Data Methods

#### `get_agg_trades(symbol, start_time, end_time, limit, as_dataframe)`

Get aggregated trades for a symbol with optional time filters.

**Parameters:**
- `symbol` (str, required): Trading symbol
  - Example: `"BTCUSDT"`, `"ETHUSDT"`

- `start_time` (datetime | int, optional): Start time filter
  - Can be `datetime` object or Unix timestamp (milliseconds)
  - Default: `None` (no start filter)

- `end_time` (datetime | int, optional): End time filter
  - Can be `datetime` object or Unix timestamp (milliseconds)
  - Default: `None` (no end filter)

- `limit` (int, optional): Maximum number of records to return
  - Default: `None` (no limit)
  - Useful for testing or sampling

- `as_dataframe` (bool, optional): Return format
  - `True`: Return Pandas DataFrame (default)
  - `False`: Return list of tuples

**Returns:**
- If `as_dataframe=True`: `pd.DataFrame` with columns:
  - `agg_trade_id`: Unique trade ID
  - `symbol`: Trading pair
  - `price`: Trade price (string, convert to float for math)
  - `quantity`: Trade quantity (string)
  - `first_trade_id`: First trade ID in aggregation
  - `last_trade_id`: Last trade ID in aggregation
  - `timestamp`: Trade timestamp (Unix milliseconds)
  - `is_buyer_maker`: Boolean (True = sell order)
  - `is_best_match`: Boolean (True = best price match)

- If `as_dataframe=False`: `List[tuple]` with same fields

**Example:**
```python
from datetime import datetime, timedelta

with BinanceDataRepository() as repo:
    # Get last 7 days
    df = repo.get_agg_trades(
        symbol="BTCUSDT",
        start_time=datetime.now() - timedelta(days=7)
    )

    # Get specific date range
    df = repo.get_agg_trades(
        symbol="BTCUSDT",
        start_time=datetime(2025, 10, 1),
        end_time=datetime(2025, 10, 15)
    )

    # Get first 1000 trades (sampling)
    df = repo.get_agg_trades(
        symbol="BTCUSDT",
        limit=1000
    )

    # Get as raw tuples (faster, less memory)
    trades = repo.get_agg_trades(
        symbol="BTCUSDT",
        limit=100,
        as_dataframe=False
    )
```

**Use Cases:**
- Historical analysis
- Backtesting strategies
- Feature engineering for ML
- Price/volume analysis

---

#### `get_agg_trades_by_date_range(symbol, days, as_dataframe)`

Convenience method to get trades for the last N days.

**Parameters:**
- `symbol` (str, required): Trading symbol
- `days` (int, optional): Number of days to look back
  - Default: `7`
- `as_dataframe` (bool, optional): Return format
  - Default: `True`

**Returns:** Same as `get_agg_trades()`

**Example:**
```python
with BinanceDataRepository() as repo:
    # Last 7 days (default)
    df = repo.get_agg_trades_by_date_range("BTCUSDT")

    # Last 30 days
    df = repo.get_agg_trades_by_date_range("BTCUSDT", days=30)
```

**Equivalent to:**
```python
end_time = datetime.now()
start_time = end_time - timedelta(days=7)
df = repo.get_agg_trades("BTCUSDT", start_time, end_time)
```

---

#### `get_realtime_trades(symbol, minutes, as_dataframe)`

Get recent trades from the last N minutes (for near real-time analysis).

**Parameters:**
- `symbol` (str, required): Trading symbol
- `minutes` (int, optional): Minutes to look back
  - Default: `5`
- `as_dataframe` (bool, optional): Return format
  - Default: `True`

**Returns:** Same format as `get_agg_trades()`

**Example:**
```python
with BinanceDataRepository() as repo:
    # Last 5 minutes
    df = repo.get_realtime_trades("BTCUSDT")

    # Last hour
    df = repo.get_realtime_trades("BTCUSDT", minutes=60)
```

**Use Cases:**
- Real-time price tracking
- Order flow monitoring
- Price alerts
- Live dashboards

---

### OHLCV (Candlestick) Methods

#### `get_ohlcv(symbol, interval, start_time, end_time, as_dataframe)`

Generate OHLCV (Open, High, Low, Close, Volume) candlestick data from tick trades.

**Parameters:**
- `symbol` (str, required): Trading symbol
- `interval` (str, optional): Candlestick interval
  - Default: `"1m"`
  - Options: `"1m"`, `"5m"`, `"15m"`, `"30m"`, `"1h"`, `"4h"`, `"1d"`

- `start_time` (datetime | int, optional): Start time filter
- `end_time` (datetime | int, optional): End time filter
- `as_dataframe` (bool, optional): Return format
  - Default: `True`

**Returns:**
- DataFrame/tuples with columns:
  - `time`: Candlestick open time (datetime)
  - `open`: Opening price (float)
  - `high`: Highest price (float)
  - `low`: Lowest price (float)
  - `close`: Closing price (float)
  - `volume`: Total volume (float)
  - `trades`: Number of trades in candle (int)

**Example:**
```python
with BinanceDataRepository() as repo:
    # 1-minute candles for last 24 hours
    candles = repo.get_ohlcv(
        symbol="BTCUSDT",
        interval="1m",
        start_time=datetime.now() - timedelta(hours=24)
    )

    # 1-hour candles for last 30 days
    hourly = repo.get_ohlcv(
        symbol="BTCUSDT",
        interval="1h",
        start_time=datetime.now() - timedelta(days=30)
    )

    # Daily candles
    daily = repo.get_ohlcv("BTCUSDT", interval="1d")

    # Calculate indicators
    hourly['sma_20'] = hourly['close'].rolling(20).mean()
    hourly['volatility'] = hourly['close'].pct_change().rolling(24).std()
```

**Use Cases:**
- Technical analysis
- Charting
- Strategy backtesting
- Indicator calculation (SMA, RSI, etc.)

**Note**: This dynamically computes OHLCV from raw trades. For frequent access to the same intervals, consider pre-computing and caching.

---

### Analytics Methods

#### `get_symbol_stats(symbol, start_time, end_time)`

Get aggregated statistics for a symbol over a time period.

**Parameters:**
- `symbol` (str, required): Trading symbol
- `start_time` (datetime | int, optional): Start time
- `end_time` (datetime | int, optional): End time

**Returns:** Dictionary with:
```python
{
    'symbol': str,              # Trading symbol
    'trade_count': int,         # Number of trades
    'total_volume': float,      # Total volume traded (base currency)
    'total_value': float,       # Total value (quote currency)
    'avg_price': float,         # Average price
    'min_price': float,         # Minimum price
    'max_price': float,         # Maximum price
    'price_range': float,       # max_price - min_price
    'avg_trade_size': float,    # Average trade volume
    'start_time': datetime,     # First trade time
    'end_time': datetime,       # Last trade time
}
```

**Example:**
```python
with BinanceDataRepository() as repo:
    # 24-hour stats
    stats = repo.get_symbol_stats(
        symbol="BTCUSDT",
        start_time=datetime.now() - timedelta(hours=24)
    )

    print(f"24h Volume: {stats['total_volume']:.2f} BTC")
    print(f"24h Range: ${stats['price_range']:.2f}")
    print(f"Average Price: ${stats['avg_price']:.2f}")
    print(f"Total Trades: {stats['trade_count']:,}")
```

**Use Cases:**
- Market overview
- Volume analysis
- Price range calculation
- Trading activity metrics

---

#### `get_volume_profile(symbol, price_bins, start_time, end_time, as_dataframe)`

Get volume distribution by price level (volume profile / market profile).

**Parameters:**
- `symbol` (str, required): Trading symbol
- `price_bins` (int, optional): Number of price buckets
  - Default: `50`
  - Higher = more granular

- `start_time` (datetime | int, optional): Start time filter
- `end_time` (datetime | int, optional): End time filter
- `as_dataframe` (bool, optional): Return format
  - Default: `True`

**Returns:**
- DataFrame/tuples with columns:
  - `price_low`: Lower bound of price range (float)
  - `price_high`: Upper bound of price range (float)
  - `total_volume`: Volume in this price range (float)
  - `trade_count`: Number of trades in this range (int)
  - `avg_price`: Average price in this range (float)

**Example:**
```python
with BinanceDataRepository() as repo:
    # Get volume profile for last 7 days
    profile = repo.get_volume_profile(
        symbol="BTCUSDT",
        price_bins=30,
        start_time=datetime.now() - timedelta(days=7)
    )

    # Find high-volume nodes (support/resistance)
    hvn = profile.sort_values('total_volume', ascending=False).head(5)
    print("High Volume Nodes (potential S/R):")
    for _, row in hvn.iterrows():
        print(f"  ${row['price_low']:.2f} - ${row['price_high']:.2f}: "
              f"{row['total_volume']:.2f} BTC")
```

**Use Cases:**
- Support/resistance identification
- Market profile analysis
- Point of control (POC) calculation
- Value area determination

**Related**: See `examples/client_examples.py` example #7 for complete support/resistance finder.

---

#### `get_order_book_snapshot(symbol, timestamp)`

Get order book snapshot at a specific time (if available).

**Parameters:**
- `symbol` (str, required): Trading symbol
- `timestamp` (datetime | int, optional): Specific time
  - Default: Latest available

**Returns:**
- DataFrame/dict with:
  - `bids`: List of [price, quantity] for buy orders
  - `asks`: List of [price, quantity] for sell orders
  - `timestamp`: Snapshot timestamp

**Example:**
```python
with BinanceDataRepository() as repo:
    # Get latest order book
    orderbook = repo.get_order_book_snapshot("BTCUSDT")

    if orderbook:
        best_bid = orderbook['bids'][0][0]
        best_ask = orderbook['asks'][0][0]
        spread = best_ask - best_bid

        print(f"Best Bid: ${best_bid:.2f}")
        print(f"Best Ask: ${best_ask:.2f}")
        print(f"Spread: ${spread:.4f}")
```

**Note**: Order book data is only available if you've enabled order book streaming. See `docs/GETTING_STARTED_STREAMING.md` for details.

---

### Utility Methods

#### `list_symbols()`

Get list of all symbols available in the database.

**Returns:** `List[str]` of symbol names

**Example:**
```python
with BinanceDataRepository() as repo:
    symbols = repo.list_symbols()
    print(f"Available symbols: {symbols}")
    # Output: ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
```

**Use Cases:**
- Multi-symbol analysis
- Portfolio tracking
- Symbol discovery

---

#### `get_data_summary()`

Get overview of all data in the database.

**Returns:** Dictionary with:
```python
{
    'total_symbols': int,           # Number of symbols
    'total_trades': int,            # Total trade count
    'symbols': [                    # Per-symbol stats
        {
            'symbol': str,
            'trade_count': int,
            'first_trade': datetime,
            'last_trade': datetime,
            'days_of_data': int,
        },
        ...
    ]
}
```

**Example:**
```python
with BinanceDataRepository() as repo:
    summary = repo.get_data_summary()

    print(f"Total symbols: {summary['total_symbols']}")
    print(f"Total trades: {summary['total_trades']:,}")

    for sym_data in summary['symbols']:
        print(f"\n{sym_data['symbol']}:")
        print(f"  Trades: {sym_data['trade_count']:,}")
        print(f"  Coverage: {sym_data['days_of_data']} days")
```

---

#### `execute_query(query, as_dataframe)`

Execute custom SQL query on the database.

**Parameters:**
- `query` (str, required): SQL query to execute
- `as_dataframe` (bool, optional): Return format
  - Default: `True`

**Returns:** Query results as DataFrame or list of tuples

**Example:**
```python
with BinanceDataRepository() as repo:
    # Custom aggregation
    query = """
        SELECT
            DATE_TRUNC('day', timestamp) as day,
            COUNT(*) as trades,
            SUM(CAST(quantity AS DOUBLE)) as volume
        FROM binance_data.agg_trades
        WHERE symbol = 'BTCUSDT'
        GROUP BY day
        ORDER BY day DESC
        LIMIT 30
    """

    daily_stats = repo.execute_query(query)
    print(daily_stats)
```

**Use Cases:**
- Complex custom queries
- Advanced filtering
- Cross-table joins
- Performance-critical queries

**Warning**: Direct SQL access bypasses type safety. Use with caution.

---

### Export Methods

#### `export_to_parquet(symbol, output_path, start_time, end_time)`

Export trades to Parquet format (efficient columnar storage).

**Parameters:**
- `symbol` (str, required): Trading symbol
- `output_path` (str | Path, required): Output file path
  - Should end with `.parquet`

- `start_time` (datetime | int, optional): Start time filter
- `end_time` (datetime | int, optional): End time filter

**Returns:** `None` (writes to file)

**Example:**
```python
with BinanceDataRepository() as repo:
    # Export last 30 days
    repo.export_to_parquet(
        symbol="BTCUSDT",
        output_path="btc_30d.parquet",
        start_time=datetime.now() - timedelta(days=30)
    )

    # Read back with pandas
    df = pd.read_parquet("btc_30d.parquet")
```

**Use Cases:**
- Data sharing
- Long-term archival
- Fast re-loading
- Cross-tool compatibility (Arrow, Spark, etc.)

**Advantages over CSV:**
- 10x smaller files
- 5x faster reads
- Preserves data types
- Column pruning support

---

#### `export_to_csv(symbol, output_path, start_time, end_time)`

Export trades to CSV format (human-readable).

**Parameters:**
- `symbol` (str, required): Trading symbol
- `output_path` (str | Path, required): Output file path
  - Should end with `.csv`

- `start_time` (datetime | int, optional): Start time filter
- `end_time` (datetime | int, optional): End time filter

**Returns:** `None` (writes to file)

**Example:**
```python
with BinanceDataRepository() as repo:
    # Export last 7 days
    repo.export_to_csv(
        symbol="BTCUSDT",
        output_path="btc_7d.csv",
        start_time=datetime.now() - timedelta(days=7)
    )

    # Can open in Excel, Google Sheets, etc.
```

**Use Cases:**
- Excel analysis
- Human inspection
- Compatibility with legacy tools
- Simple data sharing

**Note**: For large datasets (>1M rows), prefer Parquet format.

---

## Advanced Features

### Time Conversion

The repository automatically handles time conversions between:
- Python `datetime` objects
- Unix timestamps (milliseconds)
- Database timestamp format

**Example:**
```python
from datetime import datetime

# All these work:
df = repo.get_agg_trades("BTCUSDT", start_time=datetime(2025, 10, 1))
df = repo.get_agg_trades("BTCUSDT", start_time=1727740800000)  # Unix ms
df = repo.get_agg_trades("BTCUSDT", start_time="2025-10-01")   # String (if parsed)
```

### Data Type Handling

**Price and Quantity Fields:**
- Stored as strings in database (preserves precision)
- Convert to float for mathematical operations:

```python
df = repo.get_agg_trades("BTCUSDT")

# Convert for math
df['price'] = df['price'].astype(float)
df['quantity'] = df['quantity'].astype(float)

# Calculate dollar volume
df['dollar_volume'] = df['price'] * df['quantity']
```

### Read-Only vs Read-Write Mode

**Read-Only (Default, Recommended):**
```python
repo = BinanceDataRepository(read_only=True)  # Default
# Safe for concurrent access
# Multiple processes can read simultaneously
# Prevents accidental data modification
```

**Read-Write:**
```python
repo = BinanceDataRepository(read_only=False)
# Required for data modification
# Use only when necessary
# Single writer at a time
```

### Connection Pooling

For long-running applications, reuse the repository instance:

```python
# Don't do this (creates new connection each time):
def bad_pattern():
    for i in range(1000):
        with BinanceDataRepository() as repo:
            df = repo.get_agg_trades("BTCUSDT", limit=100)

# Do this instead (reuse connection):
def good_pattern():
    with BinanceDataRepository() as repo:
        for i in range(1000):
            df = repo.get_agg_trades("BTCUSDT", limit=100)
```

---

## Examples

### Example 1: Price Tracker

Build a real-time price tracker with 24h statistics:

```python
from binance_tick_data.repository import BinanceDataRepository
from datetime import datetime, timedelta

def track_price(symbol="BTCUSDT"):
    with BinanceDataRepository() as repo:
        # Get last 24 hours
        df = repo.get_agg_trades(
            symbol=symbol,
            start_time=datetime.now() - timedelta(hours=24)
        )

        # Convert price to float
        df['price'] = df['price'].astype(float)

        # Calculate metrics
        current = df['price'].iloc[-1]
        open_24h = df['price'].iloc[0]
        high_24h = df['price'].max()
        low_24h = df['price'].min()
        change = ((current / open_24h) - 1) * 100

        print(f"{symbol}")
        print(f"  Price: ${current:,.2f}")
        print(f"  24h Change: {change:+.2f}%")
        print(f"  24h High: ${high_24h:,.2f}")
        print(f"  24h Low: ${low_24h:,.2f}")

track_price()
```

### Example 2: Moving Average Crossover Strategy

```python
def sma_crossover(symbol="BTCUSDT"):
    with BinanceDataRepository() as repo:
        # Get hourly candles for last 7 days
        ohlcv = repo.get_ohlcv(
            symbol=symbol,
            interval="1h",
            start_time=datetime.now() - timedelta(days=7)
        )

        # Calculate indicators
        ohlcv['sma_20'] = ohlcv['close'].rolling(20).mean()
        ohlcv['sma_50'] = ohlcv['close'].rolling(50).mean()

        # Detect crossover
        latest = ohlcv.iloc[-1]
        prev = ohlcv.iloc[-2]

        if prev['sma_20'] <= prev['sma_50'] and latest['sma_20'] > latest['sma_50']:
            print("🟢 GOLDEN CROSS - Bullish signal!")
        elif prev['sma_20'] >= prev['sma_50'] and latest['sma_20'] < latest['sma_50']:
            print("🔴 DEATH CROSS - Bearish signal!")
        else:
            trend = "Bullish" if latest['sma_20'] > latest['sma_50'] else "Bearish"
            print(f"⚪ {trend} trend continues")

sma_crossover()
```

### Example 3: Order Flow Analysis

```python
def analyze_order_flow(symbol="BTCUSDT", hours=1):
    with BinanceDataRepository() as repo:
        # Get recent trades
        df = repo.get_agg_trades(
            symbol=symbol,
            start_time=datetime.now() - timedelta(hours=hours)
        )

        # Convert to numeric
        df['price'] = df['price'].astype(float)
        df['quantity'] = df['quantity'].astype(float)
        df['value'] = df['price'] * df['quantity']

        # Separate buy vs sell
        # is_buyer_maker=True means seller initiated (sell order)
        buys = df[~df['is_buyer_maker']]
        sells = df[df['is_buyer_maker']]

        buy_volume = buys['quantity'].sum()
        sell_volume = sells['quantity'].sum()

        ratio = buy_volume / sell_volume if sell_volume > 0 else 0

        print(f"Order Flow Analysis ({hours}h)")
        print(f"  Buy Volume: {buy_volume:,.2f} BTC")
        print(f"  Sell Volume: {sell_volume:,.2f} BTC")
        print(f"  Buy/Sell Ratio: {ratio:.2f}")

        if ratio > 1.2:
            print("  🟢 Strong buying pressure")
        elif ratio < 0.8:
            print("  🔴 Strong selling pressure")
        else:
            print("  ⚪ Balanced market")

analyze_order_flow()
```

### Example 4: Export for Machine Learning

```python
def prepare_ml_features(symbol="BTCUSDT", days=30):
    with BinanceDataRepository() as repo:
        # Get 5-minute candles
        ohlcv = repo.get_ohlcv(
            symbol=symbol,
            interval="5m",
            start_time=datetime.now() - timedelta(days=days)
        )

        # Add technical indicators
        ohlcv['returns'] = ohlcv['close'].pct_change()
        ohlcv['log_returns'] = np.log(ohlcv['close'] / ohlcv['close'].shift(1))
        ohlcv['volatility'] = ohlcv['returns'].rolling(24).std()
        ohlcv['sma_10'] = ohlcv['close'].rolling(10).mean()
        ohlcv['sma_30'] = ohlcv['close'].rolling(30).mean()
        ohlcv['rsi'] = calculate_rsi(ohlcv['close'], 14)  # Your RSI function

        # Drop NaN rows
        ohlcv = ohlcv.dropna()

        # Export for ML training
        ohlcv.to_parquet("ml_features.parquet")
        print(f"Exported {len(ohlcv)} samples for ML training")

prepare_ml_features()
```

### Example 5: Multi-Symbol Dashboard

```python
def multi_symbol_dashboard():
    with BinanceDataRepository() as repo:
        symbols = repo.list_symbols()

        print("24h Performance Dashboard")
        print(f"{'Symbol':<12} {'Price':>12} {'Change':>10} {'Volume':>12}")
        print("-" * 50)

        for symbol in symbols:
            stats = repo.get_symbol_stats(
                symbol=symbol,
                start_time=datetime.now() - timedelta(hours=24)
            )

            if stats['trade_count'] > 0:
                change_pct = ((stats['avg_price'] / stats['min_price']) - 1) * 100
                indicator = "🟢" if change_pct > 0 else "🔴"

                print(f"{symbol:<12} ${stats['avg_price']:>10,.2f} "
                      f"{indicator} {change_pct:>6.2f}% {stats['total_volume']:>10,.2f}")

multi_symbol_dashboard()
```

For more examples, see `examples/client_examples.py` which includes 10 complete usage patterns.

---

## Error Handling

### Common Errors and Solutions

#### Database Not Found

```python
try:
    with BinanceDataRepository() as repo:
        df = repo.get_agg_trades("BTCUSDT")
except FileNotFoundError:
    print("Database not found. Run data pipeline first:")
    print("  uv run python jobs/03_fill_gaps.py --symbol BTCUSDT --recent")
```

#### No Data for Symbol

```python
with BinanceDataRepository() as repo:
    df = repo.get_agg_trades("BTCUSDT")

    if df.empty:
        print("No data available for BTCUSDT")
        print("Available symbols:", repo.list_symbols())
```

#### Connection Issues

```python
repo = BinanceDataRepository()
try:
    repo.connect()
    df = repo.get_agg_trades("BTCUSDT")
except Exception as e:
    print(f"Connection error: {e}")
finally:
    repo.close()
```

### Best Practices

1. **Always use context manager** (`with` statement) for automatic cleanup
2. **Use read-only mode** unless writing data
3. **Convert price/quantity to float** before mathematical operations
4. **Check for empty DataFrames** before processing
5. **Use appropriate time ranges** to avoid memory issues
6. **Cache frequently accessed data** instead of re-querying
7. **Use Parquet for large exports** instead of CSV

---

## Performance Tips

### Query Optimization

**Bad (slow):**
```python
# Gets all data then filters in Python
with BinanceDataRepository() as repo:
    all_data = repo.get_agg_trades("BTCUSDT")
    recent = all_data[all_data['timestamp'] > some_time]  # Slow!
```

**Good (fast):**
```python
# Filters in database
with BinanceDataRepository() as repo:
    recent = repo.get_agg_trades(
        "BTCUSDT",
        start_time=some_time  # Fast! Database filters
    )
```

### Memory Management

For large datasets:

```python
# Process in chunks
with BinanceDataRepository() as repo:
    # Get date range
    start = datetime(2025, 10, 1)
    end = datetime(2025, 10, 30)

    # Process day by day
    current = start
    while current < end:
        next_day = current + timedelta(days=1)

        df = repo.get_agg_trades(
            "BTCUSDT",
            start_time=current,
            end_time=next_day
        )

        # Process chunk
        process_data(df)

        current = next_day
```

### Caching

For repeated queries:

```python
import functools

@functools.lru_cache(maxsize=128)
def get_cached_ohlcv(symbol, interval, days):
    with BinanceDataRepository() as repo:
        return repo.get_ohlcv(
            symbol,
            interval,
            start_time=datetime.now() - timedelta(days=days)
        )

# First call: hits database
df1 = get_cached_ohlcv("BTCUSDT", "1h", 7)

# Second call: returns cached result (instant)
df2 = get_cached_ohlcv("BTCUSDT", "1h", 7)
```

---

## Related Documentation

- **Quick Start Guide**: `docs/QUICK_START.md`
- **Usage Examples**: `examples/client_examples.py`
- **Streaming API**: `docs/GETTING_STARTED_STREAMING.md`
- **Data Quality**: `docs/JOBS_QUICK_START.md`
- **RLlib Integration**: `specs/rllib_specs.md`

---

## API Summary Table

| Method | Purpose | Returns |
|--------|---------|---------|
| `get_agg_trades()` | Get historical trades | DataFrame |
| `get_agg_trades_by_date_range()` | Get trades for last N days | DataFrame |
| `get_realtime_trades()` | Get recent trades | DataFrame |
| `get_ohlcv()` | Generate candlesticks | DataFrame |
| `get_symbol_stats()` | Get trading statistics | Dict |
| `get_volume_profile()` | Get volume by price | DataFrame |
| `get_order_book_snapshot()` | Get order book | Dict |
| `list_symbols()` | List available symbols | List[str] |
| `get_data_summary()` | Get database overview | Dict |
| `execute_query()` | Run custom SQL | DataFrame |
| `export_to_parquet()` | Export to Parquet | None |
| `export_to_csv()` | Export to CSV | None |

---

## Version Information

- **API Version**: 1.0
- **File**: `src/binance_tick_data/repository.py` (585 lines)
- **Enhanced Version**: `src/binance_tick_data/repository_v2.py` (873 lines)
- **Status**: Stable, production-ready
- **Last Updated**: 2025-10-21

---

## Support

For issues or questions:
1. Check `examples/client_examples.py` for usage patterns
2. Review error handling section above
3. Consult related documentation

---

**Happy trading! 📈**
