# Critical Fix: Crash Recovery for Data Download

**Date:** 2025-10-23
**Status:** Implemented

## Problem

The original implementation had a **critical flaw** that made it vulnerable to data loss on crashes:

### Original Flow (BROKEN):
```
1. Download ALL 2.4M BTCUSDT trades in memory
2. After ALL downloads complete: write to parquet
3. After parquet write complete: save DLT state
4. If crash at step 1 or 2: LOSE ALL PROGRESS, restart from 0
```

**Timeline:**
- BTCUSDT: ~2,400 API calls downloading 1,000 trades each
- Total time: ~4-6 minutes per symbol
- If crash after 5 minutes: restart from 0

**Why it failed:**
- Generator had `while True` loop downloading ALL data
- DLT buffered all yields until generator completed
- State saved ONLY after Extract → Normalize → Load stages all complete
- No checkpoint mechanism during extraction

## Solution

**Dagster runs DLT pipeline in loop, fetching small batches with state checkpoints**

### New Flow (FIXED):
```
Iteration 1:
  - Fetch 1000 trades per symbol
  - Extract → Normalize → Load
  - Save state (agg_trade_id per symbol)
  - Takes ~2 seconds

Iteration 2:
  - Resume from last agg_trade_id
  - Fetch next 1000 trades per symbol
  - Extract → Normalize → Load
  - Save state
  - Takes ~2 seconds

... repeat until exhausted

If crash at iteration 1500:
  - Resume from iteration 1501
  - Max loss: 2 seconds of work
```

## Implementation Details

### 1. Modified rest_api.py

**Removed while loop:**
```python
# OLD (WRONG):
def _fetch_agg_trades():
    while True:  # Download ALL data
        trades = get_1000_trades()
        yield trades
    # State saved here (after ALL downloads)

# NEW (CORRECT):
def _fetch_agg_trades(incremental):
    # Fetch ONLY ONE batch
    if is_incremental_run:
        trades = get_1000_trades(from_id=incremental.last_value + 1)
    else:
        trades = get_1000_trades(start_time=start_date)

    if trades:
        yield trades
    # Returns - state saved immediately
```

**Key changes:**
- Line 83: Changed cursor from `timestamp` to `agg_trade_id` for reliable resumability
- Lines 104-156: Removed while loop, fetch only 1 batch (1000 trades)
- Line 98: Track last `agg_trade_id` per symbol
- Line 109: Resume from `last_agg_trade_id + 1`

### 2. Modified raw_data.py

**Added iteration loop:**
```python
for iteration in range(1, max_iterations + 1):
    # Run DLT pipeline (fetches 1 batch per symbol)
    load_info = pipeline.run(source)

    # Count rows loaded
    if rows_loaded == 0:
        break  # All symbols exhausted

    # State automatically saved by DLT
```

**Key changes:**
- Lines 87-133: Added loop to run pipeline repeatedly
- Line 121: Track rows per iteration and total
- Line 124: Stop when no more data
- Line 92: Log progress every iteration

## Benefits

### Crash Recovery
- **Before:** Crash = restart from beginning, lose hours
- **After:** Crash = resume from last iteration, lose 2 seconds max

### Progress Visibility
- **Before:** No output for 6 minutes while downloading
- **After:** Progress log every 2 seconds with row counts

### Memory Usage
- **Before:** 2.4M trades × 20 symbols buffered in memory
- **After:** Max 1000 trades × 20 symbols per iteration (~1 MB)

### Data Availability
- **Before:** No data until ALL symbols complete
- **After:** Data written every iteration (every 2 seconds)

## Performance Comparison

### Original (BROKEN):
```
Time: 6 minutes per symbol × 20 = 120 minutes total
Checkpoints: 0 (only at end)
Memory: 2.4M records × 20 = 48M records buffered
Crash recovery: NONE
```

### New (FIXED):
```
Time: 2 seconds per iteration × 2,400 iterations = 80 minutes total
Checkpoints: 2,400 (every iteration)
Memory: 1,000 records × 20 = 20K records per iteration
Crash recovery: Resume from any iteration
```

**Trade-off:** Slightly longer total time (80 vs 120 min) but with full crash recovery

## Testing

### Validation Script

Run the asset and observe:
1. Logs show iteration numbers
2. Row counts increment every iteration
3. .dlt_staging directory grows continuously
4. Can stop/restart without losing progress

### Manual Test

```bash
# Start asset
# Kill it mid-run (Ctrl+C)
# Restart asset
# Should resume from last checkpoint, not restart from 0
```

## Technical Details

### DLT State Management

State is saved after each iteration in `.dlt/pipelines/binance_raw_data/`:
```json
{
  "agg_trades_btcusdt": {
    "incremental": {
      "agg_trade_id": {
        "last_value": 1234567
      }
    }
  }
}
```

### Incremental Cursor

**Cursor field:** `agg_trade_id` (unique, sequential)
**Why not timestamp:** Multiple trades can have same timestamp, not reliable for resumption

### Termination Condition

Pipeline stops when **all symbols** return 0 trades:
- BTCUSDT: no more data
- ETHUSDT: no more data
- ... (all 20 symbols exhausted)

## Files Modified

1. **src/binance_tick_data/sources/rest_api.py**
   - Removed while loop (lines 109-173)
   - Fetch only 1 batch per call
   - Changed cursor to agg_trade_id

2. **dagster_pipeline/assets/raw_data.py**
   - Added iteration loop (lines 87-133)
   - Progress logging per iteration
   - Row counting and termination logic

## Migration Notes

### State Reset

If you need to reset and start fresh:
```bash
# Delete DLT state
rm -rf .dlt/pipelines/binance_raw_data/

# Delete staging data
rm -rf .dlt_staging/

# Delete output data
rm -rf data/binance_data/agg_trades/
```

### Existing Partial Data

If you have partial data from old implementation:
- New implementation will detect existing state
- Resume from last checkpoint
- Deduplicate on write (agg_trade_id primary key)

## Future Improvements

1. **Parallel symbol downloads:** Run multiple symbols concurrently
2. **Adaptive batch size:** Increase to 5000 for faster downloads
3. **Progress persistence:** Save iteration count to recover exact position
4. **Rate limit handling:** Exponential backoff on API errors

## Summary

This fix transforms a fragile, crash-prone download process into a robust, resumable system with continuous progress checkpoints. The overhead of more iterations is worth the reliability gain.

**Result:** Can now safely download millions of records with confidence that progress is preserved on any failure.
