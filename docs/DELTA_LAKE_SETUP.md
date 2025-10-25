# Delta Lake Setup for Binance Data Pipeline

## Overview

This project uses Delta Lake as a table format for Parquet storage. Delta Lake provides:

- **True date-based partitioning**: Data is organized by actual trade dates (not pipeline run dates)
- **ACID transactions**: Consistent reads during writes
- **Time travel**: Query historical versions of data
- **Schema evolution**: Add/modify columns without rewriting data
- **Better performance**: Partition pruning and file statistics
- **Simpler architecture**: No catalog services needed (metadata stored with data)

## Architecture

Delta Lake uses a **simple, self-contained** architecture:

```
┌─────────────────────┐
│  Pipeline Process   │
│  (DLT + deltalake)  │
└──────────┬──────────┘
           │
           ▼
    ┌─────────────┐
    │   MinIO     │
    │  (S3 API)   │
    └─────────────┘
```

### Components

1. **MinIO** (ports 9000, 9001)
   - S3-compatible object storage
   - Stores both data files (Parquet) and metadata (transaction logs)
   - Console at http://localhost:9001 (minioadmin/minioadmin)

**That's it!** No PostgreSQL, no REST catalog, no separate metadata services.

### How Delta Lake Stores Metadata

Unlike Iceberg which requires a separate catalog, Delta Lake stores its transaction log **alongside the data** in the `_delta_log/` directory:

```
s3://binance-data/warehouse/
└── binance_test.db/
    └── BTCUSDT/
        ├── _delta_log/               ← Transaction log (metadata)
        │   ├── 00000000000.json      ← Initial transaction
        │   ├── 00000000001.json      ← Incremental updates
        │   └── 00000000002.json
        ├── date=2024-01-01/          ← Data partitions
        │   └── part-001.parquet
        ├── date=2024-01-02/
        │   └── part-001.parquet
        └── date=2024-01-03/
            └── part-001.parquet
```

## Getting Started

### 1. Start MinIO

```bash
# Start MinIO service
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f minio
```

Expected output:
```
NAME             STATUS   PORTS
binance-minio    Up       0.0.0.0:9000-9001->9000-9001/tcp
```

### 2. Run the Pipeline with Delta Lake

```bash
# Quick test with single symbol
uv run python examples/01_run_pipeline_example.py \
  --symbol BTCUSDT \
  --delta \
  --start-date 2024-01-01

# Multiple symbols
uv run python examples/01_run_pipeline_example.py \
  --symbols BTCUSDT --symbols ETHUSDT --symbols BNBUSDT \
  --delta

# Production config (larger buffers)
uv run python examples/01_run_pipeline_example.py \
  --symbol BTCUSDT \
  --delta \
  --profile production
```

### 3. Verify Data Partitioning

The data will be partitioned by the `date` column (actual trade date):

```
s3://binance-data/warehouse/binance_test.db/
├── BTCUSDT/
│   ├── _delta_log/
│   │   └── 00000000000.json
│   ├── date=2024-01-01/
│   │   └── *.parquet
│   ├── date=2024-01-02/
│   │   └── *.parquet
│   └── date=2024-01-03/
│       └── *.parquet
├── ETHUSDT/
│   └── ...
└── BNBUSDT/
    └── ...
```

## Querying Data

### Using DuckDB

```python
import duckdb

con = duckdb.connect()

# Query Delta table directly
result = con.execute("""
    SELECT
        date,
        COUNT(*) as trade_count,
        MIN(CAST(price AS DOUBLE)) as min_price,
        MAX(CAST(price AS DOUBLE)) as max_price,
        SUM(CAST(quantity AS DOUBLE)) as total_volume
    FROM delta_scan('s3://binance-data/warehouse/binance_test.db/BTCUSDT')
    WHERE date >= '2024-01-01'
    GROUP BY date
    ORDER BY date
""").fetchdf()

print(result)
```

### Using deltalake-python

```python
from deltalake import DeltaTable
import pyarrow.compute as pc

# Load Delta table
dt = DeltaTable("s3://binance-data/warehouse/binance_test.db/BTCUSDT")

# Scan with partition filter (efficient!)
df = dt.to_pyarrow_dataset().to_table(
    filter=(pc.field("date") >= "2024-01-01") & (pc.field("date") <= "2024-01-31")
).to_pandas()

print(f"Loaded {len(df)} trades from January 2024")

# View table metadata
print(f"Version: {dt.version()}")
print(f"Files: {dt.file_uris()}")
```

### Using PySpark

```python
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .appName("binance-analysis") \
    .config("spark.jars.packages", "io.delta:delta-core_2.12:2.4.0") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
    .getOrCreate()

# Read Delta table
df = spark.read.format("delta").load("s3://binance-data/warehouse/binance_test.db/BTCUSDT")

# Query with partition pruning
df.filter("date = '2024-01-01'").show()
```

## Configuration

### DLT Delta Lake Settings

Delta Lake is configured in `examples/01_run_pipeline_example.py`:

```python
# Filesystem destination with S3 bucket
filesystem(bucket_url="s3://binance-data/warehouse")

# Enable Delta table format
pipeline.run(source, table_format="delta")
```

### Partition Configuration

Partitioning is defined in `src/binance_tick_data/sources/rest_api.py`:

```python
@dlt.resource(
    name=f"agg_trades_{symbol.lower()}",
    table_name=symbol.upper(),
    write_disposition="append",
    primary_key="agg_trade_id",
    columns={"date": {"partition": True}},  # Partition by trade date
)
```

The `date` column is extracted from the trade timestamp:

```python
dt = datetime.fromtimestamp(trade["T"] / 1000, tz=timezone.utc)
transformed_trades.append({
    "agg_trade_id": trade["a"],
    "price": trade["p"],
    # ... other fields ...
    "date": dt.date().isoformat(),  # Trade date for partitioning
})
```

### S3 Credentials

Credentials are configured in `.dlt/secrets.toml`:

```toml
[destination.filesystem.credentials]
aws_access_key_id = "minioadmin"
aws_secret_access_key = "minioadmin"
endpoint_url = "http://localhost:9000"
region_name = "us-east-1"
```

## Maintenance

### View Logs

```bash
# MinIO logs
docker-compose logs -f minio
```

### Access MinIO Console

1. Open http://localhost:9001
2. Login: `minioadmin` / `minioadmin`
3. Browse bucket: `binance-data` → `warehouse/`

You'll see the `_delta_log/` directories alongside your partitioned data.

### Backup Data

```bash
# Backup MinIO data (includes both data and Delta transaction logs)
docker run --rm \
  -v binance-minio-data:/data \
  -v $(pwd)/backup:/backup \
  alpine tar czf /backup/minio-backup-$(date +%Y%m%d).tar.gz -C /data .
```

### Clean Up

```bash
# Stop services (data persists)
docker-compose down

# Stop and remove all data
docker-compose down -v

# Remove only MinIO data
docker volume rm binance-minio-data
```

## Advanced Features

### Time Travel

Query historical versions of your data:

```python
from deltalake import DeltaTable

dt = DeltaTable("s3://binance-data/warehouse/binance_test.db/BTCUSDT")

# List all versions
for v in range(dt.version() + 1):
    print(f"Version {v}: {dt.history(limit=v+1)[-1]}")

# Query specific version
df = dt.load_version(version=0).to_pandas()

# Query as of timestamp
df = dt.load_as_of_timestamp("2024-01-15T10:00:00Z").to_pandas()
```

### Schema Evolution

Add columns without rewriting data:

```python
from deltalake import DeltaTable, write_deltalake
import pyarrow as pa

dt = DeltaTable("s3://binance-data/warehouse/binance_test.db/BTCUSDT")

# Add new column (shown conceptually - actual implementation varies)
# Delta Lake automatically handles schema evolution when new columns appear
```

### Optimize and Vacuum

```python
from deltalake import DeltaTable

dt = DeltaTable("s3://binance-data/warehouse/binance_test.db/BTCUSDT")

# Optimize: Compact small files
dt.optimize()

# Vacuum: Remove old files (after 7 days retention)
dt.vacuum(retention_hours=168)
```

## Comparison: Regular Parquet vs Delta Lake

| Feature | Regular Parquet | Delta Lake |
|---------|----------------|------------|
| Partitioning | Pipeline run date | Actual trade date |
| Schema changes | Requires rewrite | Handled automatically |
| Concurrent writes | Not safe | ACID transactions |
| Time travel | Not supported | Built-in |
| Query optimization | Manual file selection | Automatic partition pruning |
| Infrastructure | None (just storage) | None (just storage) |
| Performance | Good for simple queries | Better for complex analytics |

## Troubleshooting

### Connection Refused

**Problem**: `Connection refused` when running pipeline

**Solution**:
```bash
# Check MinIO is running
docker-compose ps

# If not running, start it
docker-compose up -d

# Wait for health check
docker-compose logs -f minio
```

### Permission Denied

**Problem**: `Access Denied` when writing to MinIO

**Solution**:
```bash
# Verify bucket exists
docker-compose exec minio mc ls myminio

# Recreate bucket if needed
docker-compose restart minio-setup
```

### Slow Performance

**Problem**: Pipeline runs slowly

**Solution**:
- Use production profile: `--profile production`
- Increase buffer sizes in `.dlt/config.toml`
- Consider batching multiple symbols in single pipeline run

### Delta Log Not Found

**Problem**: `_delta_log not found` when querying

**Solution**:
- Ensure you ran pipeline with `--delta` flag
- Check MinIO bucket for `_delta_log/` directory
- Verify S3 credentials are correct

## References

- [Delta Lake Documentation](https://delta.io/)
- [DLT Delta Lake Destination](https://dlthub.com/docs/dlt-ecosystem/destinations/delta-iceberg)
- [deltalake-python Guide](https://delta-io.github.io/delta-rs/python/)
- [MinIO Documentation](https://min.io/docs/minio/linux/index.html)
