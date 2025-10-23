"""Quick test of DLT integration before running full pipeline."""

import dlt
from binance_tick_data import BinanceConfig, binance_historical_data

# Test with just 1 symbol and limited records
config = BinanceConfig(
    symbols=["ETHUSDT"],
    historical_start_date="2025-10-21",
    historical_max_records=1000,  # Just 1000 records for testing
)

# Create pipeline with filesystem destination
pipeline = dlt.pipeline(
    pipeline_name="test_binance",
    destination=dlt.destinations.filesystem("data/test_parquet"),
    dataset_name="test_data",
)

print("Fetching test data from Binance...")
source = binance_historical_data(config)

# Run and specify parquet format
load_info = pipeline.run(source, loader_file_format="parquet")

print(f"\n✅ Load completed!")
print(f"Load packages: {len(load_info.load_packages)}")

# Check what was created
import os
parquet_dir = "data/test_parquet"
if os.path.exists(parquet_dir):
    print(f"\n📁 Files created in {parquet_dir}:")
    for root, dirs, files in os.walk(parquet_dir):
        for file in files:
            filepath = os.path.join(root, file)
            size = os.path.getsize(filepath)
            print(f"  {filepath}: {size:,} bytes")
else:
    print(f"\n❌ Directory {parquet_dir} not created!")

# Try to read the data back
print("\n📊 Trying to read data back with DuckDB...")
import duckdb
conn = duckdb.connect(":memory:")
result = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{parquet_dir}/**/*.parquet')").fetchone()
print(f"  Total records in parquet files: {result[0]:,}")
conn.close()

print("\n✅ TEST COMPLETE - DLT integration works!")
