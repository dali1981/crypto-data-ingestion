"""Job definitions for Dagster pipeline."""

from dagster import define_asset_job, AssetSelection

# Note: Jobs are defined using AssetSelection which doesn't need imports

# ============================================================================
# JOB 1: Fetch Latest Data
# ============================================================================

fetch_latest_job = define_asset_job(
    name="fetch_latest",
    selection=AssetSelection.groups("raw_data"),  # Select all assets in raw_data group
    description="Fetch latest data from Binance API for all symbols (append mode)"
)

# ============================================================================
# JOB 2: Detect Issues
# ============================================================================

detect_issues_job = define_asset_job(
    name="detect_issues",
    selection=AssetSelection.groups("data_quality"),  # Select all assets in data_quality group
    description="Scan database for duplicates and gaps"
)

# ============================================================================
# JOB 3: Cleanup Duplicates
# ============================================================================

cleanup_duplicates_job = define_asset_job(
    name="cleanup_duplicates",
    selection=AssetSelection.groups("data_cleaning"),  # All cleaning assets
    description="Remove duplicate records from database"
)

# ============================================================================
# JOB 4: Fill Gaps
# ============================================================================

fill_gaps_job = define_asset_job(
    name="fill_gaps",
    selection=AssetSelection.groups("data_cleaning"),  # All cleaning assets
    description="Fill largest gap in data using adaptive chunking"
)

# ============================================================================
# JOB 5: Daily Incremental Update
# ============================================================================

daily_update_job = define_asset_job(
    name="daily_update",
    selection=AssetSelection.groups("data_cleaning"),  # All cleaning assets
    description="Daily job: fetch last 24 hours of data for all symbols"
)

# ============================================================================
# JOB 6: Full Maintenance Pipeline
# ============================================================================

full_maintenance_job = define_asset_job(
    name="full_maintenance",
    selection=AssetSelection.all(),
    description="Complete pipeline: fetch latest data, detect issues, and clean database"
)
