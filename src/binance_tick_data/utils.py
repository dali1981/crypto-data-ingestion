"""Utility functions for Binance tick data library."""

from datetime import datetime
from typing import List, Dict
import duckdb


def timestamp_to_datetime(timestamp_ms: int) -> datetime:
    """
    Convert Unix timestamp in milliseconds to datetime.

    Args:
        timestamp_ms: Timestamp in milliseconds

    Returns:
        datetime object
    """
    return datetime.fromtimestamp(timestamp_ms / 1000)


def datetime_to_timestamp(dt: datetime) -> int:
    """
    Convert datetime to Unix timestamp in milliseconds.

    Args:
        dt: datetime object

    Returns:
        Timestamp in milliseconds
    """
    return int(dt.timestamp() * 1000)


def get_table_info(db_path: str, dataset_name: str, table_name: str) -> Dict:
    """
    Get information about a table in the DuckDB database.

    Args:
        db_path: Path to DuckDB database
        dataset_name: Dataset name
        table_name: Table name

    Returns:
        Dictionary with table information (row count, columns, etc.)
    """
    conn = duckdb.connect(db_path)

    try:
        # Get row count
        count_query = f"SELECT COUNT(*) FROM {dataset_name}.{table_name}"
        row_count = conn.execute(count_query).fetchone()[0]

        # Get column info
        columns_query = f"DESCRIBE {dataset_name}.{table_name}"
        columns = conn.execute(columns_query).fetchall()

        # Get date range if time column exists
        time_range = None
        time_columns = ['time', 'timestamp', 'event_time']
        for col in columns:
            if col[0].lower() in time_columns:
                range_query = f"""
                    SELECT MIN({col[0]}) as min_time, MAX({col[0]}) as max_time
                    FROM {dataset_name}.{table_name}
                """
                time_range = conn.execute(range_query).fetchone()
                break

        return {
            "table_name": table_name,
            "row_count": row_count,
            "columns": [{"name": col[0], "type": col[1]} for col in columns],
            "time_range": time_range,
        }

    finally:
        conn.close()


def list_tables(db_path: str) -> List[str]:
    """
    List all tables in the DuckDB database.

    Args:
        db_path: Path to DuckDB database

    Returns:
        List of table names
    """
    conn = duckdb.connect(db_path)

    try:
        result = conn.execute("SHOW TABLES").fetchall()
        return [row[0] for row in result]

    finally:
        conn.close()


def get_latest_records(
    db_path: str,
    dataset_name: str,
    table_name: str,
    limit: int = 10,
    time_column: str = "time",
) -> List[tuple]:
    """
    Get the latest records from a table.

    Args:
        db_path: Path to DuckDB database
        dataset_name: Dataset name
        table_name: Table name
        limit: Number of records to return
        time_column: Name of the time column for sorting

    Returns:
        List of tuples containing the latest records
    """
    conn = duckdb.connect(db_path)

    try:
        query = f"""
            SELECT * FROM {dataset_name}.{table_name}
            ORDER BY {time_column} DESC
            LIMIT {limit}
        """
        return conn.execute(query).fetchall()

    finally:
        conn.close()


def get_symbol_stats(
    db_path: str,
    dataset_name: str,
    table_name: str,
    symbol: str,
) -> Dict:
    """
    Get trading statistics for a specific symbol.

    Args:
        db_path: Path to DuckDB database
        dataset_name: Dataset name
        table_name: Table name
        symbol: Trading symbol (e.g., "BTCUSDT")

    Returns:
        Dictionary with statistics (count, price range, volume, etc.)
    """
    conn = duckdb.connect(db_path)

    try:
        query = f"""
            SELECT
                COUNT(*) as trade_count,
                MIN(CAST(price AS DECIMAL)) as min_price,
                MAX(CAST(price AS DECIMAL)) as max_price,
                AVG(CAST(price AS DECIMAL)) as avg_price,
                SUM(CAST(qty AS DECIMAL)) as total_volume
            FROM {dataset_name}.{table_name}
            WHERE symbol = '{symbol}'
        """

        result = conn.execute(query).fetchone()

        return {
            "symbol": symbol,
            "trade_count": result[0],
            "min_price": float(result[1]) if result[1] else None,
            "max_price": float(result[2]) if result[2] else None,
            "avg_price": float(result[3]) if result[3] else None,
            "total_volume": float(result[4]) if result[4] else None,
        }

    finally:
        conn.close()


def export_to_csv(
    db_path: str,
    dataset_name: str,
    table_name: str,
    output_path: str,
    where_clause: str = "",
):
    """
    Export table data to CSV file.

    Args:
        db_path: Path to DuckDB database
        dataset_name: Dataset name
        table_name: Table name
        output_path: Path for output CSV file
        where_clause: Optional WHERE clause for filtering (e.g., "symbol = 'BTCUSDT'")
    """
    conn = duckdb.connect(db_path)

    try:
        where = f"WHERE {where_clause}" if where_clause else ""
        query = f"""
            COPY (SELECT * FROM {dataset_name}.{table_name} {where})
            TO '{output_path}' (HEADER, DELIMITER ',')
        """
        conn.execute(query)
        print(f"Data exported to {output_path}")

    finally:
        conn.close()


def export_to_parquet(
    db_path: str,
    dataset_name: str,
    table_name: str,
    output_path: str,
    where_clause: str = "",
):
    """
    Export table data to Parquet file.

    Args:
        db_path: Path to DuckDB database
        dataset_name: Dataset name
        table_name: Table name
        output_path: Path for output Parquet file
        where_clause: Optional WHERE clause for filtering
    """
    conn = duckdb.connect(db_path)

    try:
        where = f"WHERE {where_clause}" if where_clause else ""
        query = f"""
            COPY (SELECT * FROM {dataset_name}.{table_name} {where})
            TO '{output_path}' (FORMAT PARQUET)
        """
        conn.execute(query)
        print(f"Data exported to {output_path}")

    finally:
        conn.close()
