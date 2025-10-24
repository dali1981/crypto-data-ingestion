"""Binance REST API source for historical data."""

import dlt
import logging
from typing import Iterator, Optional, List
from datetime import datetime, timedelta, timezone
from binance.client import Client
from binance.exceptions import BinanceAPIException
import time
from ..config import BinanceConfig
from ..utils.rate_limiter import BinanceRateLimiter

logger = logging.getLogger(__name__)

# Global rate limiter shared across all symbols to prevent IP-level rate limiting
_rate_limiter = BinanceRateLimiter()


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
        incremental: dlt.sources.incremental[int] = dlt.sources.incremental("agg_trade_id", initial_value=None),
    ) -> Iterator[dict]:
        """
        Fetch aggregated trades for a single symbol with incremental loading.

        Loops fetching batches of 1000 trades until reaching current_time - 1 hour.
        Uses global rate limiter to prevent IP-level rate limiting.
        """
        # Increase timeout to 60 seconds for large data fetches
        client = Client(
            config.api_key,
            config.api_secret,
            requests_params={'timeout': 60}
        )

        # Calculate cutoff time (current time - 1 hour)
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)
        cutoff_ts_ms = int(cutoff_time.timestamp() * 1000)

        # Use incremental cursor's last value if available, otherwise use start_date
        last_agg_trade_id = incremental.last_value
        is_incremental_run = last_agg_trade_id is not None

        # Determine starting point
        if is_incremental_run:
            from_id = last_agg_trade_id + 1
            logger.info(f"[{symbol}] Resuming from agg_trade_id {from_id}")

            # Check if already up-to-date by fetching one trade
            try:
                _rate_limiter.wait_if_needed(weight=1)
                test_trades = client.get_aggregate_trades(
                    symbol=symbol,
                    limit=1,
                    fromId=from_id
                )

                # Update rate limiter from response (if python-binance exposes headers)
                # Note: python-binance Client doesn't expose headers easily,
                # but rate limiter will still work with token bucket

                if not test_trades or test_trades[0]["T"] > cutoff_ts_ms:
                    logger.info(
                        f"[{symbol}] Already up-to-date "
                        f"(last trade within 1 hour of current time)"
                    )
                    return

            except BinanceAPIException as e:
                if e.status_code == 429:
                    _rate_limiter.handle_429()
                logger.error(f"[{symbol}] Error checking if up-to-date: {e}")
                return
        else:
            start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)
            from_id = None
            logger.info(f"[{symbol}] Starting initial backfill from {start_date}")

        # Loop fetching batches until we reach cutoff time
        batch_count = 0
        total_trades = 0

        try:
            while True:
                # Rate limit before API call
                _rate_limiter.wait_if_needed(weight=1)

                # Fetch batch
                try:
                    if from_id is not None:
                        # Incremental: use fromId
                        trades = client.get_aggregate_trades(
                            symbol=symbol,
                            limit=1000,
                            fromId=from_id
                        )
                    else:
                        # Initial: use startTime
                        trades = client.get_aggregate_trades(
                            symbol=symbol,
                            limit=1000,
                            startTime=start_ts
                        )
                except BinanceAPIException as e:
                    if e.status_code == 429:
                        _rate_limiter.handle_429()
                        continue  # Retry after backoff
                    else:
                        logger.error(f"[{symbol}] API error: {e}")
                        return

                if not trades:
                    logger.info(f"[{symbol}] No more data available from Binance")
                    break

                # Check if we've reached cutoff time
                last_trade_ts = trades[-1]["T"]
                if last_trade_ts > cutoff_ts_ms:
                    # Filter trades to only include those before cutoff
                    trades = [t for t in trades if t["T"] <= cutoff_ts_ms]

                    if not trades:
                        logger.info(
                            f"[{symbol}] Reached cutoff time "
                            f"({cutoff_time.strftime('%Y-%m-%d %H:%M:%S')} UTC)"
                        )
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

                # Update progress tracking
                batch_count += 1
                total_trades += len(transformed_trades)

                # Update from_id for next iteration
                from_id = transformed_trades[-1]["agg_trade_id"] + 1

                # Log progress
                first_trade_time = datetime.fromtimestamp(trades[0]["T"] / 1000, tz=timezone.utc)
                last_trade_time = datetime.fromtimestamp(trades[-1]["T"] / 1000, tz=timezone.utc)

                logger.info(
                    f"[{symbol}] Batch {batch_count}: {first_trade_time.strftime('%Y-%m-%d %H:%M:%S')} "
                    f"to {last_trade_time.strftime('%Y-%m-%d %H:%M:%S')} "
                    f"({len(transformed_trades)} trades, {total_trades} total)"
                )

                # Yield the batch
                yield transformed_trades

                # Check if we've reached cutoff after yielding
                if last_trade_ts > cutoff_ts_ms:
                    logger.info(
                        f"[{symbol}] Completed: {batch_count} batches, "
                        f"{total_trades} trades fetched"
                    )
                    break

        except Exception as e:
            logger.error(f"[{symbol}] Unexpected error: {e}", exc_info=True)
            return

    return _fetch_agg_trades


# Dead code removed: order_book_snapshots()
# This is now handled by the Dagster asset raw_order_books in dagster_pipeline/assets/raw_data.py
