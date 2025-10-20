# Data Management Guide

## Where Does the Data Go?

All downloaded data is stored in a **DuckDB database** file:

```
./dlt_binance.duckdb
```

This file is created automatically in your project root directory.

## Database Structure

### Historical Data Tables
- `binance_historical.trades` - Individual trade ticks
- `binance_historical.agg_trades` - Aggregated trades (recommended)
- `binance_historical.order_book_snapshots` - Order book snapshots

### Real-time Data Tables
- `binance_realtime.realtime_trades` - Live trade stream
- `binance_realtime.realtime_agg_trades` - Live aggregated trades
- `binance_realtime.realtime_depth` - Order book depth updates

## Checking Your Data

### 1. Check Database Size
```bash
ls -lh dlt_binance.duckdb
```

### 2. Query Record Counts
```bash
duckdb dlt_binance.duckdb
```

```sql
-- Count aggregated trades
SELECT COUNT(*) FROM binance_historical.agg_trades;

-- Count by symbol
SELECT symbol, COUNT(*) as count
FROM binance_historical.agg_trades
GROUP BY symbol;

-- Check date range
SELECT
    symbol,
    MIN(timestamp) as first_trade,
    MAX(timestamp) as last_trade,
    COUNT(*) as total_trades
FROM binance_historical.agg_trades
GROUP BY symbol;
```

### 3. Using Python
```python
import duckdb

conn = duckdb.connect("dlt_binance.duckdb")

# Count records
result = conn.execute("""
    SELECT COUNT(*) FROM binance_historical.agg_trades
""").fetchone()
print(f"Total records: {result[0]:,}")

conn.close()
```

## Controlling Download Size

### Problem: Downloads Too Much Data

If you start from 2024-01-01, you'll download **millions of trades**!

### Solution 1: Use Recent Start Date

```bash
# Download last 7 days only
uv run python pipelines/historical_pipeline.py \
    --symbols BTCUSDT \
    --start-date 2025-10-12

# Download just today
uv run python pipelines/historical_pipeline.py \
    --symbols BTCUSDT \
    --start-date 2025-10-19
```

### Solution 2: Limit Number of Records (NEW!)

```bash
# Download only 10,000 records
uv run python pipelines/historical_pipeline.py \
    --symbols BTCUSDT \
    --start-date 2024-01-01 \
    --max-records 10000

# Download 100,000 records
uv run python pipelines/historical_pipeline.py \
    --symbols BTCUSDT \
    --max-records 100000
```

### Solution 3: Stop Anytime with Ctrl+C

The pipeline saves data in batches, so you can stop it anytime:
- Press **Ctrl+C**
- Data already downloaded will be saved
- You can resume later (dlt handles deduplication)

## Data Volume Examples

For BTCUSDT aggregated trades:

| Time Period | Approximate Records | Download Time |
|-------------|---------------------|---------------|
| 1 day | ~50,000 | 1-2 minutes |
| 1 week | ~350,000 | 5-10 minutes |
| 1 month | ~1,500,000 | 20-30 minutes |
| 1 year | ~18,000,000 | 3-6 hours |

**Tip**: Start with **1 week** of data for testing!

## Managing Storage

### Check Database Size
```bash
# On macOS/Linux
du -h dlt_binance.duckdb

# Detailed info
ls -lh dlt_binance.duckdb
```

### Export Data
```python
from binance_tick_data.utils import export_to_parquet

# Export to Parquet (compressed)
export_to_parquet(
    db_path="dlt_binance.duckdb",
    dataset_name="binance_historical",
    table_name="agg_trades",
    output_path="btc_trades.parquet",
    where_clause="symbol = 'BTCUSDT'"
)

# Then you can delete the database if needed
```

### Delete Old Data
```sql
-- Connect to database
duckdb dlt_binance.duckdb

-- Delete old data
DELETE FROM binance_historical.agg_trades
WHERE timestamp < 1704067200000;  -- Before 2024-01-01

-- Vacuum to reclaim space
VACUUM;
```

## Recommended Download Strategies

### 1. Quick Test (Recommended for First Time)
```bash
# Just 10,000 records from yesterday
uv run python pipelines/historical_pipeline.py \
    --symbols BTCUSDT \
    --start-date 2025-10-18 \
    --max-records 10000
```

### 2. Last Week Analysis
```bash
# One week of data
uv run python pipelines/historical_pipeline.py \
    --symbols BTCUSDT ETHUSDT \
    --start-date 2025-10-12
```

### 3. Full Historical Backfill
```bash
# WARNING: This will take HOURS and use lots of disk space!
uv run python pipelines/historical_pipeline.py \
    --symbols BTCUSDT \
    --start-date 2024-01-01
```

### 4. Incremental Updates
```bash
# Download today's data
uv run python pipelines/historical_pipeline.py \
    --symbols BTCUSDT \
    --start-date $(date +%Y-%m-%d)
```

## Monitoring Downloads

### Watch Progress in Real-time

In another terminal while download is running:

```bash
# On macOS/Linux
watch -n 2 'duckdb dlt_binance.duckdb "SELECT symbol, COUNT(*) FROM binance_historical.agg_trades GROUP BY symbol"'

# Or manually
while true; do
    duckdb dlt_binance.duckdb "SELECT COUNT(*) FROM binance_historical.agg_trades"
    sleep 5
done
```

### Python Monitoring Script
```python
import duckdb
import time

conn = duckdb.connect("dlt_binance.duckdb")

while True:
    try:
        result = conn.execute("""
            SELECT
                symbol,
                COUNT(*) as count,
                MAX(timestamp) as latest
            FROM binance_historical.agg_trades
            GROUP BY symbol
        """).fetchall()

        print("\n" + "="*50)
        for symbol, count, latest in result:
            print(f"{symbol}: {count:,} trades (latest: {latest})")

        time.sleep(5)
    except KeyboardInterrupt:
        break

conn.close()
```

## Understanding the Data

### Aggregated Trades vs Regular Trades

**Use `agg_trades` (recommended)**:
- ✅ Smaller file size (10x less data)
- ✅ Faster downloads
- ✅ Good for price analysis
- ✅ Includes price, quantity, time

**Use `trades` only if**:
- You need individual trade IDs
- You need exact order matching details
- You're doing microstructure analysis

### Data Schema

**Aggregated Trades** (`agg_trades`):
```sql
agg_trade_id    BIGINT    -- Unique ID
price           VARCHAR   -- Trade price (as string for precision)
quantity        VARCHAR   -- Trade quantity
first_trade_id  BIGINT    -- First trade in aggregate
last_trade_id   BIGINT    -- Last trade in aggregate
timestamp       BIGINT    -- Milliseconds since epoch
is_buyer_maker  BOOLEAN   -- True = sell, False = buy
is_best_match   BOOLEAN   -- Best price match
symbol          VARCHAR   -- Trading pair (BTCUSDT)
```

## Backup and Recovery

### Backup Database
```bash
# Simple copy
cp dlt_binance.duckdb dlt_binance_backup.duckdb

# With timestamp
cp dlt_binance.duckdb dlt_binance_$(date +%Y%m%d).duckdb

# Compress
tar -czf dlt_binance_backup.tar.gz dlt_binance.duckdb
```

### Export for Analysis
```bash
# Export to CSV
duckdb dlt_binance.duckdb "COPY (SELECT * FROM binance_historical.agg_trades) TO 'trades.csv' (HEADER, DELIMITER ',')"

# Export to Parquet
duckdb dlt_binance.duckdb "COPY (SELECT * FROM binance_historical.agg_trades) TO 'trades.parquet' (FORMAT PARQUET)"
```

## Troubleshooting

### "Database is locked"
Only one process can write at a time. Close other connections.

### Running Out of Disk Space
1. Use `--max-records` to limit downloads
2. Export to Parquet and delete database
3. Download smaller date ranges

### Download Taking Forever
1. Use more recent `--start-date`
2. Add `--max-records` limit
3. Press Ctrl+C and use the data you have

### How to Resume After Stopping
Just run the same command again! dlt handles deduplication automatically.

## Quick Commands Reference

```bash
# Check what you have
duckdb dlt_binance.duckdb "SELECT symbol, COUNT(*) FROM binance_historical.agg_trades GROUP BY symbol"

# Check date range
duckdb dlt_binance.duckdb "SELECT MIN(timestamp), MAX(timestamp) FROM binance_historical.agg_trades"

# Check database size
ls -lh dlt_binance.duckdb

# Download with limit (RECOMMENDED!)
uv run python pipelines/historical_pipeline.py --symbols BTCUSDT --start-date 2025-10-12 --max-records 10000

# Stop download safely
Ctrl+C
```

---

**Remember**: Start small with `--max-records 10000` or a recent `--start-date`, then scale up once you understand the data volume!
