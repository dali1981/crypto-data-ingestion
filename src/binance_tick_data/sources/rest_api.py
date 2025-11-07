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
        name=f"agg_trades_{symbol.lower()}",  # Resource name (internal)
        table_name=symbol.upper(),             # Table name = symbol
        write_disposition="append",
        primary_key="agg_trade_id",
        columns={"date": {"partition": True}},  # Partition by trade date
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
                transformed_trades = []
                for trade in trades:
                    # Extract date for partitioning
                    dt = datetime.fromtimestamp(trade["T"] / 1000, tz=timezone.utc)

                    transformed_trades.append({
                        "agg_trade_id": trade["a"],
                        "price": trade["p"],
                        "quantity": trade["q"],
                        "first_trade_id": trade["f"],
                        "last_trade_id": trade["l"],
                        "timestamp": trade["T"],
                        "is_buyer_maker": trade["m"],
                        "is_best_match": trade["M"],
                        "symbol": symbol,
                        "date": dt.date().isoformat(),  # Add date for partitioning
                    })

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


# Interval name mapping for user-friendly names
INTERVAL_MAP = {
    "1s": "1SECOND",
    "1m": "1MINUTE",
    "3m": "3MINUTE",
    "5m": "5MINUTE",
    "15m": "15MINUTE",
    "30m": "30MINUTE",
    "1h": "1HOUR",
    "2h": "2HOUR",
    "4h": "4HOUR",
    "6h": "6HOUR",
    "8h": "8HOUR",
    "12h": "12HOUR",
    "1d": "1DAY",
    "3d": "3DAY",
    "1w": "1WEEK",
    "1M": "1MONTH",
}


def _parse_interval_to_timedelta(interval_str: str) -> timedelta:
    """Parse interval string to timedelta for incremental step calculation."""
    unit = interval_str[-1]
    value = int(interval_str[:-1]) if len(interval_str) > 1 else 1

    if unit == 's':
        return timedelta(seconds=value)
    elif unit == 'm':
        return timedelta(minutes=value)
    elif unit == 'h':
        return timedelta(hours=value)
    elif unit == 'd':
        return timedelta(days=value)
    elif unit == 'w':
        return timedelta(weeks=value)
    elif unit == 'M':
        return timedelta(days=value * 30)  # Approximate
    else:
        raise ValueError(f"Unknown interval unit: {unit}")


def _get_cutoff_time(interval_str: str) -> datetime:
    """Calculate cutoff time based on interval to avoid incomplete candles."""
    now = datetime.now(timezone.utc)

    # For intraday intervals (< 1 day), use 1 hour buffer
    # For daily+ intervals, use 1 day buffer
    if interval_str in ["1s", "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h"]:
        return now - timedelta(hours=1)
    else:
        return (now - timedelta(days=1)).replace(hour=23, minute=59, second=59)


def _create_candles_resource_internal(
    config: BinanceConfig,
    symbol: str,
    start_date: str,
    interval_str: str,  # User-friendly format (1m, 5m, 1h, 1d, etc.)
    table_suffix: str,  # Table name suffix (e.g., "5m", "1h", "DAILY")
) -> dlt.resource:
    """
    Internal helper to create a DLT resource for candlestick data with any interval.

    This function contains all the common logic for fetching candles, avoiding code duplication
    between daily and intraday implementations.

    Args:
        config: BinanceConfig instance
        symbol: Trading symbol (e.g., "BTCUSDT")
        start_date: Start date in YYYY-MM-DD format
        interval_str: Interval in user-friendly format (1m, 5m, 1h, 1d, etc.)
        table_suffix: Suffix for table name (e.g., "5m" -> "BTCUSDT_5m")

    Returns:
        DLT resource for the specified interval
    """
    # Map user-friendly interval to Binance constant name
    if interval_str not in INTERVAL_MAP:
        raise ValueError(
            f"Invalid interval: {interval_str}. "
            f"Valid intervals: {', '.join(INTERVAL_MAP.keys())}"
        )

    # Get Binance Client constant (e.g., "1MINUTE")
    binance_interval_name = INTERVAL_MAP[interval_str]

    @dlt.resource(
        name=f"{table_suffix.lower()}_candles_{symbol.lower()}",
        table_name=f"{symbol.upper()}_{table_suffix}",
        write_disposition="merge",
        primary_key=["symbol", "open_time"],
    )
    def _fetch_candles(
        incremental: dlt.sources.incremental[int] = dlt.sources.incremental(
            "open_time",
            initial_value=None
        )
    ) -> Iterator[dict]:
        """Fetch candles with incremental loading."""

        client = Client(
            config.api_key,
            config.api_secret,
            requests_params={'timeout': 60}
        )

        # Calculate cutoff time based on interval
        cutoff_time = _get_cutoff_time(interval_str)
        cutoff_ts_ms = int(cutoff_time.timestamp() * 1000)

        last_open_time = incremental.last_value

        if last_open_time:
            # Incremental: start from next interval after last candle
            start_dt = datetime.fromtimestamp(last_open_time / 1000, tz=timezone.utc)
            interval_delta = _parse_interval_to_timedelta(interval_str)
            start_dt = start_dt + interval_delta
            logger.info(f"[{symbol}] Resuming {interval_str} candles from {start_dt}")
        else:
            # Initial: use config start_date
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            start_dt = start_dt.replace(tzinfo=timezone.utc)
            logger.info(f"[{symbol}] Starting initial {interval_str} candle fetch from {start_date}")

        # Don't fetch if already up-to-date
        if start_dt.timestamp() * 1000 > cutoff_ts_ms:
            logger.info(f"[{symbol}] Already up-to-date (no new complete {interval_str} candles)")
            return

        # Get the Binance interval constant from Client class
        interval_attr = f"KLINE_INTERVAL_{binance_interval_name}"
        binance_interval = getattr(Client, interval_attr)

        # Loop fetching batches until we reach cutoff time
        batch_count = 0
        total_candles = 0
        current_start_ts = int(start_dt.timestamp() * 1000)

        try:
            while True:
                # Rate limit before API call
                _rate_limiter.wait_if_needed(weight=2)  # Klines endpoint weight = 2

                # Fetch batch
                try:
                    candles = client.get_historical_klines(
                        symbol=symbol,
                        interval=binance_interval,
                        start_str=current_start_ts,
                        end_str=cutoff_ts_ms,
                        limit=1000
                    )
                except BinanceAPIException as e:
                    if e.status_code == 429:
                        _rate_limiter.handle_429()
                        continue  # Retry after backoff
                    else:
                        logger.error(f"[{symbol}] API error: {e}")
                        return

                if not candles:
                    logger.info(f"[{symbol}] No more data available from Binance")
                    break

                # Check if we've reached cutoff time
                last_candle_close_ts = candles[-1][6]  # close_time
                if last_candle_close_ts > cutoff_ts_ms:
                    # Filter candles to only include those before cutoff
                    candles = [c for c in candles if c[6] <= cutoff_ts_ms]

                    if not candles:
                        logger.info(
                            f"[{symbol}] Reached cutoff time "
                            f"({cutoff_time.strftime('%Y-%m-%d %H:%M:%S')} UTC)"
                        )
                        break

                # Transform to schema
                transformed_candles = []
                for candle in candles:
                    open_dt = datetime.fromtimestamp(candle[0] / 1000, tz=timezone.utc)

                    transformed_candles.append({
                        "symbol": symbol,
                        "open_time": candle[0],
                        "open": candle[1],
                        "high": candle[2],
                        "low": candle[3],
                        "close": candle[4],
                        "volume": candle[5],
                        "close_time": candle[6],
                        "quote_volume": candle[7],
                        "trades": candle[8],
                        "taker_buy_base": candle[9],
                        "taker_buy_quote": candle[10],
                        "date": open_dt.date().isoformat(),
                    })

                # Update progress tracking
                batch_count += 1
                total_candles += len(transformed_candles)

                # Update start time for next iteration (start from next ms after last close_time)
                current_start_ts = candles[-1][6] + 1

                # Log progress
                first_candle_time = datetime.fromtimestamp(candles[0][0] / 1000, tz=timezone.utc)
                last_candle_time = datetime.fromtimestamp(candles[-1][0] / 1000, tz=timezone.utc)

                logger.info(
                    f"[{symbol}] Batch {batch_count}: {first_candle_time.strftime('%Y-%m-%d %H:%M:%S')} "
                    f"to {last_candle_time.strftime('%Y-%m-%d %H:%M:%S')} "
                    f"({len(transformed_candles)} candles, {total_candles} total)"
                )

                # Yield the batch
                yield transformed_candles

                # Check if we've reached cutoff after yielding
                if last_candle_close_ts > cutoff_ts_ms:
                    logger.info(
                        f"[{symbol}] Completed: {batch_count} batches, "
                        f"{total_candles} candles fetched"
                    )
                    break

        except Exception as e:
            logger.error(f"[{symbol}] Unexpected error: {e}", exc_info=True)
            return

    return _fetch_candles


def create_daily_candles_resource(
    config: BinanceConfig,
    symbol: str,
    start_date: str,
) -> dlt.resource:
    """
    Create a DLT resource for daily candlestick data.

    Uses MERGE write disposition because:
    - Today's incomplete candle updates throughout the day
    - Re-running historical data won't create duplicates
    - Small dataset (~365 rows/year) - merge overhead negligible

    Args:
        config: BinanceConfig instance
        symbol: Trading symbol (e.g., "BTCUSDT")
        start_date: Start date in YYYY-MM-DD format

    Returns:
        DLT resource for daily candles
    """
    return _create_candles_resource_internal(
        config=config,
        symbol=symbol,
        start_date=start_date,
        interval_str="1d",
        table_suffix="DAILY"
    )


@dlt.source
def binance_daily_candles(
    config: BinanceConfig,
    symbols: Optional[List[str]] = None,
    start_date: Optional[str] = None,
):
    """
    DLT source for daily candlestick data.

    Completely separate from agg trades - can run independently.
    Uses merge write disposition for idempotent loads.

    Args:
        config: BinanceConfig instance
        symbols: List of symbols to fetch (defaults to config.symbols)
        start_date: Start date in YYYY-MM-DD format (defaults to config.historical_start_date)

    Returns:
        DLT source with daily candle resources (one per symbol)
    """
    symbols = symbols or config.symbols
    start_date = start_date or config.historical_start_date

    # Create one resource per symbol for independent processing
    resources = []
    for symbol in symbols:
        resources.append(create_daily_candles_resource(config, symbol, start_date))

    return resources


def create_intraday_candles_resource(
    config: BinanceConfig,
    symbol: str,
    start_date: str,
    interval: str,
) -> dlt.resource:
    """
    Create a DLT resource for intraday candlestick data.

    Supports any Binance interval: 1m, 5m, 15m, 30m, 1h, 4h, etc.
    Uses MERGE write disposition for idempotent loads and handling incomplete candles.

    Args:
        config: BinanceConfig instance
        symbol: Trading symbol (e.g., "BTCUSDT")
        start_date: Start date in YYYY-MM-DD format
        interval: Interval string (1m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h)

    Returns:
        DLT resource for the specified interval

    Examples:
        >>> # 5-minute candles for BTCUSDT
        >>> resource = create_intraday_candles_resource(
        ...     config, "BTCUSDT", "2024-01-01", "5m"
        ... )
        >>> # 1-hour candles for ETHUSDT
        >>> resource = create_intraday_candles_resource(
        ...     config, "ETHUSDT", "2024-01-01", "1h"
        ... )
    """
    return _create_candles_resource_internal(
        config=config,
        symbol=symbol,
        start_date=start_date,
        interval_str=interval,
        table_suffix=interval
    )


@dlt.source
def binance_intraday_candles(
    config: BinanceConfig,
    interval: str,
    symbols: Optional[List[str]] = None,
    start_date: Optional[str] = None,
):
    """
    DLT source for intraday candlestick data.

    Fetches OHLCV candles at specified interval (1m, 5m, 15m, 30m, 1h, etc.).
    Uses merge write disposition for idempotent loads.

    Args:
        config: BinanceConfig instance
        interval: Interval string (1m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h)
        symbols: List of symbols to fetch (defaults to config.symbols)
        start_date: Start date in YYYY-MM-DD format (defaults to config.historical_start_date)

    Returns:
        DLT source with intraday candle resources (one per symbol)

    Examples:
        >>> # Fetch 5-minute candles for all configured symbols
        >>> config = BinanceConfig()
        >>> source = binance_intraday_candles(config, interval="5m")
        >>>
        >>> # Fetch 1-minute candles for specific symbols
        >>> source = binance_intraday_candles(
        ...     config, interval="1m", symbols=["BTCUSDT", "ETHUSDT"]
        ... )
        >>>
        >>> # Run pipeline
        >>> pipeline = dlt.pipeline(
        ...     pipeline_name="binance_intraday",
        ...     destination="filesystem",
        ...     dataset_name="binance_5m"
        ... )
        >>> pipeline.run(source, loader_file_format="parquet")
    """
    symbols = symbols or config.symbols
    start_date = start_date or config.historical_start_date

    # Validate interval
    if interval not in INTERVAL_MAP:
        raise ValueError(
            f"Invalid interval: {interval}. "
            f"Valid intervals: {', '.join(INTERVAL_MAP.keys())}"
        )

    # Create one resource per symbol for independent processing
    resources = []
    for symbol in symbols:
        resources.append(
            create_intraday_candles_resource(config, symbol, start_date, interval)
        )

    return resources
