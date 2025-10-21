# Binance Tick Data - Dagster Pipeline

Automated data acquisition and maintenance pipeline for Binance tick data using Dagster.

## Overview

This Dagster pipeline manages:
- **Raw data acquisition** (agg_trades, order_books) for 20 trading pairs
- **Data quality detection** (duplicates, gaps)
- **Automatic cleaning** (deduplication, gap filling)
- **Scheduled maintenance** (daily updates, weekly gap fills)
- **Event-driven triggers** (sensors for freshness, duplicates, gaps)

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    DAGSTER PIPELINE                       │
├──────────────────────────────────────────────────────────┤
│                                                           │
│  RAW DATA ASSETS                                         │
│  ├─ raw_agg_trades     (fetch latest trades)            │
│  └─ raw_order_books    (fetch order book snapshots)      │
│                                                           │
│  QUALITY DETECTION                                        │
│  ├─ duplicate_detection (find duplicates)                │
│  └─ gap_detection       (find time gaps)                 │
│                                                           │
│  DATA CLEANING                                            │
│  ├─ deduplicate_trades  (remove duplicates)              │
│  ├─ fill_largest_gap    (fill biggest gap)               │
│  └─ fill_recent_data    (daily incremental update)       │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Install Dependencies

```bash
# Install Dagster and dependencies
uv pip install dagster dagster-webserver
```

### 2. Launch Dagster UI

```bash
# From the project root (dlt-starter/)
dagster dev -f dagster_pipeline/__init__.py
```

This will start the Dagster UI at http://localhost:3000

### 3. Explore the Pipeline

In the Dagster UI:
- **Assets tab**: View all data assets and their lineage
- **Jobs tab**: See available jobs and trigger manual runs
- **Schedules tab**: View and enable/disable schedules
- **Sensors tab**: Monitor event-driven triggers

## Assets

### Raw Data Assets

#### `raw_agg_trades`
- **Purpose**: Fetch latest aggregated trades for all 20 symbols
- **Source**: Binance REST API
- **Mode**: Append (allows duplicates temporarily)
- **Frequency**: Every 6 hours (schedule) or when data is stale (sensor)

#### `raw_order_books`
- **Purpose**: Fetch current order book snapshots
- **Source**: Binance REST API
- **Depth**: 20 levels per side
- **Frequency**: On-demand or with `raw_agg_trades`

### Quality Detection Assets

#### `duplicate_detection`
- **Purpose**: Count duplicate records by `agg_trade_id`
- **Output**: Duplicate count + breakdown by symbol
- **Triggers**: `deduplicate_trades` asset

#### `gap_detection`
- **Purpose**: Find time gaps > 1 hour
- **Output**: List of gaps with duration and timestamps
- **Triggers**: `fill_largest_gap` asset

### Data Cleaning Assets

#### `deduplicate_trades`
- **Purpose**: Remove duplicate records
- **Strategy**: Keep first occurrence, delete rest
- **Safety**: Creates backup table before deletion
- **Trigger**: Runs when duplicates detected

#### `fill_largest_gap`
- **Purpose**: Fill the largest gap found in data
- **Strategy**: Adaptive chunking (learns data density)
- **Limit**: One gap per run (avoids API rate limits)

#### `fill_recent_data`
- **Purpose**: Daily incremental update for all symbols
- **Window**: Last 24 hours
- **Strategy**: Fetch from last_timestamp to now

## Jobs

| Job | Assets | Description |
|-----|--------|-------------|
| `fetch_latest` | raw_agg_trades, raw_order_books | Fetch latest data from Binance |
| `detect_issues` | duplicate_detection, gap_detection | Scan for problems |
| `cleanup_duplicates` | deduplicate_trades | Remove duplicates |
| `fill_gaps` | fill_largest_gap | Fill largest gap |
| `daily_update` | fill_recent_data | Incremental daily update |
| `full_maintenance` | ALL | Complete pipeline |

## Schedules

| Schedule | Job | Cron | Description |
|----------|-----|------|-------------|
| `daily_maintenance` | full_maintenance | `0 2 * * *` | Daily at 2 AM UTC |
| `incremental_update` | daily_update | `0 */6 * * *` | Every 6 hours |
| `weekly_gap_fill` | fill_gaps | `0 3 * * 0` | Sunday 3 AM UTC |

## Sensors

### `data_freshness_sensor`
- **Monitors**: Last timestamp in database
- **Triggers**: `fetch_latest_job`
- **Condition**: Data > 2 hours old
- **Frequency**: Check every hour

### `duplicate_cleanup_sensor`
- **Monitors**: Duplicate count
- **Triggers**: `cleanup_duplicates_job`
- **Condition**: Duplicates > 1000
- **Frequency**: Check every hour

### `gap_fill_sensor`
- **Monitors**: Largest gap in data
- **Triggers**: `fill_gaps_job`
- **Condition**: Gap > 6 hours
- **Frequency**: Check daily

## Configuration

Edit `dagster_pipeline/config.py` to customize:

```python
# Trading pairs (20 symbols)
SYMBOLS = ["ETHUSDT", "BTCUSDT", ...]

# Data quality thresholds
DUPLICATE_THRESHOLD = 1000
GAP_THRESHOLD_HOURS = 6.0
FRESHNESS_THRESHOLD_HOURS = 2.0

# Database
DB_PATH = "binance_pipeline.duckdb"
```

## Monitoring

### View Asset Lineage

The Dagster UI shows the dependency graph:

```
raw_agg_trades
    ├─→ duplicate_detection → deduplicate_trades
    └─→ gap_detection → fill_largest_gap

fill_recent_data (independent)
```

### Check Asset Metadata

Each asset materialization includes metadata:
- Records fetched/added/removed
- Processing time
- Status (success/failure)
- Symbol-level breakdown

### Monitor Sensors

In the **Sensors** tab:
- See last evaluation time
- Check skip reasons
- View trigger history

## Manual Operations

### Materialize Individual Assets

```bash
# In Dagster UI: Assets tab → Select asset → Materialize
```

Or via CLI:
```bash
dagster asset materialize -f dagster_pipeline/__init__.py --select raw_agg_trades
```

### Run Jobs Manually

```bash
# In Dagster UI: Jobs tab → Select job → Launch run
```

Or via CLI:
```bash
dagster job execute -f dagster_pipeline/__init__.py --job daily_update
```

### Enable/Disable Schedules

In the Dagster UI:
1. Go to **Schedules** tab
2. Toggle schedule on/off
3. View next scheduled run time

### Enable/Disable Sensors

In the Dagster UI:
1. Go to **Sensors** tab
2. Toggle sensor on/off
3. View evaluation history

## Production Deployment

### Option 1: Dagster Cloud

```bash
# Deploy to Dagster Cloud (managed service)
dagster-cloud deploy
```

### Option 2: Self-Hosted

```bash
# Run Dagster daemon (for schedules/sensors)
dagster-daemon run

# Run Dagster webserver (for UI)
dagster-webserver -f dagster_pipeline/__init__.py
```

### Option 3: Docker

```dockerfile
FROM python:3.10

WORKDIR /app
COPY . /app

RUN pip install dagster dagster-webserver
RUN uv pip install -e .

CMD ["dagster", "dev", "-f", "dagster_pipeline/__init__.py", "-h", "0.0.0.0"]
```

## Troubleshooting

### Assets Not Materializing

1. Check logs in Dagster UI
2. Verify database path in config
3. Ensure Binance API connectivity

### Sensors Not Triggering

1. Verify sensor is enabled (green in UI)
2. Check sensor evaluation history
3. Review skip reasons in logs

### Gap Filling Fails

1. Check API rate limits
2. Verify `jobs/03_fill_gaps.py` exists
3. Review chunk size in config

## Resources

- [Dagster Documentation](https://docs.dagster.io/)
- [Binance API Docs](https://binance-docs.github.io/apidocs/spot/en/)
- [DuckDB Documentation](https://duckdb.org/docs/)

## Support

For issues or questions:
1. Check Dagster UI logs
2. Review sensor/schedule history
3. Open an issue in the repository
