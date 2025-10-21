# Quick Start Guide

Get your Dagster pipeline running in 3 steps!

## Step 1: Launch Dagster UI

From the project root (`dlt-starter/`):

```bash
# Option A: Using the start script
./start_dagster.sh

# Option B: Direct command
uv run dagster dev -f dagster_pipeline/__init__.py
```

The UI will be available at **http://localhost:3000**

## Step 2: Enable Schedules and Sensors

In the Dagster UI:

### Enable Schedules

1. Go to **Schedules** tab
2. Enable the schedules you want:
   - `daily_maintenance` - Daily at 2 AM UTC
   - `incremental_update` - Every 6 hours
   - `weekly_gap_fill` - Sunday at 3 AM UTC

### Enable Sensors

1. Go to **Sensors** tab
2. Enable the sensors you want:
   - `data_freshness_sensor` - Auto-fetch when data is stale
   - `duplicate_cleanup_sensor` - Auto-clean when duplicates found
   - `gap_fill_sensor` - Auto-fill large gaps

## Step 3: Run Your First Job

### Option A: Full Maintenance (Recommended)

1. Go to **Jobs** tab
2. Click on `full_maintenance`
3. Click **Launch Run**

This will:
- Fetch latest data for all 20 symbols
- Detect duplicates and gaps
- Clean the database automatically

### Option B: Individual Assets

1. Go to **Assets** tab
2. Select `raw_agg_trades`
3. Click **Materialize**

This will fetch only the latest trades data.

## What to Expect

### First Run (No Existing Data)

```
1. raw_agg_trades: Fetches data from 2024-10-01 to now
   - Takes ~5-10 minutes for all 20 symbols
   - Downloads ~100K-500K records per symbol

2. duplicate_detection: Scans for duplicates
   - Likely 0 duplicates on first run

3. gap_detection: Scans for gaps
   - Likely 0 gaps on first run

4. All cleaning jobs: Skip (no issues to fix)
```

### Subsequent Runs (Incremental Updates)

```
1. raw_agg_trades: Fetches only new data since last run
   - Takes ~30 seconds for all symbols
   - Downloads only new trades

2. duplicate_detection: May find duplicates from overlapping fetches
   - Auto-cleaned if > 1000 duplicates

3. gap_detection: May find gaps from network issues
   - Auto-filled if > 6 hours

4. Cleaning jobs: Run only when needed
```

## Monitoring

### View Asset Lineage

**Assets** tab → Click on any asset → See **Upstream** and **Downstream** dependencies

### Check Run History

**Runs** tab → See all materializations, success/failure status, and logs

### View Logs

Click on any run → **Logs** tab → See detailed execution logs

### Check Metadata

Click on any materialized asset → **Metadata** tab → See:
- Records fetched/added/removed
- Processing time
- Symbol-level breakdown

## Common Operations

### Manual Fetch for One Symbol

Currently fetches all symbols. To fetch one symbol only:

1. Edit `dagster_pipeline/config.py`
2. Change `SYMBOLS = ["BTCUSDT"]`
3. Re-run `raw_agg_trades`

### Fill Specific Gap

Use the existing CLI tool:

```bash
uv run python jobs/03_fill_gaps.py \
  --symbol BTCUSDT \
  --start-date 2024-10-15 \
  --end-date 2024-10-20
```

Then refresh the Dagster assets.

### Remove Duplicates Manually

Use the existing CLI tool:

```bash
uv run python jobs/02_deduplication.py --execute
```

Then refresh the Dagster assets.

## Troubleshooting

### "ModuleNotFoundError: No module named 'dagster'"

```bash
# Install Dagster
uv add dagster dagster-webserver
```

### "Database not found"

The database will be created automatically on first run. Just materialize `raw_agg_trades`.

### "API rate limit exceeded"

Wait a few minutes and try again. The pipeline has built-in rate limiting, but manual runs may hit limits.

### Assets not showing in UI

Make sure you're running from the correct directory:

```bash
cd /path/to/dlt-starter
uv run dagster dev -f dagster_pipeline/__init__.py
```

## Next Steps

Once your pipeline is running:

1. **Enable all sensors** for automatic maintenance
2. **Set up schedules** for regular updates
3. **Monitor the Assets page** to see data freshness
4. **Check logs regularly** for any issues

## Help

- Dagster UI: http://localhost:3000
- Dagster Docs: https://docs.dagster.io/
- Project README: `dagster_pipeline/README.md`
