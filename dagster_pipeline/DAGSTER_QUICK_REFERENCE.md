# Dagster Pipeline - Quick Reference

## Launch UI

```bash
./start_dagster.sh
# UI: http://localhost:3000
```

## Assets (7)

| Asset | Purpose |
|-------|---------|
| `raw_agg_trades` | Fetch latest trades (20 symbols) |
| `raw_order_books` | Fetch order books (20 symbols) |
| `duplicate_detection` | Find duplicates |
| `gap_detection` | Find time gaps |
| `deduplicate_trades` | Remove duplicates |
| `fill_largest_gap` | Fill biggest gap |
| `fill_recent_data` | Daily incremental update |

## Jobs (6)

| Job | When |
|-----|------|
| `fetch_latest` | Manual or sensor |
| `detect_issues` | Manual |
| `cleanup_duplicates` | Manual or sensor |
| `fill_gaps` | Manual or sensor |
| `daily_update` | Every 6h or manual |
| `full_maintenance` | Daily 2 AM or manual |

## Schedules (3)

| Schedule | Frequency |
|----------|-----------|
| `daily_maintenance` | 2 AM UTC daily |
| `incremental_update` | Every 6 hours |
| `weekly_gap_fill` | Sunday 3 AM UTC |

## Sensors (3)

| Sensor | Trigger Condition |
|--------|-------------------|
| `data_freshness_sensor` | Data > 2 hours old |
| `duplicate_cleanup_sensor` | Duplicates > 1000 |
| `gap_fill_sensor` | Gap > 6 hours |

## Configuration

Edit: `dagster_pipeline/config.py`

```python
SYMBOLS = [...]  # 20 trading pairs
DUPLICATE_THRESHOLD = 1000
GAP_THRESHOLD_HOURS = 6.0
FRESHNESS_THRESHOLD_HOURS = 2.0
```

## Common Operations

### First Run
```
Jobs → full_maintenance → Launch Run
```

### Enable Automation
```
Schedules → Enable all
Sensors → Enable all
```

### View Asset Lineage
```
Assets → Select asset → Lineage tab
```

### Check Logs
```
Runs → Select run → Logs tab
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Assets not showing | Check you're in correct directory |
| Sensors not triggering | Verify sensors are enabled (green) |
| API rate limit | Wait a few minutes, built-in rate limiting |
| Database not found | Normal - created on first run |

## Symbols (20)

ETHUSDT, BTCUSDT, FLOKIUSDT, SOLUSDT, BNBUSDT, XRPUSDT, DOGEUSDT, FFUSDT, SUIUSDT, ZECUSDT, 2ZUSDT, AVNTUSDT, PAXGUSDT, AAVEUSDT, HBARUSDT, ADAUSDT, FORMUSDT, LTCUSDT, WALUSDT, TAOUSDT

## Documentation

- Full docs: `dagster_pipeline/README.md`
- Quick start: `dagster_pipeline/QUICK_START.md`
- Setup summary: `DAGSTER_SETUP_SUMMARY.md`
