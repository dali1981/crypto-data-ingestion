"""
Explore what data is in the DuckDB database.

Shows:
- Available tables
- Symbols and date ranges
- Data volume statistics
- Sample data
- Data quality metrics

Run with: uv run python explore_database.py
"""

import duckdb
from pathlib import Path
from datetime import datetime
import sys


def format_number(num):
    """Format large numbers with commas."""
    return f"{num:,}"


def format_bytes(bytes_size):
    """Format bytes to human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"


def explore_database(db_path="binance_pipeline.duckdb"):
    """Explore the database and show what data is available."""

    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        print(f"\nAvailable .duckdb files:")
        for db_file in Path(".").glob("*.duckdb"):
            print(f"  - {db_file.name}")
        return

    print("\n" + "="*80)
    print(f"DATABASE EXPLORER: {db_path}")
    print("="*80 + "\n")

    conn = duckdb.connect(db_path, read_only=True)

    # 1. Database Size
    print("📊 DATABASE SIZE")
    print("-" * 80)
    db_size = Path(db_path).stat().st_size
    print(f"File size: {format_bytes(db_size)}")
    print()

    # 2. List all tables
    print("📋 TABLES")
    print("-" * 80)
    tables = conn.execute("""
        SELECT schema_name, table_name,
               estimated_size as row_count
        FROM duckdb_tables()
        WHERE schema_name NOT IN ('information_schema', 'pg_catalog')
        ORDER BY schema_name, table_name
    """).fetchall()

    if not tables:
        print("No tables found in database.")
        return

    for schema, table, rows in tables:
        full_name = f"{schema}.{table}" if schema else table
        print(f"  {full_name:<50} {format_number(rows):>15} rows")
    print()

    # 3. Analyze each table
    for schema, table_name, _ in tables:
        full_table = f'"{schema}"."{table_name}"' if schema else f'"{table_name}"'

        print(f"\n{'='*80}")
        print(f"TABLE: {schema}.{table_name if schema else table_name}")
        print("="*80)

        # Get columns
        try:
            columns = conn.execute(f"""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = '{schema}' AND table_name = '{table_name}'
                ORDER BY ordinal_position
            """).fetchall()

            print("\n📝 Columns:")
            for col_name, col_type in columns:
                print(f"  {col_name:<30} {col_type}")

        except Exception as e:
            print(f"  ⚠️  Could not get columns: {e}")

        # Get row count
        try:
            result = conn.execute(f"SELECT COUNT(*) FROM {full_table}").fetchone()
            row_count = result[0] if result else 0
            print(f"\n📈 Total Records: {format_number(row_count)}")

            if row_count == 0:
                print("  (Table is empty)")
                continue

        except Exception as e:
            print(f"  ⚠️  Could not count rows: {e}")
            continue

        # Check for symbol column
        has_symbol = any(col[0].lower() == 'symbol' for col in columns)
        has_timestamp = any(col[0].lower() in ['timestamp', 'time', 'trade_time'] for col in columns)

        # Symbol breakdown
        if has_symbol:
            try:
                symbols = conn.execute(f"""
                    SELECT symbol, COUNT(*) as count
                    FROM {full_table}
                    GROUP BY symbol
                    ORDER BY count DESC
                """).fetchall()

                print(f"\n💱 Symbols ({len(symbols)} total):")
                for symbol, count in symbols[:10]:  # Show top 10
                    print(f"  {symbol:<15} {format_number(count):>15} records")
                if len(symbols) > 10:
                    print(f"  ... and {len(symbols) - 10} more symbols")

            except Exception as e:
                print(f"  ⚠️  Could not get symbol breakdown: {e}")

        # Date range
        if has_timestamp:
            try:
                # Try different timestamp column names
                ts_col = None
                for col in ['timestamp', 'time', 'trade_time', 'event_time']:
                    if any(c[0].lower() == col for c in columns):
                        ts_col = col
                        break

                if ts_col:
                    if has_symbol:
                        # Per-symbol date ranges
                        date_ranges = conn.execute(f"""
                            SELECT
                                symbol,
                                MIN({ts_col}) as min_time,
                                MAX({ts_col}) as max_time,
                                COUNT(*) as count
                            FROM {full_table}
                            GROUP BY symbol
                            ORDER BY symbol
                        """).fetchall()

                        print(f"\n📅 Date Ranges by Symbol:")
                        for symbol, min_time, max_time, count in date_ranges[:10]:
                            if isinstance(min_time, int):
                                # Unix timestamp in milliseconds
                                min_dt = datetime.fromtimestamp(min_time / 1000)
                                max_dt = datetime.fromtimestamp(max_time / 1000)
                            else:
                                min_dt = min_time
                                max_dt = max_time

                            duration = max_dt - min_dt
                            print(f"  {symbol:<12} {min_dt.strftime('%Y-%m-%d %H:%M')} to {max_dt.strftime('%Y-%m-%d %H:%M')} ({duration.days}d {duration.seconds//3600}h)")

                        if len(date_ranges) > 10:
                            print(f"  ... and {len(date_ranges) - 10} more symbols")
                    else:
                        # Overall date range
                        result = conn.execute(f"""
                            SELECT
                                MIN({ts_col}) as min_time,
                                MAX({ts_col}) as max_time
                            FROM {full_table}
                        """).fetchone()

                        if result:
                            min_time, max_time = result
                            if isinstance(min_time, int):
                                min_dt = datetime.fromtimestamp(min_time / 1000)
                                max_dt = datetime.fromtimestamp(max_time / 1000)
                            else:
                                min_dt = min_time
                                max_dt = max_time

                            duration = max_dt - min_dt
                            print(f"\n📅 Date Range:")
                            print(f"  From: {min_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                            print(f"  To:   {max_dt.strftime('%Y-%m-%d %H:%M:%S')}")
                            print(f"  Duration: {duration.days} days, {duration.seconds//3600} hours")

            except Exception as e:
                print(f"  ⚠️  Could not get date range: {e}")

        # Data quality
        try:
            print(f"\n🔍 Data Quality:")

            # Check for nulls in each column
            null_checks = []
            for col_name, _ in columns[:10]:  # Check first 10 columns
                try:
                    result = conn.execute(f"""
                        SELECT COUNT(*)
                        FROM {full_table}
                        WHERE "{col_name}" IS NULL
                    """).fetchone()
                    null_count = result[0] if result else 0
                    if null_count > 0:
                        null_checks.append((col_name, null_count))
                except:
                    pass

            if null_checks:
                print(f"  Columns with NULL values:")
                for col, null_count in null_checks:
                    pct = (null_count / row_count * 100) if row_count > 0 else 0
                    print(f"    {col:<30} {format_number(null_count):>10} ({pct:.1f}%)")
            else:
                print(f"  ✅ No NULL values found")

        except Exception as e:
            print(f"  ⚠️  Could not check data quality: {e}")

        # Sample data
        try:
            print(f"\n📄 Sample Data (first 3 rows):")
            sample = conn.execute(f"SELECT * FROM {full_table} LIMIT 3").fetchall()
            col_names = [desc[0] for desc in conn.description]

            # Print header
            header = " | ".join(f"{col[:15]:<15}" for col in col_names[:8])  # First 8 columns
            print(f"  {header}")
            print(f"  {'-' * len(header)}")

            # Print rows
            for row in sample:
                row_str = " | ".join(f"{str(val)[:15]:<15}" for val in row[:8])
                print(f"  {row_str}")

            if len(col_names) > 8:
                print(f"  ... and {len(col_names) - 8} more columns")

        except Exception as e:
            print(f"  ⚠️  Could not get sample data: {e}")

        print()

    # 4. Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    total_rows = sum(row[2] for row in tables if row[2])
    print(f"Total tables: {len(tables)}")
    print(f"Total records: {format_number(total_rows)}")
    print(f"Database size: {format_bytes(db_size)}")

    if total_rows > 0:
        bytes_per_row = db_size / total_rows
        print(f"Average bytes per row: {bytes_per_row:.2f}")

    print("\n" + "="*80)
    print("✅ Exploration complete!")
    print("="*80 + "\n")

    conn.close()


if __name__ == "__main__":
    # Check if custom db path provided
    db_path = sys.argv[1] if len(sys.argv) > 1 else "binance_pipeline.duckdb"

    explore_database(db_path)
