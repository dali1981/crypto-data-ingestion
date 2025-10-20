"""Incremental pipeline that writes data as it downloads (safer for long-running downloads)."""

import dlt
from .. import BinanceConfig, binance_historical_data


def run_incremental_pipeline(
    symbols=None,
    start_date=None,
    destination="duckdb",
    dataset_name="binance_data",
    max_records=None,
    chunk_size=10000,  # Write to DB every N records
):
    """
    Run historical pipeline with incremental writes.

    This version writes data to the database every `chunk_size` records
    instead of waiting until the end. Safer for long downloads!

    Args:
        symbols: List of symbols to fetch
        start_date: Start date in YYYY-MM-DD format
        destination: Destination type (default: "duckdb")
        dataset_name: Dataset name in the destination
        max_records: Maximum number of records to fetch per symbol
        chunk_size: Write to database every N records (default: 10000)
    """
    # Initialize configuration
    config = BinanceConfig()

    # Override with provided parameters
    if symbols:
        config.symbols = symbols
    if start_date:
        config.historical_start_date = start_date
    if max_records:
        config.historical_max_records = max_records

    print(f"Starting INCREMENTAL pipeline for: {config.symbols}")
    print(f"Start date: {config.historical_start_date}")
    if config.historical_max_records:
        print(f"Max records per symbol: {config.historical_max_records:,}")
    print(f"Chunk size: {chunk_size:,} (writes to DB every {chunk_size:,} records)")
    print(f"Destination: {destination} (dataset: {dataset_name})")

    # Create the pipeline
    # Use same pipeline name as historical to share database
    pipeline = dlt.pipeline(
        pipeline_name="binance_pipeline",
        destination=destination,
        dataset_name=dataset_name,
    )

    # Process in chunks
    from ..sources.rest_api import aggregated_trades

    print("\nProcessing aggregated trades in chunks...")
    total_loaded = 0
    chunk_count = 0

    # Get the resource
    resource = aggregated_trades(config, symbols or config.symbols, start_date or config.historical_start_date)

    # Buffer for chunking
    buffer = []

    for batch in resource:
        # batch is already a list from the modified source
        if isinstance(batch, list):
            buffer.extend(batch)
        else:
            buffer.append(batch)

        # Check if we have enough to write
        if len(buffer) >= chunk_size:
            chunk_count += 1
            chunk_to_write = buffer[:chunk_size]
            buffer = buffer[chunk_size:]

            # Write this chunk
            print(f"\n📝 Writing chunk {chunk_count} ({len(chunk_to_write):,} records)...")

            # Create a simple list resource for this chunk
            @dlt.resource(name="agg_trades", write_disposition="append", primary_key="agg_trade_id")
            def chunk_data():
                yield chunk_to_write

            load_info = pipeline.run(chunk_data())
            total_loaded += len(chunk_to_write)

            print(f"✅ Chunk {chunk_count} written! Total loaded so far: {total_loaded:,}")

    # Write remaining buffer
    if buffer:
        chunk_count += 1
        print(f"\n📝 Writing final chunk ({len(buffer):,} records)...")

        @dlt.resource(name="agg_trades", write_disposition="append", primary_key="agg_trade_id")
        def final_chunk():
            yield buffer

        load_info = pipeline.run(final_chunk())
        total_loaded += len(buffer)
        print(f"✅ Final chunk written! Total loaded: {total_loaded:,}")

    # Print statistics
    print("\n" + "=" * 60)
    print("Incremental pipeline completed successfully!")
    print("=" * 60)
    print(f"Total chunks: {chunk_count}")
    print(f"Total records: {total_loaded:,}")

    # Print table statistics
    print("\nTable statistics:")
    try:
        with pipeline.sql_client() as client:
            with client.execute_query(
                f"SELECT COUNT(*) as count FROM {dataset_name}.agg_trades"
            ) as cursor:
                count = cursor.fetchone()[0]
                print(f"  agg_trades: {count:,} records")
    except Exception as e:
        print(f"  Could not retrieve count: {e}")

    return load_info


def main():
    """CLI entry point for incremental pipeline."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Download Binance data with incremental writes (safer for long downloads)"
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        help="Trading symbols (e.g., BTCUSDT ETHUSDT)",
        default=None,
    )
    parser.add_argument(
        "--start-date",
        help="Start date in YYYY-MM-DD format",
        default=None,
    )
    parser.add_argument(
        "--destination",
        help="Destination type (default: duckdb)",
        default="duckdb",
    )
    parser.add_argument(
        "--dataset",
        help="Dataset name (default: binance_data)",
        default="binance_data",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        help="Maximum number of records to fetch per symbol (default: unlimited)",
        default=None,
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        help="Write to database every N records (default: 10000)",
        default=10000,
    )

    args = parser.parse_args()

    run_incremental_pipeline(
        symbols=args.symbols,
        start_date=args.start_date,
        destination=args.destination,
        dataset_name=args.dataset,
        max_records=args.max_records,
        chunk_size=args.chunk_size,
    )


if __name__ == "__main__":
    main()
