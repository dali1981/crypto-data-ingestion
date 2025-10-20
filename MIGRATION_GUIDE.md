# Migration Guide: New Configuration System

## Overview

We've refactored the codebase to fix the recurring issue of different scripts pointing to different database locations. The new system provides:

1. **Centralized Configuration** using `config.yaml` + environment variables
2. **Type-safe Configuration** with Pydantic models
3. **Comprehensive Error Handling** with actionable error messages
4. **Dollar-Volume Bar Sampling** built into the repository
5. **No More Hardcoded Paths** - single source of truth

## What Changed?

### Before (Old System)
```python
# Different scripts had different hardcoded paths
from binance_tick_data.repository import BinanceDataRepository

# Database path hardcoded in multiple places
# Schema name hardcoded differently across files
repo = BinanceDataRepository()  # Where does this connect?
```

### After (New System)
```python
# All configuration centralized in config.yaml
from binance_tick_data import BinanceDataRepository, get_config

# Configuration loaded from config.yaml (or environment)
config = get_config()
print(f"Database: {config.database.db_path}")
print(f"Schema: {config.database.full_schema_path}")

repo = BinanceDataRepository()  # Uses config.yaml settings
```

## Migration Steps

### Step 1: Use the New Repository

The new `BinanceDataRepository` (from `repository_v2.py`) is now the default. It:
- Reads configuration from `config.yaml`
- Provides comprehensive error messages
- Includes dollar-volume bar sampling

**Old Code:**
```python
from binance_tick_data.repository import BinanceDataRepository

repo = BinanceDataRepository(db_path="...", dataset_name="...")
```

**New Code:**
```python
from binance_tick_data import BinanceDataRepository

# Uses config.yaml automatically
repo = BinanceDataRepository()

# Or provide custom config
from binance_tick_data import load_config
config = load_config("my_config.yaml")
repo = BinanceDataRepository(config=config)
```

### Step 2: Configuration File

Create `config.yaml` in your project root (already created):

```yaml
database:
  db_path: "binance_pipeline.duckdb"
  catalog_name: "binance_pipeline"
  schema_name: "binance_data"
  read_only: false

tables:
  agg_trades: "agg_trades"
  dollar_bars: "dollar_bars"
  # ... other tables

pipeline:
  default_batch_size: 10000
  bar_thresholds:
    dollar_bars:
      BTCUSDT: 1000000
      default: 100000
```

### Step 3: Environment Variables (Optional)

Override any setting with environment variables:

```bash
# Override database path
export BINANCE_DATABASE__DB_PATH=/path/to/my/db.duckdb

# Override schema
export BINANCE_DATABASE__SCHEMA_NAME=my_schema

# Override dollar bar threshold
export BINANCE_PIPELINE__BAR_THRESHOLDS__DOLLAR_BARS__BTCUSDT=2000000
```

## New Features

### 1. Comprehensive Error Messages

**Before:**
```python
# Generic error
CatalogException: Table with name agg_trades does not exist!
```

**After:**
```python
# Detailed error with suggestions
❌ Table 'agg_trades' not found in schema 'binance_data'

📋 Details:
   • table_name: agg_trades
   • schema_name: binance_data
   • db_path: binance_pipeline.duckdb
   • available_tables: _dlt_loads, _dlt_version

💡 Suggestions:
   → Run the data ingestion pipeline to create the table
   → Check if you're using the correct table name
   → Verify the database has been initialized
   → Available tables: _dlt_loads, _dlt_version
```

### 2. Dollar-Volume Bar Sampling

Built-in support for creating dollar-volume bars:

```python
from binance_tick_data import BinanceDataRepository
from datetime import datetime

with BinanceDataRepository() as repo:
    # Create dollar bars with automatic threshold from config
    dollar_bars = repo.create_dollar_bars(
        symbol="BTCUSDT",
        start_time=datetime(2025, 10, 1)
    )

    # Or specify custom threshold
    dollar_bars = repo.create_dollar_bars(
        symbol="BTCUSDT",
        start_time=datetime(2025, 10, 1),
        dollar_threshold=500_000  # $500k per bar
    )

    print(f"Created {len(dollar_bars)} bars")
    print(dollar_bars.head())
```

### 3. Type-Safe Configuration

```python
from binance_tick_data import get_config

config = get_config()

# All configuration is type-checked
config.database.db_path  # str
config.pipeline.default_batch_size  # int
config.pipeline.bar_thresholds.get_dollar_threshold("BTCUSDT")  # float
```

## Examples

### Example 1: Reading Data with Error Handling

```python
from binance_tick_data import BinanceDataRepository, NoDataFoundError
from datetime import datetime

try:
    with BinanceDataRepository() as repo:
        df = repo.get_agg_trades(
            symbol="BTCUSDT",
            start_time=datetime(2025, 10, 1)
        )
        print(f"Retrieved {len(df)} trades")

except NoDataFoundError as e:
    print(e)  # Comprehensive error message with suggestions
    # ❌ No data found for the specified criteria
    # 📋 Details:
    #    • symbol: BTCUSDT
    #    • start_time: 2025-10-01T00:00:00
    # 💡 Suggestions:
    #    → Check if data exists for this symbol and time range
    #    → Try a broader date range
```

### Example 2: Creating Dollar Bars

```python
from binance_tick_data import BinanceDataRepository
from datetime import datetime
import matplotlib.pyplot as plt

with BinanceDataRepository() as repo:
    # Get regular tick data
    ticks = repo.get_agg_trades(
        symbol="BTCUSDT",
        start_time=datetime(2025, 10, 1),
        limit=100000
    )

    # Create dollar bars (uses config threshold automatically)
    dollar_bars = repo.create_dollar_bars(
        symbol="BTCUSDT",
        start_time=datetime(2025, 10, 1)
    )

    # Plot candlestick chart
    print(f"Ticks: {len(ticks)}, Bars: {len(dollar_bars)}")
    print(f"Average ticks per bar: {len(ticks) / len(dollar_bars):.1f}")
```

### Example 3: Custom Configuration

```python
from binance_tick_data import DatabaseConfig, AppConfig, BinanceDataRepository

# Create custom configuration
custom_config = AppConfig(
    database=DatabaseConfig(
        db_path="my_custom.duckdb",
        schema_name="my_schema"
    )
)

# Use custom config
repo = BinanceDataRepository(config=custom_config)
```

### Example 4: Validation

```python
from binance_tick_data import get_config

config = get_config()

# Validate configuration
status = config.validate_setup()

if status["warnings"]:
    print("⚠️  Warnings:")
    for warning in status["warnings"]:
        print(f"  • {warning}")

if status["errors"]:
    print("❌ Errors:")
    for error in status["errors"]:
        print(f"  • {error}")

print(f"\n📊 Info:")
for key, value in status["info"].items():
    print(f"  • {key}: {value}")
```

## Backwards Compatibility

The old API still works but is deprecated:

```python
# Old API (still works)
from binance_tick_data import LegacyBinanceDataRepository
repo = LegacyBinanceDataRepository(db_path="...", dataset_name="...")

# New API (recommended)
from binance_tick_data import BinanceDataRepository
repo = BinanceDataRepository()  # Uses config.yaml
```

## Error Hierarchy

All errors inherit from `BinanceDataError`:

```
BinanceDataError (base)
├── DatabaseError
│   ├── DatabaseNotFoundError
│   ├── DatabaseConnectionError
│   ├── SchemaNotFoundError
│   └── TableNotFoundError
├── DataError
│   ├── NoDataFoundError
│   ├── InvalidSymbolError
│   ├── DataQualityError
│   └── InsufficientDataError
├── ConfigurationError
│   ├── InvalidConfigurationError
│   └── ConfigurationFileNotFoundError
├── APIError
│   ├── RateLimitError
│   └── APIConnectionError
└── QueryError
    ├── InvalidDateRangeError
    └── InvalidParameterError
```

## Testing

Run the test script to verify everything works:

```bash
uv run python examples/test_new_system.py
```

This will:
1. Load configuration
2. Validate database setup
3. Test data queries with error handling
4. Create dollar-volume bars
5. Show comprehensive error messages

## Checklist

- [ ] Review `config.yaml` and adjust for your needs
- [ ] Update scripts to use new `BinanceDataRepository`
- [ ] Add error handling with specific exception types
- [ ] Test dollar-volume bar creation
- [ ] Remove hardcoded database paths from old scripts
- [ ] Run validation tests

## Questions?

1. **Where is the configuration stored?**
   - Primary: `config.yaml` in project root
   - Override: Environment variables with `BINANCE_` prefix
   - Default: Pydantic defaults in `db_config.py`

2. **How do I change the database path?**
   - Edit `database.db_path` in `config.yaml`, OR
   - Set `BINANCE_DATABASE__DB_PATH` environment variable

3. **Do I need to update all my scripts?**
   - No, old API still works via `LegacyBinanceDataRepository`
   - But new API provides better error messages and features

4. **How do I add custom thresholds for new symbols?**
   - Edit `pipeline.bar_thresholds.dollar_bars` in `config.yaml`
   - Or use environment variables
   - Or pass `dollar_threshold` parameter directly

## Benefits Summary

✅ **Single source of truth** - No more conflicting database paths
✅ **Type-safe** - Pydantic catches configuration errors
✅ **Comprehensive errors** - Actionable error messages with suggestions
✅ **Flexible** - YAML file + environment variables + code overrides
✅ **Feature-rich** - Dollar-volume bars built-in
✅ **Backwards compatible** - Old code still works

## Next Steps

1. Read the updated examples in `examples/` directory
2. Check out the notebook at `specs/dollar_volume_sampling.ipynb`
3. Explore error handling in `src/binance_tick_data/errors.py`
4. Customize `config.yaml` for your needs
