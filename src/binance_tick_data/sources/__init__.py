"""Binance data sources."""

from .rest_api import (
    binance_historical_data,
    create_agg_trades_resource,
    binance_daily_candles,
    create_daily_candles_resource,
    binance_intraday_candles,
    create_intraday_candles_resource,
    BinanceDLTResourceFactory,
    INTERVAL_MAP,
)
from .websocket import (
    binance_realtime_data,
    realtime_trades,
    realtime_agg_trades,
    realtime_depth,
)

# OOP architecture components (advanced usage)
from .binance.client import BinanceAPIClient
from .binance.transformers import BinanceAggTradeTransformer, BinanceCandleTransformer
from .binance.constants import API_WEIGHTS, BATCH_SIZE, API_TIMEOUT
from .core.batch_fetcher import IncrementalBatchFetcher
from .core.interfaces import RateLimiter, APIClient, DataTransformer
from .core.exceptions import RateLimitError, APIError

__all__ = [
    # DLT sources (backward compatible API)
    "binance_historical_data",
    "create_agg_trades_resource",
    "binance_daily_candles",
    "create_daily_candles_resource",
    "binance_intraday_candles",
    "create_intraday_candles_resource",
    "binance_realtime_data",
    "realtime_trades",
    "realtime_agg_trades",
    "realtime_depth",
    # OOP architecture components
    "BinanceDLTResourceFactory",
    "BinanceAPIClient",
    "BinanceAggTradeTransformer",
    "BinanceCandleTransformer",
    "IncrementalBatchFetcher",
    "RateLimiter",
    "APIClient",
    "DataTransformer",
    "RateLimitError",
    "APIError",
    # Constants
    "INTERVAL_MAP",
    "API_WEIGHTS",
    "BATCH_SIZE",
    "API_TIMEOUT",
]
