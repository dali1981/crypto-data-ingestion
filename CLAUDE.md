# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a production-grade **Binance tick data ingestion library** built with:
- **dlt (data load tool)** for ETL pipeline orchestration
- **Dagster** for automated data maintenance and scheduling
- **DuckDB/Parquet** for local columnar storage and fast analytics
- **Pydantic models** for type-safe configuration and data validation

The library supports both historical data acquisition (REST API) and real-time streaming (WebSocket), with automatic deduplication, gap filling, and data quality management.

## Key Architecture Concepts

### Dual Configuration Systems

The project maintains **two separate configuration systems** for different purposes:

1. **Legacy Config (`config.py`)**: For dlt pipeline configuration
   - Used by historical/realtime pipelines
   - Contains API keys, symbols, batch sizes
   - Import: `from binance_tick_data import BinanceConfig`

2. **Modern Config (`db_config.py` + `config.yaml`)**: Single source of truth for database paths and table names
   - Used by repository, jobs, Dagster assets
   - Pydantic models with OmegaConf backend
   - Import: `from binance_tick_data import AppConfig, get_config`
   - **CRITICAL**: Always use `get_config()` to access database paths - prevents database location mismatches

### Repository Pattern

Two repository implementations exist:
- **`repository.py`**: Legacy implementation (use `LegacyBinanceDataRepository`)
- **`repository_v2.py`**: Modern implementation with comprehensive error handling (use `BinanceDataRepository`)

Always prefer `repository_v2.BinanceDataRepository` for new code.

### Per-Symbol Resources

Historical data fetching uses **one dlt resource per symbol** (not multi-symbol batching):
- Each symbol has independent extract/normalize/load cycles
- Data writes to Parquet as each symbol completes (not all-or-nothing)
- See `src/binance_tick_data/sources/rest_api.py:create_agg_trades_resource()`
- Function generates: `agg_trades_{symbol.lower()}` resource → `{SYMBOL}` table

### Data Quality Jobs System

The `jobs/` directory contains automated maintenance scripts:
- `01_data_quality_assessment.py`: Detect duplicates and gaps
- `02_deduplication.py`: Remove duplicates with backup
- `03_fill_gaps.py`: Fill data gaps with adaptive chunking
- `daily_job.py`: Daily incremental updates
- `run_all_jobs.py`: Run complete maintenance workflow

These jobs are **database-agnostic** - they write to the database specified in `config.yaml`.

### Dollar Volume Sampling

Advanced feature for creating information-driven bars:
- `dollar_volume_sampling.py`: Pandas-based implementation
- Aggregates ticks based on dollar volume (not time)
- Used for better statistical properties in ML pipelines
- Configurable thresholds in `config.yaml` → `pipeline.bar_thresholds`

## Common Commands

### Development Setup

```bash
# Install in editable mode (recommended)
uv pip install -e .

# Install with dev dependencies
uv pip install -e ".[dev]"

# Verify installation
uv run python -c "from binance_tick_data import BinanceDataRepository; print('✅ Installed!')"
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_dollar_volume_sampling.py

# Run with verbose output
uv run pytest -v

# Run specific test function
uv run pytest tests/test_repository_connection.py::test_connection -v
```

### Console Scripts (Entry Points)

Three main console scripts are installed via `pyproject.toml`:

```bash
# Download historical data (one-time fetch)
binance-download --symbols BTCUSDT --start-date 2024-10-01 --max-records 10000

# Download with incremental loading (safe for repeated runs)
binance-download-safe --symbols BTCUSDT ETHUSDT --start-date 2024-10-01

# Stream real-time data
binance-stream --symbols BTCUSDT ETHUSDT --max-batches 10
```

All console scripts can also be run via `uv run`:
```bash
uv run binance-download --symbols BTCUSDT --start-date 2024-10-01
```

### Data Quality Maintenance

```bash
# Run complete data quality workflow (assessment → dedup → fill gaps)
uv run python jobs/run_all_jobs.py --symbol BTCUSDT --auto

# Run individual jobs
uv run python jobs/01_data_quality_assessment.py --symbol BTCUSDT
uv run python jobs/02_deduplication.py --symbol BTCUSDT --backup
uv run python jobs/03_fill_gaps.py --symbol BTCUSDT --auto

# Daily incremental update (production)
uv run python jobs/daily_job.py --symbol BTCUSDT
```

### Dagster Pipeline

```bash
# Start Dagster UI (http://localhost:3000)
./start_dagster.sh

# Alternative (direct command)
uv run dagster dev -m dagster_pipeline

# Materialize specific asset
uv run dagster asset materialize -m dagster_pipeline --select raw_agg_trades

# Run specific job
uv run dagster job execute -m dagster_pipeline --job daily_update
```

### DuckDB Queries

```bash
# Open DuckDB CLI
duckdb binance_pipeline.duckdb

# Common queries (in DuckDB shell)
SHOW TABLES;
SELECT * FROM binance_data.BTCUSDT LIMIT 10;
SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM binance_data.BTCUSDT;
```

## Configuration Files

- **`config.yaml`**: Central database and table configuration (single source of truth)
- **`config.toml`**: dlt runtime configuration (log level, Parquet format, DuckDB settings)
- **`pyproject.toml`**: Package dependencies and console script entry points
- **`dagster_pipeline/config.py`**: Dagster-specific settings (symbols, thresholds, sensors)

## Important Implementation Details

### Rate Limiting

Global rate limiter prevents IP-level throttling:
```python
# In rest_api.py - shared across all symbols
_rate_limiter = BinanceRateLimiter()
```

### Incremental Loading

dlt tracks state automatically via `dlt.sources.incremental`:
```python
@dlt.resource(
    write_disposition="append",
    primary_key="agg_trade_id",
)
def _fetch_agg_trades(
    incremental: dlt.sources.incremental[int] = dlt.sources.incremental("agg_trade_id"),
):
    # Last loaded value tracked automatically
    last_id = incremental.last_value
```

### Error Hierarchy

Comprehensive error hierarchy in `errors.py`:
- Base: `BinanceDataError`
- Database: `DatabaseNotFoundError`, `TableNotFoundError`, `DatabaseConnectionError`
- Data: `NoDataFoundError`, `DataQualityError`, `InsufficientDataError`
- API: `RateLimitError`, `APIError`
- Config: `InvalidConfigurationError`

Always raise specific errors (not generic `Exception`).

### Date Partitioning

Tables are partitioned by date for efficient queries:
```python
@dlt.resource(
    columns={"date": {"partition": True}},  # Partition by trade date
)
```

This creates Parquet files like: `BTCUSDT/date=2024-10-01/*.parquet`

## Adding New Features

### Adding a New Data Source

1. Create source in `src/binance_tick_data/sources/` (e.g., `klines.py`)
2. Define Pydantic schema in `sources/schemas.py`
3. Add dlt resource with `@dlt.resource` decorator
4. Update `__init__.py` exports
5. Add table name to `config.yaml` → `tables`
6. Write tests in `tests/unit/sources/`

### Adding a New Console Script

1. Create script in `src/binance_tick_data/pipelines/`
2. Add `main()` function with typer CLI
3. Register in `pyproject.toml` → `[project.scripts]`
4. Reinstall: `uv pip install -e .`

### Adding a Dagster Asset

1. Add asset function in `dagster_pipeline/assets.py`
2. Use `@asset` decorator with dependencies
3. Access config via `from .config import SYMBOLS, DB_PATH`
4. Return metadata dict with `MaterializeResult`

## Database Locations

**CRITICAL**: The project may have multiple DuckDB databases:
- `binance_pipeline.duckdb`: Main production database (default in `config.yaml`)
- `dlt_binance.duckdb`: Legacy dlt default (check `config.toml`)
- Test databases created by pytest

Always check which database you're working with:
```python
from binance_tick_data import get_config
config = get_config()
print(f"Using database: {config.database.db_path}")
```

## Testing Strategy

- **Unit tests**: `tests/unit/` - test individual components (rate limiter, fetchers)
- **Integration tests**: `tests/` - test full pipelines and repository operations
- **Test fixtures**: Avoid hardcoded database paths - use config or fixtures
- **Mock API calls**: Use `pytest.mock` or `responses` library for Binance API tests

## Key Dependencies

- **dlt**: ETL pipeline framework (not Dagster orchestrator)
- **Dagster**: Job orchestration and scheduling
- **DuckDB**: Embedded columnar database
- **Pydantic**: Data validation and settings management
- **python-binance**: Official Binance API client
- **websockets**: For real-time streaming
- **typer**: CLI framework for console scripts
- **OmegaConf**: YAML configuration with validation

## Documentation Structure

- `README.md`: Main project overview and quick start
- `docs/QUICK_START.md`: Installation and first-time usage
- `docs/SOLUTION_SUMMARY.md`: Data quality architecture
- `docs/JOBS_QUICK_START.md`: Maintenance jobs guide
- `dagster_pipeline/README.md`: Dagster pipeline documentation
- `jobs/README.md`: Data quality jobs technical docs
- `examples/README.md`: Client code examples

## Common Pitfalls

1. **Multiple database files**: Always use `get_config().database.db_path` to avoid database mismatch
2. **Import paths**: Use absolute imports (`from binance_tick_data.xyz`) not relative (`from .xyz`) in user-facing code
3. **dlt state**: dlt stores incremental state in `.dlt/` - don't delete this directory between runs
4. **Rate limiting**: Don't bypass the global rate limiter - it prevents IP bans
5. **Read-only mode**: Default repository opens DB read-only - jobs must open with `read_only=False`