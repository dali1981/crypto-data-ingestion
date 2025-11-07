# Quick Start Guide - Fixed Pipeline

## Overview

The Dagster pipeline has been fixed to properly produce parquet files in a date-partitioned structure.

## What Changed?

**Before:** Pipeline ran for hours but produced NO files ❌

**After:** Pipeline creates properly partitioned parquet files ✅

```
data/binance_data/agg_trades/
├── 2025-10-22/
│   ├── BTCUSDT.parquet
│   ├── ETHUSDT.parquet
│   └── ... (20 symbols)
└── 2025-10-23/
    └── ...
```

## Quick Start

### 1. Validate Setup

```bash
uv run python test_dagster_asset.py
```

Expected output:
```
✅ All validation tests passed!
```

### 2. Start Dagster UI

```bash
./start_dagster.sh
```

Navigate to: http://localhost:3000

### 3. Materialize Asset

In Dagster UI:
1. Go to **Assets** tab
2. Click `raw_agg_trades`
3. Click **Materialize**
4. Monitor logs

### 4. Verify Output

```bash
# Check files were created
ls -lh data/binance_data/agg_trades/*/

# Count files
find data/binance_data/agg_trades -name "*.parquet" | wc -l

# Check file sizes
du -sh data/binance_data/agg_trades/*
```

### 5. Query Data

```python
import duckdb

conn = duckdb.connect('binance_pipeline.duckdb', read_only=True)

# Get total row count
result = conn.execute("SELECT COUNT(*) FROM binance_data.agg_trades").fetchone()
print(f"Total rows: {result[0]:,}")

# Get data for specific symbol and date
df = conn.execute("""
    SELECT *
    FROM binance_data.agg_trades
    WHERE symbol = 'BTCUSDT'
      AND date = '2025-10-22'
    LIMIT 10
""").df()

print(df)
```

## Expected Timeline

### Initial Backfill (First Run)
- **Symbols:** 20
- **Date Range:** 2025-10-22 to present
- **Time:** 5-10 minutes (varies by data volume)
- **Output:** ~40 files (2 days × 20 symbols)

### Incremental Updates (Subsequent Runs)
- **Time:** 2-3 minutes
- **Fetches:** Last 24 hours per symbol
- **Output:** 20 files per day

## Data Structure

### File Naming
```
data/binance_data/agg_trades/{date}/{symbol}.parquet

Examples:
  data/binance_data/agg_trades/2025-10-22/BTCUSDT.parquet
  data/binance_data/agg_trades/2025-10-22/ETHUSDT.parquet
  data/binance_data/agg_trades/2025-10-23/BTCUSDT.parquet
```

### Schema
```
agg_trade_id: int64        # Unique trade ID
price: float64             # Trade price
quantity: float64          # Trade quantity
first_trade_id: int64      # First trade ID in aggregation
last_trade_id: int64       # Last trade ID in aggregation
timestamp: int64           # Unix timestamp (ms)
is_buyer_maker: bool       # Buyer was maker
is_best_match: bool        # Best price match
symbol: string             # Trading pair
date: date                 # Trade date (for partitioning)
```

## Validation

### Asset Checks

The pipeline includes built-in validation:

1. **validate_agg_trades_files**
   - Verifies parquet files exist
   - Checks files contain data
   - Reports file counts and row counts

2. **validate_agg_trades_coverage**
   - Ensures all 20 symbols have data
   - Reports coverage percentage
   - Identifies missing symbols

View in Dagster UI: **Asset Details** → **Checks** tab

## Troubleshooting

### No Files Created

```bash
# Check Dagster logs
# Look for errors in materialization

# Verify staging directory
ls -la .dlt_staging/binance_staging/

# If staging has data but output doesn't, check permissions
chmod -R u+w data/
```

### DuckDB View Missing

```bash
# Recreate view manually
uv run python -c "
import duckdb
conn = duckdb.connect('binance_pipeline.duckdb')
conn.execute('CREATE SCHEMA IF NOT EXISTS binance_data')
conn.execute('''
    CREATE OR REPLACE VIEW binance_data.agg_trades AS
    SELECT * FROM read_parquet(\"data/binance_data/agg_trades/**/*.parquet\")
''')
print('View created successfully')
"
```

### Performance Issues

```bash
# Reduce symbol count for testing
# Edit dagster_pipeline/config.py:
SYMBOLS = ["BTCUSDT", "ETHUSDT"]  # Test with 2 symbols first

# Or limit date range
HISTORICAL_START_DATE = "2025-10-22"  # Recent date only
```

## Testing

### Small Test Run

```bash
uv run python test_asset_materialize.py
```

This runs a limited test:
- 2 symbols only (BTCUSDT, ETHUSDT)
- Recent date (2025-10-22)
- ~1-2 minutes

### Full Production Run

Via Dagster UI (all 20 symbols, full date range)

## Next Steps

1. ✅ Initial backfill complete
2. Set up scheduled updates (optional)
3. Enable downstream assets:
   - Dollar bars
   - Volume bars
   - Tick bars
4. Set up monitoring/alerts

## Configuration

**Symbols:** `dagster_pipeline/config.py` → `SYMBOLS` list

**Date Range:** `dagster_pipeline/config.py` → `HISTORICAL_START_DATE`

**DuckDB Path:** `dagster_pipeline/config.py` → `DB_PATH`

## Support

For issues, check:
1. `ARCHITECTURE_UPDATE.md` - Detailed architecture documentation
2. Dagster UI logs - Real-time execution logs
3. `.dlt_staging/` - DLT staging data

## Summary

**✅ Pipeline Fixed**
- Produces date-partitioned parquet files
- DuckDB read layer for efficient queries
- Built-in validation checks
- Ready for production use

**📊 Data Location**
- Parquet: `data/binance_data/agg_trades/{date}/{symbol}.parquet`
- DuckDB: `binance_data.agg_trades` view

**🚀 Performance**
- Initial: 5-10 min for 2 days
- Incremental: 2-3 min per day
- Scales to millions of rows
