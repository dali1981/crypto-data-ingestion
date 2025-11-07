"""
Investigation script for October 10, 2025 data quality issue.

This script queries MinIO Delta Lake to investigate:
- BNB crash: -20.95% ($1,114 → $881) at 21:15 UTC
- XRP crash: -21.34% ($2.28 → $1.80) at 21:15 UTC
"""

import pandas as pd
from datetime import datetime, timedelta
import deltalake as dl

# MinIO configuration (from notebook)
STORAGE_OPTIONS = {
    'AWS_ENDPOINT_URL': 'http://localhost:9000',
    'AWS_ACCESS_KEY_ID': 'minioadmin',
    'AWS_SECRET_ACCESS_KEY': 'minioadmin',
    'AWS_REGION': 'us-east-1',
    'AWS_ALLOW_HTTP': 'true',
}

TABLE_PATH = 's3://binance-data/warehouse/liquid_100_5m'

def load_symbol_data(symbol: str, start_time: datetime, end_time: datetime):
    """Load data for a specific symbol and time range."""
    print(f"\n{'='*70}")
    print(f"Loading {symbol} data from {start_time} to {end_time}")
    print(f"{'='*70}")

    try:
        # Load Delta table
        dt = dl.DeltaTable(TABLE_PATH, storage_options=STORAGE_OPTIONS)

        # Convert to Arrow table, then pandas
        arrow_table = dt.to_pyarrow_table()
        df = arrow_table.to_pandas()

        # Filter for symbol and time range
        df = df[df['symbol'] == symbol].copy()

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
            print(f"  Price range: ${df['low'].min():.2f} to ${df['high'].max():.2f}")

        return df

    except Exception as e:
        print(f"✗ Error loading data: {e}")
        return pd.DataFrame()


def analyze_price_changes(df: pd.DataFrame, symbol: str):
    """Analyze price changes and detect anomalies."""
    if df.empty:
        print(f"No data to analyze for {symbol}")
        return

    print(f"\n{'='*70}")
    print(f"Price Change Analysis: {symbol}")
    print(f"{'='*70}")

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
        marker = ">>> " if row['open_time_dt'] == target_time else "    "
        print(f"{marker}{row['open_time_dt']} | "
              f"O: ${row['open']:>8.2f} | H: ${row['high']:>8.2f} | "
              f"L: ${row['low']:>8.2f} | C: ${row['close']:>8.2f} | "
              f"Δ: {row.get('price_change_pct', 0):>6.2f}%")

    # Check if crash prices exist
    has_from_price = any((time_window['open'] - expected_from).abs() < 5)
    has_to_price = any((time_window['close'] - expected_to).abs() < 5)

    print(f"\nCrash Validation:")
    print(f"  Expected 'from' price ${expected_from:.2f}: {'FOUND' if has_from_price else 'NOT FOUND'}")
    print(f"  Expected 'to' price ${expected_to:.2f}: {'FOUND' if has_to_price else 'NOT FOUND'}")


def main():
    print("="*70)
    print("INVESTIGATING OCTOBER 10, 2025 DATA QUALITY ISSUE")
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

    # Investigate XRP
    print("\n" + "="*70)
    print("PART 2: XRP INVESTIGATION")
    print("="*70)
    xrp_df = load_symbol_data('XRPUSDT', start_time, end_time)
    if not xrp_df.empty:
        xrp_df = analyze_price_changes(xrp_df, 'XRPUSDT')
        check_specific_crash(xrp_df, 'XRPUSDT', crash_time, 2.28, 1.80)

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
    print("\nNext steps:")
    print("1. Review the data above to determine:")
    print("   - Does the crash exist in the data?")
    print("   - Is it isolated to BNB/XRP or market-wide?")
    print("   - Do the reported prices match actual data?")
    print("2. If crash exists, cross-validate with Binance API")
    print("3. Implement anomaly detection to prevent future issues")


if __name__ == '__main__':
    main()
