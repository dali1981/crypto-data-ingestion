# Implementation Summary: Loop-Based Incremental Data Fetching with Rate Limiting

**Date**: 2025-10-24
**Branch**: review/assets

## Overview

Implemented loop-based incremental data fetching for Binance aggregated trades with smart rate limiting. The resource now fetches data continuously until reaching `current_time - 1 hour`, with one resource per symbol for parallel processing.

## Key Features Implemented

### 1. **Loop-Based Fetching** (`rest_api.py`)
- Changed from single-batch to loop-based fetching
- Fetches 1000-trade batches continuously until cutoff time
- Cutoff time: `current_time - 1 hour` (prevents fetching real-time data)
- Early exit if already up-to-date (last trade within 1 hour)
- Maintains incremental state using `agg_trade_id`

### 2. **Smart Rate Limiter** (`utils/rate_limiter.py`)
**Token Bucket Algorithm:**
- Capacity: 1000 tokens (weight/minute)
- Refill rate: 16.67 tokens/second (~1000/minute)
- Allows bursts up to capacity
- Weight-based limiting (aggTrades = 1 weight)

**Adaptive Throttling:**
- Monitors Binance API response headers (`X-MBX-USED-WEIGHT-1M`)
- At 80% of limit (960/1200): throttles to 50% speed
- At 90% of limit (1080/1200): throttles to 25% speed
- Below 80%: full speed

**Exponential Backoff:**
- On 429 errors: 2s → 4s → 8s → 16s → max 60s
- Automatically resets on successful requests
- Thread-safe implementation

### 3. **DLT Buffer Configuration** (`.dlt/config.toml`)
**Development (Default):**
- `buffer_max_items = 10,000`
- Flushes every 10K records for visible progress

**Production:**
- `buffer_max_items = 100,000`
- Larger buffers for better throughput
- Use with: `--profile production`

### 4. **Example Script** (`examples/run_pipeline_example.py`)
- Command-line interface for running pipeline
- Supports single or multiple symbols
- Configurable date range
- Test destination (filesystem, duckdb)
- Progress monitoring and statistics

## Architecture

```
┌─────────────────────────────────────────────────┐
│  DLT Pipeline                                    │
│  ┌──────────────────────────────────────────┐  │
│  │  binance_historical_data (source)        │  │
│  │  ┌────────────────────────────────────┐  │  │
│  │  │  agg_trades_btcusdt (resource)     │  │  │
│  │  │  ├─ Loop: fetch batches            │  │  │
│  │  │  ├─ Rate limiter: wait_if_needed() │  │  │
│  │  │  ├─ Check cutoff time              │  │  │
│  │  │  └─ Yield transformed trades       │  │  │
│  │  └────────────────────────────────────┘  │  │
│  │  ┌────────────────────────────────────┐  │  │
│  │  │  agg_trades_ethusdt (resource)     │  │  │
│  │  │  ... (parallel processing)          │  │  │
│  │  └────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────┘  │
│                                                  │
│  Global Rate Limiter (shared across symbols)   │
│  └─ Token bucket + adaptive throttling          │
└─────────────────────────────────────────────────┘
```

## Files Modified/Created

### Created:
1. `src/binance_tick_data/utils/__init__.py`
2. `src/binance_tick_data/utils/rate_limiter.py` (200 lines)
3. `tests/unit/utils/__init__.py`
4. `tests/unit/utils/test_rate_limiter.py` (300+ lines, 25 tests)
5. `tests/unit/sources/test_fetch_agg_trades.py` (added 4 new loop tests)
6. `examples/run_pipeline_example.py` (200 lines)

### Modified:
1. `src/binance_tick_data/sources/rest_api.py`:
   - Imported `BinanceRateLimiter` and `timezone`
   - Added global `_rate_limiter` instance
   - Rewrote `_fetch_agg_trades()` with loop logic
   - Added cutoff time calculation
   - Added up-to-date check
   - Integrated rate limiting before API calls
   - Added 429 error handling with backoff

2. `.dlt/config.toml`:
   - Updated buffer sizes for dev (10K) and prod (100K)
   - Added profile-specific configurations

## Usage Examples

### Basic Usage (Single Symbol)
```bash
uv run python examples/run_pipeline_example.py --symbol BTCUSDT
```

### Multiple Symbols
```bash
uv run python examples/run_pipeline_example.py --symbols BTCUSDT ETHUSDT BNBUSDT
```

### With Date Range
```bash
uv run python examples/run_pipeline_example.py \
  --symbol BTCUSDT \
  --start-date 2024-01-01
```

### Production Mode (Larger Buffers)
```bash
uv run python examples/run_pipeline_example.py \
  --symbols BTCUSDT ETHUSDT \
  --profile production
```

## Testing

### Rate Limiter Tests
```bash
# Run all rate limiter tests
uv run pytest tests/unit/utils/test_rate_limiter.py -v

# Skip slow tests (those with actual sleeps)
uv run pytest tests/unit/utils/test_rate_limiter.py -v \
  -k "not (wait_if_needed_blocks or handle_429 or adaptive_throttling)"
```

### Resource Tests
```bash
# Run fetch_agg_trades tests
uv run pytest tests/unit/sources/test_fetch_agg_trades.py -v

# Run specific tests
uv run pytest tests/unit/sources/test_fetch_agg_trades.py::TestFetchAggTrades::test_loop_fetches_until_cutoff_time -v
```

## Performance Characteristics

### Rate Limiting:
- **Target**: 1000 weight/minute (~16.67 requests/second)
- **Binance limit**: 1200 weight/minute
- **Safety buffer**: 200 weight/minute (17%)
- **Adaptive**: Automatically slows when approaching limits

### Data Throughput:
- **Per batch**: 1000 trades
- **Dev mode flush**: Every 10,000 trades
- **Prod mode flush**: Every 100,000 trades
- **Symbol processing**: Parallel (one resource per symbol)

### Cutoff Time:
- **Real-time buffer**: 1 hour from current time
- **Rationale**: Avoids fetching incomplete/rapidly changing recent data
- **Up-to-date check**: Skips if last trade within 1 hour

## Known Issues / TODOs

1. **Test Coverage**: Some old tests need updating for new loop behavior
   - Tests that call `list(resource)` need datetime mocking
   - Class-level `@patch` decorators need parameter order fixes

2. **Header Parsing**: python-binance Client doesn't expose response headers
   - Rate limiter works with token bucket regardless
   - Could switch to `requests` directly for header access

3. **Async Support**: Could improve parallelism with asyncio
   - Current: Sequential API calls per symbol
   - Potential: Async API calls with `aiohttp`

## Migration Notes

### For Existing Users:
- **No breaking changes** to external API
- Existing pipelines will work but fetch more data per run
- Configure buffer sizes in `.dlt/config.toml` if needed

### For Developers:
- Rate limiter is global - shared across all symbols
- Mock `_rate_limiter` in tests to avoid actual rate limiting
- Mock `datetime.now()` in tests to control cutoff time

## Next Steps

1. **Fix remaining tests**: Update old tests for loop behavior
2. **Add async support**: Use `asyncio` for parallel API calls
3. **Add metrics**: Track rate limiter performance
4. **Header access**: Switch to raw `requests` for header parsing
5. **Backfill mode**: Add option to disable 1-hour cutoff for historical backfills

## References

- Binance API Docs: https://developers.binance.com/docs/binance-spot-api-docs/rest-api
- DLT Docs: https://dlthub.com/docs
- Token Bucket Algorithm: https://en.wikipedia.org/wiki/Token_bucket
