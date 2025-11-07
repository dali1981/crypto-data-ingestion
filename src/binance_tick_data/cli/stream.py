"""Stream business logic - separated from CLI presentation.

This module contains pure business logic for real-time data streaming.
No print statements, no CLI dependencies - only structured inputs and outputs.
"""

import time
import signal
from typing import Optional, Callable
import dlt

from .models import StreamParams, StreamResult
from ..config import BinanceConfig
from ..sources import binance_realtime_data


# Global flag for graceful shutdown
_shutdown_requested = False


def request_shutdown():
    """Request graceful shutdown of streaming operation.

    This is called by signal handlers or when max_batches is reached.
    """
    global _shutdown_requested
    _shutdown_requested = True


def reset_shutdown_flag():
    """Reset shutdown flag (for testing or multiple runs)."""
    global _shutdown_requested
    _shutdown_requested = False


def execute_stream(
    params: StreamParams,
    config_factory: Optional[Callable[[StreamParams], BinanceConfig]] = None,
    pipeline_factory: Optional[Callable[[StreamParams], dlt.Pipeline]] = None,
    setup_signal_handlers: bool = True,
) -> StreamResult:
    """
    Execute real-time data streaming with injectable dependencies.

    This is pure business logic with no CLI concerns:
    - No print() statements
    - No typer/argparse dependencies
    - Returns structured result
    - All I/O is injectable for testing

    Args:
        params: Validated stream parameters (Pydantic model)
        config_factory: Optional factory for creating BinanceConfig (for testing)
        pipeline_factory: Optional factory for creating dlt.Pipeline (for testing)
        setup_signal_handlers: Whether to set up SIGINT handler (disable for testing)

    Returns:
        StreamResult with success status, metrics, and any errors

    Example:
        >>> params = StreamParams(
        ...     symbols=["BTCUSDT"],
        ...     max_batches=10,
        ...     buffer_size=100,
        ... )
        >>> result = execute_stream(params)
        >>> print(f"Streamed {result.records_count} records in {result.batches_processed} batches")
    """
    start_time = time.time()
    pipeline_name = "binance_realtime"
    warnings = []
    batch_count = 0
    total_records = 0

    # Reset shutdown flag
    reset_shutdown_flag()

    # Set up signal handler for graceful shutdown (unless disabled)
    if setup_signal_handlers:
        def signal_handler(sig, frame):
            """Handle Ctrl+C for graceful shutdown."""
            request_shutdown()

        signal.signal(signal.SIGINT, signal_handler)

    try:
        # Create configuration
        if config_factory:
            config = config_factory(params)
        else:
            config = _create_config_from_params(params)

        # Create pipeline
        if pipeline_factory:
            pipeline = pipeline_factory(params)
        else:
            pipeline = _create_pipeline(params)

        # Get output path (database file)
        output_path = _get_output_path(pipeline)

        # Create data source
        source = binance_realtime_data(config, params.symbols)

        # Stream data continuously
        for load_info in pipeline.run(source, loader_file_format="parquet"):
            batch_count += 1

            # Count records in this batch (approximation)
            # In streaming mode, we get batches based on buffer_size
            # For now, use buffer_size as approximate records per batch
            batch_records = params.buffer_size
            total_records += batch_records

            # Check if we should stop
            if _shutdown_requested:
                warnings.append("Shutdown requested - stopping gracefully")
                break

            if params.max_batches and batch_count >= params.max_batches:
                break

        # Calculate duration
        duration = time.time() - start_time

        return StreamResult(
            success=True,
            records_count=total_records,
            batches_processed=batch_count,
            duration_seconds=duration,
            pipeline_name=pipeline_name,
            output_path=output_path,
            warnings=warnings,
        )

    except KeyboardInterrupt:
        # User interrupted - return graceful result
        duration = time.time() - start_time
        warnings.append("Interrupted by user (KeyboardInterrupt)")

        return StreamResult(
            success=True,  # Still success - we processed some data
            records_count=total_records,
            batches_processed=batch_count,
            duration_seconds=duration,
            pipeline_name=pipeline_name,
            output_path="",
            warnings=warnings,
        )

    except Exception as e:
        # Real error - return failure result
        duration = time.time() - start_time
        return StreamResult(
            success=False,
            records_count=total_records,
            batches_processed=batch_count,
            duration_seconds=duration,
            pipeline_name=pipeline_name,
            output_path="",
            error=str(e),
            warnings=warnings,
        )


def _create_config_from_params(params: StreamParams) -> BinanceConfig:
    """Create BinanceConfig from StreamParams.

    This is separated for dependency injection in tests.
    """
    config = BinanceConfig()
    config.symbols = params.symbols
    config.stream_buffer_size = params.buffer_size
    return config


def _create_pipeline(params: StreamParams) -> dlt.Pipeline:
    """Create dlt pipeline.

    This is separated for dependency injection in tests.
    """
    return dlt.pipeline(
        pipeline_name="binance_realtime",
        destination=params.destination,
        dataset_name="binance_realtime",
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
