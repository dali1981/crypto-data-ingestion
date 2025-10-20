# Project Structure - Complete

## Overview

```
dlt-starter/
├── 📚 docs/                           # Documentation
│   ├── README.md                      # Documentation index
│   ├── JOBS_QUICK_START.md            # 5-minute quick start
│   ├── SOLUTION_SUMMARY.md            # Complete solution
│   └── DATA_QUALITY_REPORT.md         # Original analysis
│
├── 🔧 jobs/                           # Data quality jobs
│   ├── 01_data_quality_assessment.py  # Quality checker
│   ├── 02_deduplication.py            # Duplicate remover
│   ├── 03_fill_gaps.py                # Gap filler ⭐
│   ├── run_all_jobs.py                # Job orchestrator
│   ├── daily_job.py                   # Daily automation
│   ├── README.md                      # Jobs documentation
│   ├── .gitignore
│   ├── reports/                       # Generated reports
│   │   └── *.json
│   └── systemd/                       # Systemd configs
│       ├── binance-daily.service
│       └── binance-daily.timer
│
├── 📦 src/binance_tick_data/          # Main library
│   ├── __init__.py
│   ├── config.py
│   ├── db_config.py                   # New config system
│   ├── errors.py                      # Error hierarchy
│   ├── repository_v2.py               # New repository ⭐
│   ├── repository.py                  # Legacy
│   ├── sources/
│   │   ├── __init__.py
│   │   ├── rest_api.py                # Historical data (append mode)
│   │   ├── websocket.py               # Real-time data
│   │   └── schemas.py
│   └── pipelines/
│       ├── historical_pipeline.py
│       └── realtime_pipeline.py
│
├── 📊 examples/                       # Usage examples
│   ├── simple_read.py
│   ├── data_analysis.py
│   ├── dollar_bars_example.py
│   └── test_new_system.py
│
├── 🔍 Analysis Tools/                 # Manual tools
│   ├── data_gap_analysis.py           # Manual analysis
│   └── fix_data_issues.py             # Manual fixes
│
├── 📄 Documentation/                  # Project docs
│   ├── README.md                      # Main README
│   ├── IMPLEMENTATION_COMPLETE.md     # Implementation summary
│   ├── PROJECT_STRUCTURE.md           # This file
│   ├── INSTALLATION.md
│   ├── QUICK_START.md
│   ├── MIGRATION_GUIDE.md
│   └── ...other docs...
│
├── ⚙️ Configuration/
│   ├── config.yaml                    # Pipeline config
│   ├── pyproject.toml                 # Dependencies
│   └── uv.lock
│
└── 💾 Database/
    └── binance_pipeline.duckdb        # DuckDB database
```

---

## Key Directories

### 📚 docs/
Complete documentation for data quality system
- Quick start guide
- Architecture documentation
- Analysis reports

### 🔧 jobs/
**Most important directory** - Data quality management
- 5 automated jobs
- Orchestration
- Daily automation
- Systemd configs

### 📦 src/binance_tick_data/
Main library code
- Data sources (REST API, WebSocket)
- Repository (data access)
- Configuration
- Error handling

### 📊 examples/
Example usage scripts
- Simple reading
- Data analysis
- Dollar bars
- Testing

---

## Important Files

### Job Files (New)
```
jobs/01_data_quality_assessment.py  ← Analyze data quality
jobs/02_deduplication.py            ← Remove duplicates
jobs/03_fill_gaps.py                ← Fill gaps (auto-chunking) ⭐
jobs/run_all_jobs.py                ← Run all jobs
jobs/daily_job.py                   ← Daily automation
```

### Documentation (New)
```
docs/JOBS_QUICK_START.md            ← Start here!
docs/SOLUTION_SUMMARY.md            ← Complete solution
docs/DATA_QUALITY_REPORT.md         ← Analysis findings
IMPLEMENTATION_COMPLETE.md          ← What was built
```

### Core Library
```
src/binance_tick_data/repository_v2.py   ← New repository
src/binance_tick_data/db_config.py       ← Configuration
src/binance_tick_data/errors.py          ← Error handling
src/binance_tick_data/sources/rest_api.py ← Data ingestion
```

### Configuration
```
config.yaml                         ← Pipeline settings
pyproject.toml                      ← Dependencies
```

---

## Data Flow

```
1. Data Ingestion
   ↓
   src/binance_tick_data/sources/rest_api.py
   (append mode)
   ↓
2. Database Storage
   ↓
   binance_pipeline.duckdb
   (may have duplicates)
   ↓
3. Quality Assessment
   ↓
   jobs/01_data_quality_assessment.py
   ↓
4. Deduplication
   ↓
   jobs/02_deduplication.py
   (creates backup)
   ↓
5. Gap Filling
   ↓
   jobs/03_fill_gaps.py
   (auto-chunks)
   ↓
6. Clean Data
   ↓
   Ready for analysis!
```

---

## File Counts

| Category | Count | Lines |
|----------|-------|-------|
| Job Scripts | 5 | ~1,700 |
| Documentation | 8 | ~5,000 words |
| Library Code | 15+ | ~3,000 |
| Examples | 4 | ~500 |
| **Total New** | **13** | **~3,000 + docs** |

---

## Quick Navigation

### To fix data issues:
→ `docs/JOBS_QUICK_START.md`

### To understand the solution:
→ `docs/SOLUTION_SUMMARY.md`

### To read technical docs:
→ `jobs/README.md`

### To see implementation:
→ `IMPLEMENTATION_COMPLETE.md`

### To run jobs:
```bash
cd jobs/
ls -1 *.py
```

---

## Database Structure

```
binance_pipeline.duckdb
├── binance_data (schema)
│   ├── agg_trades               # Main data table
│   ├── agg_trades_backup        # Backup (created by dedup job)
│   ├── _dlt_loads               # DLT metadata
│   ├── _dlt_pipeline_state      # DLT state
│   └── _dlt_version             # DLT version
└── (other schemas)
```

---

## Command Reference

### Quality Management
```bash
# Assess quality
uv run python jobs/01_data_quality_assessment.py

# Remove duplicates
uv run python jobs/02_deduplication.py --execute

# Fill gaps
uv run python jobs/03_fill_gaps.py --symbol BTCUSDT --fill-largest-gap

# Run all
uv run python jobs/run_all_jobs.py --symbol BTCUSDT --auto

# Daily job
uv run python jobs/daily_job.py --symbol BTCUSDT
```

### Data Analysis
```bash
# Simple read
uv run python examples/simple_read.py

# Data analysis with fractional differencing
uv run python examples/data_analysis.py

# Dollar bars
uv run python examples/dollar_bars_example.py
```

### Manual Tools
```bash
# Gap analysis
uv run python data_gap_analysis.py

# Fix issues manually
uv run python fix_data_issues.py
```

---

## Configuration Files

### Pipeline Configuration
`config.yaml` - Database paths, table names, bar thresholds

### Dependencies
`pyproject.toml` - Python dependencies managed by uv

### Jobs Configuration
Each job accepts command-line arguments:
- `--db-path`: Database path
- `--symbol`: Trading symbol
- `--max-records`: Max records per chunk
- etc.

---

## Logs & Reports

### Quality Assessment
```
jobs/reports/quality_assessment_YYYYMMDD_HHMMSS.json
jobs/reports/quality_assessment_latest.json
```

### Deduplication
```
jobs/reports/deduplication_YYYYMMDD_HHMMSS.json
jobs/reports/deduplication_latest.json
```

### Gap Filling
```
jobs/reports/gap_filling_YYYYMMDD_HHMMSS.json
jobs/reports/gap_filling_latest.json
```

### Daily Job
```
jobs/reports/daily/daily_job_YYYYMMDD.json
```

---

## Git Structure

### Tracked
- All source code
- Documentation
- Configuration files
- Job scripts
- Examples

### Ignored (`.gitignore`)
```
jobs/reports/          # Generated reports
*.pyc                  # Python cache
__pycache__/          # Python cache
.pytest_cache/        # Test cache
*.log                 # Log files
binance_pipeline.duckdb # Database
```

---

## Next Steps

1. **Read:** `docs/JOBS_QUICK_START.md`
2. **Run:** `uv run python jobs/run_all_jobs.py --symbol BTCUSDT --auto`
3. **Automate:** Add daily job to cron
4. **Monitor:** Check `jobs/reports/` directory

---

**Last Updated:** 2025-10-20
**Status:** Complete and production-ready
