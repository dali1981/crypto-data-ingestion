"""Data cleaning assets."""

from dagster import asset, Output, AssetExecutionContext, AssetIn
from datetime import datetime, timedelta
from typing import Dict, List
import sys
from pathlib import Path

# Add project root to path to import jobs module
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


@asset(
    ins={"duplicates": AssetIn("duplicate_detection")},
    group_name="data_cleaning",
    compute_kind="duckdb",
    description="Remove duplicate records (keeps first occurrence)"
)
def deduplicate_trades(
    context: AssetExecutionContext,
    duckdb_conn,
    duplicates: Dict
) -> Output[int]:
    """
    Remove duplicates from agg_trades table.

    Only runs if duplicates detected.
    Creates backup before deletion.

    Returns:
        Number of duplicates removed
    """
    if not duplicates["has_duplicates"]:
        context.log.info("No duplicates found - skipping deduplication")
        return Output(
            value=0,
            metadata={
                "duplicates_removed": 0,
                "skipped": True
            }
        )

    duplicate_count = duplicates["duplicate_count"]
    context.log.info(f"\n{'='*80}")
    context.log.info(f"DEDUPLICATION")
    context.log.info(f"{'='*80}")
    context.log.info(f"Duplicates to remove: {duplicate_count:,}")

    conn = duckdb_conn.get_connection()

    # Create backup
    context.log.info("\n📦 Creating backup table...")
    conn.execute("DROP TABLE IF EXISTS binance_data.agg_trades_backup")
    conn.execute("""
        CREATE TABLE binance_data.agg_trades_backup AS
        SELECT * FROM binance_data.agg_trades
    """)

    backup_count = conn.execute("""
        SELECT COUNT(*) FROM binance_data.agg_trades_backup
    """).fetchone()[0]

    context.log.info(f"   ✅ Backup created: {backup_count:,} records")

    # Get count before
    records_before = conn.execute("""
        SELECT COUNT(*) FROM binance_data.agg_trades
    """).fetchone()[0]

    # Delete duplicates (keep first occurrence by rowid)
    context.log.info("\n🗑️  Removing duplicates...")
    conn.execute("""
        DELETE FROM binance_data.agg_trades
        WHERE rowid NOT IN (
            SELECT MIN(rowid)
            FROM binance_data.agg_trades
            GROUP BY agg_trade_id
        )
    """)

    # Get count after
    records_after = conn.execute("""
        SELECT COUNT(*) FROM binance_data.agg_trades
    """).fetchone()[0]

    removed = records_before - records_after

    # Verify
    remaining_dups = conn.execute("""
        SELECT COUNT(*) - COUNT(DISTINCT agg_trade_id)
        FROM binance_data.agg_trades
    """).fetchone()[0]

    conn.close()

    context.log.info(f"\n{'='*80}")
    context.log.info(f"DEDUPLICATION COMPLETE")
    context.log.info(f"{'='*80}")
    context.log.info(f"Removed: {removed:,} duplicates")
    context.log.info(f"Before: {records_before:,} records")
    context.log.info(f"After: {records_after:,} records")
    context.log.info(f"Remaining duplicates: {remaining_dups:,}")
    context.log.info(f"\n💾 Backup preserved: binance_data.agg_trades_backup")

    if remaining_dups > 0:
        context.log.warning(f"⚠️  {remaining_dups} duplicates still remain!")

    return Output(
        value=removed,
        metadata={
            "duplicates_removed": removed,
            "records_before": records_before,
            "records_after": records_after,
            "remaining_duplicates": remaining_dups,
            "backup_table": "binance_data.agg_trades_backup",
            "cleanup_time": datetime.now().isoformat(),
        }
    )


@asset(
    ins={"gaps": AssetIn("gap_detection")},
    group_name="data_cleaning",
    compute_kind="binance_api",
    description="Fill largest gap found in data using adaptive chunking"
)
def fill_largest_gap(
    context: AssetExecutionContext,
    duckdb_conn,
    gaps: List[Dict]
) -> Output[int]:
    """
    Fill the largest gap (if any) using adaptive chunking.

    Only fills one gap per run to avoid API rate limits.

    Returns:
        Number of records added
    """
    if not gaps:
        context.log.info("No gaps found - skipping gap fill")
        return Output(
            value=0,
            metadata={
                "records_added": 0,
                "skipped": True
            }
        )

    # Get largest gap
    largest_gap = gaps[0]

    context.log.info(f"\n{'='*80}")
    context.log.info(f"FILLING LARGEST GAP")
    context.log.info(f"{'='*80}")
    context.log.info(f"Symbol: {largest_gap['symbol']}")
    context.log.info(f"Duration: {largest_gap['days']:.1f} days ({largest_gap['hours']:.1f} hours)")
    context.log.info(f"From: {largest_gap['start']}")
    context.log.info(f"To: {largest_gap['end']}")

    # Use existing GapFiller logic
    from jobs.fill_gaps import GapFiller

    try:
        with GapFiller(db_path=duckdb_conn.db_path) as filler:
            stats = filler.fill_date_range(
                symbol=largest_gap['symbol'],
                start_date=largest_gap['start'],
                end_date=largest_gap['end'],
                max_records=50000
            )

        records_added = stats.get('records_added', 0)
        chunks_processed = stats.get('chunks_processed', 0)
        status = stats.get('status', 'unknown')

        context.log.info(f"\n{'='*80}")
        context.log.info(f"GAP FILL COMPLETE")
        context.log.info(f"{'='*80}")
        context.log.info(f"Status: {status}")
        context.log.info(f"Records added: {records_added:,}")
        context.log.info(f"Chunks processed: {chunks_processed}")

        return Output(
            value=records_added,
            metadata={
                "records_added": records_added,
                "chunks_processed": chunks_processed,
                "gap_days": round(largest_gap['days'], 1),
                "gap_hours": round(largest_gap['hours'], 1),
                "symbol": largest_gap['symbol'],
                "status": status,
                "fill_time": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        context.log.error(f"❌ Failed to fill gap: {e}")
        return Output(
            value=0,
            metadata={
                "records_added": 0,
                "error": str(e),
                "symbol": largest_gap['symbol'],
            }
        )


@asset(
    group_name="data_cleaning",
    compute_kind="binance_api",
    description="Incremental daily update: fill recent data (last 24 hours) for all symbols"
)
def fill_recent_data(
    context: AssetExecutionContext,
    duckdb_conn
) -> Output[Dict]:
    """
    Incremental update: Fill last 24 hours for all symbols.

    This is the daily maintenance job - keeps data fresh.

    Returns:
        Dict with statistics per symbol
    """
    from jobs.fill_gaps import GapFiller
    from ..config import SYMBOLS

    context.log.info(f"\n{'='*80}")
    context.log.info(f"DAILY INCREMENTAL UPDATE")
    context.log.info(f"{'='*80}")
    context.log.info(f"Updating {len(SYMBOLS)} symbols")

    all_stats = {}
    total_records = 0

    for symbol in SYMBOLS:
        context.log.info(f"\n{'─'*80}")
        context.log.info(f"Updating {symbol}...")
        context.log.info(f"{'─'*80}")

        try:
            with GapFiller(db_path=duckdb_conn.db_path) as filler:
                stats = filler.fill_recent(
                    symbol=symbol,
                    hours=24,
                    max_records=50000
                )

            records_added = stats.get('records_added', 0)
            status = stats.get('status', 'unknown')

            context.log.info(f"  ✅ {symbol}: {records_added:,} records added ({status})")

            all_stats[symbol] = {
                "records_added": records_added,
                "status": status,
                "chunks_processed": stats.get('chunks_processed', 0)
            }

            total_records += records_added

        except Exception as e:
            context.log.error(f"  ❌ {symbol} failed: {e}")
            all_stats[symbol] = {
                "records_added": 0,
                "status": "failed",
                "error": str(e)
            }

    context.log.info(f"\n{'='*80}")
    context.log.info(f"DAILY UPDATE COMPLETE")
    context.log.info(f"{'='*80}")
    context.log.info(f"Total records added: {total_records:,}")
    context.log.info(f"Symbols updated: {len([s for s, st in all_stats.items() if st['records_added'] > 0])}/{len(SYMBOLS)}")

    return Output(
        value=all_stats,
        metadata={
            "total_records": total_records,
            "symbols_processed": len(SYMBOLS),
            "symbols_updated": len([s for s, st in all_stats.items() if st['records_added'] > 0]),
            "update_time": datetime.now().isoformat(),
        }
    )
