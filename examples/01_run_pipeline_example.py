"""
Example script demonstrating how to run the Binance data pipeline.

This script shows how to:
1. Configure the pipeline
2. Run with different destinations (filesystem with optional Delta Lake)
3. Monitor progress
4. Verify results

Prerequisites for Delta Lake:
    # Start MinIO for S3-compatible storage
    docker-compose up -d

Usage:
    # Run with single symbol (fast test, filesystem)
    uv run python examples/01_run_pipeline_example.py --symbol BTCUSDT

    # Run with Delta Lake (date-based partitioning + ACID guarantees)
    uv run python examples/01_run_pipeline_example.py --symbol BTCUSDT --delta

    # Run with multiple symbols
    uv run python examples/01_run_pipeline_example.py --symbols BTCUSDT ETHUSDT BNBUSDT

    # Run with date range
    uv run python examples/01_run_pipeline_example.py --start-date 2024-01-01

    # Use production config (larger buffers)
    uv run python examples/01_run_pipeline_example.py --symbol BTCUSDT --delta --profile production
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import dlt
import typer
from typing_extensions import Annotated
from dlt.destinations import filesystem

from binance_tick_data.config import BinanceConfig
from binance_tick_data.sources.rest_api import binance_historical_data

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Typer app
app = typer.Typer(
    help="Run Binance data pipeline with test destination",
    no_args_is_help=True,
)


def configure_destination(destination: str, use_delta: bool = False):
    """Configure destination with appropriate settings.

    Filesystem: Uses pipeline run date for partitioning
    Delta Lake: Uses column-based partitioning (date column from data)
    """
    if destination == "filesystem":
        if use_delta:
            # Delta Lake uses filesystem destination with S3 bucket
            return filesystem(bucket_url="s3://binance-data/warehouse")
        else:
            # Regular filesystem with date-based layout
            return filesystem(
                layout="{table_name}/{YYYY}-{MM}-{DD}/{load_id}.{file_id}.{ext}"
            )
    return destination


def print_results(load_info, elapsed, destination: str, dataset_name: str):
    """Print pipeline results and output files."""
    # Print summary
    logger.info("=" * 80)
    logger.info("Pipeline completed successfully!")
    logger.info(f"Elapsed time: {elapsed}")
    logger.info("=" * 80)

    # Print load info
    logger.info(f"\nLoad info:")
    logger.info(f"  Pipeline: {load_info.pipeline.pipeline_name}")
    logger.info(f"  Destination: {load_info.destination_type}")
    logger.info(f"  Dataset: {load_info.dataset_name}")

    # Print output files for filesystem
    if destination == "filesystem":
        bucket_url = load_info.destination_displayable_credentials.replace("file://", "")
        output_dir = Path(bucket_url) / dataset_name
        logger.info(f"\nData written to: {output_dir}")

        if output_dir.exists():
            data_files = list(output_dir.rglob("*.parquet"))
            logger.info(f"Total data files: {len(data_files)}")

            for file in data_files[:5]:
                size_mb = file.stat().st_size / (1024 * 1024)
                logger.info(f"  {file.name}: {size_mb:.2f} MB")

            if len(data_files) > 5:
                logger.info(f"  ... and {len(data_files) - 5} more files")

    logger.info("\n" + "=" * 80)


def run_pipeline(
    symbols: list[str],
    start_date: str,
    destination: str = "filesystem",
    dataset_name: str = "binance_test",
    profile: str = None,
    use_delta: bool = False,
):
    """Run the Binance data pipeline."""
    config = BinanceConfig()

    # Log configuration
    logger.info(f"Starting pipeline for symbols: {symbols}")
    logger.info(f"Start date: {start_date}")
    logger.info(f"Destination: {destination}")
    logger.info(f"Dataset: {dataset_name}")
    logger.info(f"Table format: {'delta' if use_delta else 'parquet'}")
    if profile:
        logger.info(f"Using profile: {profile}")

    # Configure destination
    dest = configure_destination(destination, use_delta)

    # Create pipeline
    pipeline = dlt.pipeline(
        pipeline_name="binance_data_pipeline",
        destination=dest,
        dataset_name=dataset_name,
        progress="log",
    )

    # Create source
    source = binance_historical_data(
        config=config,
        symbols=symbols,
        start_date=start_date,
    )

    # Run pipeline
    logger.info("Starting data extraction...")
    start_time = datetime.now()

    try:
        # Configure loader format based on table format
        if use_delta:
            load_info = pipeline.run(
                source,
                write_disposition="append",
                table_format="delta",  # Delta Lake table format
            )
        else:
            load_info = pipeline.run(
                source,
                write_disposition="append",
                loader_file_format="parquet",
            )
        elapsed = datetime.now() - start_time
        print_results(load_info, elapsed, destination, dataset_name)
        return load_info

    except Exception as e:
        elapsed = datetime.now() - start_time
        logger.error(f"Pipeline failed after {elapsed}: {e}", exc_info=True)
        raise


@app.command()
def main(
    symbol: Annotated[
        Optional[str],
        typer.Option(help="Single symbol to fetch (e.g., BTCUSDT)")
    ] = None,
    symbols: Annotated[
        Optional[list[str]],
        typer.Option(help="Multiple symbols to fetch (e.g., BTCUSDT ETHUSDT BNBUSDT)")
    ] = None,
    start_date: Annotated[
        str,
        typer.Option(help="Start date in YYYY-MM-DD format")
    ] = "2024-01-01",
    destination: Annotated[
        str,
        typer.Option(help="DLT destination")
    ] = "filesystem",
    dataset: Annotated[
        str,
        typer.Option(help="Dataset name")
    ] = "binance_test",
    profile: Annotated[
        Optional[str],
        typer.Option(help="DLT config profile (production for larger buffers)")
    ] = None,
    delta: Annotated[
        bool,
        typer.Option(help="Use Delta Lake table format (requires filesystem destination with S3)")
    ] = False,
    log_level: Annotated[
        str,
        typer.Option(help="Logging level")
    ] = "INFO",
):
    """
    Run Binance data pipeline with test destination.

    Examples:
        # Run with single symbol (fast test)
        uv run python examples/01_run_pipeline_example.py --symbol BTCUSDT

        # Run with Delta Lake table format (requires Docker MinIO)
        uv run python examples/01_run_pipeline_example.py --symbol BTCUSDT --delta

        # Run with multiple symbols
        uv run python examples/01_run_pipeline_example.py --symbols BTCUSDT --symbols ETHUSDT

        # Run with date range
        uv run python examples/01_run_pipeline_example.py --symbol BTCUSDT --start-date 2024-01-01

        # Use production config (larger buffers) with Delta Lake
        uv run python examples/01_run_pipeline_example.py --symbol BTCUSDT --delta --profile production
    """
    # Validate destination
    valid_destinations = ["filesystem", "duckdb", "parquet"]
    if destination not in valid_destinations:
        typer.echo(f"Error: destination must be one of {valid_destinations}", err=True)
        raise typer.Exit(1)

    # Validate Delta Lake usage
    if delta and destination != "filesystem":
        typer.echo("Error: --delta requires --destination filesystem", err=True)
        raise typer.Exit(1)

    # Validate log level
    valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
    if log_level not in valid_log_levels:
        typer.echo(f"Error: log-level must be one of {valid_log_levels}", err=True)
        raise typer.Exit(1)

    # Validate profile
    if profile and profile != "production":
        typer.echo("Error: profile must be 'production' if specified", err=True)
        raise typer.Exit(1)

    # Set log level
    logging.getLogger().setLevel(getattr(logging, log_level))

    # Determine symbols
    if symbol:
        selected_symbols = [symbol]
    elif symbols:
        selected_symbols = symbols
    else:
        # Default to single symbol for quick test
        selected_symbols = ["BTCUSDT"]
        logger.info("No symbols specified, using default: BTCUSDT")

    # Run pipeline
    run_pipeline(
        symbols=selected_symbols,
        start_date=start_date,
        destination=destination,
        dataset_name=dataset,
        profile=profile,
        use_delta=delta,
    )


if __name__ == "__main__":
    app()
