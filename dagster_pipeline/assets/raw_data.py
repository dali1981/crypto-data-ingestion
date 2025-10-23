"""Raw data acquisition assets using dagster-dlt integration."""

from dagster import AssetExecutionContext, Output, asset
from dagster_dlt import DagsterDltResource, dlt_assets
from datetime import datetime
import dlt
import pandas as pd
from binance_tick_data import BinanceConfig, binance_historical_data
from dagster_pipeline.config import SYMBOLS, HISTORICAL_START_DATE, ORDER_BOOK_DEPTH, DB_PATH


@dlt_assets(
    dlt_source=binance_historical_data(BinanceConfig(
        symbols=SYMBOLS,
        historical_start_date=HISTORICAL_START_DATE,
        historical_max_records=None,
    )),
    dlt_pipeline=dlt.pipeline(
        pipeline_name="binance_raw_data",
        destination=dlt.destinations.filesystem("data/parquet"),  # Write to local Parquet files
        dataset_name="binance_data",
    ),
    name="binance_agg_trades",
    group_name="raw_data",
)
def raw_agg_trades_dlt(context: AssetExecutionContext, dlt: DagsterDltResource):
    """
    Fetch aggregated trades from Binance using dagster-dlt integration.

    Architecture:
    - 20 separate DLT resources (one per symbol) for independent processing
    - Each symbol: Extract → Normalize → Load (Parquet) independently
    - Data written as each symbol completes, not at end of all downloads
    - Parquet-first: no intermediate DuckDB files

    Initial Backfill (first run):
    - Downloads ALL historical data from HISTORICAL_START_DATE to present
    - For 1-3 months of data: ~90-120 minutes total (all 20 symbols)
    - BTCUSDT alone: ~36M records (1.2M trades/day × 90 days)
    - Data appears incrementally as each symbol completes

    Incremental Runs (subsequent runs):
    - Fetches only new data since last run
    - Max 50k trades per symbol per run (~5 seconds/symbol)
    - DLT tracks last timestamp via _dlt_pipeline_state

    Output Structure:
    - data/parquet/binance_data/agg_trades_btcusdt/*.parquet
    - data/parquet/binance_data/agg_trades_ethusdt/*.parquet
    - ... (one table per symbol)
    - data/parquet/binance_data/_dlt_loads/*.parquet (DLT metadata)
    - data/parquet/binance_data/_dlt_pipeline_state/*.parquet (DLT state)
    """
    yield from dlt.run(context=context, loader_file_format="parquet")


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
