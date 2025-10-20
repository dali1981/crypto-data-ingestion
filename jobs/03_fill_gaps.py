"""
Job 3: Incremental Gap Filling

This job intelligently fills data gaps:
- Handles gaps larger than max_records by breaking into chunks
- Can fill specific date ranges or recent data
- Runs incrementally (daily) to keep data fresh
- Respects API rate limits
- Tracks progress and can resume

Usage:
  # Fill all gaps for a symbol
  uv run python jobs/03_fill_gaps.py --symbol BTCUSDT

  # Fill specific date range (auto-chunks if needed)
  uv run python jobs/03_fill_gaps.py --symbol BTCUSDT --start-date 2025-10-01 --end-date 2025-10-20

  # Daily job: get last 24 hours
  uv run python jobs/03_fill_gaps.py --symbol BTCUSDT --recent

  # Fill largest gaps first
  uv run python jobs/03_fill_gaps.py --symbol BTCUSDT --fill-largest-gap
"""

import duckdb
from datetime import datetime, timedelta
from pathlib import Path
import sys
import json
import time
from typing import List, Dict, Optional, Tuple
import dlt
from binance_tick_data import BinanceConfig, binance_historical_data


class GapFiller:
    """Intelligently fill data gaps with adaptive chunking."""

    def __init__(self, db_path: str = "binance_pipeline.duckdb"):
        self.db_path = db_path
        self.conn = None
        self.stats = {
            'timestamp': datetime.now().isoformat(),
            'symbol': None,
            'chunks_processed': 0,
            'chunks_total': 0,
            'records_added': 0,
            'gaps_filled': [],
            'status': 'pending'
        }
        # Adaptive learning
        self.observed_records_per_hour = []  # Track actual density
        self.estimated_records_per_hour = 4000  # Initial estimate

    def __enter__(self):
        # Database may not exist yet - that's OK
        if Path(self.db_path).exists():
            self.conn = duckdb.connect(self.db_path, read_only=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()

    def find_gaps(self, symbol: str, min_gap_hours: float = 1.0) -> List[Dict]:
        """Find time gaps in the data."""
        if not self.conn:
            return []

        min_gap_ms = int(min_gap_hours * 3600 * 1000)

        try:
            gaps = self.conn.execute(f"""
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
                WHERE gap_ms > {min_gap_ms}
                ORDER BY gap_ms DESC
            """).fetchall()

            gap_list = []
            for prev_ts, curr_ts, gap_ms in gaps:
                gap_list.append({
                    'start': datetime.fromtimestamp(prev_ts / 1000),
                    'end': datetime.fromtimestamp(curr_ts / 1000),
                    'hours': gap_ms / 3600000,
                    'days': gap_ms / (86400000)
                })

            return gap_list

        except Exception:
            return []

    def get_data_range(self, symbol: str) -> Optional[Tuple[datetime, datetime]]:
        """Get current data range for symbol."""
        if not self.conn:
            return None

        try:
            result = self.conn.execute(f"""
                SELECT MIN(timestamp), MAX(timestamp)
                FROM binance_data.agg_trades
                WHERE symbol = '{symbol}'
            """).fetchone()

            if result and result[0]:
                first_dt = datetime.fromtimestamp(result[0] / 1000)
                last_dt = datetime.fromtimestamp(result[1] / 1000)
                return first_dt, last_dt

        except Exception:
            pass

        return None

    def get_adaptive_chunk_hours(self, max_records: int) -> float:
        """
        Calculate next chunk size based on observed data density.

        Learns from previous chunks and adapts in real-time.
        """
        # Use observed average if we have data, otherwise use estimate
        if self.observed_records_per_hour:
            avg_density = sum(self.observed_records_per_hour) / len(self.observed_records_per_hour)
            # Use pessimistic estimate (90th percentile)
            sorted_density = sorted(self.observed_records_per_hour, reverse=True)
            pessimistic_density = sorted_density[min(len(sorted_density) // 10, len(sorted_density) - 1)]

            print(f"\n📊 Adaptive learning:")
            print(f"   Observed chunks: {len(self.observed_records_per_hour)}")
            print(f"   Average density: {avg_density:,.0f} records/hour")
            print(f"   Pessimistic (p90): {pessimistic_density:,.0f} records/hour")

            # Use pessimistic estimate for safety
            records_per_hour = pessimistic_density
        else:
            records_per_hour = self.estimated_records_per_hour
            print(f"\n📊 Initial estimate: {records_per_hour:,} records/hour")

        # Calculate hours with 60% safety margin (more conservative)
        hours = (max_records * 0.6) / records_per_hour
        hours = max(0.5, min(hours, 6))  # Between 30 minutes and 6 hours

        print(f"   Next chunk size: {hours:.1f} hours (~{int(hours * records_per_hour):,} records)")

        return hours

    def record_chunk_density(self, hours: float, records: int):
        """Record observed data density from a completed chunk."""
        if hours > 0 and records > 0:
            density = records / hours
            self.observed_records_per_hour.append(density)
            print(f"   📈 Recorded: {density:,.0f} records/hour")

    def fetch_data_chunk(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        max_records: int = 50000
    ) -> Dict[str, any]:
        """
        Fetch data for a specific date range chunk.

        Returns dict with:
            - records_fetched: number of records
            - hit_limit: whether max_records was reached
            - actual_end_time: actual last timestamp fetched
        """
        hours = (end_date - start_date).total_seconds() / 3600
        print(f"\n📥 Fetching {symbol}")
        print(f"   From: {start_date}")
        print(f"   To:   {end_date}")
        print(f"   Duration: {hours:.1f} hours")
        print(f"   Max records: {max_records:,}")

        # Count records before
        records_before = 0
        if Path(self.db_path).exists():
            try:
                conn = duckdb.connect(self.db_path, read_only=True)
                result = conn.execute(f"SELECT COUNT(*) FROM binance_data.agg_trades WHERE symbol = '{symbol}'").fetchone()
                records_before = result[0] if result else 0
                conn.close()
            except Exception:
                pass

        config = BinanceConfig()
        config.symbols = [symbol]
        config.historical_start_date = start_date.strftime('%Y-%m-%d')
        config.historical_max_records = max_records

        # Create pipeline
        pipeline = dlt.pipeline(
            pipeline_name="binance_gap_filler",
            destination="duckdb",
            dataset_name="binance_data",
        )

        try:
            # Fetch data
            source = binance_historical_data(
                config,
                symbols=[symbol],
                start_date=config.historical_start_date
            )

            # Run with append mode
            load_info = pipeline.run(
                source,
                write_disposition="append",
                loader_file_format="parquet"
            )

            # Count records after
            records_after = 0
            actual_end_time = None
            try:
                conn = duckdb.connect(self.db_path, read_only=True)
                result = conn.execute(f"SELECT COUNT(*) FROM binance_data.agg_trades WHERE symbol = '{symbol}'").fetchone()
                records_after = result[0] if result else 0

                # Get actual last timestamp
                result = conn.execute(f"""
                    SELECT MAX(timestamp)
                    FROM binance_data.agg_trades
                    WHERE symbol = '{symbol}' AND timestamp >= {int(start_date.timestamp() * 1000)}
                """).fetchone()
                if result and result[0]:
                    actual_end_time = datetime.fromtimestamp(result[0] / 1000)

                conn.close()
            except Exception as e:
                print(f"   ⚠️  Could not count records: {e}")

            records_fetched = records_after - records_before
            hit_limit = records_fetched >= (max_records * 0.95)  # Consider 95% as hitting limit

            print(f"   ✅ Chunk complete")
            print(f"   Records fetched: {records_fetched:,}")
            if actual_end_time:
                print(f"   Actual end: {actual_end_time}")
            if hit_limit:
                print(f"   ⚠️  Hit max_records limit")

            # Record density for adaptive learning
            if records_fetched > 0:
                actual_hours = (actual_end_time - start_date).total_seconds() / 3600 if actual_end_time else hours
                self.record_chunk_density(actual_hours, records_fetched)

            return {
                'records_fetched': records_fetched,
                'hit_limit': hit_limit,
                'actual_end_time': actual_end_time or end_date,
                'planned_end_time': end_date
            }

        except Exception as e:
            print(f"   ❌ Chunk failed: {e}")
            raise

    def get_existing_data_ranges(self, symbol: str, start_date: datetime, end_date: datetime) -> List[Tuple[datetime, datetime]]:
        """
        Find which parts of the date range already have data.
        Returns list of (start, end) tuples for ranges WITH data.
        """
        if not Path(self.db_path).exists():
            return []

        try:
            conn = duckdb.connect(self.db_path, read_only=True)

            # Get all data points in the range
            result = conn.execute(f"""
                SELECT DISTINCT timestamp
                FROM binance_data.agg_trades
                WHERE symbol = '{symbol}'
                  AND timestamp >= {int(start_date.timestamp() * 1000)}
                  AND timestamp <= {int(end_date.timestamp() * 1000)}
                ORDER BY timestamp
            """).fetchall()

            conn.close()

            if not result:
                return []

            # Convert to datetime
            timestamps = [datetime.fromtimestamp(ts[0] / 1000) for ts in result]

            print(f"\n📊 Existing data analysis:")
            print(f"   Found {len(timestamps):,} unique timestamps in range")
            print(f"   First: {timestamps[0]}")
            print(f"   Last: {timestamps[-1]}")

            # Find continuous ranges (gap > 1 hour means new range)
            ranges = []
            range_start = timestamps[0]
            prev_ts = timestamps[0]

            for ts in timestamps[1:]:
                gap_hours = (ts - prev_ts).total_seconds() / 3600
                if gap_hours > 1:  # Gap detected
                    ranges.append((range_start, prev_ts))
                    range_start = ts
                prev_ts = ts

            # Add last range
            ranges.append((range_start, timestamps[-1]))

            print(f"   Continuous data ranges: {len(ranges)}")
            for i, (start, end) in enumerate(ranges, 1):
                duration = (end - start).total_seconds() / 3600
                print(f"     Range {i}: {start} to {end} ({duration:.1f} hours)")

            return ranges

        except Exception as e:
            print(f"   ⚠️  Could not check existing data: {e}")
            return []

    def find_gaps_to_fill(self, symbol: str, start_date: datetime, end_date: datetime) -> List[Tuple[datetime, datetime]]:
        """
        Find the actual gaps that need to be filled.
        Returns list of (start, end) tuples for ranges WITHOUT data.
        """
        existing_ranges = self.get_existing_data_ranges(symbol, start_date, end_date)

        if not existing_ranges:
            # No data exists - entire range is a gap
            print(f"\n✓ No existing data - will fill entire range")
            return [(start_date, end_date)]

        gaps = []
        current = start_date

        for range_start, range_end in existing_ranges:
            # Gap before this range?
            if current < range_start:
                gap_hours = (range_start - current).total_seconds() / 3600
                if gap_hours > 0.1:  # Ignore tiny gaps < 6 minutes
                    gaps.append((current, range_start))
                    print(f"\n✓ Gap found: {current} to {range_start} ({gap_hours:.1f} hours)")

            # Move past this range
            current = range_end

        # Gap after last range?
        if current < end_date:
            gap_hours = (end_date - current).total_seconds() / 3600
            if gap_hours > 0.1:
                gaps.append((current, end_date))
                print(f"\n✓ Gap found: {current} to {end_date} ({gap_hours:.1f} hours)")

        if not gaps:
            print(f"\n✓ No gaps found - data already complete!")
        else:
            total_gap_hours = sum((end - start).total_seconds() / 3600 for start, end in gaps)
            print(f"\n📋 Summary: {len(gaps)} gap(s) to fill ({total_gap_hours:.1f} total hours)")

        return gaps

    def fill_date_range(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        max_records: int = 50000
    ) -> Dict:
        """
        Fill a date range with adaptive chunking.

        Smart: Only fills gaps, skips existing data.
        Learns data density as it goes and adjusts chunk sizes dynamically.
        """
        print(f"\n{'=' * 80}")
        print(f"SMART GAP FILLING: {symbol}")
        print(f"{'=' * 80}")
        print(f"Requested range: {start_date} to {end_date}")
        total_hours = (end_date - start_date).total_seconds() / 3600
        print(f"Duration: {(end_date - start_date).days:.1f} days ({total_hours:.1f} hours)")

        self.stats['symbol'] = symbol

        # Find actual gaps to fill
        gaps_to_fill = self.find_gaps_to_fill(symbol, start_date, end_date)

        if not gaps_to_fill:
            print(f"\n✅ Data already complete - nothing to fill!")
            self.stats['status'] = 'already_complete'
            return self.stats

        print(f"\n🧠 Adaptive mode: Will fill {len(gaps_to_fill)} gap(s)")

        records_before = 0
        if Path(self.db_path).exists():
            try:
                conn = duckdb.connect(self.db_path, read_only=True)
                result = conn.execute(f"""
                    SELECT COUNT(*) FROM binance_data.agg_trades WHERE symbol = '{symbol}'
                """).fetchone()
                records_before = result[0] if result else 0
                conn.close()
            except Exception:
                pass

        # Process each gap
        total_chunk_num = 0

        for gap_num, (gap_start, gap_end) in enumerate(gaps_to_fill, 1):
            gap_hours = (gap_end - gap_start).total_seconds() / 3600

            print(f"\n{'═' * 80}")
            print(f"FILLING GAP {gap_num}/{len(gaps_to_fill)}")
            print(f"{'═' * 80}")
            print(f"Gap: {gap_start} to {gap_end} ({gap_hours:.1f} hours)")

            # Adaptive chunking within this gap
            current_start = gap_start

            while current_start < gap_end:
                total_chunk_num += 1

                # Calculate next chunk size based on learning
                chunk_hours = self.get_adaptive_chunk_hours(max_records)
                chunk_end = min(
                    current_start + timedelta(hours=chunk_hours),
                    gap_end  # Don't go past this gap's end
                )

                print(f"\n{'─' * 80}")
                print(f"CHUNK {total_chunk_num} (Gap {gap_num})")
                print(f"{'─' * 80}")

                try:
                    result = self.fetch_data_chunk(symbol, current_start, chunk_end, max_records)
                    self.stats['chunks_processed'] += 1

                    # If we hit the limit, we didn't reach planned end
                    # Continue from actual end instead of planned end
                    if result['hit_limit']:
                        current_start = result['actual_end_time']
                        print(f"   ⚠️  Stopped at {current_start} (hit limit)")
                        print(f"   📍 Continuing from actual end position...")
                    else:
                        # Normal case - move to planned end
                        current_start = chunk_end

                    # Rate limiting between chunks
                    if current_start < gap_end:
                        print(f"\n   ⏳ Waiting 5 seconds before next chunk...")
                        time.sleep(5)

                except Exception as e:
                    print(f"\n❌ Chunk {total_chunk_num} failed: {e}")
                    self.stats['status'] = 'partial_failure'
                    print("\n⚠️  Failed - you can rerun to retry from this point")
                    break

            # Gap completed or failed
            if current_start < gap_end:
                print(f"\n⚠️  Gap {gap_num} incomplete - stopped at {current_start}")
                break  # Stop processing further gaps

            print(f"\n✅ Gap {gap_num} filled completely!")

        self.stats['chunks_total'] = total_chunk_num

        # Calculate records added
        records_after = 0
        try:
            conn = duckdb.connect(self.db_path, read_only=True)
            result = conn.execute(f"""
                SELECT COUNT(*) FROM binance_data.agg_trades WHERE symbol = '{symbol}'
            """).fetchone()
            records_after = result[0] if result else 0
            conn.close()
            self.stats['records_added'] = records_after - records_before
        except Exception:
            pass

        # Check if we completed all gaps
        all_gaps_filled = (gap_num == len(gaps_to_fill) and current_start >= gap_end)

        if all_gaps_filled or self.stats.get('status') != 'partial_failure':
            self.stats['status'] = 'success'
            print(f"\n{'=' * 80}")
            print(f"✅ ALL GAPS FILLED")
            print(f"{'=' * 80}")
            print(f"Gaps filled: {gap_num}/{len(gaps_to_fill)}")
            print(f"Chunks processed: {self.stats['chunks_processed']}")
            print(f"Records added: {self.stats['records_added']:,}")

            if self.observed_records_per_hour:
                avg_density = sum(self.observed_records_per_hour) / len(self.observed_records_per_hour)
                print(f"\n📊 Learned density: {avg_density:,.0f} records/hour (actual)")
        else:
            print(f"\n{'=' * 80}")
            print(f"⚠️  PARTIAL COMPLETION")
            print(f"{'=' * 80}")
            print(f"Gaps filled: {gap_num - 1}/{len(gaps_to_fill)}")
            print(f"Chunks processed: {self.stats['chunks_processed']}")
            print(f"Records added: {self.stats['records_added']:,}")

        return self.stats

    def fill_largest_gap(self, symbol: str, max_records: int = 50000) -> Dict:
        """Find and fill the largest gap."""
        print(f"\n{'=' * 80}")
        print(f"FILLING LARGEST GAP: {symbol}")
        print(f"{'=' * 80}")

        gaps = self.find_gaps(symbol, min_gap_hours=1.0)

        if not gaps:
            print("\n✅ No gaps found!")
            self.stats['status'] = 'no_gaps'
            return self.stats

        # Get largest gap
        largest = gaps[0]

        print(f"\nLargest gap:")
        print(f"  Start: {largest['start']}")
        print(f"  End:   {largest['end']}")
        print(f"  Duration: {largest['days']:.2f} days ({largest['hours']:.1f} hours)")

        return self.fill_date_range(
            symbol,
            largest['start'],
            largest['end'],
            max_records
        )

    def fill_recent(self, symbol: str, hours: int = 24, max_records: int = 50000) -> Dict:
        """Fill recent data (for daily jobs)."""
        print(f"\n{'=' * 80}")
        print(f"FILLING RECENT DATA: {symbol}")
        print(f"{'=' * 80}")

        end_date = datetime.now()
        start_date = end_date - timedelta(hours=hours)

        # If we have existing data, start from last timestamp
        data_range = self.get_data_range(symbol)
        if data_range:
            last_dt = data_range[1]
            if last_dt > start_date:
                start_date = last_dt
                print(f"\nLast data: {last_dt}")
                print(f"Fetching from last timestamp to now")

        print(f"Start: {start_date}")
        print(f"End:   {end_date}")

        return self.fill_date_range(symbol, start_date, end_date, max_records)

    def save_report(self, output_dir: str = "jobs/reports"):
        """Save gap filling report."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        report_file = output_path / f"gap_filling_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(report_file, 'w') as f:
            json.dump(self.stats, f, indent=2, default=str)

        print(f"\n📄 Report saved: {report_file}")

        # Also save as latest
        latest_file = output_path / "gap_filling_latest.json"
        with open(latest_file, 'w') as f:
            json.dump(self.stats, f, indent=2, default=str)


def main():
    """Run gap filling job."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Fill data gaps incrementally",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Daily job: get last 24 hours
  %(prog)s --symbol BTCUSDT --recent

  # Fill specific date range (auto-chunks)
  %(prog)s --symbol BTCUSDT --start-date 2025-10-01 --end-date 2025-10-20

  # Fill largest gap
  %(prog)s --symbol BTCUSDT --fill-largest-gap

  # Fill all gaps
  %(prog)s --symbol BTCUSDT --fill-all-gaps
        """
    )

    parser.add_argument('--symbol', required=True, help='Trading symbol (e.g., BTCUSDT)')
    parser.add_argument('--db-path', default='binance_pipeline.duckdb',
                       help='Path to DuckDB database')
    parser.add_argument('--max-records', type=int, default=50000,
                       help='Maximum records per chunk (default: 50000)')

    # Mode selection (mutually exclusive)
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument('--recent', action='store_true',
                           help='Fill recent data (last 24 hours)')
    mode_group.add_argument('--fill-largest-gap', action='store_true',
                           help='Fill the largest gap found')
    mode_group.add_argument('--fill-all-gaps', action='store_true',
                           help='Fill all gaps found')
    mode_group.add_argument('--start-date', type=str,
                           help='Start date (YYYY-MM-DD) - requires --end-date')

    # Optional for date range mode
    parser.add_argument('--end-date', type=str,
                       help='End date (YYYY-MM-DD) - requires --start-date')
    parser.add_argument('--recent-hours', type=int, default=24,
                       help='Hours to fetch for --recent mode (default: 24)')
    parser.add_argument('--output-dir', default='jobs/reports',
                       help='Directory for output reports')

    args = parser.parse_args()

    # Validate date range mode
    if args.start_date and not args.end_date:
        parser.error("--start-date requires --end-date")
    if args.end_date and not args.start_date:
        parser.error("--end-date requires --start-date")

    try:
        with GapFiller(args.db_path) as filler:
            if args.recent:
                # Daily job mode
                stats = filler.fill_recent(
                    args.symbol,
                    hours=args.recent_hours,
                    max_records=args.max_records
                )

            elif args.fill_largest_gap:
                # Fill largest gap
                stats = filler.fill_largest_gap(
                    args.symbol,
                    max_records=args.max_records
                )

            elif args.fill_all_gaps:
                # Fill all gaps
                gaps = filler.find_gaps(args.symbol)
                if not gaps:
                    print("\n✅ No gaps found!")
                    sys.exit(0)

                print(f"\nFound {len(gaps)} gap(s) to fill")
                for i, gap in enumerate(gaps, 1):
                    print(f"\nGap {i}/{len(gaps)}: {gap['days']:.2f} days")
                    stats = filler.fill_date_range(
                        args.symbol,
                        gap['start'],
                        gap['end'],
                        args.max_records
                    )

                    if stats['status'] != 'success':
                        print(f"\n⚠️  Stopping - gap {i} failed")
                        break

                    # Wait between gaps
                    if i < len(gaps):
                        time.sleep(10)

            elif args.start_date:
                # Specific date range
                start_dt = datetime.strptime(args.start_date, '%Y-%m-%d')
                end_dt = datetime.strptime(args.end_date, '%Y-%m-%d')

                if start_dt >= end_dt:
                    parser.error("start-date must be before end-date")

                stats = filler.fill_date_range(
                    args.symbol,
                    start_dt,
                    end_dt,
                    args.max_records
                )

            filler.save_report(args.output_dir)

            # Exit codes
            if stats['status'] == 'success':
                sys.exit(0)
            elif stats['status'] == 'no_gaps':
                sys.exit(0)
            else:
                sys.exit(1)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()
