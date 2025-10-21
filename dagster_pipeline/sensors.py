"""Sensor definitions for Dagster pipeline."""

from dagster import (
    sensor,
    RunRequest,
    SensorEvaluationContext,
    DefaultSensorStatus,
    SkipReason
)
from datetime import datetime
from .jobs import cleanup_duplicates_job, fill_gaps_job, fetch_latest_job
from .config import (
    DUPLICATE_THRESHOLD,
    GAP_THRESHOLD_HOURS,
    FRESHNESS_THRESHOLD_HOURS
)


@sensor(
    job=cleanup_duplicates_job,
    default_status=DefaultSensorStatus.RUNNING,
    minimum_interval_seconds=3600  # Check every hour
)
def duplicate_cleanup_sensor(
    context: SensorEvaluationContext,
    duckdb_conn
):
    """
    Trigger deduplication when duplicates exceed threshold.

    Checks every hour, triggers cleanup if duplicates > DUPLICATE_THRESHOLD.
    """
    conn = duckdb_conn.get_connection()

    try:
        result = conn.execute("""
            SELECT COUNT(*) - COUNT(DISTINCT agg_trade_id) as duplicate_count
            FROM binance_data.agg_trades
        """).fetchone()

        duplicate_count = result[0] if result else 0

        conn.close()

        if duplicate_count > DUPLICATE_THRESHOLD:
            context.log.info(
                f"Found {duplicate_count:,} duplicates "
                f"(threshold: {DUPLICATE_THRESHOLD:,}) - triggering cleanup"
            )
            yield RunRequest(
                run_key=f"cleanup_{datetime.now().isoformat()}",
                run_config={}
            )
        else:
            yield SkipReason(
                f"Only {duplicate_count:,} duplicates "
                f"(threshold: {DUPLICATE_THRESHOLD:,})"
            )

    except Exception as e:
        yield SkipReason(f"Error checking duplicates: {e}")


@sensor(
    job=fill_gaps_job,
    default_status=DefaultSensorStatus.RUNNING,
    minimum_interval_seconds=86400  # Check daily
)
def gap_fill_sensor(
    context: SensorEvaluationContext,
    duckdb_conn
):
    """
    Trigger gap filling when large gaps detected.

    Checks daily, triggers if gap > GAP_THRESHOLD_HOURS exists.
    """
    conn = duckdb_conn.get_connection()

    try:
        min_gap_ms = GAP_THRESHOLD_HOURS * 3600000  # Convert to milliseconds

        result = conn.execute(f"""
            WITH time_diffs AS (
                SELECT
                    symbol,
                    timestamp - LAG(timestamp) OVER (PARTITION BY symbol ORDER BY timestamp) as gap_ms
                FROM binance_data.agg_trades
            )
            SELECT symbol, MAX(gap_ms) as largest_gap_ms
            FROM time_diffs
            GROUP BY symbol
            ORDER BY largest_gap_ms DESC
            LIMIT 1
        """).fetchone()

        conn.close()

        if result and result[1]:
            symbol = result[0]
            largest_gap_ms = result[1]
            largest_gap_hours = largest_gap_ms / 3600000

            if largest_gap_ms > min_gap_ms:
                context.log.info(
                    f"Found gap in {symbol}: {largest_gap_hours:.1f} hours "
                    f"(threshold: {GAP_THRESHOLD_HOURS:.1f}h) - triggering fill"
                )
                yield RunRequest(
                    run_key=f"fill_gap_{symbol}_{datetime.now().isoformat()}",
                    run_config={}
                )
            else:
                yield SkipReason(
                    f"Largest gap: {largest_gap_hours:.1f}h in {symbol} "
                    f"(threshold: {GAP_THRESHOLD_HOURS:.1f}h)"
                )
        else:
            yield SkipReason("No gaps found")

    except Exception as e:
        yield SkipReason(f"Error checking gaps: {e}")


@sensor(
    job=fetch_latest_job,
    default_status=DefaultSensorStatus.RUNNING,
    minimum_interval_seconds=3600  # Check hourly
)
def data_freshness_sensor(
    context: SensorEvaluationContext,
    duckdb_conn
):
    """
    Trigger data fetch when data becomes stale.

    Checks hourly, triggers if data > FRESHNESS_THRESHOLD_HOURS old.
    """
    conn = duckdb_conn.get_connection()

    try:
        result = conn.execute("""
            SELECT MAX(timestamp) as last_ts
            FROM binance_data.agg_trades
        """).fetchone()

        conn.close()

        if not result or not result[0]:
            # No data - trigger initial fetch
            context.log.info("No data found - triggering initial fetch")
            yield RunRequest(run_key="initial_fetch")
            return

        last_timestamp = datetime.fromtimestamp(result[0] / 1000)
        hours_old = (datetime.now() - last_timestamp).total_seconds() / 3600

        if hours_old > FRESHNESS_THRESHOLD_HOURS:
            context.log.info(
                f"Data is {hours_old:.1f}h old "
                f"(threshold: {FRESHNESS_THRESHOLD_HOURS:.1f}h) - triggering fetch"
            )
            yield RunRequest(
                run_key=f"freshness_{datetime.now().isoformat()}",
                run_config={}
            )
        else:
            yield SkipReason(
                f"Data is fresh ({hours_old:.1f}h old, "
                f"threshold: {FRESHNESS_THRESHOLD_HOURS:.1f}h)"
            )

    except Exception as e:
        yield SkipReason(f"Error checking freshness: {e}")
