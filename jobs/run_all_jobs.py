"""
Job Orchestrator: Run All Data Quality Jobs

This script runs all jobs in the correct order:
1. Quality Assessment - Analyze current state
2. Deduplication - Remove duplicates
3. Gap Filling - Fill missing data

Usage:
  # Full pipeline with manual approval
  uv run python jobs/run_all_jobs.py --symbol BTCUSDT

  # Automated mode (no prompts)
  uv run python jobs/run_all_jobs.py --symbol BTCUSDT --auto

  # Dry run (no changes)
  uv run python jobs/run_all_jobs.py --symbol BTCUSDT --dry-run
"""

import sys
import subprocess
from pathlib import Path
from datetime import datetime
import json
import time


class JobOrchestrator:
    """Orchestrate execution of all data quality jobs."""

    def __init__(self, symbol: str, db_path: str = "binance_pipeline.duckdb", auto: bool = False):
        self.symbol = symbol
        self.db_path = db_path
        self.auto = auto
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'symbol': symbol,
            'jobs': {}
        }

    def run_command(self, cmd: list, job_name: str) -> dict:
        """Run a command and capture results."""
        print(f"\n{'=' * 80}")
        print(f"RUNNING: {job_name}")
        print(f"{'=' * 80}")
        print(f"Command: {' '.join(cmd)}")
        print()

        start_time = time.time()

        try:
            result = subprocess.run(
                cmd,
                capture_output=False,  # Show output in real-time
                text=True,
                check=False  # Don't raise on non-zero exit
            )

            elapsed = time.time() - start_time

            job_result = {
                'job': job_name,
                'command': ' '.join(cmd),
                'exit_code': result.returncode,
                'elapsed_seconds': round(elapsed, 2),
                'status': 'success' if result.returncode == 0 else 'failed'
            }

            return job_result

        except Exception as e:
            elapsed = time.time() - start_time
            return {
                'job': job_name,
                'command': ' '.join(cmd),
                'exit_code': -1,
                'elapsed_seconds': round(elapsed, 2),
                'status': 'error',
                'error': str(e)
            }

    def confirm(self, message: str) -> bool:
        """Ask for user confirmation."""
        if self.auto:
            print(f"\n{message} (auto-mode: yes)")
            return True

        response = input(f"\n{message} (yes/no): ").lower()
        return response == 'yes'

    def run(self, dry_run: bool = False):
        """Run all jobs in sequence."""
        print("=" * 80)
        print("DATA QUALITY JOB ORCHESTRATOR")
        print("=" * 80)
        print(f"Symbol: {self.symbol}")
        print(f"Mode: {'DRY RUN' if dry_run else 'AUTO' if self.auto else 'INTERACTIVE'}")
        print(f"Database: {self.db_path}")
        print()

        # Job 1: Quality Assessment
        print("\n" + "🔍" * 40)
        print("STEP 1: DATA QUALITY ASSESSMENT")
        print("🔍" * 40)

        assessment_cmd = [
            "uv", "run", "python",
            "jobs/01_data_quality_assessment.py",
            "--db-path", self.db_path
        ]

        assessment_result = self.run_command(assessment_cmd, "Quality Assessment")
        self.results['jobs']['assessment'] = assessment_result

        # Load assessment report
        assessment_report = None
        report_file = Path("jobs/reports/quality_assessment_latest.json")
        if report_file.exists():
            with open(report_file) as f:
                assessment_report = json.load(f)

        # Check if we need to continue
        if not assessment_report or assessment_report.get('status') == 'no_database':
            print("\n⚠️  No database found - skip to gap filling to create initial data")
            if not self.confirm("Skip to gap filling?"):
                print("\nAborted by user")
                return self.results

            # Skip to gap filling
            self.results['jobs']['deduplication'] = {'status': 'skipped', 'reason': 'no_database'}
            assessment_result = {'status': 'skipped'}

        elif assessment_report.get('status') == 'healthy':
            print("\n✅ Data quality is good!")
            if not self.confirm("Continue with gap filling to get latest data?"):
                print("\nNo further action needed")
                return self.results

            self.results['jobs']['deduplication'] = {'status': 'skipped', 'reason': 'no_duplicates'}

        # Job 2: Deduplication
        if assessment_result.get('status') != 'skipped':
            print("\n" + "🗑️" * 40)
            print("STEP 2: DEDUPLICATION")
            print("🗑️" * 40)

            # First run dry-run
            dedup_dry_cmd = [
                "uv", "run", "python",
                "jobs/02_deduplication.py",
                "--db-path", self.db_path
            ]

            dedup_dry_result = self.run_command(dedup_dry_cmd, "Deduplication (Dry Run)")

            if dedup_dry_result['exit_code'] == 0:
                # No duplicates found
                print("\n✅ No duplicates to remove")
                self.results['jobs']['deduplication'] = dedup_dry_result
                self.results['jobs']['deduplication']['status'] = 'skipped'

            elif not dry_run:
                # Duplicates found, ask to remove
                if self.confirm("⚠️  Duplicates found. Remove them?"):
                    dedup_exec_cmd = [
                        "uv", "run", "python",
                        "jobs/02_deduplication.py",
                        "--db-path", self.db_path,
                        "--execute"
                    ]

                    dedup_result = self.run_command(dedup_exec_cmd, "Deduplication (Execute)")
                    self.results['jobs']['deduplication'] = dedup_result

                    if dedup_result['status'] != 'success':
                        print("\n❌ Deduplication failed - aborting")
                        return self.results
                else:
                    print("\nSkipping deduplication")
                    self.results['jobs']['deduplication'] = {'status': 'skipped', 'reason': 'user_declined'}

        # Job 3: Gap Filling
        print("\n" + "📥" * 40)
        print("STEP 3: GAP FILLING")
        print("📥" * 40)

        if dry_run:
            print("\n⚠️  Dry run mode - skipping gap filling")
            self.results['jobs']['gap_filling'] = {'status': 'skipped', 'reason': 'dry_run'}
        else:
            # Determine what to fill
            has_gaps = assessment_report and any(
                len(s.get('time_gaps', [])) > 0
                for s in assessment_report.get('symbols', {}).values()
            )

            if has_gaps:
                print("\n⚠️  Gaps detected in data")

                if self.confirm("Fill the largest gap?"):
                    gap_fill_cmd = [
                        "uv", "run", "python",
                        "jobs/03_fill_gaps.py",
                        "--symbol", self.symbol,
                        "--db-path", self.db_path,
                        "--fill-largest-gap"
                    ]

                    gap_result = self.run_command(gap_fill_cmd, "Fill Largest Gap")
                    self.results['jobs']['gap_filling'] = gap_result
                else:
                    print("\nSkipping gap filling")
                    self.results['jobs']['gap_filling'] = {'status': 'skipped', 'reason': 'user_declined'}
            else:
                # No gaps, just get recent data
                print("\n✅ No gaps detected - fetching recent data")

                gap_fill_cmd = [
                    "uv", "run", "python",
                    "jobs/03_fill_gaps.py",
                    "--symbol", self.symbol,
                    "--db-path", self.db_path,
                    "--recent"
                ]

                gap_result = self.run_command(gap_fill_cmd, "Fill Recent Data")
                self.results['jobs']['gap_filling'] = gap_result

        # Final summary
        print("\n" + "=" * 80)
        print("JOB ORCHESTRATION COMPLETE")
        print("=" * 80)

        for job_name, job_result in self.results['jobs'].items():
            status = job_result.get('status', 'unknown')
            elapsed = job_result.get('elapsed_seconds', 0)

            status_icon = {
                'success': '✅',
                'failed': '❌',
                'skipped': '⏭️',
                'error': '💥'
            }.get(status, '❓')

            print(f"\n{status_icon} {job_name.replace('_', ' ').title()}")
            print(f"   Status: {status}")
            if elapsed:
                print(f"   Time: {elapsed:.2f}s")
            if 'reason' in job_result:
                print(f"   Reason: {job_result['reason']}")

        # Save orchestration report
        self.save_report()

        return self.results

    def save_report(self, output_dir: str = "jobs/reports"):
        """Save orchestration report."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        report_file = output_path / f"orchestration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(report_file, 'w') as f:
            json.dump(self.results, f, indent=2)

        print(f"\n📄 Orchestration report: {report_file}")

        # Also save as latest
        latest_file = output_path / "orchestration_latest.json"
        with open(latest_file, 'w') as f:
            json.dump(self.results, f, indent=2)


def main():
    """Run job orchestrator."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Run all data quality jobs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This orchestrator runs jobs in order:
  1. Quality Assessment - Analyze data quality
  2. Deduplication - Remove duplicates (if found)
  3. Gap Filling - Fill missing data

Examples:
  # Interactive mode (asks for confirmation)
  %(prog)s --symbol BTCUSDT

  # Automatic mode (no prompts)
  %(prog)s --symbol BTCUSDT --auto

  # Dry run (assessment only, no changes)
  %(prog)s --symbol BTCUSDT --dry-run
        """
    )

    parser.add_argument('--symbol', required=True,
                       help='Trading symbol (e.g., BTCUSDT)')
    parser.add_argument('--db-path', default='binance_pipeline.duckdb',
                       help='Path to DuckDB database')
    parser.add_argument('--auto', action='store_true',
                       help='Run automatically without prompts')
    parser.add_argument('--dry-run', action='store_true',
                       help='Run assessment only, make no changes')

    args = parser.parse_args()

    orchestrator = JobOrchestrator(
        symbol=args.symbol,
        db_path=args.db_path,
        auto=args.auto
    )

    results = orchestrator.run(dry_run=args.dry_run)

    # Exit with error if any job failed
    failed_jobs = [
        job for job, result in results['jobs'].items()
        if result.get('status') == 'failed' or result.get('status') == 'error'
    ]

    if failed_jobs:
        print(f"\n❌ {len(failed_jobs)} job(s) failed: {', '.join(failed_jobs)}")
        sys.exit(1)
    else:
        print("\n✅ All jobs completed successfully")
        sys.exit(0)


if __name__ == "__main__":
    main()
