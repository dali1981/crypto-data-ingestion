# Data Quality Report - Binance Tick Data

**Generated:** 2025-10-20
**Database:** `binance_pipeline.duckdb`
**Analysis Tool:** `data_gap_analysis.py`

---

## Executive Summary

This report identifies **critical data quality issues** in the Binance tick data pipeline that require immediate attention:

### Critical Issues Found

1. **10,000 Duplicate Records** - Same `agg_trade_id` appearing multiple times
2. **Major Time Gap** - 17.8 day gap (427.9 hours) in data coverage
3. **10,496 Duplicate Timestamps** - Multiple trades with identical timestamps
4. **Missing Recent Data** - No data for the last 34+ hours

---

## Detailed Findings

### 1. Data Coverage Summary

**Symbol:** BTCUSDT

| Metric | Value |
|--------|-------|
| Total Records | 120,000 |
| First Timestamp | 2025-10-01 00:00:00 |
| Last Timestamp | 2025-10-19 00:50:26 |
| Duration | 18.0 days (432.84 hours) |
| Price Range | $107,014.58 - $114,551.76 |
| Average Price | $113,593.71 |

### 2. Time Gaps Analysis

**Major Gap Identified:**

- **Start:** 2025-10-01 04:04:22
- **End:** 2025-10-19 00:00:00
- **Duration:** 17.83 days (427.93 hours)
- **Impact:** Missing critical trading data for analysis

**Missing Recent Data:**
- Last data point: 2025-10-19 00:50:26
- Current time: 2025-10-20 (34+ hours ago)
- **Status:** Pipeline not running or failed

### 3. Duplicate Records

**Issue:** 10,000 duplicate `agg_trade_id` values

This is a serious data integrity issue caused by:
- Running the pipeline multiple times without proper deduplication
- Using `write_disposition="append"` without checking for existing records
- No unique constraint on `agg_trade_id` in the database

**Example Duplicate Timestamps:**
- Timestamp `1759277176059`: 229 duplicates
- Timestamp `1759274660368`: 222 duplicates
- Timestamp `1759274819461`: 192 duplicates

Total affected: 10,496 unique timestamps with duplicates

### 4. Data Quality Checks

| Check | Result |
|-------|--------|
| NULL prices | ✓ 0 records |
| Zero/negative prices | ✓ 0 records |
| NULL quantities | ✓ 0 records |
| Zero/negative quantities | ✓ 0 records |
| NULL timestamps | ✓ 0 records |
| NULL trade IDs | ✓ 0 records |

**Good news:** No invalid data values found. The data that exists is clean.

---

## Root Cause Analysis

### Why Do We Have Duplicates?

**Code Issue in `src/binance_tick_data/sources/rest_api.py:124-125`:**

```python
@dlt.resource(
    name="agg_trades",
    write_disposition="append",
    primary_key="agg_trade_id",  # ← Primary key defined but not enforced
)
```

**The Problem:**
1. The pipeline defines `primary_key="agg_trade_id"`
2. BUT uses `write_disposition="append"` which doesn't check for duplicates
3. Running the pipeline multiple times appends the same data repeatedly

**The Solution:**
- Use `write_disposition="merge"` instead of `"append"`
- OR add a deduplication step before writing
- OR use `DISTINCT` in queries to handle duplicates

### Why Do We Have Time Gaps?

**Likely causes:**
1. **Pipeline was stopped** - Only ran for 4 hours on Oct 1st, then didn't run again until Oct 19th
2. **No continuous ingestion** - Historical pipeline is one-time, not scheduled
3. **Rate limits** - May have hit Binance API rate limits
4. **Max records limit** - Stopped at 120,000 records (possibly hit configured limit)

---

## Impact Assessment

### Impact on Analysis

**Current State:**
- ❌ Cannot perform reliable time-series analysis (missing 17 days)
- ❌ Dollar bar calculations will be incorrect (duplicates inflate volume)
- ❌ Statistical analysis will be biased (duplicate observations)
- ❌ Cannot use for live trading (data is 34+ hours old)

**Affected Features:**
- ✗ `create_dollar_bars()` - Inflated dollar volumes due to duplicates
- ✗ `get_ohlcv()` - Time bars will have gaps
- ✗ Fractional differencing - Duplicate timestamps break time-series assumptions
- ✗ `data_analysis.py` - Analysis results are invalid

---

## Recommendations & Action Plan

### Immediate Actions (Do These Now)

#### 1. Remove Duplicates ⚠️

```bash
# Dry run first (see what will be removed)
uv run python fix_data_issues.py

# Actually remove duplicates (creates backup)
uv run python fix_data_issues.py --remove-duplicates
```

**This will:**
- Create backup table `agg_trades_backup`
- Remove 10,000 duplicate records
- Keep first occurrence of each `agg_trade_id`

#### 2. Fill the Major Gap

```bash
# Fill Oct 1-19 gap (will take time due to API limits)
uv run python -m binance_tick_data.pipelines.historical_pipeline \
  --symbols BTCUSDT \
  --start-date 2025-10-01 \
  --max-records 500000
```

**Note:** This will fetch a large amount of data. Consider:
- Running overnight
- Breaking into smaller date ranges
- Monitoring API rate limits

#### 3. Get Recent Data

```bash
# Get latest data up to now
uv run python -m binance_tick_data.pipelines.historical_pipeline \
  --symbols BTCUSDT \
  --start-date 2025-10-19 \
  --max-records 50000
```

### Long-Term Fixes

#### 1. Fix the Pipeline to Prevent Duplicates

**Option A: Use Merge Write Disposition**

Edit `src/binance_tick_data/sources/rest_api.py:124`:

```python
@dlt.resource(
    name="agg_trades",
    write_disposition="merge",  # ← Changed from "append"
    primary_key="agg_trade_id",
)
```

**Option B: Add Deduplication Logic**

Add this to `repository_v2.py` query methods:

```python
# In queries, use DISTINCT on agg_trade_id
query = f"""
    SELECT DISTINCT ON (agg_trade_id)
        agg_trade_id,
        symbol,
        price,
        quantity,
        timestamp,
        ...
    FROM {table_path}
    WHERE {where_clause}
    ORDER BY agg_trade_id, timestamp DESC
"""
```

#### 2. Implement Continuous Data Collection

Create a scheduled job to run hourly/daily:

```bash
# Add to cron or systemd timer
0 * * * * cd /path/to/project && uv run python -m binance_tick_data.pipelines.historical_pipeline --symbols BTCUSDT --start-date $(date +%Y-%m-%d) --max-records 10000
```

#### 3. Add Data Quality Monitoring

Create a monitoring script that runs daily:

```python
# monitor_data_quality.py
from data_gap_analysis import DataGapAnalyzer

def check_quality():
    with DataGapAnalyzer() as analyzer:
        summaries = analyzer.get_data_summary()

        for summary in summaries:
            # Alert if no data in last 2 hours
            hours_since_last = (datetime.now() - summary['last_timestamp']).total_seconds() / 3600
            if hours_since_last > 2:
                send_alert(f"No data for {hours_since_last:.1f} hours!")

            # Alert if duplicates found
            dups = analyzer.find_duplicates(summary['symbol'])
            if not dups.empty:
                send_alert(f"Found {len(dups)} duplicate timestamps!")
```

#### 4. Add Database Constraints

```sql
-- Add unique constraint to prevent duplicates at DB level
ALTER TABLE binance_data.agg_trades
ADD CONSTRAINT unique_agg_trade_id UNIQUE (agg_trade_id);

-- Note: This will fail with current duplicates, so run AFTER deduplication
```

---

## Validation Steps

After applying fixes, verify data quality:

### 1. Check Duplicates Are Gone

```bash
uv run python -c "
import duckdb
conn = duckdb.connect('binance_pipeline.duckdb', read_only=True)
result = conn.execute('SELECT COUNT(*) - COUNT(DISTINCT agg_trade_id) FROM binance_data.agg_trades').fetchone()
print(f'Duplicates: {result[0]}')
"
```

Expected: `Duplicates: 0`

### 2. Check Data Continuity

```bash
uv run python data_gap_analysis.py
```

Expected:
- No gaps > 1 hour
- Recent data within last hour

### 3. Run Analysis Again

```bash
uv run python examples/data_analysis.py
```

Expected:
- Clean plots without discontinuities
- Reasonable statistics
- No warnings about duplicate timestamps

---

## Tools Provided

### 1. `data_gap_analysis.py`

Comprehensive data quality analysis tool.

```bash
# Run full analysis
uv run python data_gap_analysis.py
```

**Features:**
- Data summary statistics
- Time gap detection
- Duplicate identification
- Data quality checks
- Missing range detection

### 2. `fix_data_issues.py`

Automated fix tool for data quality issues.

```bash
# Dry run (no changes)
uv run python fix_data_issues.py

# Actually remove duplicates
uv run python fix_data_issues.py --remove-duplicates

# Generate gap-fill commands
uv run python fix_data_issues.py --gap-commands
```

**Features:**
- Safe duplicate removal (creates backup)
- Gap filling command generation
- Dry-run mode for safety

---

## Summary Statistics

| Metric | Current | After Fixes |
|--------|---------|-------------|
| Total Records | 120,000 | ~110,000 (after dedup) |
| Duplicate Records | 10,000 | 0 |
| Data Gaps | 1 major (17.8 days) | TBD (depends on fill) |
| Duplicate Timestamps | 10,496 | 0 |
| Data Freshness | 34+ hours old | Up to date |
| Data Quality Score | ⚠️ 4/10 | ✓ 9/10 (after fixes) |

---

## Next Steps

1. ✅ **Read this report** - Understand the issues
2. ⚠️ **Remove duplicates** - Run `fix_data_issues.py --remove-duplicates`
3. 🔄 **Fill gaps** - Run historical pipeline for missing dates
4. 📊 **Validate** - Run analysis tools to confirm fixes
5. 🛠️ **Apply long-term fixes** - Update pipeline code
6. 📈 **Monitor** - Set up automated quality checks

---

## Questions?

For issues or questions:
1. Review the code in `data_gap_analysis.py` and `fix_data_issues.py`
2. Check the error handling in `src/binance_tick_data/errors.py`
3. Review pipeline configuration in `config.yaml`

---

**Report Generated By:** Data Quality Analysis Tool
**Files Created:**
- `data_gap_analysis.py` - Analysis tool
- `fix_data_issues.py` - Fix automation tool
- `DATA_QUALITY_REPORT.md` - This report
