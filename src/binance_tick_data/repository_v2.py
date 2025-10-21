"""
Enhanced data repository for accessing Binance tick data.

Features:
- Centralized configuration via config.yaml
- Comprehensive error handling with actionable messages
- Dollar-volume bar sampling
- Type-safe operations with Pydantic
"""

from typing import List, Optional, Union, Tuple, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path
import duckdb
import pandas as pd
import polars as pl
import logging

from .db_config import AppConfig, get_config
from .errors import (
    DatabaseNotFoundError,
    DatabaseConnectionError,
    TableNotFoundError,
    NoDataFoundError,
    InvalidSymbolError,
    InvalidDateRangeError,
    SchemaNotFoundError,
    create_data_not_found_error,
)

logger = logging.getLogger(__name__)


class BinanceDataRepository:
    """Repository for accessing Binance tick data with proper configuration and error handling."""

    def __init__(self, config: Optional[AppConfig] = None):
        """
        Initialize the repository.

        Args:
            config: Application configuration (uses global config if None)
        """
        self.config = config or get_config()
        self._conn = None

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def connect(self):
        """Open database connection with error handling."""
        if self._conn is not None:
            return self._conn

        db_path = self.config.database.db_path

        # Check if database exists
        if not Path(db_path).exists():
            logger.warning(f"Database file does not exist: {db_path}")
            raise DatabaseNotFoundError(db_path)

        try:
            self._conn = duckdb.connect(
                db_path,
                read_only=self.config.database.read_only
            )
            logger.info(f"Connected to database: {db_path}")
            return self._conn

        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise DatabaseConnectionError(db_path, e)

    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.debug("Database connection closed")

    @property
    def conn(self):
        """Get or create connection."""
        if self._conn is None:
            self.connect()
        return self._conn

    @property
    def db_path(self) -> str:
        """
        Get database path.

        Returns the database path from configuration.
        """
        return self.config.database.db_path

    @property
    def read_only(self) -> bool:
        """
        Get read-only mode status.

        Returns whether the database is opened in read-only mode.
        """
        return self.config.database.read_only

    def _validate_schema_exists(self):
        """Validate that the required schema exists."""
        try:
            result = self.conn.execute(
                f"SELECT schema_name FROM information_schema.schemata WHERE catalog_name = '{self.config.database.catalog_name}' AND schema_name = '{self.config.database.schema_name}'"
            ).fetchall()

            if not result:
                # Get available schemas
                available = self.conn.execute(
                    "SELECT DISTINCT catalog_name || '.' || schema_name FROM information_schema.schemata"
                ).fetchall()
                available_schemas = [row[0] for row in available]

                raise SchemaNotFoundError(
                    self.config.database.full_schema_path,
                    self.config.database.db_path,
                    available_schemas
                )
        except SchemaNotFoundError:
            raise
        except Exception as e:
            logger.warning(f"Could not validate schema: {e}")

    def _validate_table_exists(self, table_name: str):
        """
        Validate that a table exists by attempting to query it.

        Note: Validation is best-effort. If validation fails but the actual query works,
        that's fine - the validation will be skipped.
        """
        full_table_path = self.config.database.get_table_path(table_name)

        try:
            # Try to query the table directly (more reliable than information_schema with catalogs)
            self.conn.execute(f"SELECT 1 FROM {full_table_path} LIMIT 1").fetchall()
            logger.debug(f"Table '{full_table_path}' validated successfully")
        except Exception as e:
            # Just log the warning - don't fail.
            # The actual query will fail with a proper error if the table really doesn't exist.
            logger.debug(f"Table validation skipped for '{table_name}': {e}")

    # =========================================================================
    # Aggregated Trades (Recommended for most use cases)
    # =========================================================================

    def get_agg_trades(
        self,
        symbol: str,
        start_time: Optional[Union[datetime, int]] = None,
        end_time: Optional[Union[datetime, int]] = None,
        limit: Optional[int] = None,
        as_dataframe: bool = True,
    ) -> Union[pd.DataFrame, List[tuple]]:
        """
        Get aggregated trades for a symbol with comprehensive error handling.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            start_time: Start time (datetime or timestamp in ms)
            end_time: End time (datetime or timestamp in ms)
            limit: Maximum number of records
            as_dataframe: Return as pandas DataFrame (default: True)

        Returns:
            DataFrame or list of tuples with trade data

        Raises:
            TableNotFoundError: If agg_trades table doesn't exist
            NoDataFoundError: If no data matches the criteria
            InvalidDateRangeError: If start_time > end_time
        """
        # Validate table exists
        self._validate_table_exists(self.config.tables.agg_trades)

        # Validate date range
        if start_time and end_time:
            start_dt = self._to_datetime(start_time)
            end_dt = self._to_datetime(end_time)
            if start_dt > end_dt:
                raise InvalidDateRangeError(start_dt, end_dt)

        # Build query
        conditions = [f"symbol = '{symbol}'"]

        if start_time:
            ts = self._to_timestamp(start_time)
            conditions.append(f"timestamp >= {ts}")

        if end_time:
            ts = self._to_timestamp(end_time)
            conditions.append(f"timestamp <= {ts}")

        where_clause = " AND ".join(conditions)
        limit_clause = f"LIMIT {limit}" if limit else ""

        # Try full path first, fallback to schema.table if needed
        table_path = self.config.database.get_table_path(self.config.tables.agg_trades)
        fallback_path = f"{self.config.database.schema_name}.{self.config.tables.agg_trades}"

        query = f"""
            SELECT
                agg_trade_id,
                symbol,
                price,
                quantity,
                first_trade_id,
                last_trade_id,
                timestamp,
                is_buyer_maker,
                is_best_match
            FROM {table_path}
            WHERE {where_clause}
            ORDER BY timestamp ASC
            {limit_clause}
        """

        logger.debug(f"Executing query for {symbol}: {start_time} to {end_time}")

        try:
            if as_dataframe:
                try:
                    df = self.conn.execute(query).df()
                except Exception as e:
                    # Try fallback path (schema.table without catalog)
                    if "does not exist" in str(e).lower():
                        logger.debug(f"Trying fallback path: {fallback_path}")
                        query = query.replace(table_path, fallback_path)
                        df = self.conn.execute(query).df()
                    else:
                        raise
                if df.empty:
                    raise create_data_not_found_error(
                        self.config.tables.agg_trades,
                        symbol=symbol,
                        start_time=self._to_datetime(start_time) if start_time else None,
                        end_time=self._to_datetime(end_time) if end_time else None,
                    )
                return df
            else:
                results = self.conn.execute(query).fetchall()
                if not results:
                    raise create_data_not_found_error(
                        self.config.tables.agg_trades,
                        symbol=symbol,
                        start_time=self._to_datetime(start_time) if start_time else None,
                        end_time=self._to_datetime(end_time) if end_time else None,
                    )
                return results
        except (NoDataFoundError, TableNotFoundError):
            raise
        except Exception as e:
            logger.error(f"Query failed: {e}")
            raise

    def get_agg_trades_by_date_range(
        self,
        symbol: str,
        days: int = 7,
        as_dataframe: bool = True,
    ) -> Union[pd.DataFrame, List[tuple]]:
        """
        Get aggregated trades for the last N days.

        Args:
            symbol: Trading symbol
            days: Number of days to look back
            as_dataframe: Return as pandas DataFrame

        Returns:
            Trade data
        """
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        return self.get_agg_trades(symbol, start_time, end_time, as_dataframe=as_dataframe)

    # =========================================================================
    # Dollar Volume Bars - NEW
    # =========================================================================

    def create_dollar_bars(
        self,
        symbol: str,
        start_time: Optional[Union[datetime, int]] = None,
        end_time: Optional[Union[datetime, int]] = None,
        dollar_threshold: Optional[float] = None,
        use_polars: bool = True,
    ) -> Union[pd.DataFrame, pl.DataFrame]:
        """
        Create dollar-volume bars from tick data.

        Dollar bars sample trades based on dollar volume, providing better statistical
        properties than time-based bars.

        Args:
            symbol: Trading symbol
            start_time: Start time for tick data
            end_time: End time for tick data
            dollar_threshold: Dollar volume per bar (uses config default if None)
            use_polars: Use Polars for faster processing (default: True)

        Returns:
            DataFrame with OHLCV dollar bars

        Raises:
            NoDataFoundError: If no tick data available
        """
        # Get tick data
        df = self.get_agg_trades(
            symbol=symbol,
            start_time=start_time,
            end_time=end_time,
            as_dataframe=True
        )

        # Get threshold from config if not provided
        if dollar_threshold is None:
            dollar_threshold = self.config.pipeline.bar_thresholds.get_dollar_threshold(symbol)

        logger.info(f"Creating dollar bars for {symbol} with threshold ${dollar_threshold:,.0f}")

        if use_polars:
            return self._create_dollar_bars_polars(df, dollar_threshold)
        else:
            return self._create_dollar_bars_pandas(df, dollar_threshold)

    def _create_dollar_bars_polars(
        self,
        df: pd.DataFrame,
        dollar_threshold: float
    ) -> pl.DataFrame:
        """Create dollar bars using Polars (fast)."""
        # Convert to Polars
        df_pl = pl.from_pandas(df)

        # Convert price and quantity to float
        df_pl = df_pl.with_columns([
            pl.col('price').cast(pl.Float64),
            pl.col('quantity').cast(pl.Float64)
        ])

        # Calculate dollar volume
        df_pl = df_pl.with_columns(
            (pl.col('price') * pl.col('quantity')).alias('dollar_volume')
        )

        # Calculate cumulative dollar volume
        df_pl = df_pl.with_columns(
            pl.col('dollar_volume').cum_sum().alias('cum_dollar_volume')
        )

        # Identify bar boundaries
        df_pl = df_pl.with_columns(
            (pl.col('cum_dollar_volume') // dollar_threshold).alias('bar_id')
        )

        # Aggregate to create bars
        dollar_bars = df_pl.group_by('bar_id').agg([
            pl.col('timestamp').first().alias('timestamp'),
            pl.col('price').first().alias('open'),
            pl.col('price').max().alias('high'),
            pl.col('price').min().alias('low'),
            pl.col('price').last().alias('close'),
            pl.col('quantity').sum().alias('volume'),
            pl.col('dollar_volume').sum().alias('dollar_volume'),
            pl.len().alias('tick_count'),
            pl.col('price').std().alias('price_std'),
            (pl.col('price').last() - pl.col('price').first()).alias('price_change')
        ]).sort('bar_id')

        logger.info(f"Created {len(dollar_bars)} dollar bars")
        return dollar_bars

    def _create_dollar_bars_pandas(
        self,
        df: pd.DataFrame,
        dollar_threshold: float
    ) -> pd.DataFrame:
        """Create dollar bars using Pandas (compatible)."""
        # Convert types
        df['price'] = df['price'].astype(float)
        df['quantity'] = df['quantity'].astype(float)

        # Calculate dollar volume
        df['dollar_volume'] = df['price'] * df['quantity']

        # Calculate cumulative dollar volume
        df['cum_dollar_volume'] = df['dollar_volume'].cumsum()

        # Identify bar boundaries
        df['bar_id'] = (df['cum_dollar_volume'] // dollar_threshold).astype(int)

        # Aggregate to create bars
        dollar_bars = df.groupby('bar_id').agg({
            'timestamp': 'first',
            'price': ['first', 'max', 'min', 'last', 'std'],
            'quantity': 'sum',
            'dollar_volume': 'sum'
        })

        # Flatten column names
        dollar_bars.columns = ['timestamp', 'open', 'high', 'low', 'close', 'price_std', 'volume', 'dollar_volume']

        # Add tick count and price change
        tick_counts = df.groupby('bar_id').size()
        dollar_bars['tick_count'] = tick_counts
        dollar_bars['price_change'] = dollar_bars['close'] - dollar_bars['open']

        dollar_bars = dollar_bars.reset_index()

        logger.info(f"Created {len(dollar_bars)} dollar bars")
        return dollar_bars

    # =========================================================================
    # OHLCV (Candlestick) Data - Computed from Trades
    # =========================================================================

    def get_ohlcv(
        self,
        symbol: str,
        interval: str = "1m",
        start_time: Optional[Union[datetime, int]] = None,
        end_time: Optional[Union[datetime, int]] = None,
        as_dataframe: bool = True,
    ) -> Union[pd.DataFrame, List[tuple]]:
        """
        Compute OHLCV (candlestick) data from aggregated trades.

        Args:
            symbol: Trading symbol
            interval: Time interval (1m, 5m, 15m, 1h, 4h, 1d)
            start_time: Start time
            end_time: End time
            as_dataframe: Return as pandas DataFrame

        Returns:
            OHLCV data
        """
        self._validate_table_exists(self.config.tables.agg_trades)

        interval_map = {
            "1m": "1 minute",
            "5m": "5 minutes",
            "15m": "15 minutes",
            "30m": "30 minutes",
            "1h": "1 hour",
            "4h": "4 hours",
            "1d": "1 day",
        }

        if interval not in interval_map:
            raise ValueError(f"Invalid interval. Choose from: {list(interval_map.keys())}")

        conditions = [f"symbol = '{symbol}'"]

        if start_time:
            ts = self._to_timestamp(start_time)
            conditions.append(f"timestamp >= {ts}")

        if end_time:
            ts = self._to_timestamp(end_time)
            conditions.append(f"timestamp <= {ts}")

        where_clause = " AND ".join(conditions)
        table_path = self.config.database.get_table_path(self.config.tables.agg_trades)

        query = f"""
            SELECT
                time_bucket(INTERVAL '{interval_map[interval]}',
                    to_timestamp(timestamp / 1000)) as time,
                symbol,
                FIRST(CAST(price AS DECIMAL)) as open,
                MAX(CAST(price AS DECIMAL)) as high,
                MIN(CAST(price AS DECIMAL)) as low,
                LAST(CAST(price AS DECIMAL)) as close,
                SUM(CAST(quantity AS DECIMAL)) as volume,
                COUNT(*) as trades
            FROM {table_path}
            WHERE {where_clause}
            GROUP BY time, symbol
            ORDER BY time ASC
        """

        if as_dataframe:
            df = self.conn.execute(query).df()
            if df.empty:
                raise create_data_not_found_error(
                    self.config.tables.agg_trades,
                    symbol=symbol,
                    start_time=self._to_datetime(start_time) if start_time else None,
                    end_time=self._to_datetime(end_time) if end_time else None,
                )
            return df
        else:
            results = self.conn.execute(query).fetchall()
            if not results:
                raise create_data_not_found_error(
                    self.config.tables.agg_trades,
                    symbol=symbol,
                    start_time=self._to_datetime(start_time) if start_time else None,
                    end_time=self._to_datetime(end_time) if end_time else None,
                )
            return results

    # =========================================================================
    # Helper Methods
    # =========================================================================

    @staticmethod
    def _to_timestamp(dt: Union[datetime, int]) -> int:
        """Convert datetime to millisecond timestamp."""
        if isinstance(dt, datetime):
            return int(dt.timestamp() * 1000)
        return dt

    @staticmethod
    def _to_datetime(dt: Union[datetime, int]) -> datetime:
        """Convert to datetime object."""
        if isinstance(dt, datetime):
            return dt
        return datetime.fromtimestamp(dt / 1000)

    def execute_query(
        self,
        query: str,
        as_dataframe: bool = True
    ) -> Union[pd.DataFrame, List[tuple]]:
        """
        Execute a custom SQL query.

        Args:
            query: SQL query string
            as_dataframe: Return as pandas DataFrame

        Returns:
            Query results
        """
        logger.debug(f"Executing custom query: {query[:100]}...")

        try:
            if as_dataframe:
                return self.conn.execute(query).df()
            else:
                return self.conn.execute(query).fetchall()
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise

    def list_available_symbols(self) -> List[str]:
        """Get list of all symbols in the database."""
        self._validate_table_exists(self.config.tables.agg_trades)

        table_path = self.config.database.get_table_path(self.config.tables.agg_trades)
        query = f"""
            SELECT DISTINCT symbol
            FROM {table_path}
            ORDER BY symbol
        """
        result = self.conn.execute(query).fetchall()
        return [row[0] for row in result]

    def get_data_summary(self) -> dict:
        """Get summary of available data with error handling."""
        summary = {}

        for table_name in self.config.tables.list_data_tables():
            try:
                table_path = self.config.database.get_table_path(table_name)
                query = f"""
                    SELECT
                        COUNT(*) as total_records,
                        COUNT(DISTINCT symbol) as symbol_count,
                        MIN(timestamp) as first_timestamp,
                        MAX(timestamp) as last_timestamp
                    FROM {table_path}
                """
                result = self.conn.execute(query).fetchone()

                summary[table_name] = {
                    "exists": True,
                    "total_records": result[0],
                    "symbol_count": result[1],
                    "first_timestamp": datetime.fromtimestamp(result[2] / 1000) if result[2] else None,
                    "last_timestamp": datetime.fromtimestamp(result[3] / 1000) if result[3] else None,
                }
            except Exception:
                summary[table_name] = {"exists": False}

        return summary

    # =========================================================================
    # Streaming / Real-Time Query Methods
    # =========================================================================

    def get_recent_window(
        self,
        symbol: str,
        seconds: int = 60,
        as_dataframe: bool = True
    ) -> Union[pd.DataFrame, List[Tuple]]:
        """
        Get trades from the last N seconds (optimized for repeated calls).

        Hot path for real-time analysis - fetches recent data with query caching.

        Args:
            symbol: Trading symbol
            seconds: Number of seconds to look back
            as_dataframe: Return as pandas DataFrame

        Returns:
            Recent trades within the time window

        Examples:
            >>> with BinanceDataRepository() as repo:
            ...     # Get last 60 seconds of trades
            ...     recent = repo.get_recent_window("BTCUSDT", seconds=60)
        """
        cutoff_time = datetime.now() - timedelta(seconds=seconds)
        return self.get_agg_trades(
            symbol=symbol,
            start_time=cutoff_time,
            as_dataframe=as_dataframe
        )

    def stream_trades_since(
        self,
        symbol: str,
        timestamp: datetime,
        batch_size: int = 1000
    ):
        """
        Stream trades incrementally since a timestamp.

        Yields batches of trades, useful for incremental processing without
        loading all data into memory at once.

        Args:
            symbol: Trading symbol
            timestamp: Start timestamp
            batch_size: Number of trades per batch

        Yields:
            DataFrames with batches of trades

        Examples:
            >>> with BinanceDataRepository() as repo:
            ...     for batch in repo.stream_trades_since("BTCUSDT", timestamp):
            ...         process_batch(batch)
        """
        table_path = self.config.database.get_table_path("agg_trades")
        timestamp_ms = int(timestamp.timestamp() * 1000)

        query = f"""
            SELECT *
            FROM {table_path}
            WHERE symbol = ?
              AND timestamp >= ?
            ORDER BY timestamp
        """

        # Stream results in batches
        offset = 0
        while True:
            paginated_query = f"{query} LIMIT {batch_size} OFFSET {offset}"
            result = self.conn.execute(paginated_query, [symbol, timestamp_ms]).fetchdf()

            if result.empty:
                break

            yield result
            offset += batch_size

    def get_live_orderbook(
        self,
        symbol: str,
        depth: int = 10
    ) -> Optional[Dict[str, Any]]:
        """
        Get the most recent order book snapshot.

        Args:
            symbol: Trading symbol
            depth: Number of levels to include

        Returns:
            Most recent order book or None if not found

        Examples:
            >>> with BinanceDataRepository() as repo:
            ...     book = repo.get_live_orderbook("BTCUSDT", depth=10)
            ...     print(f"Best bid: {book['bids'][0]}")
        """
        table_path = self.config.database.get_table_path("order_book_snapshots")

        try:
            query = f"""
                SELECT *
                FROM {table_path}
                WHERE symbol = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """
            result = self.conn.execute(query, [symbol]).fetchone()

            if not result:
                return None

            # Parse the result
            return {
                "symbol": result[0],
                "timestamp": datetime.fromtimestamp(result[1] / 1000),
                "last_update_id": result[2],
                "bids": result[3][:depth] if result[3] else [],
                "asks": result[4][:depth] if result[4] else [],
            }

        except Exception as e:
            logger.error(f"Error fetching order book: {e}")
            return None

    def get_realtime_vwap(
        self,
        symbol: str,
        window_seconds: int = 60
    ) -> Optional[float]:
        """
        Compute VWAP for recent window.

        Args:
            symbol: Trading symbol
            window_seconds: Time window in seconds

        Returns:
            VWAP or None if no data

        Examples:
            >>> with BinanceDataRepository() as repo:
            ...     vwap = repo.get_realtime_vwap("BTCUSDT", window_seconds=60)
        """
        try:
            df = self.get_recent_window(symbol, seconds=window_seconds, as_dataframe=True)

            if df.empty:
                return None

            df['price'] = df['price'].astype(float)
            df['quantity'] = df['quantity'].astype(float)
            df['dollar_volume'] = df['price'] * df['quantity']

            vwap = df['dollar_volume'].sum() / df['quantity'].sum()
            return float(vwap)

        except Exception as e:
            logger.error(f"Error computing VWAP: {e}")
            return None

    def get_streaming_stats(
        self,
        symbol: str,
        window_seconds: int = 60
    ) -> Dict[str, Any]:
        """
        Get real-time market statistics for recent window.

        Computes various metrics including price stats, volume, trade counts,
        and buy/sell ratios.

        Args:
            symbol: Trading symbol
            window_seconds: Time window in seconds

        Returns:
            Dictionary with market statistics

        Examples:
            >>> with BinanceDataRepository() as repo:
            ...     stats = repo.get_streaming_stats("BTCUSDT", window_seconds=60)
            ...     print(f"Trade count: {stats['trade_count']}")
            ...     print(f"Buy/Sell ratio: {stats['buy_sell_ratio']}")
        """
        try:
            df = self.get_recent_window(symbol, seconds=window_seconds, as_dataframe=True)

            if df.empty:
                return {
                    "symbol": symbol,
                    "window_seconds": window_seconds,
                    "trade_count": 0,
                    "error": "No data available"
                }

            df['price'] = df['price'].astype(float)
            df['quantity'] = df['quantity'].astype(float)

            # Compute statistics
            buy_trades = df[df['is_buyer_maker'] == False]
            sell_trades = df[df['is_buyer_maker'] == True]

            stats = {
                "symbol": symbol,
                "window_seconds": window_seconds,
                "trade_count": len(df),
                "total_volume": float(df['quantity'].sum()),
                "price_mean": float(df['price'].mean()),
                "price_std": float(df['price'].std()),
                "price_min": float(df['price'].min()),
                "price_max": float(df['price'].max()),
                "price_range": float(df['price'].max() - df['price'].min()),
                "buy_count": len(buy_trades),
                "sell_count": len(sell_trades),
                "buy_volume": float(buy_trades['quantity'].sum()) if len(buy_trades) > 0 else 0.0,
                "sell_volume": float(sell_trades['quantity'].sum()) if len(sell_trades) > 0 else 0.0,
                "buy_sell_ratio": len(buy_trades) / len(sell_trades) if len(sell_trades) > 0 else float('inf'),
                "volume_buy_sell_ratio": (
                    float(buy_trades['quantity'].sum() / sell_trades['quantity'].sum())
                    if len(sell_trades) > 0 and sell_trades['quantity'].sum() > 0
                    else float('inf')
                ),
            }

            # Add VWAP
            df['dollar_volume'] = df['price'] * df['quantity']
            stats['vwap'] = float(df['dollar_volume'].sum() / df['quantity'].sum())

            return stats

        except Exception as e:
            logger.error(f"Error computing streaming stats: {e}")
            return {
                "symbol": symbol,
                "window_seconds": window_seconds,
                "error": str(e)
            }

    def get_realtime_trades(
        self,
        symbol: str,
        limit: int = 100,
        as_dataframe: bool = True
    ) -> Union[pd.DataFrame, List[Tuple]]:
        """
        Get the most recent N trades from real-time table.

        Fetches from the realtime_trades table which is populated by
        the WebSocket streaming pipeline.

        Args:
            symbol: Trading symbol
            limit: Maximum number of trades to return
            as_dataframe: Return as pandas DataFrame

        Returns:
            Recent real-time trades

        Examples:
            >>> with BinanceDataRepository() as repo:
            ...     latest = repo.get_realtime_trades("BTCUSDT", limit=100)
        """
        table_path = self.config.database.get_table_path("realtime_trades")

        query = f"""
            SELECT *
            FROM {table_path}
            WHERE symbol = ?
            ORDER BY trade_time DESC
            LIMIT ?
        """

        try:
            if as_dataframe:
                return self.conn.execute(query, [symbol, limit]).fetchdf()
            else:
                return self.conn.execute(query, [symbol, limit]).fetchall()
        except Exception as e:
            logger.error(f"Error fetching realtime trades: {e}")
            if as_dataframe:
                return pd.DataFrame()
            else:
                return []
