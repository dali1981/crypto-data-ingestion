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
    - Available symbols (tables)
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

        # Get all symbol tables
        tables_query = f"""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = '{schema}'
            AND table_name NOT LIKE '%_load%'
            AND table_name NOT LIKE '%_state%'
            ORDER BY table_name
        """
        tables = conn.execute(tables_query).fetchall()

        summaries = []
        for (table_name,) in tables:
            # Get symbol statistics
            stats_query = f"""
                SELECT
                    COUNT(*) as record_count,
                    MIN(timestamp) as min_ts,
                    MAX(timestamp) as max_ts
                FROM {schema}.{table_name}
            """

            try:
                result = conn.execute(stats_query).fetchone()
                if result and result[0] > 0:
                    record_count, min_ts, max_ts = result

                    # Convert timestamps to dates
                    start_date = datetime.fromtimestamp(min_ts / 1000).date() if min_ts else None
                    end_date = datetime.fromtimestamp(max_ts / 1000).date() if max_ts else None
                    last_updated = datetime.fromtimestamp(max_ts / 1000) if max_ts else None

                    # Estimate size (rough approximation: ~100 bytes per record)
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
        return summaries

    except Exception:
        return []
