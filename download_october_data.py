"""
Download October 2025 data for investigation of the October 10 crash.

This will download 5-minute candle data for BNB, XRP, and other liquid pairs
for the entire month of October 2025.
"""

import dlt
from dlt.destinations import filesystem
from binance_tick_data.sources.rest_api import binance_intraday_candles, BinanceConfig

# Symbols to investigate (focus on crash + comparison symbols)
SYMBOLS = [
    'BTCUSDT',   # Bitcoin (comparison)
    'ETHUSDT',   # Ethereum (comparison)
    'BNBUSDT',   # BNB (crash victim)
    'XRPUSDT',   # XRP (crash victim)
    'SOLUSDT',   # Solana (comparison)
    'ADAUSDT',   # Cardano (comparison)
    'DOGEUSDT',  # Dogecoin (comparison)
]

def main():
    print("="*70)
    print("DOWNLOADING OCTOBER 2025 DATA FOR CRASH INVESTIGATION")
    print("="*70)
    print(f"\nSymbols: {', '.join(SYMBOLS)}")
    print("Period: October 1-31, 2025")
    print("Interval: 5 minutes")
    print("\nThis will download ~8,928 candles per symbol (31 days × 24h × 12 candles/hour)")
    print("="*70)

    # Create config
    config = BinanceConfig()

    # Configure destination (parquet files)
    dest = filesystem(
        layout="{table_name}/{YYYY}-{MM}-{DD}/{load_id}.{file_id}.{ext}"
    )

    # Configure pipeline
    pipeline = dlt.pipeline(
        pipeline_name='binance_oct2025_investigation',
        destination=dest,
        dataset_name='liquid_100_5m_oct2025',
    )

    # Download data
    # Note: binance_intraday_candles doesn't have end_date parameter
    # It will fetch from start_date until ~1 hour ago (to avoid incomplete candles)
    source = binance_intraday_candles(
        config=config,
        symbols=SYMBOLS,
        interval='5m',
        start_date='2025-10-01',
    )

    print("\nStarting download...")
    info = pipeline.run(source)

    print("\n" + "="*70)
    print("DOWNLOAD COMPLETE")
    print("="*70)
    print(f"\nPipeline info:")
    print(f"  Dataset: {info.dataset_name}")
    print(f"  Destination: {info.destination_type}")
    print(f"  Load packages: {len(info.load_packages)}")

    if info.has_failed_jobs:
        print(f"\n⚠️  Warning: {len(info.failed_jobs)} jobs failed")
        for job in info.failed_jobs:
            print(f"    - {job}")
    else:
        print("\n✓ All jobs completed successfully")

    print(f"\nData location: {pipeline.working_dir}")
    print("\nNext: Run investigate_oct10_local.py to analyze the data")


if __name__ == '__main__':
    main()
