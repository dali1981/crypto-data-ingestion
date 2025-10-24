"""Raw data acquisition assets using DLT with custom partitioning."""

from dagster import AssetExecutionContext, Output, asset, AssetExecutionContext
from datetime import datetime
import dlt
import pandas as pd
from pathlib import Path
from binance_tick_data import BinanceConfig, binance_historical_data
from dagster_pipeline.config import SYMBOLS, HISTORICAL_START_DATE, ORDER_BOOK_DEPTH, DB_PATH
import logging

logger = logging.getLogger(__name__)


class DagsterLogHandler(logging.Handler):
    """Custom logging handler that forwards logs to Dagster context."""

    def __init__(self, dagster_context):
        super().__init__()
        self.dagster_context = dagster_context

    def emit(self, record):
        """Forward log record to Dagster context logger."""
        try:
            msg = self.format(record)
            if record.levelno >= logging.ERROR:
                self.dagster_context.log.error(msg)
            elif record.levelno >= logging.WARNING:
                self.dagster_context.log.warning(msg)
            else:
                self.dagster_context.log.info(msg)
        except Exception:
            self.handleError(record)


@asset(
    name="raw_agg_trades",
    group_name="raw_data",
    compute_kind="binance_api",
    description="Fetch aggregated trades from Binance with date-based partitioning",
)
def raw_agg_trades_dlt(context: AssetExecutionContext) -> Output[dict]:
    """
    Fetch aggregated trades from Binance using DLT with custom date-based partitioning.

    Architecture:
    - DLT fetches data per symbol independently
    - Custom post-processing reorganizes into date-based partitions
    - Output: data/binance_data/agg_trades/{date}/{symbol}.parquet

    Initial Backfill (first run):
    - Downloads ALL historical data from HISTORICAL_START_DATE to present
    - For 1-3 months of data: ~90-120 minutes total (all 20 symbols)
    - BTCUSDT alone: ~36M records (1.2M trades/day × 90 days)
    - Data written incrementally as each symbol completes

    Incremental Runs (subsequent runs):
    - Fetches only new data since last run
    - Max 50k trades per symbol per run (~5 seconds/symbol)
    - DLT tracks last timestamp via state

    Output Structure:
    - data/binance_data/agg_trades/2025-10-22/BTCUSDT.parquet
    - data/binance_data/agg_trades/2025-10-22/ETHUSDT.parquet
    - data/binance_data/agg_trades/2025-10-23/BTCUSDT.parquet
    - ... (daily partitions per symbol)
    """
    # Step 1: Run DLT pipeline in loop until all data fetched
    context.log.info(f"Starting DLT pipeline for {len(SYMBOLS)} symbols...")
    context.log.info(f"Pipeline will run in iterations, fetching 1000 trades per symbol per iteration")

    # Set up logging bridge to forward DLT logs to Dagster
    dlt_logger = logging.getLogger('binance_tick_data')
    dlt_logger.setLevel(logging.INFO)
    dagster_handler = DagsterLogHandler(context)
    dagster_handler.setLevel(logging.INFO)
    dlt_logger.addHandler(dagster_handler)

    # Define paths for staging and output
    staging_path = Path(".dlt_staging/binance_staging")
    output_base = Path("data/binance_data/agg_trades")
    output_base.mkdir(parents=True, exist_ok=True)

    try:
        # Create DLT pipeline with temporary staging destination
        pipeline = dlt.pipeline(
            pipeline_name="binance_raw_data",
            destination=dlt.destinations.filesystem(".dlt_staging"),
            dataset_name="binance_staging",
        )

        # Run pipeline in loop until exhausted
        max_iterations = 100000  # Safety limit
        total_rows_all_iterations = 0

        for iteration in range(1, max_iterations + 1):
            context.log.info(f"--- Iteration {iteration} ---")

            # Create DLT source
            source = binance_historical_data(BinanceConfig(
                symbols=SYMBOLS,
                historical_start_date=HISTORICAL_START_DATE,
                historical_max_records=None,
            ))

            # Run pipeline for this iteration
            load_info = pipeline.run(source, loader_file_format="parquet")

            # Check for failures
            if load_info.has_failed_jobs:
                context.log.error(f"Iteration {iteration} had failed jobs")
                raise Exception(f"Pipeline iteration {iteration} failed")

            # Count rows loaded in this iteration
            # Check if any data was loaded by reading staging parquet files
            iteration_rows = 0
            for symbol in SYMBOLS:
                symbol_table = f"agg_trades_{symbol.lower()}"
                symbol_data_path = staging_path / symbol_table
                if symbol_data_path.exists():
                    parquet_files = list(symbol_data_path.glob("*.parquet"))
                    if parquet_files:
                        # Read latest parquet file to count rows
                        try:
                            import pyarrow.parquet as pq
                            for pf in parquet_files:
                                table = pq.read_table(pf)
                                iteration_rows += len(table)
                        except Exception as e:
                            context.log.warning(f"Failed to count rows for {symbol}: {e}")

            total_rows_all_iterations += iteration_rows

            context.log.info(f"Iteration {iteration}: loaded {iteration_rows:,} rows (total: {total_rows_all_iterations:,})")

            # Immediately reorganize data from this iteration
            if iteration_rows > 0:
                _reorganize_latest_batch(context, staging_path, output_base, iteration)

            # If no rows loaded, all symbols exhausted
            if iteration_rows == 0:
                context.log.info(f"All symbols exhausted after {iteration} iterations")
                break

            # Safety check
            if iteration == max_iterations:
                context.log.warning(f"Reached max iterations limit ({max_iterations})")
                break

        context.log.info(f"DLT pipeline completed: {iteration} iterations, {total_rows_all_iterations:,} total rows")

    except Exception as e:
        context.log.error(f"DLT pipeline failed: {e}")
        raise
    finally:
        # Clean up handler
        dlt_logger.removeHandler(dagster_handler)

    # Create DuckDB view over incrementally written data
    context.log.info("Creating DuckDB view...")
    _create_duckdb_view(context, output_base)

    # Count total files created
    files_created = sum(1 for _ in output_base.rglob("*.parquet"))

    return Output(
        value={
            "total_rows": total_rows_all_iterations,
            "files_created": files_created,
            "symbols_processed": len(SYMBOLS),
            "output_path": str(output_base),
        },
        metadata={
            "total_rows": total_rows_all_iterations,
            "files_created": files_created,
            "symbols_processed": len(SYMBOLS),
            "timestamp": datetime.now().isoformat(),
        }
    )


def _reorganize_latest_batch(
    context: AssetExecutionContext,
    staging_path: Path,
    output_base: Path,
    iteration: int
):
    """
    Reorganize latest DLT batch into date-based partitions immediately.

    This runs after each DLT iteration to write data incrementally.
    """
    for symbol in SYMBOLS:
        symbol_table = f"agg_trades_{symbol.lower()}"
        symbol_data_path = staging_path / symbol_table

        if not symbol_data_path.exists():
            continue

        # Read parquet files for this symbol
        parquet_files = list(symbol_data_path.glob("*.parquet"))
        if not parquet_files:
            continue

        try:
            # Read all data for this symbol from staging
            df = pd.read_parquet(symbol_data_path)

            if df.empty:
                continue

            # Add date column from timestamp
            df['date'] = pd.to_datetime(df['timestamp'], unit='ms').dt.date

            # Group by date and write to separate directories
            for date, date_df in df.groupby('date'):
                date_str = str(date)
                date_dir = output_base / date_str / symbol
                date_dir.mkdir(parents=True, exist_ok=True)

                # Write batch file
                output_file = date_dir / f"batch_{iteration:06d}.parquet"
                date_df.to_parquet(output_file, engine='pyarrow', compression='zstd', index=False)

                context.log.info(f"  {date_str}/{symbol}/batch_{iteration:06d}.parquet: {len(date_df):,} rows")

        except Exception as e:
            context.log.warning(f"Failed to reorganize {symbol}: {e}")


def _create_duckdb_view(context: AssetExecutionContext, parquet_path: Path):
    """Create DuckDB view over date-partitioned parquet files."""
    try:
        import duckdb

        conn = duckdb.connect(DB_PATH)

        # Create schema if needed
        conn.execute("CREATE SCHEMA IF NOT EXISTS binance_data;")

        # Create view over all parquet files in date/symbol structure
        # Use glob pattern to match: date/symbol/*.parquet
        view_query = f"""
            CREATE OR REPLACE VIEW binance_data.agg_trades AS
            SELECT * FROM read_parquet('{parquet_path}/*/*/*.parquet', hive_partitioning=false)
        """
        conn.execute(view_query)

        context.log.info(f"Created DuckDB view: binance_data.agg_trades")

        conn.close()

    except Exception as e:
        context.log.warning(f"Failed to create DuckDB view: {e}")


@asset(
    group_name="raw_data",
    compute_kind="binance_api",
    description="Fetch current order book snapshots for all symbols",
    required_resource_keys={"binance_api"}
)
def raw_order_books(
    context: AssetExecutionContext
) -> Output[pd.DataFrame]:
    """
    Fetch current order book snapshots for all symbols.

    This is a point-in-time snapshot, not historical data.
    Useful for current market state analysis.

    Returns:
        DataFrame with order book snapshots
    """
    import time
    import json

    binance_resource = context.resources.binance_api
    client = binance_resource.get_client()

    snapshots = []
    stats = {}

    for symbol in SYMBOLS:
        try:
            context.log.info(f"Fetching order book for {symbol}...")

            # Get order book
            depth_data = client.get_order_book(symbol=symbol, limit=ORDER_BOOK_DEPTH)

            snapshot = {
                "symbol": symbol,
                "timestamp": int(time.time() * 1000),
                "last_update_id": depth_data["lastUpdateId"],
                "bids_json": json.dumps(depth_data["bids"][:ORDER_BOOK_DEPTH]),
                "asks_json": json.dumps(depth_data["asks"][:ORDER_BOOK_DEPTH]),
                "bid_levels": len(depth_data["bids"][:ORDER_BOOK_DEPTH]),
                "ask_levels": len(depth_data["asks"][:ORDER_BOOK_DEPTH]),
            }

            snapshots.append(snapshot)

            stats[symbol] = {
                "success": True,
                "bid_levels": snapshot["bid_levels"],
                "ask_levels": snapshot["ask_levels"],
                "timestamp": snapshot["timestamp"]
            }

            context.log.info(f"  ✅ {snapshot['bid_levels']} bids, {snapshot['ask_levels']} asks")

            # Rate limiting
            time.sleep(0.1)

        except Exception as e:
            context.log.error(f"  ❌ Failed to fetch {symbol}: {e}")
            stats[symbol] = {
                "success": False,
                "error": str(e)
            }

    # Convert to DataFrame
    if snapshots:
        df = pd.DataFrame(snapshots)
        context.log.info(f"✅ Fetched {len(snapshots)} order book snapshots")
    else:
        df = pd.DataFrame()

    successful = len([s for s, st in stats.items() if st.get("success", False)])

    return Output(
        value=df,
        metadata={
            "symbols_successful": successful,
            "symbols_failed": len(SYMBOLS) - successful,
            "total_snapshots": len(snapshots),
            "snapshot_time": datetime.now().isoformat(),
        }
    )
