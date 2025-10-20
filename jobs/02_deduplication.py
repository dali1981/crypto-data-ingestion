"""
Job 2: Deduplication

This job removes duplicate records based on agg_trade_id.
Runs AFTER quality assessment and BEFORE gap filling.

Features:
- Safe deduplication with backup
- Keeps first occurrence of each agg_trade_id
- Dry-run mode for safety
- Progress reporting
"""

import duckdb
from datetime import datetime
from pathlib import Path
import sys
import json


class Deduplicator:
    """Remove duplicate records from the database."""

    def __init__(self, db_path: str = "binance_pipeline.duckdb"):
        self.db_path = db_path
        self.conn = None
        self.stats = {
            'timestamp': datetime.now().isoformat(),
            'duplicates_found': 0,
            'duplicates_removed': 0,
            'records_before': 0,
            'records_after': 0,
            'backup_created': False
        }

    def __enter__(self):
        if not Path(self.db_path).exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")

        # Open with read-write access
        self.conn = duckdb.connect(self.db_path, read_only=False)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()

    def count_duplicates(self) -> int:
        """Count duplicate records."""
        result = self.conn.execute("""
            SELECT COUNT(*) - COUNT(DISTINCT agg_trade_id) as duplicate_count
            FROM binance_data.agg_trades
        """).fetchone()

        return result[0]

    def get_duplicate_breakdown(self) -> dict:
        """Get duplicate count by symbol."""
        results = self.conn.execute("""
            WITH dup_records AS (
                SELECT symbol, agg_trade_id, COUNT(*) as count
                FROM binance_data.agg_trades
                GROUP BY symbol, agg_trade_id
                HAVING COUNT(*) > 1
            )
            SELECT symbol, SUM(count - 1) as dup_count
            FROM dup_records
            GROUP BY symbol
        """).fetchall()

        return {symbol: count for symbol, count in results}

    def create_backup(self) -> bool:
        """Create backup table before deduplication."""
        try:
            print("\n📦 Creating backup table...")

            # Drop old backup if exists
            self.conn.execute("DROP TABLE IF EXISTS binance_data.agg_trades_backup")

            # Create new backup
            self.conn.execute("""
                CREATE TABLE binance_data.agg_trades_backup AS
                SELECT * FROM binance_data.agg_trades
            """)

            # Verify backup
            backup_count = self.conn.execute("""
                SELECT COUNT(*) FROM binance_data.agg_trades_backup
            """).fetchone()[0]

            print(f"   ✅ Backup created with {backup_count:,} records")
            print(f"   Table: binance_data.agg_trades_backup")

            self.stats['backup_created'] = True
            return True

        except Exception as e:
            print(f"   ❌ Backup failed: {e}")
            return False

    def remove_duplicates(self) -> int:
        """Remove duplicate records, keeping first occurrence."""
        print("\n🗑️  Removing duplicates...")

        try:
            # Get count before
            self.stats['records_before'] = self.conn.execute("""
                SELECT COUNT(*) FROM binance_data.agg_trades
            """).fetchone()[0]

            # Delete duplicates (keep first occurrence by rowid)
            self.conn.execute("""
                DELETE FROM binance_data.agg_trades
                WHERE rowid NOT IN (
                    SELECT MIN(rowid)
                    FROM binance_data.agg_trades
                    GROUP BY agg_trade_id
                )
            """)

            # Get count after
            self.stats['records_after'] = self.conn.execute("""
                SELECT COUNT(*) FROM binance_data.agg_trades
            """).fetchone()[0]

            removed = self.stats['records_before'] - self.stats['records_after']
            self.stats['duplicates_removed'] = removed

            print(f"   ✅ Removed {removed:,} duplicate records")
            print(f"   Before: {self.stats['records_before']:,} records")
            print(f"   After:  {self.stats['records_after']:,} records")

            return removed

        except Exception as e:
            print(f"   ❌ Deduplication failed: {e}")
            raise

    def verify_no_duplicates(self) -> bool:
        """Verify that all duplicates have been removed."""
        remaining = self.count_duplicates()

        if remaining == 0:
            print("\n✅ Verification passed: No duplicates remain")
            return True
        else:
            print(f"\n⚠️  Verification failed: {remaining:,} duplicates still exist")
            return False

    def run(self, dry_run: bool = True) -> dict:
        """Run deduplication process."""
        print("=" * 80)
        print("DEDUPLICATION JOB")
        print("=" * 80)
        print(f"Database: {self.db_path}")
        print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
        print()

        # Count duplicates
        print("🔍 Analyzing duplicates...")
        duplicates = self.count_duplicates()
        self.stats['duplicates_found'] = duplicates

        if duplicates == 0:
            print("   ✅ No duplicates found!")
            self.stats['status'] = 'no_duplicates'
            return self.stats

        print(f"   Found {duplicates:,} duplicate records")

        # Breakdown by symbol
        breakdown = self.get_duplicate_breakdown()
        print("\n   Breakdown by symbol:")
        for symbol, count in breakdown.items():
            print(f"     {symbol}: {count:,}")

        if dry_run:
            print("\n" + "=" * 80)
            print("DRY RUN - No changes will be made")
            print("=" * 80)
            print(f"\nTo actually remove duplicates, run:")
            print("  uv run python jobs/02_deduplication.py --execute")
            print()
            print("This will:")
            print(f"  1. Create backup table with {self.stats['records_before'] or 'all'} records")
            print(f"  2. Remove {duplicates:,} duplicate records")
            print(f"  3. Keep first occurrence of each agg_trade_id")

            self.stats['status'] = 'dry_run'
            return self.stats

        # Execute deduplication
        print("\n" + "=" * 80)
        print("EXECUTING DEDUPLICATION")
        print("=" * 80)

        # Step 1: Create backup
        if not self.create_backup():
            print("\n❌ Deduplication aborted - backup failed")
            self.stats['status'] = 'backup_failed'
            return self.stats

        # Step 2: Remove duplicates
        try:
            self.remove_duplicates()
        except Exception as e:
            print(f"\n❌ Deduplication failed: {e}")
            print("\n🔄 You can restore from backup:")
            print("   DROP TABLE binance_data.agg_trades;")
            print("   ALTER TABLE binance_data.agg_trades_backup RENAME TO agg_trades;")
            self.stats['status'] = 'failed'
            return self.stats

        # Step 3: Verify
        if self.verify_no_duplicates():
            self.stats['status'] = 'success'

            print("\n" + "=" * 80)
            print("✅ DEDUPLICATION COMPLETE")
            print("=" * 80)
            print(f"\nRemoved: {self.stats['duplicates_removed']:,} records")
            print(f"Remaining: {self.stats['records_after']:,} records")
            print(f"\n💾 Backup table preserved: binance_data.agg_trades_backup")
            print("\nTo drop backup (after verifying):")
            print("  DROP TABLE binance_data.agg_trades_backup;")

        else:
            self.stats['status'] = 'verification_failed'
            print("\n⚠️  Verification failed - some duplicates may remain")

        return self.stats

    def save_report(self, output_dir: str = "jobs/reports"):
        """Save deduplication report."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        report_file = output_path / f"deduplication_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(report_file, 'w') as f:
            json.dump(self.stats, f, indent=2)

        print(f"\n📄 Report saved: {report_file}")

        # Also save as latest
        latest_file = output_path / "deduplication_latest.json"
        with open(latest_file, 'w') as f:
            json.dump(self.stats, f, indent=2)


def main():
    """Run deduplication job."""
    import argparse

    parser = argparse.ArgumentParser(description="Remove duplicate records")
    parser.add_argument('--db-path', default='binance_pipeline.duckdb',
                       help='Path to DuckDB database')
    parser.add_argument('--execute', action='store_true',
                       help='Actually remove duplicates (default is dry-run)')
    parser.add_argument('--output-dir', default='jobs/reports',
                       help='Directory for output reports')

    args = parser.parse_args()

    try:
        with Deduplicator(args.db_path) as dedup:
            stats = dedup.run(dry_run=not args.execute)
            dedup.save_report(args.output_dir)

            # Exit with error if duplicates found but not removed
            if stats['status'] == 'dry_run':
                sys.exit(1)  # Duplicates found, need to run with --execute
            elif stats['status'] in ['success', 'no_duplicates']:
                sys.exit(0)  # Success
            else:
                sys.exit(2)  # Error occurred

    except FileNotFoundError as e:
        print(f"❌ {e}")
        sys.exit(3)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(4)


if __name__ == "__main__":
    main()
