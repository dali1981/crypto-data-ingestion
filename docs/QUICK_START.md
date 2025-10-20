# Quick Start - New Configuration System

## TL;DR

The database configuration is now centralized in `config.yaml`. All scripts automatically use this configuration. No more hardcoded paths!

## Run Tests

```bash
# Test everything works
uv run python examples/test_new_system.py
```

## Basic Usage

```python
from binance_tick_data import BinanceDataRepository
from datetime import datetime

# Automatically uses config.yaml settings
with BinanceDataRepository() as repo:
    # Query tick data
    df = repo.get_agg_trades(
        symbol="BTCUSDT",
        start_time=datetime(2025, 10, 1)
    )

    # Create dollar-volume bars
    dollar_bars = repo.create_dollar_bars(
        symbol="BTCUSDT",
        start_time=datetime(2025, 10, 1)
    )
```

## Configuration

### Method 1: Edit `config.yaml`

```yaml
database:
  db_path: "binance_pipeline.duckdb"
  catalog_name: "binance_pipeline"
  schema_name: "binance_data"

pipeline:
  bar_thresholds:
    dollar_bars:
      BTCUSDT: 1000000
```

### Method 2: Environment Variables

```bash
export BINANCE_DATABASE__DB_PATH="my_db.duckdb"
export BINANCE_DATABASE__SCHEMA_NAME="my_schema"
export BINANCE_PIPELINE__BAR_THRESHOLDS__DOLLAR_BARS__BTCUSDT=2000000
```

### Method 3: Code

```python
from binance_tick_data import load_config, BinanceDataRepository

config = load_config("custom_config.yaml")
repo = BinanceDataRepository(config=config)
```

## Error Handling

```python
from binance_tick_data import (
    BinanceDataRepository,
    NoDataFoundError,
    TableNotFoundError
)

try:
    with BinanceDataRepository() as repo:
        df = repo.get_agg_trades(symbol="BTCUSDT")
except NoDataFoundError as e:
    print(e)  # Shows detailed error with suggestions
```

## Common Tasks

### List Available Symbols

```python
with BinanceDataRepository() as repo:
    symbols = repo.list_available_symbols()
    print(symbols)
```

### Get Data Summary

```python
with BinanceDataRepository() as repo:
    summary = repo.get_data_summary()
    for table, info in summary.items():
        if info.get("exists"):
            print(f"{table}: {info['total_records']} records")
```

### Create Dollar Bars

```python
with BinanceDataRepository() as repo:
    # Automatic threshold from config
    bars = repo.create_dollar_bars("BTCUSDT", start_time=datetime(2025, 10, 1))

    # Custom threshold
    bars = repo.create_dollar_bars(
        "ETHUSDT",
        start_time=datetime(2025, 10, 1),
        dollar_threshold=500_000
    )
```

### Validate Configuration

```python
from binance_tick_data import get_config

config = get_config()
status = config.validate_setup()

print(f"Database: {config.database.db_path}")
print(f"Schema: {config.database.full_schema_path}")
```

## Examples

- `examples/simple_read.py` - Basic data reading
- `examples/test_new_system.py` - Comprehensive test suite
- `specs/dollar_volume_sampling.ipynb` - Interactive notebook

## Documentation

- `MIGRATION_GUIDE.md` - Detailed migration guide
- `specs/MODULAR_SYSTEM_SUMMARY.md` - Complete technical summary
- `specs/dollar-volume-sampling-tools.md` - Dollar bar documentation

## What's New?

✅ Centralized configuration via `config.yaml`
✅ Comprehensive error messages with actionable suggestions
✅ Built-in dollar-volume bar sampling (Polars + Pandas)
✅ Type-safe configuration with Pydantic
✅ Environment variable overrides
✅ Full backwards compatibility

## Need Help?

1. Run tests: `uv run python examples/test_new_system.py`
2. Check configuration: `cat config.yaml`
3. Read migration guide: `MIGRATION_GUIDE.md`
4. See full documentation: `specs/MODULAR_SYSTEM_SUMMARY.md`
