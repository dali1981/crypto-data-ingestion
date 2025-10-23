"""Binance REST API source for historical data."""

import dlt
import logging
from typing import Iterator, Optional, List
from datetime import datetime, timedelta
from binance.client import Client
from binance.exceptions import BinanceAPIException
import time
from ..config import BinanceConfig

logger = logging.getLogger(__name__)


@dlt.source
def binance_historical_data(
    config: BinanceConfig,
    symbols: Optional[List[str]] = None,
    start_date: Optional[str] = None,
):
    """
    DLT source for historical Binance data.

    Creates one resource per symbol for independent extract/normalize/load cycles.
    This allows data to be written as each symbol completes, rather than waiting
    for all symbols to finish.

    Args:
        config: BinanceConfig instance
        symbols: List of symbols to fetch (defaults to config.symbols)
        start_date: Start date in YYYY-MM-DD format (defaults to config.historical_start_date)

    Returns:
        DLT source with multiple resources (one per symbol)
    """
    symbols = symbols or config.symbols
    start_date = start_date or config.historical_start_date

    # Create one resource per symbol so each can extract/normalize/load independently
    resources = []
    for symbol in symbols:
        resources.append(create_agg_trades_resource(config, symbol, start_date))

    return resources


# Dead code removed: historical_trades(), aggregated_trades()
# These multi-symbol functions have been replaced with per-symbol resources
# for independent extract/normalize/load cycles


def create_agg_trades_resource(
    config: BinanceConfig,
    symbol: str,
    start_date: str,
) -> dlt.resource:
    """
    Create a DLT resource for a single symbol's aggregated trades.

    DLT Process (3 stages):
    1. Extract: Generator yields data → buffered in memory → written to temp JSONL
    2. Normalize: JSONL processed → schema inference → load packages created
    3. Load: Load packages written to destination (Parquet files)

    Per-symbol resources ensure each symbol completes all 3 stages independently,
    so data is written to Parquet as each symbol finishes instead of waiting
    for all 20 symbols to complete extraction.

    Args:
        config: BinanceConfig instance with incremental_batch_size limit
        symbol: Trading symbol (e.g., "BTCUSDT")
        start_date: Start date in YYYY-MM-DD format (only used on first run)

    Returns:
        DLT resource configured for this symbol
    """
    @dlt.resource(
        name=f"agg_trades_{symbol.lower()}",
        write_disposition="append",
        primary_key="agg_trade_id",
    )
    def _fetch_agg_trades(
        incremental: dlt.sources.incremental[int] = dlt.sources.incremental("timestamp", initial_value=None),
    ) -> Iterator[dict]:
        """Fetch aggregated trades for a single symbol with incremental loading."""
        # Increase timeout to 60 seconds for large data fetches
        client = Client(
            config.api_key,
            config.api_secret,
            requests_params={'timeout': 60}
        )

        # Use incremental cursor's last value if available, otherwise use start_date
        last_timestamp = incremental.last_value
        is_incremental_run = last_timestamp is not None

        if is_incremental_run:
            start_ts = last_timestamp + 1
            logger.info(f"[{symbol}] Incremental loading from {datetime.fromtimestamp(start_ts / 1000)}")
        else:
            start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)
            logger.info(f"[{symbol}] Initial backfill from {start_date}")

        try:
            from_id = None
            batch_count = 0
            current_day = None  # Track current day for logging

            while True:
                if from_id:
                    trades = client.get_aggregate_trades(
                        symbol=symbol,
                        limit=1000,
                        fromId=from_id
                    )
                else:
                    trades = client.get_aggregate_trades(
                        symbol=symbol,
                        limit=1000,
                        startTime=start_ts
                    )

                if not trades:
                    break

                # Transform to match schema
                transformed_trades = [
                    {
                        "agg_trade_id": trade["a"],
                        "price": trade["p"],
                        "quantity": trade["q"],
                        "first_trade_id": trade["f"],
                        "last_trade_id": trade["l"],
                        "timestamp": trade["T"],
                        "is_buyer_maker": trade["m"],
                        "is_best_match": trade["M"],
                        "symbol": symbol,
                    }
                    for trade in trades
                ]

                # Log when starting a new day of data
                first_trade_day = datetime.fromtimestamp(trades[0]["T"] / 1000).date()
                if current_day != first_trade_day:
                    current_day = first_trade_day
                    logger.info(f"[{symbol}] Downloading {current_day}")

                # Yield in smaller chunks to enable incremental loading
                yield transformed_trades
                batch_count += len(transformed_trades)

                # Check if we've hit the max records limit (for testing)
                if config.historical_max_records and batch_count >= config.historical_max_records:
                    logger.info(f"[{symbol}] Reached max records limit ({config.historical_max_records:,})")
                    break

                # For incremental runs (NOT initial backfill), limit batch size
                # Keeps incremental jobs fast (~5 seconds per symbol)
                if is_incremental_run and batch_count >= config.incremental_batch_size:
                    logger.info(f"[{symbol}] Incremental batch complete ({batch_count:,} trades)")
                    break

                # Get next batch
                from_id = trades[-1]["a"] + 1

                # Rate limiting
                time.sleep(0.1)

                # Stop if we've reached current time
                if trades[-1]["T"] >= int(time.time() * 1000):
                    logger.info(f"[{symbol}] Reached current time ({batch_count:,} total trades)")
                    break

        except BinanceAPIException as e:
            logger.error(f"[{symbol}] Error: {e}")
            return

    return _fetch_agg_trades


# Dead code removed: order_book_snapshots()
# This is now handled by the Dagster asset raw_order_books in dagster_pipeline/assets/raw_data.py
