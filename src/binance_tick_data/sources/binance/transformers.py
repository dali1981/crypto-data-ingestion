"""Binance data transformers."""

from datetime import datetime, timezone
from typing import Dict, List
from ..core.interfaces import DataTransformer


class BinanceAggTradeTransformer(DataTransformer[Dict, Dict]):
    """Transform Binance aggregated trades to target schema."""

    def __init__(self, symbol: str):
        """
        Initialize transformer for a specific symbol.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
        """
        self.symbol = symbol

    def transform_batch(self, raw_trades: List[Dict]) -> List[Dict]:
        """
        Transform a batch of raw trades.

        Args:
            raw_trades: List of raw trade dictionaries from Binance API

        Returns:
            List of transformed trade dictionaries
        """
        return [self._transform_single(t) for t in raw_trades]

    def _transform_single(self, trade: Dict) -> Dict:
        """
        Transform a single trade record.

        Args:
            trade: Raw trade dictionary from Binance API

        Returns:
            Transformed trade dictionary with schema fields
        """
        dt = datetime.fromtimestamp(trade["T"] / 1000, tz=timezone.utc)
        return {
            "agg_trade_id": trade["a"],
            "price": trade["p"],
            "quantity": trade["q"],
            "first_trade_id": trade["f"],
            "last_trade_id": trade["l"],
            "timestamp": trade["T"],
            "is_buyer_maker": trade["m"],
            "is_best_match": trade["M"],
            "symbol": self.symbol,
            "date": dt.date().isoformat(),
        }

    def extract_cursor(self, item: Dict) -> int:
        """
        Extract cursor for incremental loading.

        Args:
            item: Transformed trade dictionary

        Returns:
            Trade ID for cursor
        """
        return item["agg_trade_id"]

    def extract_timestamp(self, item: Dict) -> int:
        """
        Extract timestamp in milliseconds.

        Args:
            item: Transformed trade dictionary

        Returns:
            Timestamp in milliseconds since epoch
        """
        return item["timestamp"]


class BinanceCandleTransformer(DataTransformer[List, Dict]):
    """Transform Binance candles to target schema."""

    def __init__(self, symbol: str):
        """
        Initialize transformer for a specific symbol.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
        """
        self.symbol = symbol

    def transform_batch(self, raw_candles: List[List]) -> List[Dict]:
        """
        Transform a batch of raw candles.

        Args:
            raw_candles: List of raw candle arrays from Binance API

        Returns:
            List of transformed candle dictionaries
        """
        return [self._transform_single(c) for c in raw_candles]

    def _transform_single(self, candle: List) -> Dict:
        """
        Transform a single candle record.

        Binance candle format:
        [
            0: open_time,
            1: open,
            2: high,
            3: low,
            4: close,
            5: volume,
            6: close_time,
            7: quote_volume,
            8: trades,
            9: taker_buy_base_volume,
            10: taker_buy_quote_volume,
            11: ignore
        ]

        Args:
            candle: Raw candle array from Binance API

        Returns:
            Transformed candle dictionary with schema fields
        """
        open_dt = datetime.fromtimestamp(candle[0] / 1000, tz=timezone.utc)
        return {
            "symbol": self.symbol,
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
        }

    def extract_cursor(self, item: Dict) -> int:
        """
        Extract cursor for incremental loading.

        For candles, we use close_time as the cursor because the next batch
        should start from close_time + 1ms.

        Args:
            item: Transformed candle dictionary

        Returns:
            Close time for cursor (used as start_time for next batch)
        """
        return item["close_time"]

    def extract_timestamp(self, item: Dict) -> int:
        """
        Extract timestamp in milliseconds.

        Args:
            item: Transformed candle dictionary

        Returns:
            Close time in milliseconds since epoch
        """
        return item["close_time"]
