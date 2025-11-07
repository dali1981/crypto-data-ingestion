# Project Structure

Complete directory structure for the Binance Tick Data platform.

## Directory Tree

```
dlt-starter/
├── src/                          # Source code
│   └── binance_tick_data/
│       ├── __init__.py
│       ├── analyzers/            # Market microstructure analyzers
│       │   ├── base_analyzer.py
│       │   ├── order_flow.py
│       │   ├── liquidity.py
│       │   └── volume_profile.py
│       ├── consumers/            # Real-time consumers
│       │   ├── consumer_config.py
│       │   └── realtime_consumer.py
│       ├── streaming/            # Streaming infrastructure
│       │   ├── ring_buffer.py
│       │   ├── metrics_aggregator.py
│       │   └── event_publisher.py
│       ├── sources/              # Data sources
│       │   ├── rest_api.py
│       │   ├── websocket.py
│       │   └── schemas.py
│       ├── pipelines/            # Data pipelines
│       │   ├── historical_pipeline.py
│       │   ├── incremental_pipeline.py
│       │   └── realtime_pipeline.py
│       ├── config.py             # Legacy config
│       ├── db_config.py          # Database configuration
│       ├── errors.py             # Error definitions
│       ├── repository_v2.py      # Data repository
│       └── ...
│
├── examples/                     # Usage examples
│   ├── simple_streaming_example.py
│   ├── custom_analyzer_example.py
│   ├── realtime_monitoring.py
│   ├── realtime_analysis.ipynb
│   ├── simple_read.py
│   ├── using_repository.py
│   ├── dollar_bars_example.py
│   ├── data_analysis.ipynb
│   ├── data_analysis.py
│   └── test_new_system.py
│
├── jobs/                         # Data quality jobs
│   ├── 01_data_quality_assessment.py
│   ├── 02_deduplication.py
│   ├── 03_fill_gaps.py
│   ├── run_all_jobs.py
│   ├── daily_job.py
│   ├── README.md
│   └── systemd/
│       ├── binance-daily.service
│       └── binance-daily.timer
│
├── docs/                         # Documentation
│   ├── README.md                 # Documentation index
│   ├── QUICK_START.md            # Core platform guide
│   ├── GETTING_STARTED_STREAMING.md  # Streaming guide
│   ├── JOBS_QUICK_START.md       # Data quality guide
│   ├── ADAPTIVE_CHUNKING.md
│   ├── SMART_GAP_FILLING.md
│   ├── DATA_QUALITY_REPORT.md
│   ├── SOLUTION_SUMMARY.md
│   └── legacy/                   # Historical documentation
│       ├── ALTERNATIVES.md
│       ├── DATA_MANAGEMENT.md
│       ├── IMPLEMENTATION_COMPLETE.md
│       ├── INSTALLATION.md
│       ├── MIGRATION_GUIDE.md
│       ├── PROJECT_STRUCTURE.md
│       ├── PROJECT_SUMMARY.md
│       ├── QUICKSTART.md
│       ├── REPOSITORY_GUIDE.md
│       ├── STORAGE_COMPARISON.md
│       ├── SUCCESS_SUMMARY.md
│       └── VERIFICATION_COMPLETE.md
│
├── specs/                        # Architecture specifications
│   ├── STREAMING_INTEGRATION_PLAN.md
│   ├── STREAMING_IMPLEMENTATION_SUMMARY.md
│   └── PHASE_4_COMPLETE.md
│
├── scripts/                      # Utility scripts
│   ├── test_setup.py
│   ├── test_notebook_fix.py
│   ├── test_readonly_fix.py
│   ├── test_smart_gap_detection.py
│   ├── fix_data_issues.py
│   └── data_gap_analysis.py
│
├── analysis_output/              # Analysis results
│   ├── btc_price_returns.png
│   ├── btc_fracdiff_series.png
│   ├── btc_distributions.png
│   ├── btc_qq_plots.png
│   ├── btc_fracdiff_analysis.csv
│   ├── dollar_bars_analysis.png
│   └── dollar_bars.csv
│
├── data/                         # Data directory (empty, runtime)
│
├── .venv/                        # Virtual environment
│
├── binance_pipeline.duckdb       # Main database
├── binance_gap_filler.duckdb     # Gap filling database
│
├── config.yaml                   # Main configuration
├── config.toml                   # DLT configuration
├── pyproject.toml                # Project metadata
├── uv.lock                       # Dependency lock file
│
├── README.md                     # Main project README
├── README_STREAMING.md           # Streaming platform README
├── PROJECT_STRUCTURE.md          # This file
│
└── .gitignore                    # Git ignore rules
```

## Key Directories

### `/src/binance_tick_data/`
**Core library code**
- `analyzers/` - Market microstructure analyzers
- `consumers/` - Real-time data consumers
- `streaming/` - Streaming infrastructure (buffers, aggregators)
- `sources/` - Data sources (REST API, WebSocket)
- `pipelines/` - Data ingestion pipelines
- `repository_v2.py` - Main data access layer

**Total:** ~5,800 lines of production code

### `/examples/`
**Complete working examples**
- Simple streaming example
- Custom analyzer examples
- CLI monitoring dashboard
- Jupyter notebooks
- Repository usage examples

**Total:** 4 Python scripts + 2 notebooks

### `/jobs/`
**Data quality maintenance**
- Quality assessment
- Deduplication
- Gap filling
- Daily automation
- Systemd service files

**Total:** 5 job scripts

### `/docs/`
**Comprehensive documentation**
- Quick start guides (3)
- Technical documentation (4)
- Legacy documentation (12)

**Total:** ~3,000 lines of documentation

### `/specs/`
**Architecture specifications**
- Streaming integration plan
- Implementation summary
- Delivery documentation

**Total:** ~2,400 lines of specs

### `/scripts/`
**Utility scripts**
- Test scripts
- Fix scripts
- Analysis tools

**Total:** 6 utility scripts

### `/analysis_output/`
**Generated analysis files**
- Charts and visualizations
- CSV exports
- Analysis results

## File Counts

```
Type                Count    Lines
─────────────────────────────────────
Python source       45       ~5,800
Jupyter notebooks   2        ~300 cells
Documentation       19       ~5,400
Configuration       3        ~150
Total              69       ~11,650
```

## Database Files

### `binance_pipeline.duckdb` (8.9 MB)
Main production database with:
- agg_trades table
- trades table
- order_book_snapshots table
- Derived tables (dollar_bars, etc.)

### `binance_gap_filler.duckdb` (172 MB)
Gap filling database with historical data

## Configuration Files

### `config.yaml`
Main configuration for:
- Database settings
- Table mappings
- Pipeline configuration
- Streaming configuration

### `config.toml`
DLT-specific configuration

### `pyproject.toml`
Python project metadata:
- Dependencies
- Scripts
- Build system

## Virtual Environment

### `.venv/`
Python 3.12 virtual environment with all dependencies installed

## Quick Navigation

### New User
1. Start: `README.md`
2. Core: `docs/QUICK_START.md`
3. Streaming: `docs/GETTING_STARTED_STREAMING.md`
4. Examples: `examples/`

### Developer
1. Architecture: `specs/STREAMING_INTEGRATION_PLAN.md`
2. Source: `src/binance_tick_data/`
3. Examples: `examples/custom_analyzer_example.py`

### Operations
1. Jobs: `jobs/README.md`
2. Quality: `docs/JOBS_QUICK_START.md`
3. Config: `config.yaml`

## Size Summary

```
Component          Size
─────────────────────────
Source code        ~5,800 lines
Documentation      ~5,400 lines
Examples          ~940 lines
Total code        ~12,140 lines

Databases         ~181 MB
Dependencies      ~500 MB (in .venv)
Total disk        ~700 MB
```

## Growth Over Time

```
Phase               Files    Lines Added
──────────────────────────────────────
Initial setup       15       ~2,000
Core platform       20       ~3,000
Streaming (P1-P3)   13       ~4,500
Streaming (P4)      4        ~2,000
Documentation       19       ~5,400
──────────────────────────────────────
Total              71       ~16,900
```

## Maintenance

### Regular Updates
- `uv.lock` - When dependencies change
- `config.yaml` - For configuration changes
- `docs/` - Keep documentation current

### Generated Files
- `analysis_output/` - Created by examples
- `*.duckdb` - Database files
- `.venv/` - Recreated with `uv sync`

## Version Control

### Tracked
- All source code
- Documentation
- Configuration
- Examples
- Job scripts

### Ignored (`.gitignore`)
- `.venv/`
- `*.duckdb`
- `__pycache__/`
- Analysis outputs
- Temporary files

---

**Last Updated:** 2025-10-20

For detailed information about specific components, see the documentation in `/docs/`.
