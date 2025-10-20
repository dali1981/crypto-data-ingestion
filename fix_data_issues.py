"""
Fix Data Quality Issues

This script provides tools to:
1. Remove duplicate records (keeping unique agg_trade_ids)
2. Identify gaps that need to be filled
3. Generate commands to fill missing data
"""

import duckdb
from datetime import datetime, timedelta
from pathlib import Path
import sys


def remove_duplicates(db_path: str = "binance_pipeline.duckdb", dry_run: bool = True):
    """
    Remove duplicate records based on agg_trade_id.

    Args:
        db_path: Path to DuckDB database
        dry_run: If True, only report what would be done without making changes
    """
    print("=" * 80)
    print("DUPLICATE REMOVAL TOOL")
    print("=" * 80)

    # Open connection (read-only for dry run, read-write for actual removal)
    conn = duckdb.connect(db_path, read_only=dry_run)

    try:
        # Count duplicates
        result = conn.execute("""
            SELECT COUNT(*) - COUNT(DISTINCT agg_trade_id) as duplicate_count
            FROM binance_data.agg_trades
        """).fetchone()

        duplicate_count = result[0]

        if duplicate_count == 0:
            print("\n✓ No duplicates found!")
            return

        print(f"\n⚠ Found {duplicate_count:,} duplicate records")

        # Get duplicate details by symbol
        dup_by_symbol = conn.execute("""
            WITH all_records AS (
                SELECT symbol, agg_trade_id, COUNT(*) as count
                FROM binance_data.agg_trades
                GROUP BY symbol, agg_trade_id
                HAVING COUNT(*) > 1
            )
            SELECT symbol, SUM(count - 1) as dup_count
            FROM all_records
            GROUP BY symbol
        """).fetchall()

        print("\nDuplicates by symbol:")
        for row in dup_by_symbol:
            print(f"  {row[0]}: {row[1]:,} duplicates")

        if dry_run:
            print("\n" + "=" * 80)
            print("DRY RUN MODE - No changes will be made")
            print("=" * 80)
            print("\nTo actually remove duplicates, run:")
            print("  uv run python fix_data_issues.py --remove-duplicates")
            print("\nThis will:")
            print("  1. Keep the first occurrence of each agg_trade_id")
            print("  2. Delete all subsequent duplicates")
            print(f"  3. Free up ~{duplicate_count:,} records worth of space")
        else:
            print("\n" + "=" * 80)
            print("REMOVING DUPLICATES...")
            print("=" * 80)

            # Create a backup table first
            print("\n1. Creating backup table...")
            conn.execute("DROP TABLE IF EXISTS binance_data.agg_trades_backup")
            conn.execute("""
                CREATE TABLE binance_data.agg_trades_backup AS
                SELECT * FROM binance_data.agg_trades
            """)
            print("   ✓ Backup created: binance_data.agg_trades_backup")

            # Remove duplicates (keep first occurrence)
            print("\n2. Removing duplicates...")
            conn.execute("""
                DELETE FROM binance_data.agg_trades
                WHERE rowid NOT IN (
                    SELECT MIN(rowid)
                    FROM binance_data.agg_trades
                    GROUP BY agg_trade_id
                )
            """)
            print("   ✓ Duplicates removed")

            # Verify
            result = conn.execute("""
                SELECT COUNT(*) - COUNT(DISTINCT agg_trade_id) as duplicate_count
                FROM binance_data.agg_trades
            """).fetchone()

            remaining_dups = result[0]

            if remaining_dups == 0:
                print("\n✓ SUCCESS: All duplicates removed!")
                print(f"   Removed {duplicate_count:,} duplicate records")
                print("\n💡 Backup table 'agg_trades_backup' has been created")
                print("   You can drop it once you verify everything is working:")
                print("   DROP TABLE binance_data.agg_trades_backup;")
            else:
                print(f"\n⚠ WARNING: {remaining_dups:,} duplicates still remain")
                print("   This shouldn't happen. Please investigate.")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


def generate_gap_fill_commands(db_path: str = "binance_pipeline.duckdb"):
    """Generate commands to fill data gaps."""
    print("=" * 80)
    print("GAP FILLING GUIDE")
    print("=" * 80)

    conn = duckdb.connect(db_path, read_only=True)

    try:
        # Get symbols
        symbols = conn.execute("""
            SELECT DISTINCT symbol FROM binance_data.agg_trades
        """).fetchall()

        for symbol_tuple in symbols:
            symbol = symbol_tuple[0]

            print(f"\n{symbol}")
            print("-" * 80)

            # Get data range
            result = conn.execute(f"""
                SELECT
                    MIN(timestamp) as first_ts,
                    MAX(timestamp) as last_ts
                FROM binance_data.agg_trades
                WHERE symbol = '{symbol}'
            """).fetchone()

            first_ts, last_ts = result
            first_dt = datetime.fromtimestamp(first_ts / 1000)
            last_dt = datetime.fromtimestamp(last_ts / 1000)

            print(f"Current data: {first_dt} to {last_dt}")

            # Find gaps > 1 hour
            gaps = conn.execute(f"""
                WITH time_diffs AS (
                    SELECT
                        timestamp,
                        LAG(timestamp) OVER (ORDER BY timestamp) as prev_timestamp,
                        timestamp - LAG(timestamp) OVER (ORDER BY timestamp) as gap_ms
                    FROM binance_data.agg_trades
                    WHERE symbol = '{symbol}'
                )
                SELECT prev_timestamp, timestamp, gap_ms
                FROM time_diffs
                WHERE gap_ms > 3600000  -- 1 hour
                ORDER BY gap_ms DESC
                LIMIT 5
            """).fetchall()

            if gaps:
                print(f"\n⚠ Found {len(gaps)} gap(s) > 1 hour")
                print("\nCommands to fill gaps:")

                for i, gap in enumerate(gaps, 1):
                    prev_ts, curr_ts, gap_ms = gap
                    start_dt = datetime.fromtimestamp(prev_ts / 1000)
                    end_dt = datetime.fromtimestamp(curr_ts / 1000)
                    gap_hours = gap_ms / 3600000

                    print(f"\n  Gap #{i}: {gap_hours:.1f} hours ({start_dt} to {end_dt})")

                    # Generate date range for download
                    start_date = start_dt.strftime('%Y-%m-%d')

                    print(f"  uv run python -m binance_tick_data.pipelines.historical_pipeline \\")
                    print(f"    --symbols {symbol} \\")
                    print(f"    --start-date {start_date} \\")
                    print(f"    --max-records 50000")
            else:
                print("\n✓ No significant gaps (all < 1 hour)")

            # Check if missing recent data
            now = datetime.now()
            hours_since_last = (now - last_dt).total_seconds() / 3600

            if hours_since_last > 1:
                print(f"\n⚠ Missing recent data (last: {last_dt}, {hours_since_last:.1f} hours ago)")
                print("\nTo get recent data:")
                print(f"  uv run python -m binance_tick_data.pipelines.historical_pipeline \\")
                print(f"    --symbols {symbol} \\")
                print(f"    --start-date {last_dt.strftime('%Y-%m-%d')} \\")
                print(f"    --max-records 50000")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Fix data quality issues")
    parser.add_argument('--remove-duplicates', action='store_true',
                       help='Actually remove duplicates (default is dry-run)')
    parser.add_argument('--gap-commands', action='store_true',
                       help='Generate commands to fill data gaps')
    parser.add_argument('--db-path', default='binance_pipeline.duckdb',
                       help='Path to DuckDB database')

    args = parser.parse_args()

    if not Path(args.db_path).exists():
        print(f"❌ Database not found: {args.db_path}")
        sys.exit(1)

    if args.remove_duplicates:
        # Actual removal (not dry-run)
        response = input("\n⚠ This will modify the database. Continue? (yes/no): ")
        if response.lower() == 'yes':
            remove_duplicates(args.db_path, dry_run=False)
        else:
            print("Cancelled.")
    elif args.gap_commands:
        generate_gap_fill_commands(args.db_path)
    else:
        # Default: show both dry-run and gap commands
        remove_duplicates(args.db_path, dry_run=True)
        print("\n\n")
        generate_gap_fill_commands(args.db_path)


if __name__ == "__main__":
    main()
