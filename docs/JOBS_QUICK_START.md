# Jobs Quick Start Guide

**Your data has issues. Here's how to fix them in 5 minutes.**

---

## Current Situation ⚠️

Your database has:
- **10,000 duplicate records**
- **17.8 day gap** in data (Oct 1-19)
- **35+ hours** of missing recent data

---

## Quick Fix (Choose Your Path)

### Option 1: Automated (Recommended) ✨

Run everything automatically:

```bash
# Interactive mode (asks for confirmation)
uv run python jobs/run_all_jobs.py --symbol BTCUSDT

# Or fully automated (no prompts)
uv run python jobs/run_all_jobs.py --symbol BTCUSDT --auto
```

**This will:**
1. ✅ Assess data quality
2. ✅ Remove duplicates (with backup)
3. ✅ Fill the largest gap
4. ✅ Get recent data

**Time:** ~5-10 minutes (depending on gap size)

---

### Option 2: Manual (Step by Step) 🔧

If you want control over each step:

#### Step 1: Check Current State

```bash
uv run python jobs/01_data_quality_assessment.py
```

**What you'll see:**
- Number of duplicates
- Time gaps detected
- Data freshness
- Recommendations

#### Step 2: Remove Duplicates

```bash
# Dry run first (see what will happen)
uv run python jobs/02_deduplication.py

# Execute (creates backup automatically)
uv run python jobs/02_deduplication.py --execute
```

**What happens:**
- Backup created: `binance_data.agg_trades_backup`
- 10,000 duplicates removed
- Verification step runs

#### Step 3: Fill the Gap

```bash
# Fill the largest gap (17.8 days)
uv run python jobs/03_fill_gaps.py --symbol BTCUSDT --fill-largest-gap
```

**Important:** This will automatically chunk the request into smaller pieces (2-3 day chunks) to respect the max_records limit.

**Time:** ~20-30 minutes (API rate limits)

#### Step 4: Get Recent Data

```bash
# Get last 24 hours
uv run python jobs/03_fill_gaps.py --symbol BTCUSDT --recent
```

---

## Set Up Daily Automation 📅

Once your data is clean, keep it that way:

### Using Cron (macOS/Linux)

```bash
# Edit crontab
crontab -e

# Add this line (runs at 2 AM daily)
0 2 * * * cd /path/to/binance-tick-data && uv run python jobs/daily_job.py --symbol BTCUSDT >> /tmp/binance_daily.log 2>&1
```

### Manual Daily Run

```bash
# Run this once a day
uv run python jobs/daily_job.py --symbol BTCUSDT
```

**What it does:**
- Fetches last 24 hours of data
- Checks for duplicates
- Removes them if found
- Logs everything

---

## Verify Everything Works ✅

After running the fixes:

```bash
# Check data quality
uv run python jobs/01_data_quality_assessment.py

# Should show:
# ✅ No duplicates
# ✅ No gaps > 1 hour
# ✅ Fresh data (< 2 hours old)
```

---

## Common Questions

### Q: Will I lose data?

**A:** No! The deduplication job creates a backup table before making any changes:
- Backup: `binance_data.agg_trades_backup`
- You can restore if needed

### Q: What if gap filling fails?

**A:** The job is resumable - just run it again. It will continue where it left off.

### Q: How long will gap filling take?

**A:** For your 17.8 day gap:
- Auto-chunks into ~8-9 chunks (2 days each)
- 5 seconds between chunks
- ~5-10 minutes total (depending on API)

### Q: What if I hit max_records limit?

**A:** The gap filling job automatically breaks large date ranges into chunks. You don't need to worry about it!

Example:
```bash
# This date range is too large for max_records=50000
# Job will automatically break into chunks:
# Chunk 1: Oct 1-3
# Chunk 2: Oct 3-5
# ...etc
uv run python jobs/03_fill_gaps.py --symbol BTCUSDT \
  --start-date 2025-10-01 --end-date 2025-10-20
```

---

## Troubleshooting

### "Database not found"

You don't have any data yet. Start with:

```bash
uv run python jobs/03_fill_gaps.py --symbol BTCUSDT --recent
```

### "Deduplication failed"

Restore from backup:

```sql
-- In DuckDB
DROP TABLE binance_data.agg_trades;
ALTER TABLE binance_data.agg_trades_backup RENAME TO agg_trades;
```

### "API rate limit"

The job already has delays built in. If you still hit limits:

```bash
# Use smaller max_records
uv run python jobs/03_fill_gaps.py --symbol BTCUSDT \
  --fill-largest-gap --max-records 25000
```

---

## Recommended Workflow

**Initial Setup (Now):**

```bash
# 1. Fix everything (automated)
uv run python jobs/run_all_jobs.py --symbol BTCUSDT --auto

# 2. Verify it worked
uv run python jobs/01_data_quality_assessment.py
```

**Ongoing (Daily):**

```bash
# Add to cron (runs at 2 AM daily)
0 2 * * * cd /path/to/binance-tick-data && uv run python jobs/daily_job.py --symbol BTCUSDT
```

**Weekly Check:**

```bash
# Run orchestrator to deep clean
uv run python jobs/run_all_jobs.py --symbol BTCUSDT
```

---

## Next Steps

1. ✅ **Fix current issues** - Run `jobs/run_all_jobs.py`
2. ✅ **Set up daily job** - Add to cron
3. ✅ **Monitor reports** - Check `jobs/reports/` directory
4. ✅ **Use your data** - Run analysis scripts

---

## Files Created

The jobs system created:

```
jobs/
├── 01_data_quality_assessment.py  # Assess quality
├── 02_deduplication.py            # Remove duplicates
├── 03_fill_gaps.py                # Fill missing data
├── run_all_jobs.py                # Run all jobs
├── daily_job.py                   # Daily maintenance
├── README.md                      # Full documentation
├── QUICK_START.md                 # This file
├── systemd/                       # Systemd timer configs
└── reports/                       # Auto-generated reports
```

**Old tools** (still available):
- `data_gap_analysis.py` - Analysis tool
- `fix_data_issues.py` - Manual fix tool
- `DATA_QUALITY_REPORT.md` - Detailed findings

---

## Summary

**TL;DR - Run this now:**

```bash
uv run python jobs/run_all_jobs.py --symbol BTCUSDT --auto
```

**Then set up daily automation:**

```bash
crontab -e
# Add: 0 2 * * * cd /path/to/binance-tick-data && uv run python jobs/daily_job.py --symbol BTCUSDT
```

**Done!** Your data will be clean and automatically maintained.

---

For more details, see `jobs/README.md`
