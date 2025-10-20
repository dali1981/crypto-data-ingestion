"""Pipeline for downloading historical Binance tick data."""

import dlt
from .. import BinanceConfig, binance_historical_data


def run_historical_pipeline(
    symbols=None,
    start_date=None,
    destination="duckdb",
    dataset_name="binance_historical",
    max_records=None,
):
    """
    Run the historical data pipeline.

    Args:
        symbols: List of symbols to fetch (e.g., ["BTCUSDT", "ETHUSDT"])
        start_date: Start date in YYYY-MM-DD format
        destination: Destination type (default: "duckdb")
        dataset_name: Dataset name in the destination
        max_records: Maximum number of records to fetch per symbol (None = unlimited)
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

    print(f"Starting historical data pipeline for: {config.symbols}")
    print(f"Start date: {config.historical_start_date}")
    if config.historical_max_records:
        print(f"Max records per symbol: {config.historical_max_records:,}")
    print(f"Destination: {destination} (dataset: {dataset_name})")

    # Create the pipeline
    pipeline = dlt.pipeline(
        pipeline_name="binance_pipeline",
        destination=destination,
        dataset_name=dataset_name,
    )

    # Load the data
    source = binance_historical_data(config, symbols, start_date)

    # Run the pipeline with incremental loading
    # This will write data in chunks instead of all at once
    load_info = pipeline.run(
        source,
        write_disposition="append",
        loader_file_format="parquet"
    )

    # Print statistics
    print("\n" + "=" * 60)
    print("Pipeline completed successfully!")
    print("=" * 60)
    print(f"\nLoad info:\n{load_info}")

    # Print table statistics
    print("\nTable statistics:")
    for table_name in ["trades", "agg_trades", "order_book_snapshots"]:
        try:
            with pipeline.sql_client() as client:
                with client.execute_query(
                    f"SELECT COUNT(*) as count FROM {dataset_name}.{table_name}"
                ) as cursor:
                    count = cursor.fetchone()[0]
                    print(f"  {table_name}: {count:,} records")
        except Exception as e:
            print(f"  {table_name}: Could not retrieve count ({e})")

    return load_info


def main():
    """CLI entry point for historical pipeline."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Download historical Binance tick data"
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
        help="Dataset name (default: binance_historical)",
        default="binance_historical",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        help="Maximum number of records to fetch per symbol (default: unlimited)",
        default=None,
    )

    args = parser.parse_args()

    run_historical_pipeline(
        symbols=args.symbols,
        start_date=args.start_date,
        destination=args.destination,
        dataset_name=args.dataset,
        max_records=args.max_records,
    )


if __name__ == "__main__":
    main()
