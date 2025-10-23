"""Sensor definitions for Dagster pipeline."""

from dagster import (
    sensor,
    RunRequest,
    SensorEvaluationContext,
    DefaultSensorStatus,
    SkipReason
)
from datetime import datetime
from dagster_pipeline.jobs import cleanup_duplicates_job, fill_gaps_job, fetch_latest_job
from dagster_pipeline.config import (
    DUPLICATE_THRESHOLD,
    GAP_THRESHOLD_HOURS,
    FRESHNESS_THRESHOLD_HOURS
)


@sensor(
    job=cleanup_duplicates_job,
    default_status=DefaultSensorStatus.RUNNING,
    minimum_interval_seconds=3600,  # Check every hour
    required_resource_keys={"duckdb_query"}
)
def duplicate_cleanup_sensor(
    context: SensorEvaluationContext
):
    """
    Trigger deduplication when duplicates exceed threshold.

    Checks every hour, triggers cleanup if duplicates > DUPLICATE_THRESHOLD.
    """
    duckdb_query = context.resources.duckdb_query

    try:
        result_df = duckdb_query.query("""
            SELECT COUNT(*) - COUNT(DISTINCT agg_trade_id) as duplicate_count
            FROM binance_data.agg_trades
        """)

        duplicate_count = int(result_df.iloc[0, 0]) if not result_df.empty else 0

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
    minimum_interval_seconds=86400,  # Check daily
    required_resource_keys={"duckdb_query"}
)
def gap_fill_sensor(
    context: SensorEvaluationContext
):
    """
    Trigger gap filling when large gaps detected.

    Checks daily, triggers if gap > GAP_THRESHOLD_HOURS exists.
    """
    duckdb_query = context.resources.duckdb_query

    try:
        min_gap_ms = GAP_THRESHOLD_HOURS * 3600000  # Convert to milliseconds

        result_df = duckdb_query.query(f"""
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
        """)

        if not result_df.empty and result_df.iloc[0, 1]:
            symbol = result_df.iloc[0, 0]
            largest_gap_ms = result_df.iloc[0, 1]
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
    minimum_interval_seconds=3600,  # Check hourly
    required_resource_keys={"duckdb_query"}
)
def data_freshness_sensor(
    context: SensorEvaluationContext
):
    """
    Trigger data fetch when data becomes stale.

    Checks hourly, triggers if data > FRESHNESS_THRESHOLD_HOURS old.
    """
    duckdb_query = context.resources.duckdb_query

    try:
        result_df = duckdb_query.query("""
            SELECT MAX(timestamp) as last_ts
            FROM binance_data.agg_trades
        """)

        if result_df.empty or not result_df.iloc[0, 0]:
            # No data - trigger initial fetch
            context.log.info("No data found - triggering initial fetch")
            yield RunRequest(run_key="initial_fetch")
            return

        last_timestamp = datetime.fromtimestamp(result_df.iloc[0, 0] / 1000)
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
