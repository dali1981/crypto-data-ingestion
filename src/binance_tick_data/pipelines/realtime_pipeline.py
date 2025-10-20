"""Pipeline for streaming real-time Binance tick data."""

import dlt
from .. import BinanceConfig, binance_realtime_data
import signal
import sys


# Global flag for graceful shutdown
shutdown_flag = False


def signal_handler(sig, frame):
    """Handle Ctrl+C for graceful shutdown."""
    global shutdown_flag
    print("\n\nShutdown signal received. Finishing current batch...")
    shutdown_flag = True


def run_realtime_pipeline(
    symbols=None,
    destination="duckdb",
    dataset_name="binance_realtime",
    max_batches=None,
):
    """
    Run the real-time streaming pipeline.

    Args:
        symbols: List of symbols to stream (e.g., ["BTCUSDT", "ETHUSDT"])
        destination: Destination type (default: "duckdb")
        dataset_name: Dataset name in the destination
        max_batches: Maximum number of batches to process (None = infinite)
    """
    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)

    # Initialize configuration
    config = BinanceConfig()

    # Override with provided parameters
    if symbols:
        config.symbols = symbols

    print(f"Starting real-time streaming pipeline for: {config.symbols}")
    print(f"Destination: {destination} (dataset: {dataset_name})")
    print(f"Buffer size: {config.stream_buffer_size}")
    print("Press Ctrl+C to stop gracefully\n")

    # Create the pipeline
    pipeline = dlt.pipeline(
        pipeline_name="binance_realtime",
        destination=destination,
        dataset_name=dataset_name,
    )

    # Get the source
    source = binance_realtime_data(config, symbols)

    # Stream data continuously
    batch_count = 0

    try:
        for load_info in pipeline.run(source, loader_file_format="parquet"):
            batch_count += 1
            print(f"\n{'='*60}")
            print(f"Batch {batch_count} processed at: {load_info.started_at}")
            print(f"{'='*60}")

            # Print batch statistics
            for package in load_info.load_packages:
                for table in package.jobs.get("completed_jobs", []):
                    print(f"  {table.job_file_info.table_name}: Loaded successfully")

            # Check if we should stop
            if shutdown_flag or (max_batches and batch_count >= max_batches):
                print("\nStopping pipeline...")
                break

    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Exiting...")
    except Exception as e:
        print(f"\nError in streaming pipeline: {e}")
        raise
    finally:
        print(f"\nTotal batches processed: {batch_count}")
        print("Pipeline stopped.")


def main():
    """CLI entry point for real-time pipeline."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Stream real-time Binance tick data"
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        help="Trading symbols (e.g., BTCUSDT ETHUSDT)",
        default=None,
    )
    parser.add_argument(
        "--destination",
        help="Destination type (default: duckdb)",
        default="duckdb",
    )
    parser.add_argument(
        "--dataset",
        help="Dataset name (default: binance_realtime)",
        default="binance_realtime",
    )
    parser.add_argument(
        "--max-batches",
        type=int,
        help="Maximum number of batches to process (default: unlimited)",
        default=None,
    )

    args = parser.parse_args()

    run_realtime_pipeline(
        symbols=args.symbols,
        destination=args.destination,
        dataset_name=args.dataset,
        max_batches=args.max_batches,
    )


if __name__ == "__main__":
    main()
