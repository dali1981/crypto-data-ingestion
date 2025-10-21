"""Raw data acquisition assets."""

from dagster import asset, Output, AssetExecutionContext, MetadataValue
from datetime import datetime, timedelta
import dlt
from binance_tick_data import BinanceConfig, binance_historical_data
from ..config import SYMBOLS, HISTORICAL_START_DATE, ORDER_BOOK_DEPTH


@asset(
    group_name="raw_data",
    compute_kind="binance_api",
    description="Fetch and append latest aggregated trades from Binance REST API for all symbols"
)
def raw_agg_trades(
    context: AssetExecutionContext,
    binance_api,
    duckdb_conn
) -> Output[dict]:
    """
    Fetch latest aggregated trades and append to database.

    Strategy:
    - For each symbol, fetch from last_timestamp to now
    - Append mode (allows duplicates temporarily)
    - Deduplication happens in separate asset

    Returns:
        Dict with fetch statistics per symbol
    """
    conn = duckdb_conn.get_connection()
    stats = {}
    total_records = 0

    for symbol in SYMBOLS:
        context.log.info(f"Processing {symbol}...")

        # Get last timestamp for this symbol
        try:
            result = conn.execute(f"""
                SELECT MAX(timestamp) as last_ts
                FROM binance_data.agg_trades
                WHERE symbol = '{symbol}'
            """).fetchone()

            last_timestamp = result[0] if result and result[0] else None

            if last_timestamp:
                start_date = datetime.fromtimestamp(last_timestamp / 1000)
                context.log.info(f"  Last data: {start_date}")
            else:
                # No data for this symbol - start from configured date
                start_date = datetime.strptime(HISTORICAL_START_DATE, "%Y-%m-%d")
                context.log.info(f"  No existing data - starting from {start_date}")

        except Exception as e:
            # Table doesn't exist yet
            start_date = datetime.strptime(HISTORICAL_START_DATE, "%Y-%m-%d")
            context.log.info(f"  New database - starting from {start_date}")

        end_date = datetime.now()
        hours_to_fetch = (end_date - start_date).total_seconds() / 3600

        if hours_to_fetch < 0.1:  # Less than 6 minutes
            context.log.info(f"  Data is fresh - skipping {symbol}")
            stats[symbol] = {"records_fetched": 0, "skipped": True}
            continue

        context.log.info(f"  Fetching {hours_to_fetch:.1f} hours of data")

        # Configure and fetch
        config = BinanceConfig()
        config.symbols = [symbol]
        config.historical_start_date = start_date.strftime('%Y-%m-%d')
        config.historical_max_records = None  # Get all available

        # Create pipeline
        pipeline = dlt.pipeline(
            pipeline_name="binance_raw_data",
            destination="duckdb",
            dataset_name="binance_data",
        )

        try:
            # Fetch data (append mode)
            source = binance_historical_data(config)
            load_info = pipeline.run(
                source,
                write_disposition="append"
            )

            # Extract metrics
            records_fetched = 0
            if load_info.load_packages:
                for package in load_info.load_packages:
                    for job in package.jobs:
                        records_fetched += job.metrics.get("rows", 0)

            context.log.info(f"  ✅ Fetched {records_fetched:,} records for {symbol}")

            stats[symbol] = {
                "records_fetched": records_fetched,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "hours_fetched": round(hours_to_fetch, 2),
                "skipped": False
            }

            total_records += records_fetched

        except Exception as e:
            context.log.error(f"  ❌ Failed to fetch {symbol}: {e}")
            stats[symbol] = {
                "records_fetched": 0,
                "error": str(e),
                "skipped": False
            }

    conn.close()

    context.log.info(f"\n{'='*80}")
    context.log.info(f"FETCH COMPLETE: {total_records:,} total records across {len(SYMBOLS)} symbols")
    context.log.info(f"{'='*80}")

    return Output(
        value=stats,
        metadata={
            "total_records": total_records,
            "symbols_processed": len(SYMBOLS),
            "symbols_updated": len([s for s, st in stats.items() if st.get("records_fetched", 0) > 0]),
            "fetch_time": datetime.now().isoformat(),
        }
    )


@asset(
    group_name="raw_data",
    compute_kind="binance_api",
    description="Fetch current order book snapshots for all symbols"
)
def raw_order_books(
    context: AssetExecutionContext,
    binance_api,
    duckdb_conn
) -> Output[dict]:
    """
    Fetch current order book snapshots for all symbols.

    This is a point-in-time snapshot, not historical data.
    Useful for current market state analysis.

    Returns:
        Dict with snapshot statistics per symbol
    """
    import time

    client = binance_api.get_client()
    conn = duckdb_conn.get_connection()

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
                "bids": depth_data["bids"][:ORDER_BOOK_DEPTH],
                "asks": depth_data["asks"][:ORDER_BOOK_DEPTH],
            }

            snapshots.append(snapshot)

            stats[symbol] = {
                "success": True,
                "bid_levels": len(snapshot["bids"]),
                "ask_levels": len(snapshot["asks"]),
                "timestamp": snapshot["timestamp"]
            }

            context.log.info(f"  ✅ {len(snapshot['bids'])} bids, {len(snapshot['asks'])} asks")

            # Rate limiting
            time.sleep(0.1)

        except Exception as e:
            context.log.error(f"  ❌ Failed to fetch {symbol}: {e}")
            stats[symbol] = {
                "success": False,
                "error": str(e)
            }

    # Store snapshots in database
    if snapshots:
        try:
            # Use dlt to load snapshots
            pipeline = dlt.pipeline(
                pipeline_name="binance_order_books",
                destination="duckdb",
                dataset_name="binance_data",
            )

            import dlt

            @dlt.resource(name="order_book_snapshots", write_disposition="append")
            def order_book_data():
                yield snapshots

            load_info = pipeline.run(order_book_data())
            context.log.info(f"✅ Stored {len(snapshots)} order book snapshots")

        except Exception as e:
            context.log.error(f"❌ Failed to store snapshots: {e}")

    conn.close()

    successful = len([s for s, st in stats.items() if st.get("success", False)])

    return Output(
        value=stats,
        metadata={
            "symbols_successful": successful,
            "symbols_failed": len(SYMBOLS) - successful,
            "total_snapshots": len(snapshots),
            "snapshot_time": datetime.now().isoformat(),
        }
    )
