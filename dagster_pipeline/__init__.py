"""Dagster pipeline for Binance tick data acquisition and maintenance."""

from dagster import Definitions

from .assets.raw_data import raw_agg_trades, raw_order_books
from .assets.data_quality import duplicate_detection, gap_detection
from .assets.data_cleaning import deduplicate_trades, fill_largest_gap, fill_recent_data
from .resources import binance_api_resource, duckdb_resource
from .jobs import (
    fetch_latest_job,
    detect_issues_job,
    cleanup_duplicates_job,
    fill_gaps_job,
    daily_update_job,
    full_maintenance_job,
)
from .schedules import (
    daily_maintenance_schedule,
    incremental_update_schedule,
    weekly_gap_fill_schedule,
)
from .sensors import (
    duplicate_cleanup_sensor,
    gap_fill_sensor,
    data_freshness_sensor,
)

defs = Definitions(
    assets=[
        # Raw data acquisition
        raw_agg_trades,
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
        "binance_api": binance_api_resource,
        "duckdb_conn": duckdb_resource,
    },

    jobs=[
        fetch_latest_job,
        detect_issues_job,
        cleanup_duplicates_job,
        fill_gaps_job,
        daily_update_job,
        full_maintenance_job,
    ],

    schedules=[
        daily_maintenance_schedule,
        incremental_update_schedule,
        weekly_gap_fill_schedule,
    ],

    sensors=[
        duplicate_cleanup_sensor,
        gap_fill_sensor,
        data_freshness_sensor,
    ],
)
