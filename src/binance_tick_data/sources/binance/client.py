"""Binance-specific API client implementation."""

from binance.client import Client
from binance.exceptions import BinanceAPIException
from typing import Optional, List, Dict, Any
from ..core.interfaces import APIClient
from ..core.exceptions import RateLimitError, APIError
from .constants import API_TIMEOUT


class BinanceAPIClient(APIClient):
    """Binance-specific API client wrapping python-binance."""

    def __init__(self, api_key: str, api_secret: str, timeout: int = API_TIMEOUT):
        """
        Initialize Binance client.

        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            timeout: Request timeout in seconds (default: 60)
        """
        self._client = Client(
            api_key,
            api_secret,
            requests_params={'timeout': timeout}
        )
        self._timeout = timeout

    @property
    def timeout(self) -> int:
        """Request timeout in seconds."""
        return self._timeout

    def fetch_batch(self, **kwargs) -> Any:
        """
        Generic fetch method (not used directly, use specific methods).

        Args:
            **kwargs: API-specific parameters

        Returns:
            Raw API response
        """
        raise NotImplementedError("Use fetch_agg_trades or fetch_candles instead")

    def fetch_agg_trades(
        self,
        symbol: str,
        from_id: Optional[int] = None,
        start_time: Optional[int] = None,
        limit: int = 1000
    ) -> List[Dict]:
        """
        Fetch aggregated trades from Binance.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            from_id: Trade ID to fetch from (for incremental loading)
            start_time: Start timestamp in milliseconds (for initial fetch)
            limit: Number of trades to fetch (max 1000)

        Returns:
            List of raw trade dictionaries

        Raises:
            RateLimitError: If rate limit is exceeded (429 status)
            APIError: If API request fails
        """
        try:
            if from_id is not None:
                return self._client.get_aggregate_trades(
                    symbol=symbol,
                    limit=limit,
                    fromId=from_id
                )
            else:
                return self._client.get_aggregate_trades(
                    symbol=symbol,
                    limit=limit,
                    startTime=start_time
                )
        except BinanceAPIException as e:
            if e.status_code == 429:
                raise RateLimitError("Rate limit exceeded", retry_after=None)
            else:
                raise APIError(f"Binance API error: {e}", status_code=e.status_code)

    def fetch_candles(
        self,
        symbol: str,
        interval: str,
        start_time: int,
        end_time: int,
        limit: int = 1000
    ) -> List[List]:
        """
        Fetch candlestick data from Binance.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            interval: Binance interval constant (e.g., Client.KLINE_INTERVAL_1MINUTE)
            start_time: Start timestamp in milliseconds
            end_time: End timestamp in milliseconds
            limit: Number of candles to fetch (max 1000)

        Returns:
            List of raw candle arrays

        Raises:
            RateLimitError: If rate limit is exceeded (429 status)
            APIError: If API request fails
        """
        try:
            return self._client.get_historical_klines(
                symbol=symbol,
                interval=interval,
                start_str=start_time,
                end_str=end_time,
                limit=limit
            )
        except BinanceAPIException as e:
            if e.status_code == 429:
                raise RateLimitError("Rate limit exceeded", retry_after=None)
            else:
                raise APIError(f"Binance API error: {e}", status_code=e.status_code)
