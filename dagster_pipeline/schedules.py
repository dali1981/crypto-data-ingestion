"""Schedule definitions for Dagster pipeline."""

from dagster import ScheduleDefinition
from .jobs import (
    full_maintenance_job,
    daily_update_job,
    fill_gaps_job,
)

# ============================================================================
# SCHEDULE 1: Daily Maintenance (2 AM UTC)
# ============================================================================

daily_maintenance_schedule = ScheduleDefinition(
    name="daily_maintenance",
    job=full_maintenance_job,
    cron_schedule="0 2 * * *",  # 2 AM UTC every day
    description="Daily maintenance: fetch latest data, detect issues, and clean database"
)

# ============================================================================
# SCHEDULE 2: Incremental Update (Every 6 Hours)
# ============================================================================

incremental_update_schedule = ScheduleDefinition(
    name="incremental_update",
    job=daily_update_job,
    cron_schedule="0 */6 * * *",  # Every 6 hours
    description="Incremental update: fetch last 24 hours of data every 6 hours"
)

# ============================================================================
# SCHEDULE 3: Weekly Gap Fill (Sunday 3 AM UTC)
# ============================================================================

weekly_gap_fill_schedule = ScheduleDefinition(
    name="weekly_gap_fill",
    job=fill_gaps_job,
    cron_schedule="0 3 * * 0",  # 3 AM UTC every Sunday
    description="Weekly gap fill: systematically fill largest gap found in data"
)
