"""Pipeline for downloading historical Binance tick data.

REFACTORED: This is now a thin wrapper around cli.download.execute_download().
The business logic has been extracted for better testability and reusability.
Now uses Rich for professional CLI output.
"""

from datetime import datetime, date as date_type
from ..cli import DownloadParams, execute_download
from ..cli.display import display_download_info, display_download_result


def run_historical_pipeline(
    symbols=None,
    start_date=None,
    destination="duckdb",
    dataset_name="binance_historical",
    max_records=None,
):
    """
    Run the historical data pipeline.

    NOTE: This function is now a thin wrapper for backward compatibility.
    Consider using cli.download.execute_download() directly for new code.

    Args:
        symbols: List of symbols to fetch (e.g., ["BTCUSDT", "ETHUSDT"])
        start_date: Start date in YYYY-MM-DD format or date object
        destination: Destination type (default: "duckdb")
        dataset_name: Dataset name in the destination (deprecated, uses "binance_historical")
        max_records: Maximum number of records to fetch per symbol (None = unlimited)

    Returns:
        DownloadResult object with success status and metrics
    """
    # Convert parameters to DownloadParams
    if symbols is None:
        from ..config import BinanceConfig
        config = BinanceConfig()
        symbols = config.symbols

    # Parse start_date
    if start_date is None:
        from ..config import BinanceConfig
        config = BinanceConfig()
        start_date = config.historical_start_date

    if isinstance(start_date, str):
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
    elif isinstance(start_date, date_type):
        start_date_obj = start_date
    else:
        raise ValueError(f"Invalid start_date type: {type(start_date)}")

    # Create params
    params = DownloadParams(
        symbols=symbols,
        start_date=start_date_obj,
        end_date=None,  # Will default to today
        max_records=max_records,
        destination=destination,
    )

    # Display info with Rich formatting
    display_download_info(params)

    # Execute download
    result = execute_download(params)

    # Display results with Rich formatting
    display_download_result(result)

    return result


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
