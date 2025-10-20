"""
Job 1: Data Quality Assessment

This job runs BEFORE any data operations to assess current state:
- Identifies duplicates
- Detects time gaps
- Checks data freshness
- Validates data quality
- Outputs report and recommendations
"""

import duckdb
from datetime import datetime, timedelta
from pathlib import Path
import json
import sys


class DataQualityAssessment:
    """Assess data quality and generate actionable report."""

    def __init__(self, db_path: str = "binance_pipeline.duckdb"):
        self.db_path = db_path
        self.conn = None
        self.report = {
            'timestamp': datetime.now().isoformat(),
            'symbols': {},
            'issues': [],
            'recommendations': []
        }

    def __enter__(self):
        if not Path(self.db_path).exists():
            print(f"⚠️  Database not found: {self.db_path}")
            print("Creating new database on first data ingestion...")
            self.report['status'] = 'no_database'
            return self

        self.conn = duckdb.connect(self.db_path, read_only=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()

    def assess_symbol(self, symbol: str) -> dict:
        """Assess data quality for a specific symbol."""
        assessment = {
            'symbol': symbol,
            'record_count': 0,
            'duplicate_count': 0,
            'time_gaps': [],
            'data_range': {},
            'freshness_hours': None,
            'quality_issues': []
        }

        if not self.conn:
            return assessment

        try:
            # Get basic statistics
            result = self.conn.execute(f"""
                SELECT
                    COUNT(*) as total,
                    COUNT(DISTINCT agg_trade_id) as unique_trades,
                    MIN(timestamp) as first_ts,
                    MAX(timestamp) as last_ts
                FROM binance_data.agg_trades
                WHERE symbol = '{symbol}'
            """).fetchone()

            if not result or result[0] == 0:
                assessment['quality_issues'].append('No data found')
                return assessment

            total, unique, first_ts, last_ts = result
            assessment['record_count'] = total
            assessment['duplicate_count'] = total - unique

            first_dt = datetime.fromtimestamp(first_ts / 1000)
            last_dt = datetime.fromtimestamp(last_ts / 1000)

            assessment['data_range'] = {
                'first': first_dt.isoformat(),
                'last': last_dt.isoformat(),
                'duration_days': (last_dt - first_dt).days
            }

            # Calculate freshness
            now = datetime.now()
            freshness = (now - last_dt).total_seconds() / 3600
            assessment['freshness_hours'] = round(freshness, 2)

            # Check for duplicates
            if assessment['duplicate_count'] > 0:
                assessment['quality_issues'].append(
                    f"{assessment['duplicate_count']:,} duplicate records"
                )

            # Find significant time gaps (> 1 hour)
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
                WHERE gap_ms > 3600000  -- > 1 hour
                ORDER BY gap_ms DESC
            """).fetchall()

            for prev_ts, curr_ts, gap_ms in gaps:
                prev_dt = datetime.fromtimestamp(prev_ts / 1000)
                curr_dt = datetime.fromtimestamp(curr_ts / 1000)
                gap_hours = gap_ms / 3600000

                assessment['time_gaps'].append({
                    'start': prev_dt.isoformat(),
                    'end': curr_dt.isoformat(),
                    'hours': round(gap_hours, 2),
                    'days': round(gap_hours / 24, 2)
                })

            if len(assessment['time_gaps']) > 0:
                total_gap_hours = sum(g['hours'] for g in assessment['time_gaps'])
                assessment['quality_issues'].append(
                    f"{len(assessment['time_gaps'])} time gaps (total: {total_gap_hours:.1f} hours)"
                )

            # Check data freshness
            if freshness > 2:  # More than 2 hours old
                assessment['quality_issues'].append(
                    f"Data is {freshness:.1f} hours old (stale)"
                )

            # Check for data quality issues
            quality = self.conn.execute(f"""
                SELECT
                    SUM(CASE WHEN price IS NULL OR CAST(price AS DOUBLE) <= 0 THEN 1 ELSE 0 END) as bad_price,
                    SUM(CASE WHEN quantity IS NULL OR CAST(quantity AS DOUBLE) <= 0 THEN 1 ELSE 0 END) as bad_qty,
                    SUM(CASE WHEN timestamp IS NULL THEN 1 ELSE 0 END) as bad_ts
                FROM binance_data.agg_trades
                WHERE symbol = '{symbol}'
            """).fetchone()

            if quality:
                bad_price, bad_qty, bad_ts = quality
                if bad_price > 0:
                    assessment['quality_issues'].append(f"{bad_price:,} invalid prices")
                if bad_qty > 0:
                    assessment['quality_issues'].append(f"{bad_qty:,} invalid quantities")
                if bad_ts > 0:
                    assessment['quality_issues'].append(f"{bad_ts:,} invalid timestamps")

        except Exception as e:
            assessment['quality_issues'].append(f"Assessment failed: {str(e)}")

        return assessment

    def generate_recommendations(self):
        """Generate actionable recommendations based on assessment."""
        for symbol, assessment in self.report['symbols'].items():
            # Recommend deduplication
            if assessment['duplicate_count'] > 0:
                self.report['recommendations'].append({
                    'priority': 'HIGH',
                    'action': 'deduplicate',
                    'symbol': symbol,
                    'reason': f"Found {assessment['duplicate_count']:,} duplicate records",
                    'command': 'uv run python jobs/02_deduplication.py'
                })

            # Recommend gap filling
            if len(assessment['time_gaps']) > 0:
                for gap in assessment['time_gaps'][:3]:  # Top 3 gaps
                    self.report['recommendations'].append({
                        'priority': 'HIGH',
                        'action': 'fill_gap',
                        'symbol': symbol,
                        'gap': gap,
                        'reason': f"Missing {gap['days']:.1f} days of data",
                        'command': f"uv run python jobs/03_fill_gaps.py --symbol {symbol} --start-date {gap['start'][:10]} --end-date {gap['end'][:10]}"
                    })

            # Recommend data refresh
            if assessment['freshness_hours'] and assessment['freshness_hours'] > 2:
                self.report['recommendations'].append({
                    'priority': 'MEDIUM',
                    'action': 'refresh_data',
                    'symbol': symbol,
                    'reason': f"Data is {assessment['freshness_hours']:.1f} hours old",
                    'command': f"uv run python jobs/03_fill_gaps.py --symbol {symbol} --recent"
                })

        # Overall recommendations
        if any(s['duplicate_count'] > 0 for s in self.report['symbols'].values()):
            self.report['issues'].append({
                'severity': 'HIGH',
                'category': 'duplicates',
                'message': 'Duplicate records found - run deduplication job'
            })

        if any(len(s['time_gaps']) > 0 for s in self.report['symbols'].values()):
            self.report['issues'].append({
                'severity': 'HIGH',
                'category': 'gaps',
                'message': 'Time gaps found - run gap filling job'
            })

    def run(self) -> dict:
        """Run complete assessment and return report."""
        print("=" * 80)
        print("DATA QUALITY ASSESSMENT")
        print("=" * 80)
        print(f"Database: {self.db_path}")
        print(f"Timestamp: {self.report['timestamp']}")
        print()

        if not self.conn:
            print("⚠️  No database found - will be created on first ingestion")
            self.report['status'] = 'no_database'
            return self.report

        # Get all symbols
        symbols = self.conn.execute("""
            SELECT DISTINCT symbol FROM binance_data.agg_trades
        """).fetchall()

        if not symbols:
            print("⚠️  No data in database")
            self.report['status'] = 'no_data'
            return self.report

        # Assess each symbol
        for (symbol,) in symbols:
            print(f"\nAssessing {symbol}...")
            assessment = self.assess_symbol(symbol)
            self.report['symbols'][symbol] = assessment

            # Print summary
            print(f"  Records: {assessment['record_count']:,}")
            print(f"  Duplicates: {assessment['duplicate_count']:,}")
            print(f"  Time gaps: {len(assessment['time_gaps'])}")
            print(f"  Freshness: {assessment['freshness_hours']:.1f} hours")

            if assessment['quality_issues']:
                print(f"  Issues:")
                for issue in assessment['quality_issues']:
                    print(f"    ⚠️  {issue}")

        # Generate recommendations
        self.generate_recommendations()

        print("\n" + "=" * 80)
        print("RECOMMENDATIONS")
        print("=" * 80)

        if not self.report['recommendations']:
            print("✅ No issues found - data quality is good!")
            self.report['status'] = 'healthy'
        else:
            self.report['status'] = 'issues_found'

            # Group by priority
            high_priority = [r for r in self.report['recommendations'] if r['priority'] == 'HIGH']
            medium_priority = [r for r in self.report['recommendations'] if r['priority'] == 'MEDIUM']

            if high_priority:
                print(f"\n🚨 HIGH PRIORITY ({len(high_priority)} actions):")
                for i, rec in enumerate(high_priority[:5], 1):  # Show top 5
                    print(f"\n  {i}. {rec['action'].upper()}: {rec['symbol']}")
                    print(f"     Reason: {rec['reason']}")
                    print(f"     Command: {rec['command']}")

            if medium_priority:
                print(f"\n⚠️  MEDIUM PRIORITY ({len(medium_priority)} actions):")
                for i, rec in enumerate(medium_priority[:3], 1):  # Show top 3
                    print(f"\n  {i}. {rec['action'].upper()}: {rec['symbol']}")
                    print(f"     Reason: {rec['reason']}")

        print("\n" + "=" * 80)
        print("NEXT STEPS")
        print("=" * 80)

        if self.report['status'] == 'issues_found':
            print("\n1. Review the assessment report: jobs/reports/quality_assessment.json")
            print("2. Run deduplication: uv run python jobs/02_deduplication.py")
            print("3. Fill gaps: uv run python jobs/03_fill_gaps.py")
            print("4. Or run all jobs: uv run python jobs/run_all_jobs.py")
        else:
            print("\n✅ Data quality is good!")
            print("   Run daily: uv run python jobs/03_fill_gaps.py --recent")

        return self.report

    def save_report(self, output_dir: str = "jobs/reports"):
        """Save assessment report to JSON file."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        report_file = output_path / f"quality_assessment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(report_file, 'w') as f:
            json.dump(self.report, f, indent=2)

        print(f"\n📄 Report saved: {report_file}")

        # Also save as "latest"
        latest_file = output_path / "quality_assessment_latest.json"
        with open(latest_file, 'w') as f:
            json.dump(self.report, f, indent=2)

        return report_file


def main():
    """Run data quality assessment."""
    import argparse

    parser = argparse.ArgumentParser(description="Assess data quality")
    parser.add_argument('--db-path', default='binance_pipeline.duckdb',
                       help='Path to DuckDB database')
    parser.add_argument('--output-dir', default='jobs/reports',
                       help='Directory for output reports')
    parser.add_argument('--json', action='store_true',
                       help='Output JSON only (no console output)')

    args = parser.parse_args()

    with DataQualityAssessment(args.db_path) as assessment:
        report = assessment.run()
        report_file = assessment.save_report(args.output_dir)

        if args.json:
            print(json.dumps(report, indent=2))

        # Exit with error code if issues found
        if report.get('status') == 'issues_found':
            sys.exit(1)
        else:
            sys.exit(0)


if __name__ == "__main__":
    main()
