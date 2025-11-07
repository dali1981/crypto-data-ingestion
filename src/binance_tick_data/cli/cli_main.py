#!/usr/bin/env python3
"""
Unified CLI for Binance tick data operations.

This provides a single `binance` command with subcommands for:
- download: Historical data download
- stream: Real-time data streaming
- validate: Data quality validation
- list: List available data

Example usage:
    binance download --symbols BTCUSDT --start-date 2024-01-01
    binance stream --symbols BTCUSDT ETHUSDT --max-batches 10
    binance validate --start-date 2024-01-01
    binance list --summary
"""

import sys
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Optional
import typer
from typing_extensions import Annotated

# Import CLI business logic and display functions
from binance_tick_data.cli import (
    DownloadParams,
    execute_download,
    StreamParams,
    execute_stream,
)
from binance_tick_data.cli.display import (
    display_download_info,
    display_download_result,
    display_stream_info,
    display_stream_result,
    display_error,
    display_warning,
    display_info,
    display_next_steps,
    console,
)
from binance_tick_data.utils.logging import setup_logging, get_logger

# Create Typer app
app = typer.Typer(
    name="binance",
    help="Binance tick data ingestion and management CLI",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
)

logger = get_logger(__name__)


@app.command()
def download(
    symbols: Annotated[
        List[str],
        typer.Option("--symbols", "-s", help="Trading symbols (e.g., BTCUSDT ETHUSDT)")
    ],
    start_date: Annotated[
        str,
        typer.Option("--start-date", help="Start date (YYYY-MM-DD)")
    ],
    end_date: Annotated[
        Optional[str],
        typer.Option("--end-date", help="End date (YYYY-MM-DD, default: today)")
    ] = None,
    max_records: Annotated[
        Optional[int],
        typer.Option("--max-records", help="Max records to download (for testing)")
    ] = None,
    batch_size: Annotated[
        int,
        typer.Option("--batch-size", help="Records per batch (100-10000)")
    ] = 1000,
    destination: Annotated[
        str,
        typer.Option("--destination", help="Destination type")
    ] = "duckdb",
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Verbose output (DEBUG level)")
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Quiet mode (WARNING level only)")
    ] = False,
    log_file: Annotated[
        Optional[Path],
        typer.Option("--log-file", help="Log to file")
    ] = None,
    json_logs: Annotated[
        bool,
        typer.Option("--json-logs", help="JSON log format (for production)")
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would happen without executing")
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output results as JSON")
    ] = False,
):
    """
    Download historical tick data from Binance.

    Examples:
        # Download last 30 days for BTCUSDT
        binance download --symbols BTCUSDT --start-date 2024-10-01

        # Download multiple symbols with limit
        binance download --symbols BTCUSDT ETHUSDT --start-date 2024-01-01 --max-records 10000

        # Dry run to see what would happen
        binance download --symbols BTCUSDT --start-date 2024-01-01 --dry-run
    """
    # Setup logging
    setup_logging(verbose=verbose, quiet=quiet, log_file=log_file, json_logs=json_logs)
    logger.info("download_command_started", symbols=symbols, start_date=start_date)

    try:
        # Parse dates
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
        if end_date:
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
        else:
            end_date_obj = None

        # Create params with validation
        params = DownloadParams(
            symbols=symbols,
            start_date=start_date_obj,
            end_date=end_date_obj,
            max_records=max_records,
            batch_size=batch_size,
            destination=destination,
        )

        # Display info
        if not json_output:
            display_download_info(params)

        # Dry run
        if dry_run:
            console.print("[yellow]DRY RUN MODE - No data will be downloaded[/yellow]\n")
            console.print("The following operation would be executed:\n")
            console.print(f"  • Download {len(params.symbols)} symbol(s): {', '.join(params.symbols)}")
            console.print(f"  • Date range: {params.start_date} to {params.end_date or 'today'}")
            console.print(f"  • Days to download: {params.days_to_download}")
            if params.max_records:
                console.print(f"  • Max records: {params.max_records:,}")
            console.print(f"  • Batch size: {params.batch_size}")
            console.print(f"\n[dim]Remove --dry-run to execute the download[/dim]\n")
            logger.info("dry_run_completed")
            return

        # Warn about large downloads
        if params.is_large_download:
            display_warning(
                f"Large download: {params.days_to_download} days of data for {len(params.symbols)} symbol(s)"
            )
            if not typer.confirm("Continue with download?"):
                console.print("[yellow]Download cancelled by user[/yellow]\n")
                logger.info("download_cancelled_by_user")
                return

        # Execute download
        result = execute_download(params)

        # Output results
        if json_output:
            import json
            print(json.dumps(result.model_dump(), indent=2, default=str))
        else:
            display_download_result(result)

            # Next steps guidance
            if result.success:
                display_next_steps([
                    f"Validate data: [yellow]binance validate --start-date {params.start_date}[/yellow]",
                    "List downloaded data: [yellow]binance list --summary[/yellow]",
                    "Query data using BinanceDataRepository in Python",
                ])

        # Log completion
        logger.info(
            "download_command_completed",
            success=result.success,
            records_count=result.records_count,
            duration=result.duration_seconds,
        )

        # Exit with appropriate code
        sys.exit(0 if result.success else 1)

    except ValueError as e:
        display_error("Invalid parameter", str(e))
        logger.error("download_command_failed", error=str(e))
        sys.exit(1)
    except Exception as e:
        display_error("Unexpected error", str(e))
        logger.error("download_command_failed", error=str(e), exc_info=True)
        sys.exit(1)


@app.command()
def stream(
    symbols: Annotated[
        List[str],
        typer.Option("--symbols", "-s", help="Trading symbols to stream")
    ],
    max_batches: Annotated[
        Optional[int],
        typer.Option("--max-batches", help="Max batches to process (default: unlimited)")
    ] = None,
    buffer_size: Annotated[
        int,
        typer.Option("--buffer-size", help="Buffer size before flushing")
    ] = 100,
    destination: Annotated[
        str,
        typer.Option("--destination", help="Destination type")
    ] = "duckdb",
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Verbose output")
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Quiet mode")
    ] = False,
    log_file: Annotated[
        Optional[Path],
        typer.Option("--log-file", help="Log to file")
    ] = None,
    json_logs: Annotated[
        bool,
        typer.Option("--json-logs", help="JSON log format")
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output results as JSON")
    ] = False,
):
    """
    Stream real-time tick data from Binance.

    Examples:
        # Stream BTCUSDT indefinitely (press Ctrl+C to stop)
        binance stream --symbols BTCUSDT

        # Stream multiple symbols for 10 batches
        binance stream --symbols BTCUSDT ETHUSDT --max-batches 10

        # Stream with larger buffer
        binance stream --symbols BTCUSDT --buffer-size 500
    """
    # Setup logging
    setup_logging(verbose=verbose, quiet=quiet, log_file=log_file, json_logs=json_logs)
    logger.info("stream_command_started", symbols=symbols, max_batches=max_batches)

    try:
        # Create params with validation
        params = StreamParams(
            symbols=symbols,
            max_batches=max_batches,
            buffer_size=buffer_size,
            destination=destination,
        )

        # Display info
        if not json_output:
            display_stream_info(params)

        # Execute stream
        result = execute_stream(params, setup_signal_handlers=True)

        # Output results
        if json_output:
            import json
            print(json.dumps(result.model_dump(), indent=2, default=str))
        else:
            display_stream_result(result)

        # Log completion
        logger.info(
            "stream_command_completed",
            success=result.success,
            batches=result.batches_processed,
            duration=result.duration_seconds,
        )

        # Exit with appropriate code
        sys.exit(0 if result.success else 1)

    except ValueError as e:
        display_error("Invalid parameter", str(e))
        logger.error("stream_command_failed", error=str(e))
        sys.exit(1)
    except Exception as e:
        display_error("Unexpected error", str(e))
        logger.error("stream_command_failed", error=str(e), exc_info=True)
        sys.exit(1)


@app.command()
def validate(
    start_date: Annotated[
        Optional[str],
        typer.Option("--start-date", help="Start date for validation window")
    ] = None,
    end_date: Annotated[
        Optional[str],
        typer.Option("--end-date", help="End date for validation window")
    ] = None,
    symbol: Annotated[
        Optional[str],
        typer.Option("--symbol", help="Specific symbol to validate (all if not specified)")
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output results as JSON")
    ] = False,
):
    """
    Validate data quality (check for duplicates, gaps, anomalies).

    Examples:
        # Validate all data
        binance validate

        # Validate specific symbol
        binance validate --symbol BTCUSDT

        # Validate date range
        binance validate --start-date 2024-01-01 --end-date 2024-01-31
    """
    display_error(
        "Command not yet implemented",
        "The 'validate' command will be implemented in Phase 6"
    )
    console.print("[dim]Coming soon: Data quality validation with gap detection and duplicate checking[/dim]\n")
    sys.exit(1)


@app.command(name="list")
def list_data(
    summary: Annotated[
        bool,
        typer.Option("--summary", help="Show summary view")
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output as JSON")
    ] = False,
):
    """
    List available downloaded data.

    Examples:
        # List all data with details
        binance list

        # Show summary view
        binance list --summary

        # Get JSON output for scripting
        binance list --json
    """
    display_error(
        "Command not yet implemented",
        "The 'list' command will be implemented in Phase 6"
    )
    console.print("[dim]Coming soon: List available data with date ranges and statistics[/dim]\n")
    sys.exit(1)


@app.callback()
def callback():
    """
    Binance Tick Data CLI - Production-grade data ingestion tool.

    This CLI provides commands for downloading historical data, streaming real-time data,
    validating data quality, and managing your local Binance tick data repository.
    """
    pass


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
