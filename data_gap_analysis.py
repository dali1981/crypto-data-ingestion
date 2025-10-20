"""
Data Gap Analysis and Validation Tool

This tool identifies and reports data quality issues in the Binance tick data:
1. Time gaps in the data
2. Duplicate timestamps
3. Invalid data values
4. Missing data ranges
5. Provides suggestions for filling gaps
"""

import duckdb
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import pandas as pd
from pathlib import Path


class DataGapAnalyzer:
    """Analyze and report data quality issues."""

    def __init__(self, db_path: str = "binance_pipeline.duckdb"):
        """Initialize analyzer with database path."""
        self.db_path = db_path
        self.conn = None

    def __enter__(self):
        """Context manager entry."""
        self.conn = duckdb.connect(self.db_path, read_only=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self.conn:
            self.conn.close()

    def get_data_summary(self) -> List[Dict]:
        """Get basic summary of data for each symbol."""
        query = """
            SELECT
                symbol,
                COUNT(*) as record_count,
                MIN(timestamp) as first_ts,
                MAX(timestamp) as last_ts,
                MIN(CAST(price AS DOUBLE)) as min_price,
                MAX(CAST(price AS DOUBLE)) as max_price,
                AVG(CAST(price AS DOUBLE)) as avg_price
            FROM binance_data.agg_trades
            GROUP BY symbol
        """

        results = self.conn.execute(query).fetchall()

        summaries = []
        for row in results:
            symbol, count, first_ts, last_ts, min_price, max_price, avg_price = row

            first_dt = datetime.fromtimestamp(first_ts / 1000)
            last_dt = datetime.fromtimestamp(last_ts / 1000)
            duration = last_dt - first_dt

            summaries.append({
                'symbol': symbol,
                'record_count': count,
                'first_timestamp': first_dt,
                'last_timestamp': last_dt,
                'duration_hours': duration.total_seconds() / 3600,
                'duration_days': duration.days,
                'min_price': min_price,
                'max_price': max_price,
                'avg_price': avg_price,
            })

        return summaries

    def find_time_gaps(self, symbol: str, min_gap_minutes: float = 1.0) -> List[Dict]:
        """Find time gaps larger than specified threshold."""
        min_gap_ms = int(min_gap_minutes * 60 * 1000)

        query = f"""
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
        """

        results = self.conn.execute(query).fetchall()

        gaps = []
        for row in results:
            prev_ts, curr_ts, gap_ms = row
            prev_dt = datetime.fromtimestamp(prev_ts / 1000)
            curr_dt = datetime.fromtimestamp(curr_ts / 1000)

            gaps.append({
                'start_time': prev_dt,
                'end_time': curr_dt,
                'gap_minutes': gap_ms / 60000,
                'gap_hours': gap_ms / 3600000,
                'gap_days': gap_ms / (86400000),
            })

        return gaps

    def find_duplicates(self, symbol: str) -> pd.DataFrame:
        """Find duplicate timestamps and their agg_trade_ids."""
        query = f"""
            SELECT
                symbol,
                timestamp,
                COUNT(*) as dup_count,
                STRING_AGG(CAST(agg_trade_id AS VARCHAR), ', ') as trade_ids
            FROM binance_data.agg_trades
            WHERE symbol = '{symbol}'
            GROUP BY symbol, timestamp
            HAVING COUNT(*) > 1
            ORDER BY dup_count DESC, timestamp
        """

        return self.conn.execute(query).df()

    def check_data_quality(self, symbol: str) -> Dict:
        """Check for data quality issues."""
        query = f"""
            SELECT
                COUNT(*) as total_records,
                SUM(CASE WHEN price IS NULL THEN 1 ELSE 0 END) as null_price,
                SUM(CASE WHEN CAST(price AS DOUBLE) <= 0 THEN 1 ELSE 0 END) as zero_price,
                SUM(CASE WHEN quantity IS NULL THEN 1 ELSE 0 END) as null_quantity,
                SUM(CASE WHEN CAST(quantity AS DOUBLE) <= 0 THEN 1 ELSE 0 END) as zero_quantity,
                SUM(CASE WHEN timestamp IS NULL THEN 1 ELSE 0 END) as null_timestamp,
                SUM(CASE WHEN agg_trade_id IS NULL THEN 1 ELSE 0 END) as null_trade_id
            FROM binance_data.agg_trades
            WHERE symbol = '{symbol}'
        """

        result = self.conn.execute(query).fetchone()

        return {
            'total_records': result[0],
            'null_price': result[1],
            'zero_price': result[2],
            'null_quantity': result[3],
            'zero_quantity': result[4],
            'null_timestamp': result[5],
            'null_trade_id': result[6],
        }

    def get_missing_date_ranges(self, symbol: str, expected_start: datetime, expected_end: datetime) -> List[Dict]:
        """Identify missing date ranges based on expected coverage."""
        query = f"""
            SELECT MIN(timestamp) as first_ts, MAX(timestamp) as last_ts
            FROM binance_data.agg_trades
            WHERE symbol = '{symbol}'
        """

        result = self.conn.execute(query).fetchone()
        first_ts, last_ts = result

        first_dt = datetime.fromtimestamp(first_ts / 1000)
        last_dt = datetime.fromtimestamp(last_ts / 1000)

        missing_ranges = []

        # Check if missing data at the beginning
        if first_dt > expected_start:
            missing_ranges.append({
                'range_type': 'beginning',
                'start': expected_start,
                'end': first_dt,
                'duration_days': (first_dt - expected_start).days,
            })

        # Check if missing data at the end
        if last_dt < expected_end:
            missing_ranges.append({
                'range_type': 'end',
                'start': last_dt,
                'end': expected_end,
                'duration_days': (expected_end - last_dt).days,
            })

        return missing_ranges

    def generate_report(self, symbol: str, expected_start: datetime = None, expected_end: datetime = None):
        """Generate comprehensive data quality report."""
        print("=" * 80)
        print(f"DATA QUALITY REPORT: {symbol}")
        print("=" * 80)

        # 1. Summary
        print("\n1. DATA SUMMARY")
        print("-" * 80)
        summaries = self.get_data_summary()
        for summary in summaries:
            if summary['symbol'] == symbol:
                print(f"  Symbol:           {summary['symbol']}")
                print(f"  Total Records:    {summary['record_count']:,}")
                print(f"  First Timestamp:  {summary['first_timestamp']}")
                print(f"  Last Timestamp:   {summary['last_timestamp']}")
                print(f"  Duration:         {summary['duration_days']:.2f} days ({summary['duration_hours']:.2f} hours)")
                print(f"  Price Range:      ${summary['min_price']:,.2f} - ${summary['max_price']:,.2f}")
                print(f"  Average Price:    ${summary['avg_price']:,.2f}")

        # 2. Time Gaps
        print("\n2. TIME GAPS (> 1 minute)")
        print("-" * 80)
        gaps = self.find_time_gaps(symbol, min_gap_minutes=1.0)

        if gaps:
            print(f"  ⚠ Found {len(gaps)} time gap(s)")
            print()
            for i, gap in enumerate(gaps[:10], 1):  # Show top 10
                print(f"  Gap #{i}:")
                print(f"    Start:    {gap['start_time']}")
                print(f"    End:      {gap['end_time']}")
                print(f"    Duration: {gap['gap_days']:.2f} days ({gap['gap_hours']:.2f} hours)")
                print()

            if len(gaps) > 10:
                print(f"  ... and {len(gaps) - 10} more gaps")

        else:
            print("  ✓ No significant time gaps found")

        # 3. Duplicates
        print("\n3. DUPLICATE TIMESTAMPS")
        print("-" * 80)
        duplicates = self.find_duplicates(symbol)

        if not duplicates.empty:
            print(f"  ⚠ Found {len(duplicates)} timestamp(s) with duplicates")
            print()
            print(duplicates.head(10).to_string(index=False))

            if len(duplicates) > 10:
                print(f"\n  ... and {len(duplicates) - 10} more duplicate timestamps")

            total_duplicates = duplicates['dup_count'].sum() - len(duplicates)
            print(f"\n  Total duplicate records: {total_duplicates:,}")
        else:
            print("  ✓ No duplicate timestamps found")

        # 4. Data Quality
        print("\n4. DATA QUALITY CHECKS")
        print("-" * 80)
        quality = self.check_data_quality(symbol)

        issues = []
        if quality['null_price'] > 0:
            issues.append(f"  ⚠ {quality['null_price']:,} records with NULL price")
        if quality['zero_price'] > 0:
            issues.append(f"  ⚠ {quality['zero_price']:,} records with price <= 0")
        if quality['null_quantity'] > 0:
            issues.append(f"  ⚠ {quality['null_quantity']:,} records with NULL quantity")
        if quality['zero_quantity'] > 0:
            issues.append(f"  ⚠ {quality['zero_quantity']:,} records with quantity <= 0")
        if quality['null_timestamp'] > 0:
            issues.append(f"  ⚠ {quality['null_timestamp']:,} records with NULL timestamp")
        if quality['null_trade_id'] > 0:
            issues.append(f"  ⚠ {quality['null_trade_id']:,} records with NULL agg_trade_id")

        if issues:
            print("\n".join(issues))
        else:
            print("  ✓ No data quality issues found")

        # 5. Missing Date Ranges
        if expected_start and expected_end:
            print("\n5. MISSING DATE RANGES")
            print("-" * 80)
            missing = self.get_missing_date_ranges(symbol, expected_start, expected_end)

            if missing:
                for miss in missing:
                    print(f"  ⚠ Missing data at {miss['range_type']}:")
                    print(f"    Expected: {miss['start']} to {miss['end']}")
                    print(f"    Duration: {miss['duration_days']:.2f} days")
                    print()
            else:
                print("  ✓ Data coverage matches expected range")

        # 6. Recommendations
        print("\n6. RECOMMENDATIONS")
        print("-" * 80)

        recommendations = []

        if gaps:
            recommendations.append("  → Fill time gaps by running incremental data fetch:")
            for gap in gaps[:5]:
                start_str = gap['start_time'].strftime('%Y-%m-%d')
                end_str = gap['end_time'].strftime('%Y-%m-%d')
                recommendations.append(f"     uv run binance-download --symbols {symbol} --start-date {start_str}")

        if not duplicates.empty:
            recommendations.append("  → Remove duplicate records:")
            recommendations.append(f"     Use DISTINCT or GROUP BY in queries")
            recommendations.append(f"     Consider deduplication in the pipeline")

        if issues:
            recommendations.append("  → Fix data quality issues:")
            recommendations.append(f"     Review data ingestion pipeline for validation")
            recommendations.append(f"     Add NULL checks and value range validation")

        if not recommendations:
            recommendations.append("  ✓ Data quality looks good!")

        print("\n".join(recommendations))

        print("\n" + "=" * 80)


def main():
    """Run data gap analysis."""
    db_path = "binance_pipeline.duckdb"

    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        print("\n💡 Run data ingestion first:")
        print("   uv run binance-download --symbols BTCUSDT --start-date 2025-10-01")
        return

    # Analyze each symbol in the database
    with DataGapAnalyzer(db_path) as analyzer:
        # Get all symbols
        summaries = analyzer.get_data_summary()

        for summary in summaries:
            symbol = summary['symbol']

            # Expected range: Oct 1, 2025 to now
            expected_start = datetime(2025, 10, 1)
            expected_end = datetime.now()

            analyzer.generate_report(
                symbol=symbol,
                expected_start=expected_start,
                expected_end=expected_end
            )

            print("\n")


if __name__ == "__main__":
    main()
