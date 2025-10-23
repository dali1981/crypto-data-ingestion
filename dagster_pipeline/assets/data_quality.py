"""Data quality detection assets."""

from dagster import asset, Output, AssetExecutionContext, AssetIn
from datetime import datetime
from typing import Dict, List
import pandas as pd
from dagster_pipeline.config import SYMBOLS


@asset(
    group_name="data_quality",
    compute_kind="duckdb",
    description="Detect duplicate records in aggregated trades",
    required_resource_keys={"duckdb_query"}
)
def duplicate_detection(
    context: AssetExecutionContext
) -> Output[Dict]:
    """
    Count duplicate records by agg_trade_id across all symbols.

    Returns:
        Dict with duplicate counts and breakdown by symbol
    """
    duckdb_query = context.resources.duckdb_query

    # Overall duplicate count
    result_df = duckdb_query.query("""
        SELECT COUNT(*) - COUNT(DISTINCT agg_trade_id) as duplicate_count
        FROM binance_data.agg_trades
    """)

    duplicate_count = int(result_df.iloc[0, 0]) if not result_df.empty else 0

    # Breakdown by symbol
    breakdown_df = duckdb_query.query("""
        WITH dup_records AS (
            SELECT symbol, agg_trade_id, COUNT(*) as count
            FROM binance_data.agg_trades
            GROUP BY symbol, agg_trade_id
            HAVING COUNT(*) > 1
        )
        SELECT symbol, SUM(count - 1) as dup_count
        FROM dup_records
        GROUP BY symbol
        ORDER BY dup_count DESC
    """)

    breakdown = dict(zip(breakdown_df['symbol'], breakdown_df['dup_count'])) if not breakdown_df.empty else {}

    context.log.info(f"\n{'='*80}")
    context.log.info(f"DUPLICATE DETECTION")
    context.log.info(f"{'='*80}")
    context.log.info(f"Total duplicates: {duplicate_count:,}")

    if breakdown:
        context.log.warning("\nDuplicates by symbol:")
        for symbol, count in breakdown.items():
            context.log.warning(f"  {symbol}: {count:,}")
    else:
        context.log.info("✅ No duplicates found!")

    return Output(
        value={
            "duplicate_count": duplicate_count,
            "breakdown": breakdown,
            "has_duplicates": duplicate_count > 0,
            "symbols_affected": len(breakdown),
            "timestamp": datetime.now().isoformat()
        },
        metadata={
            "duplicate_count": duplicate_count,
            "symbols_affected": len(breakdown),
            "detection_time": datetime.now().isoformat(),
        }
    )


@asset(
    group_name="data_quality",
    compute_kind="duckdb",
    description="Detect time gaps (>1 hour) in trade data",
    required_resource_keys={"duckdb_query"}
)
def gap_detection(
    context: AssetExecutionContext
) -> Output[List[Dict]]:
    """
    Find time gaps > 1 hour in the data for each symbol.

    Returns:
        List of gaps with start/end timestamps and duration
    """
    duckdb_query = context.resources.duckdb_query

    # Find gaps > 1 hour
    min_gap_ms = 3600000  # 1 hour in milliseconds

    gaps_df = duckdb_query.query(f"""
        WITH time_diffs AS (
            SELECT
                symbol,
                timestamp,
                LAG(timestamp) OVER (PARTITION BY symbol ORDER BY timestamp) as prev_timestamp,
                timestamp - LAG(timestamp) OVER (PARTITION BY symbol ORDER BY timestamp) as gap_ms
            FROM binance_data.agg_trades
        )
        SELECT symbol, prev_timestamp, timestamp, gap_ms
        FROM time_diffs
        WHERE gap_ms > {min_gap_ms}
        ORDER BY gap_ms DESC
    """)

    gap_list = []
    if not gaps_df.empty:
        for _, row in gaps_df.iterrows():
            gap_list.append({
                'symbol': row['symbol'],
                'start': datetime.fromtimestamp(row['prev_timestamp'] / 1000),
                'end': datetime.fromtimestamp(row['timestamp'] / 1000),
                'start_ts': row['prev_timestamp'],
                'end_ts': row['timestamp'],
                'hours': row['gap_ms'] / 3600000,
                'days': row['gap_ms'] / 86400000
            })

    context.log.info(f"\n{'='*80}")
    context.log.info(f"GAP DETECTION")
    context.log.info(f"{'='*80}")
    context.log.info(f"Total gaps (>1 hour): {len(gap_list)}")

    if gap_list:
        # Group by symbol
        by_symbol = {}
        for gap in gap_list:
            symbol = gap['symbol']
            if symbol not in by_symbol:
                by_symbol[symbol] = []
            by_symbol[symbol].append(gap)

        context.log.warning(f"\nGaps by symbol:")
        for symbol, gaps in sorted(by_symbol.items()):
            total_gap_days = sum(g['days'] for g in gaps)
            context.log.warning(f"  {symbol}: {len(gaps)} gap(s), {total_gap_days:.1f} total days")

            # Log largest gap per symbol
            largest = max(gaps, key=lambda g: g['days'])
            context.log.warning(
                f"    Largest: {largest['days']:.1f} days "
                f"({largest['start']} to {largest['end']})"
            )
    else:
        context.log.info("✅ No gaps found!")

    return Output(
        value=gap_list,
        metadata={
            "gap_count": len(gap_list),
            "largest_gap_days": round(gap_list[0]['days'], 1) if gap_list else 0,
            "symbols_with_gaps": len(set(g['symbol'] for g in gap_list)),
            "detection_time": datetime.now().isoformat(),
        }
    )
