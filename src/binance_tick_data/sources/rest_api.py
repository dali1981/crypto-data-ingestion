"""Binance REST API source for historical data - refactored with OOP architecture."""

import dlt
import logging
from typing import Iterator, Optional, List, Dict
from datetime import datetime, timedelta, timezone
from binance.client import Client
from ..config import BinanceConfig
from ..utils.rate_limiter import BinanceRateLimiter
from .binance.client import BinanceAPIClient
from .binance.transformers import BinanceAggTradeTransformer, BinanceCandleTransformer
from .binance.constants import API_WEIGHTS, INTERVAL_MAP, BATCH_SIZE
from .core.batch_fetcher import IncrementalBatchFetcher

logger = logging.getLogger(__name__)

# Global rate limiter shared across all symbols to prevent IP-level rate limiting
_rate_limiter = BinanceRateLimiter()


class BinanceDLTResourceFactory:
    """Factory for creating DLT resources with Binance data using OOP architecture."""

    def __init__(self, config: BinanceConfig, rate_limiter: BinanceRateLimiter):
        """
        Initialize factory with config and rate limiter.

        Args:
            config: BinanceConfig instance
            rate_limiter: Shared rate limiter instance
        """
        self.config = config
        self.rate_limiter = rate_limiter

    def create_agg_trades_resource(self, symbol: str, start_date: str) -> dlt.resource:
        """
        Create DLT resource for aggregated trades using OOP architecture.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            start_date: Start date in YYYY-MM-DD format (only used on first run)

        Returns:
            DLT resource configured for this symbol
        """
        @dlt.resource(
            name=f"agg_trades_{symbol.lower()}",
            table_name=symbol.upper(),
            write_disposition="append",
            primary_key="agg_trade_id",
            columns={"date": {"partition": True}},
        )
        def _fetch_agg_trades(
            incremental: dlt.sources.incremental[int] = dlt.sources.incremental(
                "agg_trade_id", initial_value=None
            ),
        ) -> Iterator[List[Dict]]:
            """Fetch aggregated trades with incremental loading."""

            # Create collaborators (dependency injection)
            client = BinanceAPIClient(self.config.api_key, self.config.api_secret)
            transformer = BinanceAggTradeTransformer(symbol)

            # Calculate cutoff time (current time - 1 hour)
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)
            cutoff_ts_ms = int(cutoff_time.timestamp() * 1000)

            # Determine starting point
            last_agg_trade_id = incremental.last_value
            is_incremental_run = last_agg_trade_id is not None

            if is_incremental_run:
                from_id = last_agg_trade_id + 1
                start_ts = None
                logger.info(f"[{symbol}] Resuming from agg_trade_id {from_id}")

                # Check if already up-to-date
                try:
                    self.rate_limiter.wait_if_needed(weight=1)
                    test_trades = client.fetch_agg_trades(
                        symbol=symbol, from_id=from_id, limit=1
                    )
                    if not test_trades or test_trades[0]["T"] > cutoff_ts_ms:
                        logger.info(
                            f"[{symbol}] Already up-to-date "
                            f"(last trade within 1 hour of current time)"
                        )
                        return
                except Exception as e:
                    logger.error(f"[{symbol}] Error checking if up-to-date: {e}")
                    return
            else:
                from_id = None
                start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)
                logger.info(f"[{symbol}] Starting initial backfill from {start_date}")

            # Create batch fetcher with all dependencies
            fetcher = IncrementalBatchFetcher(
                client=client,
                transformer=transformer,
                rate_limiter=self.rate_limiter,
                api_weight=API_WEIGHTS["agg_trades"],
                batch_size=BATCH_SIZE,
                logger=logger
            )

            # Fetch data using generic batch fetcher
            # Note: We need to adapt the fetch function signature
            def fetch_func(cursor, limit, **kwargs):
                if cursor is not None:
                    return client.fetch_agg_trades(
                        symbol=symbol,
                        from_id=cursor,
                        limit=limit
                    )
                else:
                    return client.fetch_agg_trades(
                        symbol=symbol,
                        start_time=start_ts,
                        limit=limit
                    )

            yield from fetcher.fetch_until_cutoff(
                fetch_func=fetch_func,
                start_cursor=from_id,
                cutoff_time=cutoff_time
            )

        return _fetch_agg_trades

    def create_candles_resource(
        self,
        symbol: str,
        start_date: str,
        interval_str: str,
        table_suffix: str
    ) -> dlt.resource:
        """
        Create DLT resource for candlestick data using OOP architecture.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            start_date: Start date in YYYY-MM-DD format
            interval_str: Interval in user-friendly format (1m, 5m, 1h, 1d, etc.)
            table_suffix: Suffix for table name (e.g., "5m", "DAILY")

        Returns:
            DLT resource for the specified interval
        """
        # Validate interval
        if interval_str not in INTERVAL_MAP:
            raise ValueError(
                f"Invalid interval: {interval_str}. "
                f"Valid intervals: {', '.join(INTERVAL_MAP.keys())}"
            )

        # Get Binance interval constant
        binance_interval_name = INTERVAL_MAP[interval_str]
        interval_attr = f"KLINE_INTERVAL_{binance_interval_name}"
        binance_interval = getattr(Client, interval_attr)

        @dlt.resource(
            name=f"{table_suffix.lower()}_candles_{symbol.lower()}",
            table_name=f"{symbol.upper()}_{table_suffix}",
            write_disposition="merge",
            primary_key=["symbol", "open_time"],
        )
        def _fetch_candles(
            incremental: dlt.sources.incremental[int] = dlt.sources.incremental(
                "open_time", initial_value=None
            )
        ) -> Iterator[List[Dict]]:
            """Fetch candles with incremental loading."""

            # Create collaborators
            client = BinanceAPIClient(self.config.api_key, self.config.api_secret)
            transformer = BinanceCandleTransformer(symbol)

            # Calculate cutoff time based on interval
            cutoff_time = self._get_cutoff_time(interval_str)
            cutoff_ts_ms = int(cutoff_time.timestamp() * 1000)

            last_open_time = incremental.last_value

            if last_open_time:
                # Incremental: start from next interval after last candle
                start_dt = datetime.fromtimestamp(last_open_time / 1000, tz=timezone.utc)
                interval_delta = self._parse_interval_to_timedelta(interval_str)
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

            # Create batch fetcher
            fetcher = IncrementalBatchFetcher(
                client=client,
                transformer=transformer,
                rate_limiter=self.rate_limiter,
                api_weight=API_WEIGHTS["klines"],
                batch_size=BATCH_SIZE,
                logger=logger
            )

            # Fetch data using generic batch fetcher
            current_start_ts = int(start_dt.timestamp() * 1000)

            def fetch_func(cursor, limit, **kwargs):
                # For candles, we use time-based pagination
                return client.fetch_candles(
                    symbol=symbol,
                    interval=binance_interval,
                    start_time=cursor,
                    end_time=cutoff_ts_ms,
                    limit=limit
                )

            # Note: For candles, we need to handle cursor differently
            # The cursor is the timestamp, not an incremental ID
            for batch in fetcher.fetch_until_cutoff(
                fetch_func=fetch_func,
                start_cursor=current_start_ts,
                cutoff_time=cutoff_time
            ):
                yield batch

        return _fetch_candles

    @staticmethod
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

    @staticmethod
    def _get_cutoff_time(interval_str: str) -> datetime:
        """Calculate cutoff time based on interval to avoid incomplete candles."""
        now = datetime.now(timezone.utc)

        # For intraday intervals (< 1 day), use 1 hour buffer
        # For daily+ intervals, use 1 day buffer
        if interval_str in ["1s", "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h"]:
            return now - timedelta(hours=1)
        else:
            return (now - timedelta(days=1)).replace(hour=23, minute=59, second=59)


# ============================================================================
# Public DLT Source Functions (Backward Compatible API)
# ============================================================================

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

    factory = BinanceDLTResourceFactory(config, _rate_limiter)

    return [
        factory.create_agg_trades_resource(symbol, start_date)
        for symbol in symbols
    ]


def create_agg_trades_resource(
    config: BinanceConfig,
    symbol: str,
    start_date: str,
) -> dlt.resource:
    """
    Create a DLT resource for a single symbol's aggregated trades.

    DEPRECATED: This function is kept for backward compatibility.
    Consider using BinanceDLTResourceFactory directly for better control.

    Args:
        config: BinanceConfig instance
        symbol: Trading symbol (e.g., "BTCUSDT")
        start_date: Start date in YYYY-MM-DD format

    Returns:
        DLT resource configured for this symbol
    """
    factory = BinanceDLTResourceFactory(config, _rate_limiter)
    return factory.create_agg_trades_resource(symbol, start_date)


@dlt.source
def binance_daily_candles(
    config: BinanceConfig,
    symbols: Optional[List[str]] = None,
    start_date: Optional[str] = None,
):
    """
    DLT source for daily candlestick data.

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

    factory = BinanceDLTResourceFactory(config, _rate_limiter)

    return [
        factory.create_candles_resource(symbol, start_date, "1d", "DAILY")
        for symbol in symbols
    ]


def create_daily_candles_resource(
    config: BinanceConfig,
    symbol: str,
    start_date: str,
) -> dlt.resource:
    """
    Create a DLT resource for daily candlestick data.

    DEPRECATED: This function is kept for backward compatibility.
    Consider using BinanceDLTResourceFactory directly.

    Args:
        config: BinanceConfig instance
        symbol: Trading symbol (e.g., "BTCUSDT")
        start_date: Start date in YYYY-MM-DD format

    Returns:
        DLT resource for daily candles
    """
    factory = BinanceDLTResourceFactory(config, _rate_limiter)
    return factory.create_candles_resource(symbol, start_date, "1d", "DAILY")


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
    """
    symbols = symbols or config.symbols
    start_date = start_date or config.historical_start_date

    # Validate interval
    if interval not in INTERVAL_MAP:
        raise ValueError(
            f"Invalid interval: {interval}. "
            f"Valid intervals: {', '.join(INTERVAL_MAP.keys())}"
        )

    factory = BinanceDLTResourceFactory(config, _rate_limiter)

    return [
        factory.create_candles_resource(symbol, start_date, interval, interval)
        for symbol in symbols
    ]


def create_intraday_candles_resource(
    config: BinanceConfig,
    symbol: str,
    start_date: str,
    interval: str,
) -> dlt.resource:
    """
    Create a DLT resource for intraday candlestick data.

    DEPRECATED: This function is kept for backward compatibility.
    Consider using BinanceDLTResourceFactory directly.

    Args:
        config: BinanceConfig instance
        symbol: Trading symbol (e.g., "BTCUSDT")
        start_date: Start date in YYYY-MM-DD format
        interval: Interval string (1m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h)

    Returns:
        DLT resource for the specified interval
    """
    factory = BinanceDLTResourceFactory(config, _rate_limiter)
    return factory.create_candles_resource(symbol, start_date, interval, interval)


# ============================================================================
# Legacy Constants (kept for backward compatibility)
# ============================================================================

# Re-export INTERVAL_MAP for backward compatibility
__all__ = [
    "binance_historical_data",
    "binance_daily_candles",
    "binance_intraday_candles",
    "create_agg_trades_resource",
    "create_daily_candles_resource",
    "create_intraday_candles_resource",
    "BinanceDLTResourceFactory",
    "INTERVAL_MAP",
]
