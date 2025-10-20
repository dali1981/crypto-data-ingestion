"""
Daily Data Maintenance Job

This job should run daily (via cron/systemd) to:
1. Fetch latest data (last 24 hours)
2. Check for duplicates
3. Assess data quality

Designed to be automated and safe for scheduled execution.

Cron example (runs at 2 AM daily):
  0 2 * * * cd /path/to/project && uv run python jobs/daily_job.py --symbol BTCUSDT

Systemd timer example:
  See jobs/systemd/binance-daily.service and binance-daily.timer
"""

import sys
from pathlib import Path
from datetime import datetime
import json
import subprocess


class DailyJob:
    """Daily maintenance job for data quality."""

    def __init__(self, symbol: str, db_path: str = "binance_pipeline.duckdb"):
        self.symbol = symbol
        self.db_path = db_path
        self.log = {
            'timestamp': datetime.now().isoformat(),
            'symbol': symbol,
            'steps': [],
            'status': 'pending'
        }

    def run_step(self, name: str, cmd: list) -> dict:
        """Run a step and log results."""
        print(f"\n{'=' * 80}")
        print(f"{name}")
        print(f"{'=' * 80}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )

            step = {
                'name': name,
                'command': ' '.join(cmd),
                'exit_code': result.exitcode,
                'status': 'success' if result.exitcode == 0 else 'failed',
                'stdout': result.stdout[-500:] if result.stdout else '',  # Last 500 chars
                'stderr': result.stderr[-500:] if result.stderr else ''
            }

            # Print output
            if result.stdout:
                print(result.stdout)
            if result.stderr and result.exitcode != 0:
                print(f"STDERR:\n{result.stderr}", file=sys.stderr)

            return step

        except Exception as e:
            return {
                'name': name,
                'command': ' '.join(cmd),
                'exit_code': -1,
                'status': 'error',
                'error': str(e)
            }

    def run(self) -> dict:
        """Run daily maintenance."""
        print("=" * 80)
        print("DAILY DATA MAINTENANCE JOB")
        print("=" * 80)
        print(f"Timestamp: {self.log['timestamp']}")
        print(f"Symbol: {self.symbol}")
        print(f"Database: {self.db_path}")

        # Step 1: Fetch recent data (last 24 hours)
        step1 = self.run_step(
            "Step 1: Fetch Recent Data",
            [
                "uv", "run", "python",
                "jobs/03_fill_gaps.py",
                "--symbol", self.symbol,
                "--db-path", self.db_path,
                "--recent"
            ]
        )
        self.log['steps'].append(step1)

        if step1['status'] == 'failed':
            print("\n⚠️  Data fetch failed - continuing with quality check")

        # Step 2: Quality assessment
        step2 = self.run_step(
            "Step 2: Quality Assessment",
            [
                "uv", "run", "python",
                "jobs/01_data_quality_assessment.py",
                "--db-path", self.db_path
            ]
        )
        self.log['steps'].append(step2)

        # Check for duplicates in assessment
        duplicates_found = False
        report_file = Path("jobs/reports/quality_assessment_latest.json")
        if report_file.exists():
            try:
                with open(report_file) as f:
                    report = json.load(f)
                    for symbol_data in report.get('symbols', {}).values():
                        if symbol_data.get('duplicate_count', 0) > 0:
                            duplicates_found = True
                            break
            except Exception:
                pass

        # Step 3: Deduplication (if needed)
        if duplicates_found:
            print("\n⚠️  Duplicates detected - running deduplication")

            step3 = self.run_step(
                "Step 3: Deduplication",
                [
                    "uv", "run", "python",
                    "jobs/02_deduplication.py",
                    "--db-path", self.db_path,
                    "--execute"
                ]
            )
            self.log['steps'].append(step3)
        else:
            print("\n✅ No duplicates found - skipping deduplication")
            self.log['steps'].append({
                'name': 'Step 3: Deduplication',
                'status': 'skipped',
                'reason': 'no_duplicates'
            })

        # Final status
        failed_steps = [s for s in self.log['steps'] if s.get('status') == 'failed']
        error_steps = [s for s in self.log['steps'] if s.get('status') == 'error']

        if error_steps:
            self.log['status'] = 'error'
        elif failed_steps:
            self.log['status'] = 'partial_failure'
        else:
            self.log['status'] = 'success'

        # Summary
        print("\n" + "=" * 80)
        print("DAILY JOB SUMMARY")
        print("=" * 80)

        for step in self.log['steps']:
            status_icon = {
                'success': '✅',
                'failed': '❌',
                'skipped': '⏭️',
                'error': '💥'
            }.get(step.get('status', 'unknown'), '❓')

            print(f"{status_icon} {step['name']}: {step.get('status', 'unknown')}")

        print(f"\nOverall Status: {self.log['status']}")

        # Save log
        self.save_log()

        return self.log

    def save_log(self, output_dir: str = "jobs/reports/daily"):
        """Save daily job log."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        log_file = output_path / f"daily_job_{datetime.now().strftime('%Y%m%d')}.json"

        with open(log_file, 'w') as f:
            json.dump(self.log, f, indent=2)

        print(f"\n📄 Log saved: {log_file}")

        # Keep only last 30 days of logs
        self.cleanup_old_logs(output_path, days=30)

    def cleanup_old_logs(self, log_dir: Path, days: int = 30):
        """Remove logs older than specified days."""
        from datetime import timedelta

        cutoff_date = datetime.now() - timedelta(days=days)

        for log_file in log_dir.glob("daily_job_*.json"):
            try:
                # Extract date from filename
                date_str = log_file.stem.split('_')[-1]  # e.g., "20251020"
                file_date = datetime.strptime(date_str, '%Y%m%d')

                if file_date < cutoff_date:
                    log_file.unlink()
                    print(f"   Cleaned up old log: {log_file.name}")
            except Exception:
                pass


def main():
    """Run daily job."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Daily data maintenance job",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This job runs automatically on a schedule:
  1. Fetches latest data (last 24 hours)
  2. Checks data quality
  3. Removes duplicates if found

Setup cron job:
  0 2 * * * cd /path/to/project && uv run python jobs/daily_job.py --symbol BTCUSDT

Setup systemd timer:
  See jobs/systemd/ for example timer configuration
        """
    )

    parser.add_argument('--symbol', required=True,
                       help='Trading symbol (e.g., BTCUSDT)')
    parser.add_argument('--db-path', default='binance_pipeline.duckdb',
                       help='Path to DuckDB database')

    args = parser.parse_args()

    job = DailyJob(symbol=args.symbol, db_path=args.db_path)
    log = job.run()

    # Exit with appropriate code
    if log['status'] == 'success':
        sys.exit(0)
    elif log['status'] == 'partial_failure':
        sys.exit(1)
    else:
        sys.exit(2)


if __name__ == "__main__":
    main()
