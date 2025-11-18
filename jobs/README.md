## Data Quality Jobs System

This directory contains automated jobs for maintaining data quality in the Binance tick data pipeline.

## Architecture

The system uses **append mode** for data ingestion with **separate deduplication jobs** to handle duplicates. This approach is more reliable than merge mode and allows for incremental data collection.

```
┌─────────────────────────────────────────────────────────────┐
│                    Data Quality Pipeline                     │
└─────────────────────────────────────────────────────────────┘

  1. Quality Assessment  →  2. Deduplication  →  3. Gap Filling
     ┌────────────┐           ┌────────────┐       ┌────────────┐
     │ Analyze    │           │ Remove     │       │ Fetch      │
     │ - Gaps     │  ──────>  │ duplicates │  ───> │ missing    │
     │ - Dups     │           │ (if found) │       │ data       │
     │ - Freshness│           └────────────┘       └────────────┘
     └────────────┘
```

## Jobs Overview

### 1. Quality Assessment (`01_data_quality_assessment.py`)

**Purpose:** Analyze current data state and generate recommendations

**What it does:**
- Counts duplicate records
- Detects time gaps (> 1 hour)
- Checks data freshness
- Validates data quality (NULL values, invalid prices, etc.)
- Generates actionable recommendations

**Usage:**
```bash
# Run assessment
uv run python jobs/01_data_quality_assessment.py

# Output JSON only
uv run python jobs/01_data_quality_assessment.py --json
```

**Output:**
- Console report with findings
- JSON report in `jobs/reports/quality_assessment_latest.json`
- Exit code 1 if issues found, 0 if healthy

---

### 2. Deduplication (`02_deduplication.py`)

**Purpose:** Remove duplicate records based on `agg_trade_id`

**What it does:**
- Creates backup table before making changes
- Removes duplicates (keeps first occurrence)
- Verifies all duplicates removed
- Safe dry-run mode by default

**Usage:**
```bash
# Dry run (default - shows what would be done)
uv run python jobs/02_deduplication.py

# Actually remove duplicates
uv run python jobs/02_deduplication.py --execute
```

**Safety Features:**
- Dry-run by default
- Creates `agg_trades_backup` table
- Verification step after removal
- Can be reverted if needed

**Output:**
- Console report with statistics
- JSON report in `jobs/reports/deduplication_latest.json`
- Backup table: `binance_data.agg_trades_backup`

---

### 3. Gap Filling (`03_fill_gaps.py`)

**Purpose:** Fill missing data ranges intelligently

**What it does:**
- Automatically chunks large date ranges to handle `max_records` limit
- Fetches data incrementally with progress tracking
- Respects API rate limits
- Can resume if interrupted

**Usage:**
```bash
# Daily job: get last 24 hours (recommended for cron)
uv run python jobs/03_fill_gaps.py --symbol BTCUSDT --recent

# Fill largest gap
uv run python jobs/03_fill_gaps.py --symbol BTCUSDT --fill-largest-gap

# Fill all gaps (one by one)
uv run python jobs/03_fill_gaps.py --symbol BTCUSDT --fill-all-gaps

# Fill specific date range (auto-chunks if needed)
uv run python jobs/03_fill_gaps.py --symbol BTCUSDT \
  --start-date 2025-10-01 --end-date 2025-10-20

# Custom max records per chunk
uv run python jobs/03_fill_gaps.py --symbol BTCUSDT --recent --max-records 100000
```

**Key Feature - Automatic Chunking:**
The job automatically breaks large date ranges into chunks that won't exceed `max_records`:

```python
# Example: Filling 10 days with max_records=50000
# Chunks: [(Oct 1-2), (Oct 2-4), (Oct 4-6), ..., (Oct 9-10)]
# Each chunk stays under 50k records
```

**Output:**
- Console report with progress
- JSON report in `jobs/reports/gap_filling_latest.json`
- Data appended to `binance_data.agg_trades`

---

### 4. Orchestrator (`run_all_jobs.py`)

**Purpose:** Run all jobs in correct order with smart coordination

**What it does:**
1. Runs quality assessment
2. If duplicates found → runs deduplication
3. If gaps found → runs gap filling
4. Interactive or automated mode

**Usage:**
```bash
# Interactive mode (asks for confirmation)
uv run python jobs/run_all_jobs.py --symbol BTCUSDT

# Automated mode (no prompts)
uv run python jobs/run_all_jobs.py --symbol BTCUSDT --auto

# Dry run (assessment only)
uv run python jobs/run_all_jobs.py --symbol BTCUSDT --dry-run
```

**Features:**
- Smart decision making (skips unnecessary steps)
- Interactive confirmations (unless `--auto`)
- Reads reports from each job
- Comprehensive logging

**Output:**
- Console report for each job
- JSON report in `jobs/reports/orchestration_latest.json`

---

### 5. Daily Job (`daily_job.py`)

**Purpose:** Automated daily maintenance (for cron/systemd)

**What it does:**
1. Fetches last 24 hours of data
2. Runs quality assessment
3. Removes duplicates if found
4. Logs all actions

**Usage:**
```bash
# Run daily job
uv run python jobs/daily_job.py --symbol BTCUSDT
```

**Cron Setup:**
```bash
# Edit crontab
crontab -e

# Add this line (runs at 2 AM daily)
0 2 * * * cd /path/to/binance-tick-data && uv run python jobs/daily_job.py --symbol BTCUSDT >> /var/log/binance_daily.log 2>&1
```

**Systemd Timer Setup:**
```bash
# See jobs/systemd/ for example configurations
sudo cp jobs/systemd/binance-daily.service /etc/systemd/system/
sudo cp jobs/systemd/binance-daily.timer /etc/systemd/system/

sudo systemctl enable binance-daily.timer
sudo systemctl start binance-daily.timer
```

**Output:**
- Console report
- Daily logs in `jobs/reports/daily/daily_job_YYYYMMDD.json`
- Auto-cleanup of logs older than 30 days

---

## Workflow Examples

### Initial Setup (First Time)

When starting fresh with no data:

```bash
# Step 1: Fill initial data
uv run python jobs/03_fill_gaps.py --symbol BTCUSDT \
  --start-date 2025-10-01 --end-date 2025-10-20

# Step 2: Assess quality
uv run python jobs/01_data_quality_assessment.py

# Step 3: Remove any duplicates
uv run python jobs/02_deduplication.py --execute
```

### Fixing Existing Issues

When you have existing data with problems:

```bash
# Run orchestrator (interactive)
uv run python jobs/run_all_jobs.py --symbol BTCUSDT

# Or automated
uv run python jobs/run_all_jobs.py --symbol BTCUSDT --auto
```

### Daily Maintenance

Set up automated daily job:

```bash
# Option 1: Cron
0 2 * * * cd /path/to/project && uv run python jobs/daily_job.py --symbol BTCUSDT

# Option 2: Run manually
uv run python jobs/daily_job.py --symbol BTCUSDT
```

### Filling Large Gaps

When you have a multi-day gap that exceeds max_records:

```bash
# Automatic chunking (recommended)
uv run python jobs/03_fill_gaps.py --symbol BTCUSDT \
  --start-date 2025-10-01 --end-date 2025-10-20

# This will automatically:
# 1. Calculate optimal chunk size
# 2. Break into chunks (e.g., 2-day chunks)
# 3. Process each chunk sequentially
# 4. Respect API rate limits between chunks
```

### Emergency: Restore from Backup

If deduplication goes wrong:

```sql
-- Connect to DuckDB
duckdb binance_pipeline.duckdb

-- Drop current table
DROP TABLE binance_data.agg_trades;

-- Restore from backup
ALTER TABLE binance_data.agg_trades_backup
RENAME TO agg_trades;
```

---

## Directory Structure

```
jobs/
├── README.md                          # This file
├── 01_data_quality_assessment.py     # Quality assessment job
├── 02_deduplication.py                # Deduplication job
├── 03_fill_gaps.py                    # Gap filling job
├── run_all_jobs.py                    # Job orchestrator
├── daily_job.py                       # Daily maintenance job
├── reports/                           # Job reports (auto-created)
│   ├── quality_assessment_latest.json
│   ├── deduplication_latest.json
│   ├── gap_filling_latest.json
│   ├── orchestration_latest.json
│   └── daily/
│       └── daily_job_YYYYMMDD.json
└── systemd/                           # Systemd timer examples
    ├── binance-daily.service
    └── binance-daily.timer
```

---

## Configuration

### Max Records Limit

All jobs respect the `--max-records` parameter (default: 50,000):

```bash
# Increase for faster bulk loading
uv run python jobs/03_fill_gaps.py --symbol BTCUSDT \
  --recent --max-records 100000

# Decrease to be more conservative with API
uv run python jobs/03_fill_gaps.py --symbol BTCUSDT \
  --recent --max-records 25000
```

### Database Path

All jobs support custom database path:

```bash
uv run python jobs/01_data_quality_assessment.py \
  --db-path /path/to/custom.duckdb
```

---

## Understanding Append Mode

**Why Append Mode?**

The pipeline uses `write_disposition="append"` for several reasons:

1. **Reliability:** Simpler than merge, less error-prone
2. **Speed:** Faster writes (no merge logic)
3. **Flexibility:** Can reprocess data without conflicts
4. **Resumable:** If pipeline crashes, just restart

**The Tradeoff:**

- ✅ **Pro:** Simple, fast, reliable
- ⚠️ **Con:** Can create duplicates if pipeline runs multiple times

**Our Solution:**

Separate deduplication job that:
- Runs after data ingestion
- Creates backup before changes
- Safe and verifiable
- Can run on schedule

**Pipeline Configuration (in `src/binance_tick_data/sources/rest_api.py`):**

```python
@dlt.resource(
    name="agg_trades",
    write_disposition="append",     # ← Append mode
    primary_key="agg_trade_id",     # ← Used by dedup job
)
def aggregated_trades(...):
    ...
```

---

## Monitoring & Alerts

### Check Last Run Status

```bash
# Check latest quality assessment
cat jobs/reports/quality_assessment_latest.json | jq '.status'

# Check latest deduplication
cat jobs/reports/deduplication_latest.json | jq '.status'

# Check latest gap filling
cat jobs/reports/gap_filling_latest.json | jq '.status'

# Check today's daily job
cat jobs/reports/daily/daily_job_$(date +%Y%m%d).json | jq '.status'
```

### Alert on Issues

Create a monitoring script:

```bash
#!/bin/bash
# monitor_data_quality.sh

# Run assessment
uv run python jobs/01_data_quality_assessment.py

# Check exit code
if [ $? -ne 0 ]; then
    # Send alert (email, Slack, PagerDuty, etc.)
    echo "Data quality issues detected!" | mail -s "Binance Data Alert" admin@example.com
fi
```

Run via cron:

```bash
# Check data quality every 4 hours
0 */4 * * * /path/to/monitor_data_quality.sh
```

---

## Troubleshooting

### "Database not found"

**Problem:** No database file exists

**Solution:** Run gap filling to create initial data:

```bash
uv run python jobs/03_fill_gaps.py --symbol BTCUSDT --recent
```

### "Deduplication failed"

**Problem:** Error during duplicate removal

**Solution:** Restore from backup:

```sql
DROP TABLE binance_data.agg_trades;
ALTER TABLE binance_data.agg_trades_backup RENAME TO agg_trades;
```

### "Gap filling chunks fail"

**Problem:** API rate limits or network issues

**Solution:** The job is resumable - just run again:

```bash
# Will continue where it left off
uv run python jobs/03_fill_gaps.py --symbol BTCUSDT \
  --start-date 2025-10-01 --end-date 2025-10-20
```

### "Chunk exceeds max_records"

**Problem:** Even after chunking, still hitting limits

**Solution:** Reduce max_records or shorten chunk duration:

```bash
# More conservative
uv run python jobs/03_fill_gaps.py --symbol BTCUSDT \
  --start-date 2025-10-01 --end-date 2025-10-02 \
  --max-records 25000
```

---

## Best Practices

### 1. Run Assessment First

Always run quality assessment before making changes:

```bash
uv run python jobs/01_data_quality_assessment.py
```

### 2. Use Dry Run Mode

Test deduplication before executing:

```bash
# See what would happen
uv run python jobs/02_deduplication.py

# Then execute
uv run python jobs/02_deduplication.py --execute
```

### 3. Schedule Daily Job

Keep data fresh with daily automated job:

```bash
0 2 * * * cd /path/to/project && uv run python jobs/daily_job.py --symbol BTCUSDT
```

### 4. Monitor Reports

Check reports directory regularly:

```bash
ls -ltr jobs/reports/
```

### 5. Keep Backups

Deduplication creates backups automatically, but verify:

```sql
-- Check backup exists
SELECT COUNT(*) FROM binance_data.agg_trades_backup;
```

---

## Performance Notes

### Chunking Strategy

The gap filling job calculates chunk size based on:
- `max_records` parameter
- Estimated records per hour (~3,000 for BTCUSDT)
- 80% safety margin

Example:
```
max_records=50,000
records_per_hour=3,000
chunk_size = (50,000 * 0.8) / 3,000 = ~13 hours
```

### Rate Limits

- 5 second delay between chunks
- 10 second delay between gaps (in fill-all-gaps mode)
- Configurable via code if needed

### Database Performance

- Deduplication uses `rowid` for efficiency
- Backup table creation is fast (metadata only until needed)
- All jobs use read-only connections when possible

---

## Future Enhancements

Potential improvements:

1. **Parallel gap filling** - Process multiple symbols simultaneously
2. **Smart scheduling** - Detect market hours, adjust frequency
3. **Incremental deduplication** - Only check recent data
4. **Real-time monitoring** - Dashboard with data quality metrics
5. **Alerting integration** - Email/Slack notifications
6. **Data validation** - More sophisticated quality checks

---

## Summary

This job system provides:

✅ **Automated data quality management**
✅ **Safe duplicate removal with backups**
✅ **Intelligent gap filling with chunking**
✅ **Daily maintenance automation**
✅ **Comprehensive reporting and logging**

**Recommended Workflow:**

1. Set up daily job in cron
2. Run orchestrator weekly for deep checks
3. Monitor reports directory
4. Use gap filling manually for historical data

**Key Command:**

```bash
# Daily maintenance (add to cron)
uv run python jobs/daily_job.py --symbol BTCUSDT
```

That's it! Your data pipeline will stay clean and up-to-date automatically.
