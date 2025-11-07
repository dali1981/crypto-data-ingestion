# CLI Modernization Plan - Adopt crypto_options Architecture

**Date:** 2025-11-07
**Status:** Approved for Implementation
**Goal:** Modernize dlt-starter CLI to match crypto_options production-grade architecture

## Executive Summary

Transform the current dlt-starter CLI from basic console scripts with mixed concerns into a production-ready, testable, and user-friendly CLI by adopting patterns from the crypto_options project.

**Key Changes:**
- Separate business logic from CLI presentation layer
- Add Pydantic models for type safety and validation
- Enhance UX with Rich library (colors, progress bars, tables)
- Implement structured logging with JSON support
- Create unified CLI entry point with subcommands
- Write comprehensive unit tests with dependency injection

## Current State Analysis

### Existing CLI Structure

```
dlt-starter/
└── src/binance_tick_data/
    └── pipelines/
        ├── historical_pipeline.py    # Console script: binance-download
        ├── incremental_pipeline.py   # Console script: binance-download-safe
        └── realtime_pipeline.py      # Console script: binance-stream
```

### Current Limitations

1. **Mixed Concerns:** CLI output and business logic intertwined
2. **No Validation:** Parameters passed as primitives, no validation
3. **Poor UX:** Basic print() statements, no colors, no progress indicators
4. **Untestable:** Can't unit test business logic without running actual pipelines
5. **No Logging:** Print statements instead of structured logs
6. **Fragmented Interface:** Three separate scripts instead of unified CLI

## Target State Architecture

### New Directory Structure

```
dlt-starter/
├── scripts/
│   └── cli.py                        # NEW: Unified Typer CLI entry point
└── src/binance_tick_data/
    ├── cli/                          # NEW: Business logic layer
    │   ├── __init__.py
    │   ├── models.py                 # Pydantic models (params/results)
    │   ├── download.py               # Download business logic
    │   ├── stream.py                 # Stream business logic
    │   ├── validate.py               # Validation business logic
    │   └── list_data.py              # List data business logic
    ├── utils/
    │   └── logging.py                # NEW: Centralized logging
    └── pipelines/                    # REFACTOR: Thin CLI wrappers
        ├── historical_pipeline.py
        ├── incremental_pipeline.py
        └── realtime_pipeline.py
```

### Architecture Pattern

```
CLI Layer (Typer) → Pydantic Models → Business Logic → Pydantic Results → Rich Display
```

## Implementation Phases

### Phase 1: Foundation - Separate Business Logic from CLI

**Objective:** Extract business logic into testable functions with dependency injection

**Tasks:**
1. Create directory structure:
   - `src/binance_tick_data/cli/` with `__init__.py`
   - `src/binance_tick_data/cli/models.py`
   - `src/binance_tick_data/cli/download.py`
   - `src/binance_tick_data/cli/stream.py`

2. Create Pydantic models in `cli/models.py`:
   ```python
   class DownloadParams(BaseModel):
       """Parameters for download operation."""
       model_config = ConfigDict(frozen=True)

       symbols: List[str] = Field(..., min_length=1)
       start_date: date
       end_date: Optional[date] = None
       max_records: Optional[int] = Field(None, ge=1000)
       batch_size: int = Field(1000, ge=100, le=10000)
       destination: str = "duckdb"

       @field_validator('symbols')
       @classmethod
       def validate_symbols(cls, v: List[str]) -> List[str]:
           return [s.upper() for s in v]

   class DownloadResult(BaseModel):
       """Result of download operation."""
       success: bool
       records_count: int = 0
       symbols_processed: List[str] = Field(default_factory=list)
       duration_seconds: float
       pipeline_name: str
       output_path: str
       error: Optional[str] = None
       warnings: List[str] = Field(default_factory=list)
   ```

3. Extract business logic into `cli/download.py`:
   ```python
   def execute_download(
       params: DownloadParams,
       pipeline_factory: Optional[Callable] = None,
   ) -> DownloadResult:
       """Execute download with injectable dependencies."""
       import time
       from datetime import datetime

       start_time = time.time()

       try:
           # Business logic here (no print statements)
           # Use pipeline_factory if provided (for testing)
           # Otherwise create real pipeline

           return DownloadResult(
               success=True,
               records_count=12345,
               symbols_processed=params.symbols,
               duration_seconds=time.time() - start_time,
               pipeline_name="binance_historical",
               output_path=str(config.database.db_path),
           )
       except Exception as e:
           logger.exception("download_failed", error=str(e))
           return DownloadResult(
               success=False,
               duration_seconds=time.time() - start_time,
               pipeline_name="binance_historical",
               output_path="",
               error=str(e),
           )
   ```

4. Refactor `pipelines/historical_pipeline.py` to thin wrapper:
   ```python
   def main():
       """CLI entry point - thin wrapper around business logic."""
       import typer
       from ..cli.download import execute_download
       from ..cli.models import DownloadParams

       # Parse CLI args
       # Create DownloadParams
       # Call execute_download()
       # Display result with Rich
   ```

**Deliverables:**
- ✅ New `cli/` directory with models and business logic
- ✅ Refactored pipeline files
- ✅ Business logic testable without CLI

**Commit:** "Refactor: Separate CLI business logic from presentation layer"

---

### Phase 2: Add Type Safety with Pydantic Models

**Objective:** Full parameter validation and structured results

**Tasks:**
1. Complete all Pydantic models in `cli/models.py`:
   - `DownloadParams` with validators
   - `StreamParams` with validators
   - `ValidateParams`
   - `ListDataParams`
   - `DownloadResult`
   - `StreamResult`
   - `ValidationResult`
   - `DataSummary`

2. Add field validators:
   - Date range validation (end_date >= start_date)
   - Future date warnings
   - Symbol format (uppercase, valid pairs)
   - Batch size constraints (100-10000)

3. Add computed properties:
   ```python
   @property
   def days_to_download(self) -> int:
       """Calculate number of days in range."""
       return (self.end_date - self.start_date).days

   @property
   def is_large_download(self) -> bool:
       """Check if download is large (>30 days)."""
       return self.days_to_download > 30
   ```

**Deliverables:**
- ✅ Complete Pydantic models with validation
- ✅ All parameters validated before execution
- ✅ Structured results with metrics

**Commit:** "Add Pydantic models for type-safe CLI parameters and results"

---

### Phase 3: Enhance UX with Rich Library

**Objective:** Professional CLI appearance with colors, progress bars, and tables

**Tasks:**
1. Add dependencies to `pyproject.toml`:
   ```toml
   dependencies = [
       # ... existing ...
       "rich>=13.0.0",
       "structlog>=24.0.0",
   ]
   ```

2. Create display functions (in CLI files):
   ```python
   from rich.console import Console
   from rich.table import Table
   from rich.progress import Progress, SpinnerColumn, BarColumn

   console = Console()

   def display_download_info(params: DownloadParams):
       """Display download info with Rich table."""
       console.print("\n[bold cyan]HISTORICAL DATA DOWNLOAD[/bold cyan]\n")

       table = Table(show_header=False, box=None)
       table.add_column("Key", style="cyan")
       table.add_column("Value", style="white")

       table.add_row("Symbols", ", ".join(params.symbols))
       table.add_row("Date Range", f"{params.start_date} to {params.end_date}")
       table.add_row("Batch Size", str(params.batch_size))

       console.print(table)

   def display_result(result: DownloadResult):
       """Display result with colors."""
       if result.success:
           console.print("\n[bold green]✓ DOWNLOAD COMPLETE[/bold green]\n")
           console.print(f"[green]Records:[/green] {result.records_count:,}")
           console.print(f"[green]Duration:[/green] {result.duration_seconds:.2f}s")
       else:
           console.print("\n[bold red]✗ DOWNLOAD FAILED[/bold red]\n")
           console.print(f"[red]Error:[/red] {result.error}")
   ```

3. Add progress bars for long operations:
   ```python
   with Progress(
       SpinnerColumn(),
       TextColumn("[progress.description]{task.description}"),
       BarColumn(),
       TaskProgressColumn(),
       console=console,
   ) as progress:
       task = progress.add_task("[cyan]Downloading...", total=None)
       result = execute_download(params)
   ```

4. Update all CLI files to use Rich console

**Deliverables:**
- ✅ Rich library integrated
- ✅ Color-coded output (green=success, red=error, yellow=warning)
- ✅ Progress bars for long operations
- ✅ Formatted tables for data display

**Commit:** "Add Rich library for professional CLI user experience"

---

### Phase 4: Add Structured Logging

**Objective:** Production-ready observability with structured logs

**Tasks:**
1. Create `src/binance_tick_data/utils/logging.py`:
   ```python
   import structlog
   import logging
   from pathlib import Path
   from typing import Optional

   def setup_logging(
       verbose: bool = False,
       quiet: bool = False,
       log_file: Optional[Path] = None,
       json_logs: bool = False,
   ) -> None:
       """Configure structured logging."""
       # Set log level
       level = logging.DEBUG if verbose else (
           logging.WARNING if quiet else logging.INFO
       )

       # Suppress noisy third-party loggers
       logging.getLogger("urllib3").setLevel(logging.WARNING)
       logging.getLogger("websockets").setLevel(logging.WARNING)
       logging.getLogger("dlt").setLevel(logging.WARNING)

       # Configure structlog
       processors = [
           structlog.contextvars.merge_contextvars,
           structlog.stdlib.add_log_level,
           structlog.processors.TimeStamper(fmt="iso"),
       ]

       if json_logs:
           processors.append(structlog.processors.JSONRenderer())
       else:
           processors.append(structlog.dev.ConsoleRenderer(colors=True))

       structlog.configure(
           processors=processors,
           wrapper_class=structlog.stdlib.BoundLogger,
           context_class=dict,
           logger_factory=structlog.stdlib.LoggerFactory(),
           cache_logger_on_first_use=True,
       )

       # File logging if specified
       if log_file:
           from logging.handlers import RotatingFileHandler
           handler = RotatingFileHandler(
               log_file,
               maxBytes=10*1024*1024,  # 10MB
               backupCount=5,
           )
           logging.root.addHandler(handler)

   def get_logger(name: str):
       """Get configured logger."""
       return structlog.get_logger(name)
   ```

2. Update business logic files to use logger:
   ```python
   from ..utils.logging import get_logger

   logger = get_logger(__name__)

   def execute_download(params: DownloadParams) -> DownloadResult:
       logger.info(
           "starting_download",
           symbols=params.symbols,
           date_range=f"{params.start_date} to {params.end_date}",
       )

       try:
           # ... business logic ...
           logger.info("download_complete", records_count=result.records_count)
           return result
       except Exception as e:
           logger.error("download_failed", error=str(e), exc_info=True)
           raise
   ```

3. Add logging CLI options:
   - `--verbose` / `-v`: DEBUG level
   - `--quiet` / `-q`: WARNING level
   - `--log-file PATH`: Log to file
   - `--json-logs`: JSON output for production

**Deliverables:**
- ✅ Centralized logging module
- ✅ Structured logs with context
- ✅ JSON logs option for production
- ✅ Log file rotation support

**Commit:** "Add structured logging with JSON support and file rotation"

---

### Phase 5: Create Unified CLI Entry Point

**Objective:** Single `binance` command with subcommands

**Tasks:**
1. Create `scripts/cli.py`:
   ```python
   #!/usr/bin/env python3
   """Unified CLI for Binance tick data operations."""

   import typer
   from typing import Optional, List
   from datetime import date, datetime, timedelta
   from pathlib import Path

   app = typer.Typer(
       name="binance",
       help="Binance tick data ingestion and management",
       add_completion=False,
   )

   @app.command()
   def download(
       symbols: List[str] = typer.Option(..., "--symbols", "-s", help="Trading symbols (e.g., BTCUSDT)"),
       start_date: str = typer.Option(..., "--start-date", help="Start date (YYYY-MM-DD)"),
       end_date: Optional[str] = typer.Option(None, "--end-date", help="End date (YYYY-MM-DD, default: today)"),
       max_records: Optional[int] = typer.Option(None, "--max-records", help="Max records to download"),
       batch_size: int = typer.Option(1000, "--batch-size", help="Records per batch"),
       verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
       quiet: bool = typer.Option(False, "--quiet", "-q", help="Quiet mode"),
       log_file: Optional[Path] = typer.Option(None, "--log-file", help="Log to file"),
       json_logs: bool = typer.Option(False, "--json-logs", help="JSON log format"),
       dry_run: bool = typer.Option(False, "--dry-run", help="Show what would happen"),
   ):
       """Download historical tick data from Binance."""
       from binance_tick_data.utils.logging import setup_logging
       from binance_tick_data.cli.download import execute_download
       from binance_tick_data.cli.models import DownloadParams

       # Setup logging
       setup_logging(verbose=verbose, quiet=quiet, log_file=log_file, json_logs=json_logs)

       # Create params with validation
       params = DownloadParams(
           symbols=symbols,
           start_date=datetime.strptime(start_date, "%Y-%m-%d").date(),
           end_date=datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else date.today(),
           max_records=max_records,
           batch_size=batch_size,
       )

       # Display info
       display_download_info(params)

       # Dry run
       if dry_run:
           console.print("[yellow]DRY RUN - No data will be downloaded[/yellow]")
           return

       # Confirm large downloads
       if params.is_large_download:
           if not typer.confirm(f"Download {params.days_to_download} days of data. Continue?"):
               console.print("[yellow]Download cancelled[/yellow]")
               return

       # Execute
       result = execute_download(params)

       # Display result
       display_result(result)

   @app.command()
   def stream(
       symbols: List[str] = typer.Option(..., "--symbols", "-s"),
       max_batches: Optional[int] = typer.Option(None, "--max-batches"),
       buffer_size: int = typer.Option(100, "--buffer-size"),
       verbose: bool = typer.Option(False, "--verbose", "-v"),
   ):
       """Stream real-time tick data from Binance."""
       # Similar structure
       pass

   @app.command()
   def validate(
       start_date: Optional[str] = typer.Option(None, "--start-date"),
       end_date: Optional[str] = typer.Option(None, "--end-date"),
       symbol: Optional[str] = typer.Option(None, "--symbol"),
       json: bool = typer.Option(False, "--json"),
   ):
       """Validate data quality (duplicates, gaps, anomalies)."""
       # NEW functionality
       pass

   @app.command(name="list")
   def list_data(
       summary: bool = typer.Option(False, "--summary"),
       json: bool = typer.Option(False, "--json"),
   ):
       """List available downloaded data."""
       # NEW functionality
       pass

   if __name__ == "__main__":
       app()
   ```

2. Update `pyproject.toml`:
   ```toml
   [project.scripts]
   binance = "scripts.cli:app"

   # Keep old scripts for backward compatibility
   binance-download = "binance_tick_data.pipelines.historical_pipeline:main"
   binance-download-safe = "binance_tick_data.pipelines.incremental_pipeline:main"
   binance-stream = "binance_tick_data.pipelines.realtime_pipeline:main"
   ```

**Deliverables:**
- ✅ Unified `binance` CLI with subcommands
- ✅ Backward compatibility with old scripts
- ✅ Consistent option naming across commands

**Commit:** "Create unified CLI entry point with subcommands"

---

### Phase 6: Add New Commands

**Objective:** Add validate and list-data commands

**Tasks:**
1. Create `cli/validate.py`:
   ```python
   def execute_validate(params: ValidateParams) -> ValidationResult:
       """Execute data validation."""
       # Check for duplicates
       # Check for gaps
       # Check for anomalies
       # Return structured result
   ```

2. Create `cli/list_data.py`:
   ```python
   def execute_list_data(params: ListDataParams) -> List[DataSummary]:
       """List available data."""
       # Query database for available symbols
       # Get date ranges and record counts
       # Return structured summaries
   ```

3. Implement commands in `scripts/cli.py`

**Deliverables:**
- ✅ `binance validate` command
- ✅ `binance list` command
- ✅ JSON output support for scripting

**Commit:** "Add validate and list-data commands with JSON output"

---

### Phase 7: Add Interactive Features

**Objective:** Dry-run mode, confirmations, guidance

**Tasks:**
1. Add dry-run support to all commands:
   ```python
   if dry_run:
       console.print("[yellow]DRY RUN MODE[/yellow]")
       console.print("The following would be executed:")
       # Show what would happen
       console.print("\nRemove --dry-run to execute")
       return
   ```

2. Add confirmations for risky operations:
   - Large downloads (>30 days)
   - Many symbols (>10)
   - Data deletion operations

3. Add next-steps guidance:
   ```python
   console.print("\n[cyan]Next steps:[/cyan]")
   console.print("  1. Validate data: [yellow]binance validate --start-date 2024-01-01[/yellow]")
   console.print("  2. List data: [yellow]binance list --summary[/yellow]")
   ```

4. Add JSON output option to all commands:
   ```python
   if json_output:
       import json
       print(json.dumps(result.model_dump(), indent=2, default=str))
   else:
       display_result(result)
   ```

**Deliverables:**
- ✅ Dry-run mode for all commands
- ✅ User confirmations for risky operations
- ✅ Next-steps guidance
- ✅ JSON output for automation

**Commit:** "Add interactive features: dry-run, confirmations, JSON output"

---

### Phase 8: Write Comprehensive Tests

**Objective:** High test coverage with dependency injection

**Tasks:**
1. Create test structure:
   ```
   tests/unit/cli/
   ├── __init__.py
   ├── test_models.py
   ├── test_download.py
   ├── test_stream.py
   ├── test_validate.py
   └── test_list_data.py
   ```

2. Write model tests (`test_models.py`):
   ```python
   class TestDownloadParams:
       def test_valid_params(self):
           params = DownloadParams(
               symbols=["BTCUSDT"],
               start_date=date(2024, 1, 1),
               end_date=date(2024, 1, 31),
           )
           assert params.symbols == ["BTCUSDT"]
           assert params.days_to_download == 30

       def test_symbols_uppercased(self):
           params = DownloadParams(
               symbols=["btcusdt", "ethusdt"],
               start_date=date(2024, 1, 1),
           )
           assert params.symbols == ["BTCUSDT", "ETHUSDT"]

       def test_end_before_start_raises(self):
           with pytest.raises(ValidationError):
               DownloadParams(
                   symbols=["BTCUSDT"],
                   start_date=date(2024, 1, 31),
                   end_date=date(2024, 1, 1),
               )
   ```

3. Write business logic tests (`test_download.py`):
   ```python
   class TestExecuteDownload:
       def test_successful_download_with_mock(self):
           """Test with injected mock pipeline."""
           mock_pipeline = MagicMock()
           mock_pipeline.run.return_value = Mock(loads_ids=["load_123"])

           def mock_factory(params):
               return mock_pipeline

           params = DownloadParams(
               symbols=["BTCUSDT"],
               start_date=date(2024, 1, 1),
               end_date=date(2024, 1, 2),
           )

           result = execute_download(params, pipeline_factory=mock_factory)

           assert isinstance(result, DownloadResult)
           assert result.success is True
           assert result.duration_seconds > 0
           mock_pipeline.run.assert_called_once()

       def test_download_handles_exception(self):
           """Test error handling."""
           def failing_factory(params):
               raise ValueError("Pipeline failed")

           params = DownloadParams(
               symbols=["BTCUSDT"],
               start_date=date(2024, 1, 1),
           )

           result = execute_download(params, pipeline_factory=failing_factory)

           assert result.success is False
           assert "Pipeline failed" in result.error
   ```

4. Run tests and achieve 80%+ coverage:
   ```bash
   uv run pytest tests/unit/cli/ -v --cov=src/binance_tick_data/cli --cov-report=html
   ```

**Deliverables:**
- ✅ Comprehensive unit tests
- ✅ 80%+ test coverage
- ✅ Fast tests (no actual API calls)
- ✅ Mocked dependencies

**Commit:** "Add comprehensive unit tests for CLI business logic"

---

## Success Criteria

✅ **Separation of Concerns:** Business logic completely separate from CLI
✅ **Type Safety:** All parameters validated with Pydantic models
✅ **Professional UX:** Rich colors, progress bars, formatted tables
✅ **Observability:** Structured logging with JSON support
✅ **Testability:** 80%+ test coverage with pure unit tests
✅ **User-Friendly:** Dry-run, confirmations, next-steps guidance
✅ **Scriptable:** JSON output for automation
✅ **Unified Interface:** Single `binance` command with subcommands

## Rollout Strategy

1. **Development:** Implement phases 1-8 sequentially
2. **Testing:** Run full test suite after each phase
3. **Commits:** Atomic commits after each phase
4. **Documentation:** Update README with new CLI usage
5. **Migration:** Keep old console scripts for backward compatibility
6. **Announcement:** Update docs with migration guide

## Risk Mitigation

**Risk:** Breaking changes for existing users
**Mitigation:** Keep old console scripts as aliases

**Risk:** Increased complexity
**Mitigation:** Clear separation of concerns, comprehensive tests

**Risk:** Performance overhead from validation
**Mitigation:** Pydantic validation is fast, negligible overhead

**Risk:** Learning curve for contributors
**Mitigation:** Clear documentation, code examples in tests

## Timeline

**Phase 1-2:** 2 days (Foundation + Models)
**Phase 3-4:** 2 days (Rich + Logging)
**Phase 5-6:** 2 days (Unified CLI + New Commands)
**Phase 7-8:** 2 days (Interactive + Tests)

**Total:** ~8 days for complete implementation

## References

- crypto_options CLI: `~/trading_project/crypto_options/scripts/cli.py`
- crypto_options business logic: `~/trading_project/crypto_options/src/crypto_options/cli/`
- Rich documentation: https://rich.readthedocs.io/
- structlog documentation: https://www.structlog.org/
- Pydantic documentation: https://docs.pydantic.dev/
- Typer documentation: https://typer.tiangolo.com/
