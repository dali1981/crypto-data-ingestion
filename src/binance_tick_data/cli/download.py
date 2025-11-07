"""Download business logic - separated from CLI presentation.

This module contains pure business logic for historical data downloads.
No print statements, no CLI dependencies - only structured inputs and outputs.
This enables:
- Unit testing without running CLI
- Reuse in Dagster, Jupyter, API contexts
- Dependency injection for mocking
"""

import time
from typing import Optional, Callable, Dict, Any
from datetime import date
import dlt

from .models import DownloadParams, DownloadResult
from ..config import BinanceConfig
from ..sources import binance_historical_data


def execute_download(
    params: DownloadParams,
    config_factory: Optional[Callable[[DownloadParams], BinanceConfig]] = None,
    pipeline_factory: Optional[Callable[[DownloadParams], dlt.Pipeline]] = None,
) -> DownloadResult:
    """
    Execute historical data download with injectable dependencies.

    This is pure business logic with no CLI concerns:
    - No print() statements
    - No typer/argparse dependencies
    - Returns structured result
    - All I/O is injectable for testing

    Args:
        params: Validated download parameters (Pydantic model)
        config_factory: Optional factory for creating BinanceConfig (for testing)
        pipeline_factory: Optional factory for creating dlt.Pipeline (for testing)

    Returns:
        DownloadResult with success status, metrics, and any errors

    Example:
        >>> params = DownloadParams(
        ...     symbols=["BTCUSDT"],
        ...     start_date=date(2024, 1, 1),
        ...     end_date=date(2024, 1, 31),
        ... )
        >>> result = execute_download(params)
        >>> print(f"Downloaded {result.records_count} records")
    """
    start_time = time.time()
    pipeline_name = "binance_historical"
    warnings = []

    try:
        # Create configuration
        if config_factory:
            config = config_factory(params)
        else:
            config = _create_config_from_params(params)

        # Warn about future dates
        if params.has_future_date:
            warnings.append(
                f"End date {params.end_date} is in the future. "
                "Only data up to current time will be downloaded."
            )

        # Create pipeline
        if pipeline_factory:
            pipeline = pipeline_factory(params)
        else:
            pipeline = _create_pipeline(params)

        # Create data source
        source = binance_historical_data(
            config,
            symbols=params.symbols,
            start_date=params.start_date.strftime("%Y-%m-%d"),
        )

        # Run pipeline
        load_info = pipeline.run(
            source,
            write_disposition="append",
            loader_file_format="parquet"
        )

        # Get output path (database file)
        output_path = _get_output_path(pipeline)

        # Get statistics
        total_records, symbol_counts = _get_table_statistics(
            pipeline,
            params.symbols,
        )

        # Determine which symbols succeeded
        symbols_processed = [s for s, count in symbol_counts.items() if count > 0]
        symbols_failed = [s for s in params.symbols if s not in symbols_processed]

        if symbols_failed:
            warnings.append(
                f"Some symbols had no data: {', '.join(symbols_failed)}"
            )

        # Calculate duration
        duration = time.time() - start_time

        return DownloadResult(
            success=True,
            records_count=total_records,
            symbols_processed=symbols_processed,
            symbols_failed=symbols_failed,
            duration_seconds=duration,
            pipeline_name=pipeline_name,
            output_path=output_path,
            warnings=warnings,
            metadata={
                "load_ids": load_info.loads_ids if hasattr(load_info, 'loads_ids') else [],
                "symbol_counts": symbol_counts,
            }
        )

    except Exception as e:
        # Don't re-raise - return failure result
        # This makes the function more robust for CLI usage
        duration = time.time() - start_time
        return DownloadResult(
            success=False,
            records_count=0,
            symbols_processed=[],
            symbols_failed=params.symbols,
            duration_seconds=duration,
            pipeline_name=pipeline_name,
            output_path="",
            error=str(e),
            warnings=warnings,
        )


def _create_config_from_params(params: DownloadParams) -> BinanceConfig:
    """Create BinanceConfig from DownloadParams.

    This is separated for dependency injection in tests.
    """
    config = BinanceConfig()
    config.symbols = params.symbols
    config.historical_start_date = params.start_date.strftime("%Y-%m-%d")

    if params.max_records:
        config.historical_max_records = params.max_records

    return config


def _create_pipeline(params: DownloadParams) -> dlt.Pipeline:
    """Create dlt pipeline.

    This is separated for dependency injection in tests.
    """
    return dlt.pipeline(
        pipeline_name="binance_historical",
        destination=params.destination,
        dataset_name="binance_historical",
    )


def _get_output_path(pipeline: dlt.Pipeline) -> str:
    """Get output path from pipeline.

    For DuckDB, this is the database file path.
    For other destinations, this might be a connection string.
    """
    try:
        # Try to get credentials from pipeline
        if hasattr(pipeline, 'destination'):
            destination = pipeline.destination
            if hasattr(destination, 'credentials'):
                creds = destination.credentials
                if hasattr(creds, 'database'):
                    return str(creds.database)
                elif hasattr(creds, 'credentials'):
                    return str(creds.credentials)
        return f"{pipeline.destination_type}://{pipeline.dataset_name}"
    except Exception:
        return f"{pipeline.destination_type}://{pipeline.dataset_name}"


def _get_table_statistics(
    pipeline: dlt.Pipeline,
    symbols: list[str],
) -> tuple[int, Dict[str, int]]:
    """Get record counts from pipeline tables.

    Returns:
        tuple: (total_records, {symbol: count})
    """
    total_records = 0
    symbol_counts = {}

    try:
        with pipeline.sql_client() as client:
            # Try to get counts for each symbol table
            # Symbols are stored as separate tables in binance_historical schema
            for symbol in symbols:
                try:
                    # Symbol tables are uppercase (e.g., BTCUSDT)
                    table_name = symbol.upper()
                    query = f"SELECT COUNT(*) FROM binance_historical.{table_name}"

                    with client.execute_query(query) as cursor:
                        count = cursor.fetchone()[0]
                        symbol_counts[symbol] = count
                        total_records += count
                except Exception:
                    # Table doesn't exist or query failed
                    symbol_counts[symbol] = 0

    except Exception:
        # SQL client not available or connection failed
        pass

    return total_records, symbol_counts
