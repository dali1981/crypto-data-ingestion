# Dagster Pipeline Architecture Update

**Date:** 2025-10-23
**Status:** ✅ Completed

## Problem Statement

The original Dagster asset `raw_agg_trades_dlt` was **not producing any parquet files** despite running for hours. The pipeline ran without errors but no aggregate trades data appeared in the expected location.

### Root Causes

1. **DLT Integration Issue**: The `@dlt_assets` decorator with `yield from dlt.run()` was not properly executing the DLT pipeline in the Dagster context
2. **File Structure Mismatch**: DLT expected structure (`data/parquet/binance_data/agg_trades_{symbol}/*.parquet`) didn't match desired structure
3. **No Validation**: Pipeline had no checks to verify output files were created
4. **IO Manager Confusion**: ParquetIOManager had workaround for dict outputs that masked the real issue

## Solution Architecture

### Target Structure

```
data/
└── binance_data/
    └── agg_trades/
        ├── 2025-10-22/
        │   ├── BTCUSDT.parquet
        │   ├── ETHUSDT.parquet
        │   └── ... (20 symbols)
        ├── 2025-10-23/
        │   └── ...
        └── {date}/
            └── {symbol}.parquet
```

**Benefits:**
- Daily partitioning for efficient date-range queries
- One file per symbol per day (simple structure)
- Easy to manage incremental updates
- Natural for time-series analysis

### DuckDB Read Layer

```sql
-- View over all parquet files
CREATE OR REPLACE VIEW binance_data.agg_trades AS
SELECT * FROM read_parquet('data/binance_data/agg_trades/**/*.parquet');

-- Query with filters
SELECT * FROM binance_data.agg_trades
WHERE symbol = 'BTCUSDT'
  AND date >= '2025-10-22'
  AND date <= '2025-10-23';
```

**Benefits:**
- No data duplication (DuckDB reads parquet directly)
- Fast columnar queries
- Automatic partition pruning
- No schema drift (single source of truth)

## Implementation Changes

### 1. Rewrite `raw_agg_trades_dlt` Asset

**File:** `dagster_pipeline/assets/raw_data.py`

**Changes:**
- Removed `@dlt_assets` decorator
- Added explicit DLT pipeline execution with error handling
- Implemented custom date-based partitioning logic
- Added deduplication on append
- Returns dict metadata instead of relying on DLT output

**Process Flow:**
```
1. Run DLT pipeline → writes to staging (.dlt_staging/binance_staging/)
2. Read staging data per symbol
3. Add date column from timestamp
4. Group by date and write to target structure
5. Create/update DuckDB view
6. Return metadata (row counts, files created)
```

### 2. Update DuckDB Resource

**File:** `dagster_pipeline/resources/duckdb_query.py`

**Changes:**
- Added `query_agg_trades()` helper method
- Support for date and symbol filtering
- Optimized for date-partitioned structure

**Usage:**
```python
# Get BTCUSDT data for specific date range
df = duckdb_query.query_agg_trades(
    symbols=['BTCUSDT'],
    start_date='2025-10-22',
    end_date='2025-10-23'
)
```

### 3. Fix ParquetIOManager

**File:** `dagster_pipeline/resources/parquet_io_manager.py`

**Changes:**
- Cleaned up dict-handling logic (removed workaround)
- Now properly handles dict metadata outputs
- Calls DuckDB view update when receiving metadata

### 4. Add Asset Validation

**File:** `dagster_pipeline/assets/asset_checks.py` (NEW)

**Checks:**
1. `validate_agg_trades_files`: Verify files exist and contain data
2. `validate_agg_trades_coverage`: Ensure all symbols have data

**Metadata Tracked:**
- Total files created
- Files with data
- Unique dates
- Unique symbols
- Coverage percentage

### 5. Update .gitignore

**File:** `.gitignore`

**Added:**
```
.dlt_staging/          # DLT staging directory
.tmp_dagster_home*/    # Dagster temporary homes
.dlt/pipelines/        # DLT pipeline state (keep config.toml)
```

## Testing

### Validation Test

```bash
uv run python test_dagster_asset.py
```

**Validates:**
- ✅ Dagster definitions load correctly
- ✅ Assets, checks, and resources defined
- ✅ Output directory structure can be created

### Materialization Test

```bash
uv run python test_asset_materialize.py
```

**Tests:**
- Limited dataset (2 symbols, recent date)
- Full pipeline execution
- File creation validation
- DuckDB view validation

### Production Run

```bash
# Start Dagster UI
./start_dagster.sh

# Navigate to http://localhost:3000
# Materialize 'raw_agg_trades' asset
# Monitor logs for progress
```

## Performance Characteristics

### Initial Backfill
- **Symbols:** 20
- **Date Range:** 2025-10-22 to present (~2 days)
- **Expected Time:** 5-10 minutes (depends on data volume)
- **Expected Output:** ~40 parquet files (2 days × 20 symbols)

### Incremental Updates
- **Frequency:** Daily or on-demand
- **Time:** ~2-3 minutes (fetches last 24h per symbol)
- **New Files:** 20 per day (one per symbol)

### Data Volume Estimates
- BTCUSDT: ~1.2M trades/day → ~50 MB/day
- Other symbols: ~100K-800K trades/day → ~5-35 MB/day
- **Total:** ~300-500 MB/day for all 20 symbols

## Migration Notes

### Before
```
data/parquet/binance_data/
├── agg_trades_btcusdt/*.parquet  (DLT structure - NOT CREATED)
├── agg_trades_ethusdt/*.parquet  (DLT structure - NOT CREATED)
└── _dlt_pipeline_state/*.parquet (DLT metadata - NOT CREATED)
```

### After
```
data/binance_data/agg_trades/
├── 2025-10-22/
│   ├── BTCUSDT.parquet
│   ├── ETHUSDT.parquet
│   └── ...
└── 2025-10-23/
    └── ...
```

### State Tracking

DLT state is still tracked in `.dlt_staging/` for incremental loading:
- `.dlt_staging/binance_staging/_dlt_pipeline_state/*.parquet`

This allows incremental updates to fetch only new data since last run.

## Verification Checklist

After running the pipeline, verify:

- [ ] Files created in `data/binance_data/agg_trades/{date}/{symbol}.parquet`
- [ ] All 20 symbols have files
- [ ] Each date directory has 20 parquet files
- [ ] DuckDB view `binance_data.agg_trades` exists
- [ ] View returns data: `SELECT COUNT(*) FROM binance_data.agg_trades`
- [ ] Asset checks pass (green in Dagster UI)
- [ ] File sizes reasonable (~5-50 MB per file)

## Next Steps

1. **Run initial backfill** to populate historical data
2. **Enable schedules** for automatic daily updates
3. **Monitor asset checks** for data quality
4. **Set up downstream assets** for:
   - Dollar bars computation
   - Volume bars computation
   - Tick bars computation
5. **Re-enable jobs and sensors** (currently disabled)

## Files Modified

- `dagster_pipeline/assets/raw_data.py` - Complete rewrite of DLT asset
- `dagster_pipeline/__init__.py` - Remove DagsterDltResource, add asset checks
- `dagster_pipeline/resources/duckdb_query.py` - Add query helper
- `dagster_pipeline/resources/parquet_io_manager.py` - Fix dict handling
- `.gitignore` - Add DLT staging and Dagster temp directories

## Files Created

- `dagster_pipeline/assets/asset_checks.py` - Validation checks
- `test_dagster_asset.py` - Validation test script
- `test_asset_materialize.py` - Materialization test script
- `ARCHITECTURE_UPDATE.md` - This document

## Dependencies

No new dependencies added. Uses existing:
- `dagster` - Orchestration framework
- `dlt` - Data loading tool (explicit pipeline execution)
- `duckdb` - Query engine for parquet files
- `pandas` - Data manipulation
- `pyarrow` - Parquet I/O

## Rollback Plan

If issues arise:

1. Revert to commit before changes: `git checkout <previous-commit>`
2. Or manually revert files listed above
3. DLT staging data in `.dlt_staging/` can be safely deleted
4. No data loss (original structure was never created anyway)
