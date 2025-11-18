"""Binance-specific constants."""

# API configuration
API_TIMEOUT = 60  # seconds
BATCH_SIZE = 1000  # records per request

# API weights (for rate limiting)
# Based on Binance API documentation:
# https://binance-docs.github.io/apidocs/spot/en/#limits
API_WEIGHTS = {
    "agg_trades": 1,  # GET /api/v3/aggTrades
    "klines": 2,      # GET /api/v3/klines
}

# Interval name mapping for user-friendly names → Binance constant names
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
