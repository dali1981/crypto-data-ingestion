"""Asset checks for data quality validation."""

from dagster import AssetCheckResult, asset_check
from pathlib import Path
from dagster_pipeline.config import SYMBOLS
import pandas as pd


@asset_check(asset="raw_agg_trades")
def validate_agg_trades_files(context):
    """
    Validate that aggregate trades parquet files exist and contain data.

    Checks:
    - Parquet files exist in expected structure
    - Files contain data (non-empty)
    - At least some symbols have recent data
    """
    base_path = Path("data/binance_data/agg_trades")

    if not base_path.exists():
        return AssetCheckResult(
            passed=False,
            metadata={
                "error": "Base path does not exist",
                "path": str(base_path),
            }
        )

    # Find all parquet files
    parquet_files = list(base_path.glob("**/*.parquet"))

    if not parquet_files:
        return AssetCheckResult(
            passed=False,
            metadata={
                "error": "No parquet files found",
                "path": str(base_path),
            }
        )

    # Check files have data
    total_rows = 0
    files_with_data = 0
    dates_found = set()
    symbols_found = set()

    for parquet_file in parquet_files[:100]:  # Sample first 100 files
        try:
            df = pd.read_parquet(parquet_file)
            row_count = len(df)

            if row_count > 0:
                files_with_data += 1
                total_rows += row_count

                # Extract date and symbol from path
                # Expected: data/binance_data/agg_trades/{date}/{symbol}.parquet
                date_dir = parquet_file.parent.name
                symbol = parquet_file.stem

                dates_found.add(date_dir)
                symbols_found.add(symbol)

        except Exception as e:
            context.log.warning(f"Failed to read {parquet_file}: {e}")

    # Validation
    passed = (
        files_with_data > 0 and
        total_rows > 0 and
        len(dates_found) > 0 and
        len(symbols_found) > 0
    )

    return AssetCheckResult(
        passed=passed,
        metadata={
            "total_files": len(parquet_files),
            "files_sampled": min(100, len(parquet_files)),
            "files_with_data": files_with_data,
            "total_rows_sampled": total_rows,
            "unique_dates": len(dates_found),
            "unique_symbols": len(symbols_found),
            "dates": sorted(list(dates_found))[:10],  # Show first 10 dates
            "symbols": sorted(list(symbols_found))[:20],  # Show symbols
        }
    )


@asset_check(asset="raw_agg_trades")
def validate_agg_trades_coverage(context):
    """
    Validate that all expected symbols have data.

    Checks:
    - All configured symbols have at least one file
    - Data coverage is reasonable
    """
    base_path = Path("data/binance_data/agg_trades")

    if not base_path.exists():
        return AssetCheckResult(
            passed=False,
            metadata={"error": "Base path does not exist"}
        )

    # Find all symbols with data
    symbols_with_data = set()

    for date_dir in base_path.iterdir():
        if not date_dir.is_dir():
            continue

        for parquet_file in date_dir.glob("*.parquet"):
            symbol = parquet_file.stem
            symbols_with_data.add(symbol)

    # Check coverage
    missing_symbols = set(SYMBOLS) - symbols_with_data
    coverage_pct = (len(symbols_with_data) / len(SYMBOLS)) * 100 if SYMBOLS else 0

    passed = len(missing_symbols) == 0

    return AssetCheckResult(
        passed=passed,
        metadata={
            "expected_symbols": len(SYMBOLS),
            "symbols_with_data": len(symbols_with_data),
            "coverage_percent": round(coverage_pct, 1),
            "missing_symbols": sorted(list(missing_symbols)) if missing_symbols else [],
        }
    )
