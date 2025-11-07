"""Validation business logic - separated from CLI presentation.

This module integrates with the existing data quality jobs system
to provide validation functionality through the CLI.
"""

import time
import duckdb
from typing import Optional, List, Dict, Any
from datetime import date as date_type

from .models import ValidateParams, ValidationResult
from ..db_config import get_config
from ..errors import DatabaseNotFoundError


def execute_validate(
    params: ValidateParams,
) -> ValidationResult:
    """
    Execute data validation by checking for duplicates and gaps.

    Integrates with existing data quality system to provide:
    - Duplicate detection
    - Gap detection
    - Data quality metrics
    - Per-symbol breakdown

    Args:
        params: Validated parameters

    Returns:
        ValidationResult with quality metrics

    Example:
        >>> params = ValidateParams(symbol="BTCUSDT")
        >>> result = execute_validate(params)
        >>> print(f"Quality score: {result.quality_score:.1f}%")
    """
    start_time = time.time()

    # Get database configuration
    config = get_config()
    db_path = config.database.db_path
    schema = config.database.schema_name

    try:
        # Connect to database
        conn = duckdb.connect(str(db_path), read_only=True)

        # Determine which symbols to validate
        if params.symbol:
            symbols = [params.symbol.upper()]
        else:
            # Get all symbols from database
            symbols = _get_all_symbols(conn, schema)

        if not symbols:
            conn.close()
            return ValidationResult(
                success=True,
                total_records=0,
                duplicate_count=0,
                gap_count=0,
                anomaly_count=0,
                symbols_checked=[],
                issues=[],
                duration_seconds=time.time() - start_time,
            )

        # Check each symbol
        total_records = 0
        duplicate_count = 0
        gap_count = 0
        issues = []

        for symbol in symbols:
            # Check if table exists
            if not _table_exists(conn, schema, symbol):
                issues.append({
                    "symbol": symbol,
                    "type": "missing_table",
                    "message": f"Table {symbol} does not exist",
                })
                continue

            # Get record count
            count = _get_record_count(conn, schema, symbol)
            total_records += count

            # Check for duplicates
            duplicates = _check_duplicates(conn, schema, symbol)
            duplicate_count += duplicates
            if duplicates > 0:
                issues.append({
                    "symbol": symbol,
                    "type": "duplicates",
                    "count": duplicates,
                    "message": f"Found {duplicates} duplicate records",
                })

            # Check for gaps (if date range specified)
            if params.start_date or params.end_date:
                gaps = _check_gaps(
                    conn,
                    schema,
                    symbol,
                    params.start_date,
                    params.end_date
                )
                gap_count += len(gaps)
                for gap in gaps:
                    issues.append({
                        "symbol": symbol,
                        "type": "gap",
                        **gap,
                    })

        conn.close()

        return ValidationResult(
            success=True,
            total_records=total_records,
            duplicate_count=duplicate_count,
            gap_count=gap_count,
            anomaly_count=0,  # TODO: Implement anomaly detection
            symbols_checked=symbols,
            issues=issues,
            duration_seconds=time.time() - start_time,
        )

    except Exception as e:
        return ValidationResult(
            success=False,
            total_records=0,
            duplicate_count=0,
            gap_count=0,
            anomaly_count=0,
            symbols_checked=[],
            issues=[{"type": "error", "message": str(e)}],
            duration_seconds=time.time() - start_time,
        )


def _get_all_symbols(conn: duckdb.DuckDBPyConnection, schema: str) -> List[str]:
    """Get all symbol tables from database."""
    try:
        query = f"""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = '{schema}'
            AND table_name NOT LIKE '%_load%'
            AND table_name NOT LIKE '%_state%'
        """
        result = conn.execute(query).fetchall()
        return [row[0] for row in result]
    except:
        return []


def _table_exists(conn: duckdb.DuckDBPyConnection, schema: str, table: str) -> bool:
    """Check if table exists."""
    try:
        query = f"""
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = '{schema}'
            AND table_name = '{table}'
        """
        result = conn.execute(query).fetchone()
        return result[0] > 0
    except:
        return False


def _get_record_count(conn: duckdb.DuckDBPyConnection, schema: str, table: str) -> int:
    """Get total record count for a table."""
    try:
        query = f"SELECT COUNT(*) FROM {schema}.{table}"
        result = conn.execute(query).fetchone()
        return result[0]
    except:
        return 0


def _check_duplicates(conn: duckdb.DuckDBPyConnection, schema: str, table: str) -> int:
    """Check for duplicate records by agg_trade_id."""
    try:
        query = f"""
            SELECT COUNT(*) - COUNT(DISTINCT agg_trade_id)
            FROM {schema}.{table}
        """
        result = conn.execute(query).fetchone()
        return result[0]
    except:
        return 0


def _check_gaps(
    conn: duckdb.DuckDBPyConnection,
    schema: str,
    table: str,
    start_date: Optional[date_type],
    end_date: Optional[date_type],
) -> List[Dict[str, Any]]:
    """Check for time gaps in data."""
    try:
        # Get date range
        date_filter = ""
        if start_date:
            date_filter += f" AND date >= '{start_date}'"
        if end_date:
            date_filter += f" AND date <= '{end_date}'"

        # Find gaps > 1 hour
        query = f"""
            WITH ordered_data AS (
                SELECT
                    timestamp,
                    LAG(timestamp) OVER (ORDER BY timestamp) as prev_timestamp
                FROM {schema}.{table}
                WHERE 1=1 {date_filter}
            )
            SELECT
                prev_timestamp as gap_start,
                timestamp as gap_end,
                (timestamp - prev_timestamp) / 1000 / 3600.0 as gap_hours
            FROM ordered_data
            WHERE (timestamp - prev_timestamp) / 1000 / 3600.0 > 1.0
            ORDER BY gap_hours DESC
            LIMIT 10
        """

        result = conn.execute(query).fetchall()
        gaps = []
        for row in result:
            gaps.append({
                "gap_start": row[0],
                "gap_end": row[1],
                "gap_hours": float(row[2]),
                "message": f"Gap of {row[2]:.1f} hours",
            })
        return gaps
    except:
        return []
