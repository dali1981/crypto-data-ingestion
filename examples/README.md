# Examples - Client Code for Reading Binance Data

This directory contains practical examples of how to read and analyze your Binance tick data.

## Quick Start

First, make sure you have data:

```bash
# Download some data (10,000 records for testing)
uv run python pipelines/historical_pipeline.py --symbols BTCUSDT --max-records 10000
```

Then run any example:

```bash
# Simplest example
uv run python examples/simple_read.py

# Complete client examples (10 different use cases)
uv run python examples/client_examples.py --example 1
```

## Available Examples

### 1. `simple_read.py` - Getting Started ⭐
**Best for**: First-time users, understanding the basics

A minimal example showing how to:
- Connect to the database
- Read last 24 hours of trades
- Display basic statistics

```bash
uv run python examples/simple_read.py
```

**Output**:
```
✅ Retrieved 1,234 trades
📅 From: 2024-10-18 10:00:00
📅 To: 2024-10-19 10:00:00
💰 Current Price: $108,850.21
```

---

### 2. `client_examples.py` - Complete Use Cases ⭐⭐⭐
**Best for**: Real-world applications, production code

10 complete examples showing practical use cases:

#### Example 1: Price Tracker
```bash
uv run python examples/client_examples.py --example 1
```
Track current price and 24h statistics.

#### Example 2: Trading Signals
```bash
uv run python examples/client_examples.py --example 2
```
Generate buy/sell signals using moving averages (Golden Cross/Death Cross).

#### Example 3: Order Flow Analysis
```bash
uv run python examples/client_examples.py --example 3
```
Analyze buy vs sell pressure, detect market sentiment.

#### Example 4: Multi-Timeframe Analysis
```bash
uv run python examples/client_examples.py --example 4
```
Compare price action across 15m, 1h, and 4h timeframes.

#### Example 5: Export Data
```bash
uv run python examples/client_examples.py --example 5
```
Export to CSV, Parquet, and Excel with technical indicators.

#### Example 6: Price Alert
```bash
uv run python examples/client_examples.py --example 6
```
Check if price has crossed a threshold.

#### Example 7: Support/Resistance
```bash
uv run python examples/client_examples.py --example 7
```
Find potential support and resistance levels using volume profile.

#### Example 8: Compare Symbols
```bash
uv run python examples/client_examples.py --example 8
```
Compare performance across multiple trading pairs.

#### Example 9: Simple Backtest
```bash
uv run python examples/client_examples.py --example 9
```
Backtest a simple moving average crossover strategy.

#### Example 10: Custom Template
```bash
uv run python examples/client_examples.py --example 10
```
Template for building your own analysis.

**Run all examples**:
```bash
uv run python examples/client_examples.py --example 0
```

---

### 3. `notebook_example.py` - Jupyter Notebook Style ⭐⭐
**Best for**: Data scientists, interactive analysis, Jupyter users

Copy-paste code blocks into Jupyter notebook cells. Includes:
- Loading data
- Generating OHLCV candles
- Calculating technical indicators (SMA, RSI, Bollinger Bands)
- Plotting charts with matplotlib
- Order flow analysis
- Volume profile
- Helper functions

```bash
# Run as script
uv run python examples/notebook_example.py

# Or copy cells into Jupyter notebook
jupyter notebook examples/notebook_example.py
```

---

### 4. `download_historical.py` - Pipeline Examples
**Best for**: Understanding data ingestion

Examples of using the historical pipeline:
- Basic download
- Custom symbols
- Date ranges
- Querying downloaded data

```bash
uv run python examples/download_historical.py --example 1
```

---

### 5. `stream_realtime.py` - Real-time Data
**Best for**: Live trading, real-time monitoring

Examples of streaming and querying real-time data:
- Basic streaming
- Monitoring while streaming
- Querying stream data

```bash
uv run python examples/stream_realtime.py --example 5
```

---

### 6. `using_repository.py` - Repository API Examples
**Best for**: Learning the API, advanced usage

8 examples demonstrating the full Repository API:
- Basic queries
- OHLCV generation
- Market statistics
- Volume profile
- Data export
- Custom SQL
- Time series analysis

```bash
uv run python examples/using_repository.py --example 1
```

---

## Common Code Patterns

### Pattern 1: Read Recent Data

```python
from binance_tick_data.repository import BinanceDataRepository
from datetime import datetime, timedelta

with BinanceDataRepository() as repo:
    df = repo.get_agg_trades(
        symbol="BTCUSDT",
        start_time=datetime.now() - timedelta(hours=24)
    )
```

### Pattern 2: Generate Candlesticks

```python
with BinanceDataRepository() as repo:
    ohlcv = repo.get_ohlcv(
        symbol="BTCUSDT",
        interval="1h",  # 1m, 5m, 15m, 1h, 4h, 1d
        start_time=datetime.now() - timedelta(days=7)
    )
```

### Pattern 3: Get Statistics

```python
with BinanceDataRepository() as repo:
    stats = repo.get_symbol_stats("BTCUSDT")
    print(f"Average price: ${stats['avg_price']:.2f}")
    print(f"Total volume: {stats['total_volume']:.2f}")
```

### Pattern 4: Export Data

```python
with BinanceDataRepository() as repo:
    repo.export_to_parquet(
        symbol="BTCUSDT",
        output_path="btc_data.parquet",
        start_time=datetime(2024, 1, 1)
    )
```

### Pattern 5: Custom SQL

```python
with BinanceDataRepository() as repo:
    df = repo.execute_query("""
        SELECT * FROM binance_historical.agg_trades
        WHERE symbol = 'BTCUSDT'
        AND timestamp > 1234567890
        LIMIT 10000
    """)
```

## Example Output Gallery

### Price Tracker
```
💰 BTC/USDT
   Current Price: $108,850.21
   24h Change: +2.34%
   24h High: $109,500.00
   24h Low: $106,000.00
```

### Trading Signals
```
📊 Technical Analysis (1H timeframe)
   Current Price: $108,850.21
   SMA 20: $108,200.50
   SMA 50: $107,500.00

   🟢 Bullish trend (SMA20 > SMA50)
```

### Order Flow
```
📈 Order Flow (Last 1 hour)

   Buy Orders:
      Count: 1,234
      Volume: 45.67 BTC
      Value: $4,970,000.00

   Sell Orders:
      Count: 1,100
      Volume: 40.23 BTC
      Value: $4,380,000.00

   📊 Buy/Sell Ratio: 1.14
   🟢 Strong buying pressure!
```

## Tips for Using Examples

### 1. Start Simple
Begin with `simple_read.py` to understand the basics, then move to more complex examples.

### 2. Modify for Your Needs
All examples are templates - copy and customize them for your specific use case.

### 3. Check Data Availability
If an example returns "No data available", you need to download data first:
```bash
uv run python pipelines/historical_pipeline.py --symbols BTCUSDT --max-records 10000
```

### 4. Use Context Managers
Always use `with BinanceDataRepository() as repo:` to ensure connections are closed properly.

### 5. Filter Early
Filter data at query time, not after loading:
```python
# ✅ Good - filter in database
df = repo.get_agg_trades(symbol="BTCUSDT", start_time=recent_date)

# ❌ Bad - load everything then filter
df = repo.execute_query("SELECT * FROM ...")
df = df[df['symbol'] == 'BTCUSDT']  # Slow!
```

## Building Your Own Application

### Quick Template

```python
from binance_tick_data.repository import BinanceDataRepository
from datetime import datetime, timedelta

def my_analysis():
    """Your custom analysis function."""
    with BinanceDataRepository() as repo:
        # 1. Get your data
        df = repo.get_agg_trades_by_date_range("BTCUSDT", days=7)

        # 2. Process it
        df['price'] = df['price'].astype(float)

        # 3. Your analysis here
        avg_price = df['price'].mean()
        print(f"Average price: ${avg_price:,.2f}")

        # 4. Return or save results
        return avg_price

if __name__ == "__main__":
    my_analysis()
```

## Troubleshooting

### "No data available"
**Solution**: Download data first:
```bash
uv run python pipelines/historical_pipeline.py --symbols BTCUSDT --max-records 10000
```

### "Table does not exist"
**Solution**: Same as above - download data first.

### "Database is locked"
**Solution**: Close other connections:
```python
with BinanceDataRepository() as repo:
    # Your code here
# Connection auto-closed
```

### Import errors
**Solution**: Install missing packages:
```bash
uv add pandas pyarrow matplotlib  # For plotting examples
```

## Next Steps

1. **Run simple_read.py** to verify everything works
2. **Explore client_examples.py** for real-world patterns
3. **Modify examples** for your specific needs
4. **Read REPOSITORY_GUIDE.md** for complete API reference
5. **Check STORAGE_COMPARISON.md** for storage options

## Additional Resources

- **REPOSITORY_GUIDE.md** - Complete API documentation
- **DATA_MANAGEMENT.md** - Data management guide
- **STORAGE_COMPARISON.md** - DuckDB vs Parquet
- **README.md** - Main project documentation

---

**Ready to analyze your data?**

```bash
uv run python examples/simple_read.py
```
