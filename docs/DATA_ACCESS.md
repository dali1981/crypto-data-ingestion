# Accessing Binance Data from Other Projects

This guide shows how to access the Binance data (daily candles and aggregated trades) stored in MinIO from other Python projects.

## Overview

Data is stored in **MinIO** (S3-compatible storage) using **Delta Lake** format:

```
s3://binance-data/warehouse/binance_test/
├── BTCUSDT_DAILY/          # Daily candlestick data
│   ├── _delta_log/         # Delta Lake transaction log
│   └── *.parquet           # Data files
└── BTCUSDT/                # Aggregated trades (if using Delta Lake)
    ├── _delta_log/
    ├── date=2024-01-01/    # Date-partitioned data
    ├── date=2024-01-02/
    └── ...
```

**Key Features:**
- ACID transactions via Delta Lake
- Efficient partition pruning (for agg trades)
- Time travel capabilities
- S3-compatible storage (MinIO running on localhost:9000)

## Prerequisites

Install required Python packages:

```bash
pip install deltalake pyarrow pandas duckdb
```

Or with uv:

```bash
uv add deltalake pyarrow pandas duckdb
```

## Configuration

### MinIO Credentials

MinIO is running locally with these credentials:
- **S3 Endpoint**: `http://localhost:9000`
- **Access Key**: `minioadmin`
- **Secret Key**: `minioadmin`
- **Region**: `us-east-1`

Set environment variables:

```python
import os

os.environ['AWS_ACCESS_KEY_ID'] = 'minioadmin'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'minioadmin'
os.environ['AWS_ENDPOINT_URL'] = 'http://localhost:9000'
os.environ['AWS_REGION'] = 'us-east-1'
```

## Access Methods

### Method 1: Using deltalake-python (Recommended)

#### Daily Candles

```python
import os
from deltalake import DeltaTable
import pandas as pd

# Configure S3 credentials
os.environ['AWS_ACCESS_KEY_ID'] = 'minioadmin'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'minioadmin'
os.environ['AWS_ENDPOINT_URL'] = 'http://localhost:9000'

# Load Delta table
dt = DeltaTable('s3://binance-data/warehouse/binance_test/BTCUSDT_DAILY')

# Convert to pandas
df = dt.to_pandas()

print(f"Loaded {len(df)} daily candles")
print(df.head())

# Schema
print("\nColumns:")
print(df.columns.tolist())
# ['symbol', 'open_time', 'open', 'high', 'low', 'close',
#  'volume', 'close_time', 'quote_volume', 'trades',
#  'taker_buy_base', 'taker_buy_quote', 'date']
```

#### Aggregated Trades (with Partition Filtering)

```python
from deltalake import DeltaTable
import pyarrow.compute as pc

# Load Delta table
dt = DeltaTable('s3://binance-data/warehouse/binance_test/BTCUSDT')

# Efficient partition filtering (only reads relevant partitions)
df = dt.to_pyarrow_dataset().to_table(
    filter=(pc.field("date") >= "2024-01-01") & (pc.field("date") <= "2024-01-31")
).to_pandas()

print(f"Loaded {len(df)} trades from January 2024")

# Schema
# ['agg_trade_id', 'price', 'quantity', 'first_trade_id', 'last_trade_id',
#  'timestamp', 'is_buyer_maker', 'is_best_match', 'symbol', 'date']
```

### Method 2: Using DuckDB

DuckDB provides SQL interface with Delta Lake support:

```python
import duckdb

# Create connection
con = duckdb.connect()

# Configure S3 credentials
con.execute("""
    SET s3_endpoint='localhost:9000';
    SET s3_access_key_id='minioadmin';
    SET s3_secret_access_key='minioadmin';
    SET s3_use_ssl=false;
    SET s3_url_style='path';
""")

# Query daily candles
df = con.execute("""
    SELECT
        date,
        CAST(open AS DOUBLE) as open,
        CAST(high AS DOUBLE) as high,
        CAST(low AS DOUBLE) as low,
        CAST(close AS DOUBLE) as close,
        CAST(volume AS DOUBLE) as volume,
        trades
    FROM delta_scan('s3://binance-data/warehouse/binance_test/BTCUSDT_DAILY')
    WHERE date >= '2024-01-01'
    ORDER BY date
""").df()

print(df.head())
```

### Method 3: PyArrow with Pandas

Direct PyArrow access for advanced filtering:

```python
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.compute as pc
from deltalake import DeltaTable

# Load as PyArrow dataset
dt = DeltaTable('s3://binance-data/warehouse/binance_test/BTCUSDT')
dataset = dt.to_pyarrow_dataset()

# Advanced filtering
table = dataset.to_table(
    filter=(
        (pc.field("date") >= "2024-01-01") &
        (pc.field("date") <= "2024-01-31") &
        (pc.field("price").cast(pa.float64()) > 40000.0)
    ),
    columns=['agg_trade_id', 'price', 'quantity', 'timestamp', 'date']
)

df = table.to_pandas()
print(f"Filtered to {len(df)} trades")
```

## Complete Example Script

```python
"""
Example script to load Binance data from another project.
"""
import os
from deltalake import DeltaTable
import pyarrow.compute as pc
import pandas as pd

# Configure MinIO S3 access
os.environ['AWS_ACCESS_KEY_ID'] = 'minioadmin'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'minioadmin'
os.environ['AWS_ENDPOINT_URL'] = 'http://localhost:9000'

def load_daily_candles(symbol: str, start_date: str = None, end_date: str = None):
    """Load daily candles for a symbol with optional date filtering."""
    table_path = f's3://binance-data/warehouse/binance_test/{symbol}_DAILY'

    dt = DeltaTable(table_path)

    if start_date or end_date:
        filters = []
        if start_date:
            filters.append(pc.field("date") >= start_date)
        if end_date:
            filters.append(pc.field("date") <= end_date)

        filter_expr = filters[0]
        for f in filters[1:]:
            filter_expr = filter_expr & f

        df = dt.to_pyarrow_dataset().to_table(filter=filter_expr).to_pandas()
    else:
        df = dt.to_pandas()

    # Convert string columns to numeric
    numeric_cols = ['open', 'high', 'low', 'close', 'volume',
                   'quote_volume', 'taker_buy_base', 'taker_buy_quote']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col])

    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')

    return df

def load_agg_trades(symbol: str, start_date: str, end_date: str):
    """Load aggregated trades for a symbol with date filtering."""
    table_path = f's3://binance-data/warehouse/binance_test/{symbol}'

    dt = DeltaTable(table_path)

    # Efficient partition filtering
    df = dt.to_pyarrow_dataset().to_table(
        filter=(pc.field("date") >= start_date) & (pc.field("date") <= end_date)
    ).to_pandas()

    # Convert string columns to numeric
    df['price'] = pd.to_numeric(df['price'])
    df['quantity'] = pd.to_numeric(df['quantity'])

    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

    return df

if __name__ == "__main__":
    # Example: Load daily candles
    print("Loading daily candles...")
    candles = load_daily_candles('BTCUSDT', start_date='2024-01-01', end_date='2024-01-31')
    print(f"Loaded {len(candles)} daily candles")
    print(candles.head())

    # Example: Load aggregated trades
    print("\nLoading aggregated trades...")
    trades = load_agg_trades('BTCUSDT', start_date='2024-01-01', end_date='2024-01-01')
    print(f"Loaded {len(trades)} trades for 2024-01-01")
    print(trades.head())
```

## Data Schemas

### Daily Candles Schema

| Column | Type | Description |
|--------|------|-------------|
| `symbol` | string | Trading pair (e.g., "BTCUSDT") |
| `open_time` | int64 | Candle open time (milliseconds) |
| `open` | string | Open price |
| `high` | string | High price |
| `low` | string | Low price |
| `close` | string | Close price |
| `volume` | string | Trading volume |
| `close_time` | int64 | Candle close time (milliseconds) |
| `quote_volume` | string | Quote asset volume |
| `trades` | int64 | Number of trades |
| `taker_buy_base` | string | Taker buy base asset volume |
| `taker_buy_quote` | string | Taker buy quote asset volume |
| `date` | string | Date in YYYY-MM-DD format |

**Primary Key**: `["symbol", "open_time"]`

### Aggregated Trades Schema

| Column | Type | Description |
|--------|------|-------------|
| `agg_trade_id` | int64 | Aggregate trade ID |
| `price` | string | Trade price |
| `quantity` | string | Trade quantity |
| `first_trade_id` | int64 | First trade ID in aggregate |
| `last_trade_id` | int64 | Last trade ID in aggregate |
| `timestamp` | int64 | Trade timestamp (milliseconds) |
| `is_buyer_maker` | bool | Buyer is maker |
| `is_best_match` | bool | Best price match |
| `symbol` | string | Trading pair |
| `date` | string | Date in YYYY-MM-DD format (partition key) |

**Primary Key**: `agg_trade_id`
**Partition Key**: `date`

## Performance Tips

### 1. Use Partition Filtering

For aggregated trades (date-partitioned), always filter by date to avoid scanning all partitions:

```python
# Good - only scans January partitions
df = dt.to_pyarrow_dataset().to_table(
    filter=pc.field("date") >= "2024-01-01"
).to_pandas()

# Bad - scans all partitions
df = dt.to_pandas()
df_filtered = df[df['date'] >= '2024-01-01']
```

### 2. Select Only Required Columns

```python
# Only load needed columns
df = dt.to_pyarrow_dataset().to_table(
    columns=['date', 'open', 'high', 'low', 'close'],
    filter=pc.field("date") >= "2024-01-01"
).to_pandas()
```

### 3. Use PyArrow for Large Datasets

PyArrow is more memory-efficient than pandas for initial filtering:

```python
# Filter in PyArrow, then convert to pandas
table = dt.to_pyarrow_dataset().to_table(
    filter=pc.field("date") >= "2024-01-01"
)
# Additional PyArrow operations...
df = table.to_pandas()  # Convert only final result
```

## Advanced Features

### Time Travel

Query historical versions of Delta tables:

```python
from deltalake import DeltaTable

dt = DeltaTable('s3://binance-data/warehouse/binance_test/BTCUSDT_DAILY')

# List versions
print(f"Current version: {dt.version()}")
history = dt.history()
print(history)

# Load specific version
dt_v0 = DeltaTable('s3://binance-data/warehouse/binance_test/BTCUSDT_DAILY', version=0)
df_v0 = dt_v0.to_pandas()

# Load as of timestamp
dt_past = DeltaTable(
    's3://binance-data/warehouse/binance_test/BTCUSDT_DAILY',
    as_of_timestamp="2024-10-20T12:00:00Z"
)
df_past = dt_past.to_pandas()
```

### Incremental Processing

Track which data you've already processed:

```python
import json
from pathlib import Path

STATE_FILE = Path("processing_state.json")

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"last_date": None}

def save_state(state):
    STATE_FILE.write_text(json.dumps(state))

# Load only new data
state = load_state()
last_date = state.get("last_date", "2024-01-01")

dt = DeltaTable('s3://binance-data/warehouse/binance_test/BTCUSDT')
df = dt.to_pyarrow_dataset().to_table(
    filter=pc.field("date") > last_date
).to_pandas()

if not df.empty:
    # Process new data
    process_data(df)

    # Update state
    save_state({"last_date": df['date'].max()})
```

## Troubleshooting

### Connection Refused

**Problem**: `Connection refused` when accessing MinIO

**Solution**:
```bash
# Check if MinIO is running
docker-compose ps

# Start MinIO if not running
docker-compose up -d

# Check MinIO logs
docker-compose logs -f minio
```

### Access Denied

**Problem**: `Access Denied` error

**Solution**: Verify S3 credentials are set:
```python
import os
print(os.environ.get('AWS_ACCESS_KEY_ID'))  # Should be 'minioadmin'
print(os.environ.get('AWS_ENDPOINT_URL'))   # Should be 'http://localhost:9000'
```

### Table Not Found

**Problem**: `Table not found` error

**Solution**: Verify the table exists in MinIO:
```bash
# List buckets
docker exec binance-minio mc ls myminio

# List tables (if mc alias is configured)
docker exec binance-minio mc ls myminio/binance-data/warehouse/binance_test/
```

Or check via MinIO Console: http://localhost:9001

### SSL Certificate Errors

**Problem**: SSL verification errors

**Solution**: Ensure `AWS_ENDPOINT_URL` uses `http://` (not `https://`):
```python
os.environ['AWS_ENDPOINT_URL'] = 'http://localhost:9000'  # Not https
```

### Memory Issues with Large Datasets

**Problem**: Out of memory when loading large date ranges

**Solution**: Process in chunks:
```python
import pandas as pd
from datetime import datetime, timedelta

def load_in_chunks(start_date, end_date, chunk_days=7):
    """Load data in weekly chunks."""
    current = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    while current <= end:
        chunk_end = min(current + timedelta(days=chunk_days), end)

        df_chunk = load_agg_trades(
            'BTCUSDT',
            current.strftime("%Y-%m-%d"),
            chunk_end.strftime("%Y-%m-%d")
        )

        yield df_chunk
        current = chunk_end + timedelta(days=1)

# Process in chunks
for df_chunk in load_in_chunks('2024-01-01', '2024-12-31', chunk_days=7):
    process_chunk(df_chunk)
```

## References

- [Delta Lake Documentation](https://delta.io/)
- [deltalake-python API](https://delta-io.github.io/delta-rs/python/)
- [DuckDB Delta Lake Extension](https://duckdb.org/docs/extensions/delta.html)
- [PyArrow Documentation](https://arrow.apache.org/docs/python/)
- [MinIO Python Client](https://min.io/docs/minio/linux/developers/python/minio-py.html)
