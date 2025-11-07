"""
Investigation script for October 10, 2025 data quality issue (LOCAL PARQUET FILES).

This script queries local parquet files to investigate:
- BNB crash: -20.95% ($1,114 → $881) at 21:15 UTC
- XRP crash: -21.34% ($2.28 → $1.80) at 21:15 UTC
"""

import pandas as pd
import pyarrow.parquet as pq
from datetime import datetime, timedelta
from pathlib import Path
import glob

# Use the newly downloaded October data (in project directory)
DATA_DIR = Path("/Users/mohamedali/trading_project/dlt-starter/dev/data/liquid_100_5m_oct2025")

def load_symbol_data(symbol: str, start_time: datetime, end_time: datetime):
    """Load data for a specific symbol from local parquet files."""
    print(f"\n{'='*70}")
    print(f"Loading {symbol} data from {start_time} to {end_time}")
    print(f"{'='*70}")

    symbol_dir = DATA_DIR / f"{symbol.lower()}_5m"

    if not symbol_dir.exists():
        print(f"✗ Directory not found: {symbol_dir}")
        return pd.DataFrame()

    # Find all parquet and jsonl.gz files
    parquet_files = list(symbol_dir.rglob("*.parquet"))
    jsonl_files = list(symbol_dir.rglob("*.jsonl.gz"))
    all_files = parquet_files + jsonl_files
    print(f"Found {len(parquet_files)} parquet files and {len(jsonl_files)} jsonl.gz files")

    if not all_files:
        print(f"✗ No data files found in {symbol_dir}")
        return pd.DataFrame()

    # Load all data files
    dfs = []
    for file in all_files:
        try:
            if file.suffix == '.parquet':
                df = pd.read_parquet(file)
            elif file.name.endswith('.jsonl.gz'):
                # Read compressed JSONL
                import gzip
                import json
                records = []
                with gzip.open(file, 'rt') as f:
                    for line in f:
                        records.append(json.loads(line))
                df = pd.DataFrame(records)
            dfs.append(df)
        except Exception as e:
            print(f"Warning: Could not read {file.name}: {e}")

    if not dfs:
        print(f"✗ No data loaded")
        return pd.DataFrame()

    # Concatenate all data
    df = pd.concat(dfs, ignore_index=True)

    # Convert timestamps
    df['open_time_dt'] = pd.to_datetime(df['open_time'], unit='ms')
    df['close_time_dt'] = pd.to_datetime(df['close_time'], unit='ms')

    # Filter time range
    df = df[
        (df['open_time_dt'] >= start_time) &
        (df['open_time_dt'] <= end_time)
    ].sort_values('open_time')

    print(f"✓ Loaded {len(df)} candles")

    if len(df) > 0:
        print(f"  Time range: {df['open_time_dt'].min()} to {df['open_time_dt'].max()}")
        print(f"  Price range: ${float(df['low'].min()):.2f} to ${float(df['high'].max()):.2f}")
    else:
        # Show what data is actually available
        all_df = pd.concat(dfs, ignore_index=True)
        all_df['open_time_dt'] = pd.to_datetime(all_df['open_time'], unit='ms')
        print(f"  Available data range: {all_df['open_time_dt'].min()} to {all_df['open_time_dt'].max()}")

    return df


def analyze_price_changes(df: pd.DataFrame, symbol: str):
    """Analyze price changes and detect anomalies."""
    if df.empty:
        print(f"No data to analyze for {symbol}")
        return df

    print(f"\n{'='*70}")
    print(f"Price Change Analysis: {symbol}")
    print(f"{'='*70}")

    # Convert to float
    df['open'] = df['open'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['close'] = df['close'].astype(float)
    df['volume'] = df['volume'].astype(float)

    # Calculate price changes
    df['price_change'] = df['close'] - df['open']
    df['price_change_pct'] = (df['price_change'] / df['open']) * 100
    df['candle_range'] = df['high'] - df['low']
    df['candle_range_pct'] = (df['candle_range'] / df['low']) * 100

    # Detect large moves
    large_moves = df[abs(df['price_change_pct']) > 5.0].copy()

    if len(large_moves) > 0:
        print(f"\n⚠️  Found {len(large_moves)} candles with >5% price change:")
        print("-" * 70)
        for idx, row in large_moves.iterrows():
            print(f"Time:   {row['open_time_dt']}")
            print(f"Open:   ${row['open']:.2f}")
            print(f"High:   ${row['high']:.2f}")
            print(f"Low:    ${row['low']:.2f}")
            print(f"Close:  ${row['close']:.2f}")
            print(f"Change: {row['price_change_pct']:.2f}%")
            print(f"Volume: {row['volume']:.2f}")
            print(f"Trades: {row['trades']}")
            print("-" * 70)
    else:
        print("✓ No candles with >5% price change detected")

    # Summary statistics
    print(f"\nPrice Change Statistics:")
    print(f"  Mean change:    {df['price_change_pct'].mean():.4f}%")
    print(f"  Std deviation:  {df['price_change_pct'].std():.4f}%")
    print(f"  Min change:     {df['price_change_pct'].min():.4f}%")
    print(f"  Max change:     {df['price_change_pct'].max():.4f}%")
    print(f"  Range (Hi-Lo):  {df['candle_range_pct'].mean():.4f}% (mean)")

    return df


def check_specific_crash(df: pd.DataFrame, symbol: str, target_time: datetime,
                         expected_from: float, expected_to: float):
    """Check for specific crash at target time."""
    print(f"\n{'='*70}")
    print(f"Checking for specific crash: {symbol}")
    print(f"{'='*70}")
    print(f"Target time:     {target_time}")
    print(f"Expected crash:  ${expected_from:.2f} → ${expected_to:.2f}")
    print(f"Expected change: {((expected_to - expected_from) / expected_from * 100):.2f}%")

    if df.empty:
        print(f"✗ No data available to check")
        return

    # Find candles around target time (±30 minutes)
    time_window = df[
        (df['open_time_dt'] >= target_time - timedelta(minutes=30)) &
        (df['open_time_dt'] <= target_time + timedelta(minutes=30))
    ].copy()

    if time_window.empty:
        print(f"✗ No data found around {target_time}")
        return

    print(f"\n✓ Found {len(time_window)} candles in ±30min window")
    print("\nCandles around crash time:")
    print("-" * 70)

    for idx, row in time_window.iterrows():
        marker = ">>> " if abs((row['open_time_dt'] - target_time).total_seconds()) < 300 else "    "
        print(f"{marker}{row['open_time_dt']} | "
              f"O: ${row['open']:>8.2f} | H: ${row['high']:>8.2f} | "
              f"L: ${row['low']:>8.2f} | C: ${row['close']:>8.2f} | "
              f"Δ: {row.get('price_change_pct', 0):>6.2f}%")

    # Check if crash prices exist
    has_from_price = any((time_window['open'] - expected_from).abs() < 50)
    has_to_price = any((time_window['close'] - expected_to).abs() < 50)

    print(f"\nCrash Validation:")
    print(f"  Expected 'from' price ${expected_from:.2f}: {'FOUND' if has_from_price else 'NOT FOUND'}")
    print(f"  Expected 'to' price ${expected_to:.2f}: {'FOUND' if has_to_price else 'NOT FOUND'}")


def main():
    print("="*70)
    print("INVESTIGATING OCTOBER 10, 2025 DATA QUALITY ISSUE (LOCAL FILES)")
    print("="*70)
    print("\nReported crashes:")
    print("  - BNB: -20.95% ($1,114 → $881) at 21:15 UTC")
    print("  - XRP: -21.34% ($2.28 → $1.80) at 21:15 UTC")

    # Target time
    crash_time = datetime(2025, 10, 10, 21, 15)

    # Load data for wider time range (entire day)
    start_time = datetime(2025, 10, 10, 0, 0)
    end_time = datetime(2025, 10, 11, 0, 0)

    # Investigate BNB
    print("\n" + "="*70)
    print("PART 1: BNB INVESTIGATION")
    print("="*70)
    bnb_df = load_symbol_data('BNBUSDT', start_time, end_time)
    if not bnb_df.empty:
        bnb_df = analyze_price_changes(bnb_df, 'BNBUSDT')
        check_specific_crash(bnb_df, 'BNBUSDT', crash_time, 1114.0, 881.0)
    else:
        print("\n⚠️  BNB data not found in expected date range")
        print("     Loading ALL available BNB data to show what exists...")
        bnb_all = load_symbol_data('BNBUSDT',
                                   datetime(2020, 1, 1),
                                   datetime(2030, 12, 31))
        if not bnb_all.empty:
            bnb_all = analyze_price_changes(bnb_all, 'BNBUSDT')

    # Investigate XRP
    print("\n" + "="*70)
    print("PART 2: XRP INVESTIGATION")
    print("="*70)
    xrp_df = load_symbol_data('XRPUSDT', start_time, end_time)
    if not xrp_df.empty:
        xrp_df = analyze_price_changes(xrp_df, 'XRPUSDT')
        check_specific_crash(xrp_df, 'XRPUSDT', crash_time, 2.28, 1.80)
    else:
        print("\n⚠️  XRP data not found in expected date range")
        print("     Loading ALL available XRP data to show what exists...")
        xrp_all = load_symbol_data('XRPUSDT',
                                   datetime(2020, 1, 1),
                                   datetime(2030, 12, 31))
        if not xrp_all.empty:
            xrp_all = analyze_price_changes(xrp_all, 'XRPUSDT')

    # Cross-check: Load other symbols to see if crash was market-wide
    print("\n" + "="*70)
    print("PART 3: MARKET-WIDE CHECK")
    print("="*70)
    print("Checking if crash affected other symbols...")

    other_symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
    for symbol in other_symbols:
        df = load_symbol_data(symbol,
                             crash_time - timedelta(minutes=30),
                             crash_time + timedelta(minutes=30))
        if not df.empty:
            df = analyze_price_changes(df, symbol)

    print("\n" + "="*70)
    print("INVESTIGATION COMPLETE")
    print("="*70)


if __name__ == '__main__':
    main()
