"""Binance data sources."""

from .rest_api import (
    binance_historical_data,
    historical_trades,
    aggregated_trades,
    order_book_snapshots,
)
from .websocket import (
    binance_realtime_data,
    realtime_trades,
    realtime_agg_trades,
    realtime_depth,
)

# Backward compatibility aliases
binance_rest_api = binance_historical_data
binance_websocket = binance_realtime_data

__all__ = [
    "binance_historical_data",
    "historical_trades",
    "aggregated_trades",
    "order_book_snapshots",
    "binance_realtime_data",
    "realtime_trades",
    "realtime_agg_trades",
    "realtime_depth",
    # Backward compatibility aliases
    "binance_rest_api",
    "binance_websocket",
]
