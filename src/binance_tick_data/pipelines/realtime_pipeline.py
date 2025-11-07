"""Pipeline for streaming real-time Binance tick data.

REFACTORED: This is now a thin wrapper around cli.stream.execute_stream().
The business logic has been extracted for better testability and reusability.
"""

from ..cli import StreamParams, execute_stream


def run_realtime_pipeline(
    symbols=None,
    destination="duckdb",
    dataset_name="binance_realtime",
    max_batches=None,
):
    """
    Run the real-time streaming pipeline.

    NOTE: This function is now a thin wrapper for backward compatibility.
    Consider using cli.stream.execute_stream() directly for new code.

    Args:
        symbols: List of symbols to stream (e.g., ["BTCUSDT", "ETHUSDT"])
        destination: Destination type (default: "duckdb")
        dataset_name: Dataset name in the destination (deprecated, uses "binance_realtime")
        max_batches: Maximum number of batches to process (None = infinite)

    Returns:
        StreamResult object with success status and metrics
    """
    # Get symbols from config if not provided
    if symbols is None:
        from ..config import BinanceConfig
        config = BinanceConfig()
        symbols = config.symbols
        buffer_size = config.stream_buffer_size
    else:
        buffer_size = 100  # Default

    # Create params
    params = StreamParams(
        symbols=symbols,
        max_batches=max_batches,
        buffer_size=buffer_size,
        destination=destination,
    )

    # Display info (keeping backward compatibility)
    print(f"Starting real-time streaming pipeline for: {params.symbols}")
    print(f"Destination: {params.destination}")
    print(f"Buffer size: {params.buffer_size}")
    if params.max_batches:
        print(f"Max batches: {params.max_batches}")
    print("Press Ctrl+C to stop gracefully\n")

    # Execute stream
    result = execute_stream(params, setup_signal_handlers=True)

    # Display results (keeping backward compatibility)
    print(f"\n{'='*60}")
    if result.success:
        print("Stream completed successfully!")
    else:
        print("Stream FAILED!")
    print(f"{'='*60}")

    print(f"\nTotal batches processed: {result.batches_processed}")
    print(f"Approximate records: {result.records_count:,}")
    print(f"Duration: {result.duration_seconds:.2f} seconds")

    if result.output_path:
        print(f"Output path: {result.output_path}")

    if result.warnings:
        print("\nWarnings:")
        for warning in result.warnings:
            print(f"  - {warning}")

    if result.error:
        print(f"\nError: {result.error}")

    print("\nPipeline stopped.")

    return result


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
