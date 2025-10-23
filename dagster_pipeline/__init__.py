"""Dagster pipeline for Binance tick data acquisition and maintenance."""

from dagster import Definitions
from dagster_dlt import DagsterDltResource

# Use absolute imports instead of relative imports for Dagster compatibility
from dagster_pipeline.assets.raw_data import raw_agg_trades_dlt, raw_order_books
from dagster_pipeline.assets.data_quality import duplicate_detection, gap_detection
from dagster_pipeline.assets.data_cleaning import deduplicate_trades, fill_largest_gap, fill_recent_data
from dagster_pipeline.resources import binance_api_resource, duckdb_query_resource, parquet_io_manager
# Jobs, schedules, and sensors temporarily disabled during migration to DLT
# TODO: Re-enable and update after DLT integration is stable
# from dagster_pipeline.jobs import (
#     fetch_latest_job,
#     detect_issues_job,
#     cleanup_duplicates_job,
#     fill_gaps_job,
#     daily_update_job,
#     full_maintenance_job,
# )
# from dagster_pipeline.schedules import (
#     daily_maintenance_schedule,
#     incremental_update_schedule,
#     weekly_gap_fill_schedule,
# )
# from dagster_pipeline.sensors import (
#     duplicate_cleanup_sensor,
#     gap_fill_sensor,
#     data_freshness_sensor,
# )

defs = Definitions(
    assets=[
        # Raw data acquisition (using dagster-dlt)
        raw_agg_trades_dlt,
        raw_order_books,

        # Quality detection
        duplicate_detection,
        gap_detection,

        # Cleaning
        deduplicate_trades,
        fill_largest_gap,
        fill_recent_data,
    ],

    resources={
        "dlt": DagsterDltResource(),  # DLT integration resource
        "binance_api": binance_api_resource,
        "duckdb_query": duckdb_query_resource,
        "io_manager": parquet_io_manager,
    },

    # Jobs, schedules, and sensors removed during migration to DLT
    # TODO: Re-enable and update after DLT integration is stable
)
