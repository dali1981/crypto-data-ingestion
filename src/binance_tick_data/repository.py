"""Data repository for accessing Binance tick data.

Provides a clean interface for querying historical and real-time data
from both DuckDB and Parquet files.
"""

from typing import List, Optional, Union, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import duckdb
import pandas as pd

from .models import SymbolStats


class BinanceDataRepository:
    """Repository for accessing Binance tick data."""

    def __init__(self, db_path: str = "binance_pipeline.duckdb", dataset_name: str = "binance_data", read_only: bool = True):
        """
        Initialize the repository.

        Args:
            db_path: Path to DuckDB database file
            dataset_name: Dataset/schema name (default: binance_data)
            read_only: Open database in read-only mode (default: True for safe concurrent access)
        """
        self.db_path = db_path
        self.dataset_name = dataset_name
        self.read_only = read_only
        self._conn = None

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def connect(self):
        """Open database connection."""
        if self._conn is None:
            self._conn = duckdb.connect(self.db_path, read_only=self.read_only)
        return self._conn

    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self):
        """Get or create connection."""
        if self._conn is None:
            self.connect()
        return self._conn

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
        Get aggregated trades for a symbol.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            start_time: Start time (datetime or timestamp in ms)
            end_time: End time (datetime or timestamp in ms)
            limit: Maximum number of records
            as_dataframe: Return as pandas DataFrame (default: True)

        Returns:
            DataFrame or list of tuples with trade data
        """
        conditions = [f"symbol = '{symbol}'"]

        if start_time:
            ts = self._to_timestamp(start_time)
            conditions.append(f"timestamp >= {ts}")

        if end_time:
            ts = self._to_timestamp(end_time)
            conditions.append(f"timestamp <= {ts}")

        where_clause = " AND ".join(conditions)
        limit_clause = f"LIMIT {limit}" if limit else ""

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
            FROM {self.dataset_name}.agg_trades
            WHERE {where_clause}
            ORDER BY timestamp ASC
            {limit_clause}
        """

        if as_dataframe:
            return self.conn.execute(query).df()
        else:
            return self.conn.execute(query).fetchall()

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
            FROM {self.dataset_name}.agg_trades
            WHERE {where_clause}
            GROUP BY time, symbol
            ORDER BY time ASC
        """

        if as_dataframe:
            return self.conn.execute(query).df()
        else:
            return self.conn.execute(query).fetchall()

    # =========================================================================
    # Market Statistics
    # =========================================================================

    def get_symbol_stats(
        self,
        symbol: str,
        start_time: Optional[Union[datetime, int]] = None,
        end_time: Optional[Union[datetime, int]] = None,
    ) -> SymbolStats:
        """
        Get trading statistics for a symbol.

        Args:
            symbol: Trading symbol
            start_time: Start time (optional)
            end_time: End time (optional)

        Returns:
            SymbolStats object with statistics and rich display methods
        """
        conditions = [f"symbol = '{symbol}'"]

        if start_time:
            ts = self._to_timestamp(start_time)
            conditions.append(f"timestamp >= {ts}")

        if end_time:
            ts = self._to_timestamp(end_time)
            conditions.append(f"timestamp <= {ts}")

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT
                COUNT(*) as trade_count,
                MIN(CAST(price AS DECIMAL)) as min_price,
                MAX(CAST(price AS DECIMAL)) as max_price,
                AVG(CAST(price AS DECIMAL)) as avg_price,
                SUM(CAST(quantity AS DECIMAL)) as total_volume,
                SUM(CASE WHEN is_buyer_maker THEN 1 ELSE 0 END) as sell_count,
                SUM(CASE WHEN NOT is_buyer_maker THEN 1 ELSE 0 END) as buy_count,
                MIN(timestamp) as first_trade_time,
                MAX(timestamp) as last_trade_time
            FROM {self.dataset_name}.agg_trades
            WHERE {where_clause}
        """

        result = self.conn.execute(query).fetchone()

        # Extract values
        trade_count = result[0]
        min_price = float(result[1]) if result[1] is not None else None
        max_price = float(result[2]) if result[2] is not None else None
        avg_price = float(result[3]) if result[3] is not None else None
        total_volume = float(result[4]) if result[4] is not None else None
        sell_count = result[5] if result[5] is not None else 0
        buy_count = result[6] if result[6] is not None else 0
        first_trade_time = datetime.fromtimestamp(result[7] / 1000) if result[7] is not None else None
        last_trade_time = datetime.fromtimestamp(result[8] / 1000) if result[8] is not None else None

        # Calculate ratio
        buy_sell_ratio = buy_count / sell_count if sell_count > 0 else None

        return SymbolStats(
            symbol=symbol,
            trade_count=trade_count,
            min_price=min_price,
            max_price=max_price,
            avg_price=avg_price,
            total_volume=total_volume,
            sell_count=sell_count,
            buy_count=buy_count,
            buy_sell_ratio=buy_sell_ratio,
            first_trade_time=first_trade_time,
            last_trade_time=last_trade_time,
        )

    def get_volume_profile(
        self,
        symbol: str,
        price_bins: int = 50,
        start_time: Optional[Union[datetime, int]] = None,
        end_time: Optional[Union[datetime, int]] = None,
        as_dataframe: bool = True,
    ) -> Union[pd.DataFrame, List[tuple]]:
        """
        Get volume profile (volume at each price level).

        Args:
            symbol: Trading symbol
            price_bins: Number of price bins
            start_time: Start time
            end_time: End time
            as_dataframe: Return as pandas DataFrame

        Returns:
            Volume profile data
        """
        conditions = [f"symbol = '{symbol}'"]

        if start_time:
            ts = self._to_timestamp(start_time)
            conditions.append(f"timestamp >= {ts}")

        if end_time:
            ts = self._to_timestamp(end_time)
            conditions.append(f"timestamp <= {ts}")

        where_clause = " AND ".join(conditions)

        query = f"""
            WITH price_range AS (
                SELECT
                    MIN(CAST(price AS DECIMAL)) as min_price,
                    MAX(CAST(price AS DECIMAL)) as max_price
                FROM {self.dataset_name}.agg_trades
                WHERE {where_clause}
            ),
            binned_trades AS (
                SELECT
                    FLOOR((CAST(price AS DECIMAL) - pr.min_price) /
                          ((pr.max_price - pr.min_price) / {price_bins})) as bin,
                    CAST(price AS DECIMAL) as price,
                    CAST(quantity AS DECIMAL) as volume
                FROM {self.dataset_name}.agg_trades, price_range pr
                WHERE {where_clause}
            )
            SELECT
                bin,
                MIN(price) as price_low,
                MAX(price) as price_high,
                AVG(price) as price_avg,
                SUM(volume) as total_volume,
                COUNT(*) as trade_count
            FROM binned_trades
            GROUP BY bin
            ORDER BY bin ASC
        """

        if as_dataframe:
            return self.conn.execute(query).df()
        else:
            return self.conn.execute(query).fetchall()

    # =========================================================================
    # Order Book Data
    # =========================================================================

    def get_order_book_snapshot(
        self,
        symbol: str,
        timestamp: Optional[Union[datetime, int]] = None,
    ) -> Optional[dict]:
        """
        Get order book snapshot closest to the specified time.

        Args:
            symbol: Trading symbol
            timestamp: Timestamp (if None, gets latest)

        Returns:
            Order book snapshot or None
        """
        if timestamp:
            ts = self._to_timestamp(timestamp)
            query = f"""
                SELECT symbol, timestamp, last_update_id, bids, asks
                FROM {self.dataset_name}.order_book_snapshots
                WHERE symbol = '{symbol}' AND timestamp <= {ts}
                ORDER BY timestamp DESC
                LIMIT 1
            """
        else:
            query = f"""
                SELECT symbol, timestamp, last_update_id, bids, asks
                FROM {self.dataset_name}.order_book_snapshots
                WHERE symbol = '{symbol}'
                ORDER BY timestamp DESC
                LIMIT 1
            """

        result = self.conn.execute(query).fetchone()

        if result:
            return {
                "symbol": result[0],
                "timestamp": result[1],
                "last_update_id": result[2],
                "bids": result[3],
                "asks": result[4],
            }
        return None

    # =========================================================================
    # Real-time Data
    # =========================================================================

    def get_realtime_trades(
        self,
        symbol: str,
        limit: int = 100,
        as_dataframe: bool = True,
    ) -> Union[pd.DataFrame, List[tuple]]:
        """
        Get latest real-time trades.

        Args:
            symbol: Trading symbol
            limit: Number of recent trades
            as_dataframe: Return as pandas DataFrame

        Returns:
            Recent trades
        """
        query = f"""
            SELECT
                trade_id,
                symbol,
                price,
                quantity,
                trade_time,
                is_buyer_maker
            FROM {self.dataset_name}_realtime.realtime_trades
            WHERE symbol = '{symbol}'
            ORDER BY trade_time DESC
            LIMIT {limit}
        """

        if as_dataframe:
            return self.conn.execute(query).df()
        else:
            return self.conn.execute(query).fetchall()

    # =========================================================================
    # Data Export
    # =========================================================================

    def export_to_parquet(
        self,
        symbol: str,
        output_path: Union[str, Path],
        start_time: Optional[Union[datetime, int]] = None,
        end_time: Optional[Union[datetime, int]] = None,
        table: str = "agg_trades",
    ):
        """
        Export data to Parquet file.

        Args:
            symbol: Trading symbol
            output_path: Path for output Parquet file
            start_time: Start time (optional)
            end_time: End time (optional)
            table: Table name (agg_trades, trades, etc.)
        """
        conditions = [f"symbol = '{symbol}'"]

        if start_time:
            ts = self._to_timestamp(start_time)
            conditions.append(f"timestamp >= {ts}")

        if end_time:
            ts = self._to_timestamp(end_time)
            conditions.append(f"timestamp <= {ts}")

        where_clause = " AND ".join(conditions)

        query = f"""
            COPY (
                SELECT * FROM {self.dataset_name}.{table}
                WHERE {where_clause}
                ORDER BY timestamp ASC
            ) TO '{output_path}' (FORMAT PARQUET, COMPRESSION 'ZSTD')
        """

        self.conn.execute(query)
        print(f"✓ Exported to {output_path}")

    def export_to_csv(
        self,
        symbol: str,
        output_path: Union[str, Path],
        start_time: Optional[Union[datetime, int]] = None,
        end_time: Optional[Union[datetime, int]] = None,
        table: str = "agg_trades",
    ):
        """
        Export data to CSV file.

        Args:
            symbol: Trading symbol
            output_path: Path for output CSV file
            start_time: Start time (optional)
            end_time: End time (optional)
            table: Table name (agg_trades, trades, etc.)
        """
        conditions = [f"symbol = '{symbol}'"]

        if start_time:
            ts = self._to_timestamp(start_time)
            conditions.append(f"timestamp >= {ts}")

        if end_time:
            ts = self._to_timestamp(end_time)
            conditions.append(f"timestamp <= {ts}")

        where_clause = " AND ".join(conditions)

        query = f"""
            COPY (
                SELECT * FROM {self.dataset_name}.{table}
                WHERE {where_clause}
                ORDER BY timestamp ASC
            ) TO '{output_path}' (HEADER, DELIMITER ',')
        """

        self.conn.execute(query)
        print(f"✓ Exported to {output_path}")

    # =========================================================================
    # Metadata & Info
    # =========================================================================

    def list_symbols(self) -> List[str]:
        """Get list of all symbols in the database."""
        query = """
            SELECT DISTINCT symbol
            FROM {self.dataset_name}.agg_trades
            ORDER BY symbol
        """
        result = self.conn.execute(query).fetchall()
        return [row[0] for row in result]

    def get_data_summary(self) -> dict:
        """Get summary of available data."""
        tables = ["agg_trades", "trades", "order_book_snapshots"]
        summary = {}

        for table in tables:
            try:
                query = f"""
                    SELECT
                        COUNT(*) as total_records,
                        COUNT(DISTINCT symbol) as symbol_count,
                        MIN(timestamp) as first_timestamp,
                        MAX(timestamp) as last_timestamp
                    FROM {self.dataset_name}.{table}
                """
                result = self.conn.execute(query).fetchone()

                summary[table] = {
                    "total_records": result[0],
                    "symbol_count": result[1],
                    "first_timestamp": datetime.fromtimestamp(result[2] / 1000) if result[2] else None,
                    "last_timestamp": datetime.fromtimestamp(result[3] / 1000) if result[3] else None,
                }
            except:
                summary[table] = None

        return summary

    # =========================================================================
    # Helper Methods
    # =========================================================================

    @staticmethod
    def _to_timestamp(dt: Union[datetime, int]) -> int:
        """Convert datetime to millisecond timestamp."""
        if isinstance(dt, datetime):
            return int(dt.timestamp() * 1000)
        return dt

    def execute_query(self, query: str, as_dataframe: bool = True) -> Union[pd.DataFrame, List[tuple]]:
        """
        Execute a custom SQL query.

        Args:
            query: SQL query string
            as_dataframe: Return as pandas DataFrame

        Returns:
            Query results
        """
        if as_dataframe:
            return self.conn.execute(query).df()
        else:
            return self.conn.execute(query).fetchall()
