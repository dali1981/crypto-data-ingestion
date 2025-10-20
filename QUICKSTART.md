# Binance Tick Data Library - Quick Start

## Installation

```bash
uv pip install -e .
```

## Download Data

### Safe Incremental Download (Recommended)
Downloads data with incremental writes - safe to interrupt:

```bash
# Download 10k records
uv run binance-download-safe --symbols BTCUSDT --max-records 10000 --start-date 2025-10-01

# Download unlimited (all available data from start date)
uv run binance-download-safe --symbols BTCUSDT ETHUSDT --start-date 2025-01-01

# Custom chunk size (writes every N records)
uv run binance-download-safe --symbols BTCUSDT --max-records 100000 --chunk-size 5000
```

### Standard Download
Buffers all data in memory and writes at the end:

```bash
uv run binance-download --symbols BTCUSDT --max-records 10000 --start-date 2025-10-01
```

## Read Data

### Using Python

```python
from binance_tick_data.repository import BinanceDataRepository
from datetime import datetime, timedelta

# Read last 24 hours
with BinanceDataRepository() as repo:
    df = repo.get_agg_trades(
        symbol="BTCUSDT",
        start_time=datetime.now() - timedelta(hours=24)
    )
    print(f"Retrieved {len(df):,} trades")
    print(df.head())
```

### Example Script

```bash
uv run examples/simple_read.py
```

## Database

All data is stored in: **`binance_pipeline.duckdb`**

- Both `binance-download` and `binance-download-safe` write to the same database
- Data is stored in the `binance_data` schema
- Tables: `agg_trades`, `trades`, `order_book_snapshots`

## Repository Features

```python
from binance_tick_data.repository import BinanceDataRepository

with BinanceDataRepository() as repo:
    # Get aggregated trades
    df = repo.get_agg_trades(symbol="BTCUSDT", start_time=datetime(2025, 10, 1))

    # Get OHLCV candlesticks (computed from trades)
    candles = repo.get_ohlcv(symbol="BTCUSDT", interval="5m")

    # Get statistics
    stats = repo.get_symbol_stats(symbol="BTCUSDT")

    # Get volume profile
    volume_profile = repo.get_volume_profile(symbol="BTCUSDT", price_bins=50)

    # Export to Parquet
    repo.export_to_parquet(
        symbol="BTCUSDT",
        output_path="btc_data.parquet",
        start_time=datetime(2025, 10, 1)
    )

    # Export to CSV
    repo.export_to_csv(
        symbol="BTCUSDT",
        output_path="btc_data.csv"
    )
```

## CLI Commands

After installation, these commands are available globally:

- `binance-download` - Standard historical download
- `binance-download-safe` - Incremental download (recommended)
- `binance-stream` - Real-time WebSocket streaming

## Next Steps

1. Download some data: `uv run binance-download-safe --symbols BTCUSDT --max-records 10000 --start-date 2025-10-01`
2. Run the example: `uv run examples/simple_read.py`
3. Build your own analysis using the repository methods
