"""List data business logic - separated from CLI presentation.

This module provides functionality to list and summarize available data.
"""

import duckdb
from typing import List
from datetime import datetime
from pathlib import Path

from .models import DataSummary
from ..db_config import get_config


def execute_list_data() -> List[DataSummary]:
    """
    List available data in the database.

    Queries the database to discover:
    - Available trading pair symbols (BTCUSDT, ETHUSDT, etc.)
    - Date ranges per symbol
    - Record counts
    - Last update timestamps
    - Approximate data sizes

    Returns:
        List of DataSummary objects, one per symbol

    Example:
        >>> summaries = execute_list_data()
        >>> for summary in summaries:
        ...     print(f"{summary.symbol}: {summary.record_count:,} records")
    """
    # Get database configuration
    config = get_config()
    db_path = config.database.db_path
    schema = config.database.schema_name

    # Check if database exists
    if not Path(db_path).exists():
        return []

    try:
        # Connect to database
        conn = duckdb.connect(str(db_path), read_only=True)

        # Get all data tables
        # Exclude: Internal dlt tables (_load, _state), backups
        tables_query = f"""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = '{schema}'
            AND table_name NOT LIKE '%_load%'
            AND table_name NOT LIKE '%_state%'
            AND table_name NOT LIKE '%backup%'
            ORDER BY table_name
        """
        tables = conn.execute(tables_query).fetchall()

        summaries = []

        # Check each table for symbol column
        for (table_name,) in tables:
            try:
                # Check if table has 'symbol' column (aggregated data)
                columns = conn.execute(f"""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = '{schema}'
                    AND table_name = '{table_name}'
                """).fetchall()

                column_names = [col[0] for col in columns]

                if 'symbol' in column_names:
                    # Table has symbol column - get per-symbol stats
                    symbols_query = f"""
                        SELECT
                            symbol,
                            COUNT(*) as record_count,
                            MIN(timestamp) as min_ts,
                            MAX(timestamp) as max_ts
                        FROM {schema}.{table_name}
                        GROUP BY symbol
                        ORDER BY symbol
                    """

                    results = conn.execute(symbols_query).fetchall()
                    for symbol, record_count, min_ts, max_ts in results:
                        start_date = datetime.fromtimestamp(min_ts / 1000).date() if min_ts else None
                        end_date = datetime.fromtimestamp(max_ts / 1000).date() if max_ts else None
                        last_updated = datetime.fromtimestamp(max_ts / 1000) if max_ts else None
                        size_bytes = record_count * 100

                        summaries.append(DataSummary(
                            symbol=symbol,
                            record_count=record_count,
                            start_date=start_date,
                            end_date=end_date,
                            size_bytes=size_bytes,
                            last_updated=last_updated,
                        ))
                else:
                    # Table is named after symbol (e.g., BTCUSDT table)
                    stats_query = f"""
                        SELECT
                            COUNT(*) as record_count,
                            MIN(timestamp) as min_ts,
                            MAX(timestamp) as max_ts
                        FROM {schema}.{table_name}
                    """

                    result = conn.execute(stats_query).fetchone()
                    if result and result[0] > 0:
                        record_count, min_ts, max_ts = result
                        start_date = datetime.fromtimestamp(min_ts / 1000).date() if min_ts else None
                        end_date = datetime.fromtimestamp(max_ts / 1000).date() if max_ts else None
                        last_updated = datetime.fromtimestamp(max_ts / 1000) if max_ts else None
                        size_bytes = record_count * 100

                        summaries.append(DataSummary(
                            symbol=table_name,
                            record_count=record_count,
                            start_date=start_date,
                            end_date=end_date,
                            size_bytes=size_bytes,
                            last_updated=last_updated,
                        ))
            except Exception:
                # Skip tables that can't be queried
                continue

        conn.close()

        # Sort by symbol name
        summaries.sort(key=lambda s: s.symbol)

        return summaries

    except Exception:
        return []
