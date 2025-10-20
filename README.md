# Binance Tick Data Ingestion Library

A comprehensive Python library for downloading and streaming Binance tick data using [dlt (data load tool)](https://dlthub.com/). Supports both historical data backfill and real-time WebSocket streaming, with local storage in DuckDB/Parquet format.

## Features

- **Multiple Data Types**: Trade ticks, aggregated trades, and order book snapshots
- **Historical Data**: Download historical tick data via Binance REST API
- **Real-time Streaming**: Stream live data via Binance WebSocket API
- **Efficient Storage**: DuckDB with Parquet backing for fast queries and analysis
- **Incremental Loading**: Automatic deduplication using trade IDs
- **Schema Validation**: Pydantic models for data validation
- **Rate Limiting**: Built-in respect for Binance API rate limits
- **Error Handling**: Automatic reconnection and retry logic

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Binance Tick Data Library                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Historical Data (REST API)    Real-time Data (WebSocket)   │
│  ├─ Trade ticks                ├─ Live trade stream         │
│  ├─ Aggregated trades          ├─ Live agg trade stream     │
│  └─ Order book snapshots       └─ Order book depth updates  │
│                                                              │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
         ┌──────────────────┐
         │   dlt Pipeline    │
         │  - Data loading   │
         │  - Schema mgmt    │
         │  - Incremental    │
         └─────────┬─────────┘
                   │
                   ▼
         ┌──────────────────┐
         │  DuckDB + Parquet │
         │  - Fast queries   │
         │  - Columnar store │
         │  - Low overhead   │
         └──────────────────┘
```

## Installation

This project uses `uv` for dependency management:

```bash
# 1. Navigate to the project
cd dlt-starter

# 2. Install the package in editable mode (recommended)
uv pip install -e .

# 3. Verify installation
uv run python -c "from binance_tick_data import BinanceDataRepository; print('✅ Installed!')"
```

**Why editable mode?**
- Changes to code are immediately available
- Can import `binance_tick_data` from anywhere
- Perfect for development

See [INSTALLATION.md](INSTALLATION.md) for details.

## Quick Start

### 1. Historical Data Download

Download historical tick data for specified symbols:

```bash
# Using uv (recommended for first time - limits to 10k records)
uv run python pipelines/historical_pipeline.py \
    --symbols BTCUSDT \
    --start-date 2024-10-01 \
    --max-records 10000

# Full download (can take a while!)
uv run python pipelines/historical_pipeline.py --symbols BTCUSDT ETHUSDT --start-date 2024-10-01
```

### 2. Real-time Streaming

Stream live tick data:

```bash
# Using uv
uv run python pipelines/realtime_pipeline.py --symbols BTCUSDT ETHUSDT

# Stream with limited batches (for testing)
uv run python pipelines/realtime_pipeline.py --symbols BTCUSDT --max-batches 10
```

### 3. Query Your Data

```python
from binance_tick_data.repository import BinanceDataRepository

# Query data easily
with BinanceDataRepository() as repo:
    # Get last 7 days of trades
    df = repo.get_agg_trades_by_date_range("BTCUSDT", days=7)

    # Get OHLCV candlesticks
    ohlcv = repo.get_ohlcv("BTCUSDT", interval="1h")

    # Get market statistics
    stats = repo.get_symbol_stats("BTCUSDT")

print(f"Retrieved {len(df):,} trades")
print(f"Average price: ${stats['avg_price']:.2f}")
```

### 4. Using the Library Directly

```python
import dlt
from binance_tick_data import BinanceConfig, binance_historical_data

# Configure with max records limit
config = BinanceConfig(
    symbols=["BTCUSDT"],
    historical_start_date="2024-10-01",
    historical_max_records=10000,  # Limit download
)

# Create pipeline
pipeline = dlt.pipeline(
    pipeline_name="binance_data",
    destination="duckdb",
    dataset_name="binance",
)

# Download historical data
source = binance_historical_data(config)
load_info = pipeline.run(source)
print(load_info)
```

## Project Structure

```
dlt-starter/
├── src/
│   └── binance_tick_data/       # Main package (pip installed)
│       ├── __init__.py
│       ├── config.py
│       ├── repository.py        # ⭐ Data access layer
│       ├── parquet_storage.py   # Parquet storage
│       ├── utils.py
│       └── sources/
│           ├── rest_api.py      # Historical (REST)
│           ├── websocket.py     # Real-time (WebSocket)
│           └── schemas.py
│
├── pipelines/                   # Pipeline scripts
│   ├── historical_pipeline.py
│   └── realtime_pipeline.py
│
├── examples/                    # Client code examples
│   ├── simple_read.py          # ⭐ Start here!
│   ├── client_examples.py      # 10 real-world use cases
│   ├── notebook_example.py     # Jupyter style
│   └── README.md
│
├── config.toml                  # dlt configuration
└── pyproject.toml               # Package configuration
```

## Configuration

### Using config.toml

Edit `config.toml` to configure data sources, destinations, and pipeline settings:

```toml
[sources.binance_tick_data]
api_key = ""                     # Optional (for higher rate limits)
api_secret = ""
symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
historical_start_date = "2024-01-01"
stream_buffer_size = 100

[destination.duckdb]
credentials = "dlt_binance.duckdb"
```

### Using Python Config

```python
from binance_tick_data import BinanceConfig

config = BinanceConfig(
    symbols=["BTCUSDT", "ETHUSDT"],
    historical_start_date="2024-10-01",
    stream_buffer_size=100,
    api_key="your_api_key",        # Optional
    api_secret="your_api_secret",  # Optional
)
```

## Data Schema

### Trade Ticks
Individual executed trades with:
- `id`: Trade ID (primary key)
- `price`: Trade price
- `qty`: Trade quantity
- `time`: Trade timestamp (milliseconds)
- `isBuyerMaker`: Whether buyer is maker
- `symbol`: Trading pair symbol

### Aggregated Trades
Trades aggregated by Binance:
- `agg_trade_id`: Aggregated trade ID (primary key)
- `price`: Price
- `quantity`: Quantity
- `timestamp`: Timestamp
- `first_trade_id`: First trade in aggregate
- `last_trade_id`: Last trade in aggregate
- `symbol`: Trading pair symbol

### Order Book Snapshots
Current order book state:
- `symbol`: Trading pair
- `timestamp`: Snapshot time
- `last_update_id`: Last update ID
- `bids`: Array of [price, quantity] bid levels
- `asks`: Array of [price, quantity] ask levels

## Querying Data

### Using DuckDB CLI

```bash
duckdb dlt_binance.duckdb
```

```sql
-- View all tables
SHOW TABLES;

-- Count trades by symbol
SELECT symbol, COUNT(*) as trade_count
FROM binance_historical.trades
GROUP BY symbol;

-- Get average trade price
SELECT symbol, AVG(CAST(price AS DECIMAL)) as avg_price
FROM binance_historical.trades
GROUP BY symbol;

-- Analyze buy/sell pressure
SELECT
    symbol,
    SUM(CASE WHEN is_buyer_maker THEN 1 ELSE 0 END) as sells,
    SUM(CASE WHEN NOT is_buyer_maker THEN 1 ELSE 0 END) as buys
FROM binance_realtime.realtime_trades
GROUP BY symbol;
```

### Using Python

```python
import duckdb

conn = duckdb.connect("dlt_binance.duckdb")

# Query data
result = conn.execute("""
    SELECT symbol, COUNT(*) as count
    FROM binance_historical.trades
    GROUP BY symbol
""").fetchall()

print(result)
conn.close()
```

## Examples

Run the provided examples:

```bash
# Historical data examples
uv run python examples/download_historical.py --example 1  # Basic download
uv run python examples/download_historical.py --example 2  # Custom symbols
uv run python examples/download_historical.py --example 3  # Single symbol
uv run python examples/download_historical.py --example 4  # Query data

# Real-time streaming examples
uv run python examples/stream_realtime.py --example 1  # Basic streaming
uv run python examples/stream_realtime.py --example 2  # Custom symbols
uv run python examples/stream_realtime.py --example 3  # Limited batches
uv run python examples/stream_realtime.py --example 4  # Real-time monitoring
uv run python examples/stream_realtime.py --example 5  # Query stream data
```

## Alternative Tools Comparison

| Tool | Best For | Pros | Cons |
|------|----------|------|------|
| **dlt** ✅ | Python-native pipelines | Lightweight, flexible, great for streaming | Fewer pre-built connectors |
| **Airbyte** | UI-driven ETL | Pre-built Binance connector, good UI | Heavy, less Python-native |
| **Meltano** | Scheduled ELT | Good for production schedules | More complex setup |
| **Prefect/Dagster** | Complex orchestration | Advanced workflow features | Overkill for simple pipelines |
| **Custom** | Full control | Complete flexibility | More development time |

**Why dlt?**
- Python-first design perfect for data science workflows
- Native support for streaming and batch processing
- Automatic schema evolution and inference
- Minimal overhead compared to full orchestration frameworks
- Excellent DuckDB integration for local analytics

## Advanced Features

### Incremental Loading

dlt automatically handles incremental loading using primary keys:

```python
@dlt.resource(
    name="trades",
    write_disposition="append",
    primary_key="id",  # Automatic deduplication
)
def historical_trades(...):
    ...
```

### Custom Destinations

Switch destinations easily in `config.toml`:

```toml
# PostgreSQL
[destination.postgres]
credentials = "postgresql://user:password@localhost:5432/binance"

# BigQuery
[destination.bigquery]
credentials.project_id = "your-project"
credentials.private_key = "path/to/key.json"
```

### Rate Limiting

The library respects Binance API limits:
- REST API: 1200 requests/minute (configurable)
- WebSocket: Automatic reconnection on disconnection
- Built-in backoff and retry logic

## Troubleshooting

### DuckDB Connection Issues

If you get "database is locked" errors:
```python
# Ensure proper connection closing
conn = duckdb.connect("dlt_binance.duckdb")
try:
    # ... queries ...
finally:
    conn.close()
```

### WebSocket Disconnections

WebSocket streams automatically reconnect. Configure reconnection delay:
```python
config = BinanceConfig(reconnect_delay=5)  # seconds
```

### API Rate Limits

If you hit rate limits:
1. Add API credentials to `config.toml` for higher limits
2. Reduce batch sizes in `BinanceConfig`
3. Add delays between requests

## Contributing

Contributions welcome! Areas for improvement:
- Additional data types (klines, book ticker, etc.)
- More destination support (ClickHouse, TimescaleDB)
- Advanced data transformations
- Performance optimizations

## Resources

- [dlt Documentation](https://dlthub.com/docs)
- [Binance API Documentation](https://binance-docs.github.io/apidocs/spot/en/)
- [DuckDB Documentation](https://duckdb.org/docs/)
- [python-binance Library](https://python-binance.readthedocs.io/)

## License

MIT License - See LICENSE file for details

## Support

For issues or questions:
1. Check the [dlt documentation](https://dlthub.com/docs)
2. Review Binance API docs for data-specific questions
3. Open an issue in this repository

---

Built with [dlt](https://dlthub.com/) - The open-source Python library for data ingestion.
