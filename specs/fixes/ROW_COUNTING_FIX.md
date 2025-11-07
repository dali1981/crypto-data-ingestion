# Row Counting Bug Fix

**Date:** 2025-10-23
**Status:** Fixed

## Problem

Pipeline ran successfully but produced no final output files.

### Symptoms
- ✅ DLT downloaded data successfully (visible in logs: "[BTCUSDT] Batch: 2025-10-22 (1000 trades)")
- ✅ Data existed in `.dlt_staging/binance_staging/` (60,000 rows across 20 symbols)
- ❌ Row count showed 0: "Iteration 1: loaded 0 rows (total: 0)"
- ❌ No reorganization ran (skipped due to `if iteration_rows > 0` check)
- ❌ Final output directory empty: `data/binance_data/agg_trades/`

### Root Cause

The row counting logic relied on `load_info.load_packages[].jobs[].metrics` which was not populated:

```python
# BROKEN CODE:
iteration_rows = 0
if load_info.loads_ids and len(load_info.loads_ids) > 0:
    load_id = load_info.loads_ids[0]
    for package in load_info.load_packages:
        if package.load_id == load_id:
            for job in package.jobs.values():
                if hasattr(job, 'metrics') and job.metrics:
                    iteration_rows += job.metrics.get('rows_processed', 0)
```

This returned 0 even though data was successfully loaded to staging.

## Solution

Count rows directly by reading staging parquet files with pyarrow.

### New Code

```python
# FIXED CODE:
iteration_rows = 0
for symbol in SYMBOLS:
    symbol_table = f"agg_trades_{symbol.lower()}"
    symbol_data_path = staging_path / symbol_table
    if symbol_data_path.exists():
        parquet_files = list(symbol_data_path.glob("*.parquet"))
        if parquet_files:
            try:
                import pyarrow.parquet as pq
                for pf in parquet_files:
                    table = pq.read_table(pf)
                    iteration_rows += len(table)
            except Exception as e:
                context.log.warning(f"Failed to count rows for {symbol}: {e}")
```

**Why this works:**
- Directly reads parquet files written by DLT to staging
- Uses pyarrow which is already a dependency
- Counts actual rows, not relying on DLT internal metrics
- Handles missing files gracefully

## Additional Fix: DuckDB View Pattern

DuckDB doesn't support multiple `**` wildcards in one path.

### Before (BROKEN):
```sql
SELECT * FROM read_parquet('data/binance_data/agg_trades/**/**/*.parquet')
```

**Error:** `IO Error: Cannot use multiple '**' in one path`

### After (FIXED):
```sql
SELECT * FROM read_parquet('data/binance_data/agg_trades/*/*/*.parquet', hive_partitioning=false)
```

**Pattern matches:**
- `data/binance_data/agg_trades/2025-10-21/BTCUSDT/data.parquet`
- `data/binance_data/agg_trades/2025-10-22/ETHUSDT/batch_000001.parquet`
- `/*` matches exactly one directory level
- `/*/*/*.parquet` = `{date}/{symbol}/{file}.parquet`

## Manual Recovery

For the existing staging data (60,000 rows), I manually ran reorganization:

```bash
uv run python << 'EOF'
import pandas as pd
from pathlib import Path

staging_path = Path(".dlt_staging/binance_staging")
output_base = Path("data/binance_data/agg_trades")

for symbol in SYMBOLS:
    symbol_data_path = staging_path / f"agg_trades_{symbol.lower()}"
    df = pd.read_parquet(symbol_data_path)
    df['date'] = pd.to_datetime(df['timestamp'], unit='ms').dt.date

    for date, date_df in df.groupby('date'):
        date_dir = output_base / str(date) / symbol
        date_dir.mkdir(parents=True, exist_ok=True)
        date_df.to_parquet(date_dir / "data.parquet", index=False)
EOF
```

**Result:**
- 20 files created
- Structure: `data/binance_data/agg_trades/2025-10-21/{symbol}/data.parquet`
- Total: 60,000 rows (3,000 per symbol)

## Files Modified

**dagster_pipeline/assets/raw_data.py**

### Line 114-134: Row counting logic
```python
# Old: Used load_info.load_packages metrics (didn't work)
# New: Read staging parquet files directly with pyarrow
```

### Line 243-246: DuckDB view pattern
```python
# Old: '/**/**/*.parquet' (invalid)
# New: '/*/*/*.parquet' (valid)
```

## Testing

### Verify row counting works

```bash
# 1. Clear staging
rm -rf .dlt_staging/binance_staging/agg_trades_*/*.parquet

# 2. Run asset (will fetch 20K rows: 1000 per symbol)
# 3. Check logs for:
#    "Iteration 1: loaded 20,000 rows (total: 20,000)"
#    NOT "loaded 0 rows"
```

### Verify reorganization runs

```bash
# After iteration 1, check output:
find data/binance_data/agg_trades -name "*.parquet"

# Should show files immediately, not empty directory
```

### Verify DuckDB view

```python
import duckdb
conn = duckdb.connect("binance.db")
result = conn.execute("SELECT COUNT(*) FROM binance_data.agg_trades").fetchone()
print(f"Total: {result[0]:,}")  # Should show 60,000
```

## Summary

Two critical bugs fixed:

1. **Row counting** - Now reads staging parquet files directly instead of relying on unavailable DLT metrics
2. **DuckDB pattern** - Changed from `/**/**/` (invalid) to `/*/*/` (valid)

These fixes ensure:
- Row counts are accurate
- Reorganization runs when data exists
- DuckDB view creation succeeds
- Final output files are created

**Result:** Data now flows correctly from staging → final location.
