"""Data cleaning assets."""

from dagster import asset, Output, AssetExecutionContext, AssetIn
from datetime import datetime, timedelta
from typing import Dict, List
import sys
from pathlib import Path

# Add project root to path to import jobs module
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


@asset(
    ins={"duplicates": AssetIn("duplicate_detection")},
    group_name="data_cleaning",
    compute_kind="duckdb",
    description="Remove duplicate records (keeps first occurrence)",
    required_resource_keys={"duckdb_query"}
)
def deduplicate_trades(
    context: AssetExecutionContext,
    duplicates: Dict
) -> Output[int]:
    """
    Remove duplicates from agg_trades Parquet files.

    NOTE: With Parquet-first architecture, this asset needs refactoring.
    Currently uses DuckDB views for deduplication detection only.
    Full deduplication should rebuild Parquet files with unique records.

    Returns:
        Number of duplicates detected
    """
    if not duplicates["has_duplicates"]:
        context.log.info("No duplicates found - skipping deduplication")
        return Output(
            value=0,
            metadata={
                "duplicates_detected": 0,
                "skipped": True
            }
        )

    duplicate_count = duplicates["duplicate_count"]
    context.log.info(f"\n{'='*80}")
    context.log.info(f"DEDUPLICATION STATUS")
    context.log.info(f"{'='*80}")
    context.log.info(f"⚠️  Duplicates detected: {duplicate_count:,}")
    context.log.info(f"⚠️  This asset needs refactoring for Parquet-first architecture")
    context.log.info(f"⚠️  Deduplication should rebuild Parquet files, not modify DuckDB")

    # For now, just return the count
    return Output(
        value=duplicate_count,
        metadata={
            "duplicates_detected": duplicate_count,
            "symbols_affected": duplicates.get("symbols_affected", 0),
            "needs_refactoring": True,
            "detection_time": datetime.now().isoformat(),
        }
    )


@asset(
    ins={"gaps": AssetIn("gap_detection")},
    group_name="data_cleaning",
    compute_kind="binance_api",
    description="Fill largest gap found in data using adaptive chunking",
    required_resource_keys={"duckdb_query"}
)
def fill_largest_gap(
    context: AssetExecutionContext,
    gaps: List[Dict]
) -> Output[int]:
    """
    Identify the largest gap for filling.

    NOTE: With Parquet-first architecture, this asset needs refactoring.
    Gap filling should fetch data and return DataFrame for I/O manager to append.

    Returns:
        Gap information (not yet implemented as DataFrame return)
    """
    if not gaps:
        context.log.info("No gaps found - skipping gap fill")
        return Output(
            value=0,
            metadata={
                "gap_size_days": 0,
                "skipped": True
            }
        )

    # Get largest gap
    largest_gap = gaps[0]

    context.log.info(f"\n{'='*80}")
    context.log.info(f"LARGEST GAP IDENTIFIED")
    context.log.info(f"{'='*80}")
    context.log.info(f"Symbol: {largest_gap['symbol']}")
    context.log.info(f"Duration: {largest_gap['days']:.1f} days ({largest_gap['hours']:.1f} hours)")
    context.log.info(f"From: {largest_gap['start']}")
    context.log.info(f"To: {largest_gap['end']}")
    context.log.info(f"⚠️  This asset needs refactoring for Parquet-first architecture")
    context.log.info(f"⚠️  Should fetch gap data and return DataFrame for I/O manager")

    return Output(
        value=int(largest_gap['days']),
        metadata={
            "gap_size_days": round(largest_gap['days'], 1),
            "gap_size_hours": round(largest_gap['hours'], 1),
            "symbol": largest_gap['symbol'],
            "start_ts": largest_gap['start_ts'],
            "end_ts": largest_gap['end_ts'],
            "needs_refactoring": True,
            "detection_time": datetime.now().isoformat(),
        }
    )


@asset(
    group_name="data_cleaning",
    compute_kind="binance_api",
    description="Incremental daily update: fill recent data (last 24 hours) for all symbols",
    required_resource_keys={"duckdb_query"}
)
def fill_recent_data(
    context: AssetExecutionContext
) -> Output[Dict]:
    """
    Identify symbols needing recent data updates.

    NOTE: With Parquet-first architecture, this asset needs refactoring.
    Should be merged with raw_agg_trades asset or removed as duplicate functionality.
    raw_agg_trades already does incremental fetching.

    Returns:
        Dict with status (refactoring needed)
    """
    from dagster_pipeline.config import SYMBOLS

    context.log.info(f"\n{'='*80}")
    context.log.info(f"RECENT DATA STATUS CHECK")
    context.log.info(f"{'='*80}")
    context.log.info(f"Checking {len(SYMBOLS)} symbols")
    context.log.info(f"⚠️  This asset duplicates raw_agg_trades functionality")
    context.log.info(f"⚠️  raw_agg_trades already does incremental fetching")
    context.log.info(f"⚠️  Consider removing this asset or refactoring")

    all_stats = {}

    for symbol in SYMBOLS:
        all_stats[symbol] = {
            "status": "needs_refactoring",
            "message": "Use raw_agg_trades for incremental updates"
        }

    return Output(
        value=all_stats,
        metadata={
            "symbols_processed": len(SYMBOLS),
            "needs_refactoring": True,
            "duplicate_of": "raw_agg_trades",
            "check_time": datetime.now().isoformat(),
        }
    )
