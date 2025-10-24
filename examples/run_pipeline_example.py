"""
Example script demonstrating how to run the Binance data pipeline.

This script shows how to:
1. Configure the pipeline
2. Run with test destination (filesystem)
3. Monitor progress
4. Verify results

Usage:
    # Run with single symbol (fast test)
    uv run python examples/run_pipeline_example.py --symbol BTCUSDT

    # Run with multiple symbols
    uv run python examples/run_pipeline_example.py --symbols BTCUSDT ETHUSDT BNBUSDT

    # Run with date range
    uv run python examples/run_pipeline_example.py --start-date 2024-01-01

    # Use production config (larger buffers)
    uv run python examples/run_pipeline_example.py --profile production
"""

import argparse
import logging
from datetime import datetime
from pathlib import Path

import dlt

from binance_tick_data.config import BinanceConfig
from binance_tick_data.sources.rest_api import binance_historical_data

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_pipeline(
    symbols: list[str],
    start_date: str,
    destination: str = "filesystem",
    dataset_name: str = "binance_test",
    profile: str = None,
):
    """
    Run the Binance data pipeline.

    Args:
        symbols: List of trading symbols to fetch
        start_date: Start date in YYYY-MM-DD format
        destination: DLT destination (filesystem, duckdb, etc.)
        dataset_name: Name of the dataset
        profile: DLT config profile to use (dev, production, etc.)
    """
    # Load configuration
    config = BinanceConfig()

    logger.info(f"Starting pipeline for symbols: {symbols}")
    logger.info(f"Start date: {start_date}")
    logger.info(f"Destination: {destination}")
    logger.info(f"Dataset: {dataset_name}")

    if profile:
        logger.info(f"Using profile: {profile}")

    # Create pipeline
    pipeline = dlt.pipeline(
        pipeline_name="binance_data_pipeline",
        destination=destination,
        dataset_name=dataset_name,
        progress="log",  # Show progress in logs
    )

    # Create source with specified symbols
    source = binance_historical_data(
        config=config,
        symbols=symbols,
        start_date=start_date,
    )

    logger.info("Starting data extraction...")
    start_time = datetime.now()

    try:
        # Run pipeline
        load_info = pipeline.run(
            source,
            write_disposition="append",
        )

        elapsed = datetime.now() - start_time

        # Print results
        logger.info("=" * 80)
        logger.info("Pipeline completed successfully!")
        logger.info(f"Elapsed time: {elapsed}")
        logger.info("=" * 80)

        # Print load info details
        logger.info(f"\nLoad info:")
        logger.info(f"  Pipeline: {load_info.pipeline.pipeline_name}")
        logger.info(f"  Destination: {load_info.pipeline.destination_type}")
        logger.info(f"  Dataset: {load_info.pipeline.dataset_name}")

        # Print table statistics
        if hasattr(load_info, 'load_packages'):
            for package in load_info.load_packages:
                logger.info(f"\nLoad package: {package.load_id}")
                if hasattr(package, 'jobs'):
                    for job in package.jobs:
                        if hasattr(job, 'file_path'):
                            logger.info(f"  File: {job.file_path}")

        # Get destination info
        if destination == "filesystem":
            output_dir = Path(pipeline.working_dir) / dataset_name
            logger.info(f"\nData written to: {output_dir}")

            # List files if directory exists
            if output_dir.exists():
                parquet_files = list(output_dir.rglob("*.parquet"))
                logger.info(f"Total parquet files: {len(parquet_files)}")

                for file in parquet_files[:5]:  # Show first 5 files
                    size_mb = file.stat().st_size / (1024 * 1024)
                    logger.info(f"  {file.name}: {size_mb:.2f} MB")

                if len(parquet_files) > 5:
                    logger.info(f"  ... and {len(parquet_files) - 5} more files")

        logger.info("\n" + "=" * 80)

        return load_info

    except Exception as e:
        elapsed = datetime.now() - start_time
        logger.error(f"Pipeline failed after {elapsed}: {e}", exc_info=True)
        raise


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run Binance data pipeline with test destination",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--symbol",
        type=str,
        help="Single symbol to fetch (e.g., BTCUSDT)",
    )

    parser.add_argument(
        "--symbols",
        type=str,
        nargs="+",
        help="Multiple symbols to fetch (e.g., BTCUSDT ETHUSDT BNBUSDT)",
    )

    parser.add_argument(
        "--start-date",
        type=str,
        default="2024-01-01",
        help="Start date in YYYY-MM-DD format (default: 2024-01-01)",
    )

    parser.add_argument(
        "--destination",
        type=str,
        default="filesystem",
        choices=["filesystem", "duckdb", "parquet"],
        help="DLT destination (default: filesystem)",
    )

    parser.add_argument(
        "--dataset",
        type=str,
        default="binance_test",
        help="Dataset name (default: binance_test)",
    )

    parser.add_argument(
        "--profile",
        type=str,
        choices=["production"],
        help="DLT config profile (production for larger buffers)",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()

    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Determine symbols
    if args.symbol:
        symbols = [args.symbol]
    elif args.symbols:
        symbols = args.symbols
    else:
        # Default to single symbol for quick test
        symbols = ["BTCUSDT"]
        logger.info("No symbols specified, using default: BTCUSDT")

    # Run pipeline
    run_pipeline(
        symbols=symbols,
        start_date=args.start_date,
        destination=args.destination,
        dataset_name=args.dataset,
        profile=args.profile,
    )


if __name__ == "__main__":
    main()
