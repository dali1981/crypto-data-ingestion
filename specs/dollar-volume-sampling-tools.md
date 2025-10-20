# Dollar-Volume Sampling Tools for Tick Data

## Overview
Dollar-volume sampling is a technique used in quantitative finance to create volume-weighted bars (dollar bars) from high-frequency tick data. This document outlines the most efficient tools and approaches for this task.

## Recommended Tools & Libraries

### 1. Arctic/ArcticDB (Best for Large-Scale Tick Data)
**Purpose**: High-performance datastore for time-series tick data

**Advantages**:
- Extremely fast read/write for tick data
- Built-in support for financial time series
- Efficient storage with compression
- Works seamlessly with pandas

**Use case**: Store and retrieve tick data efficiently before processing

**Installation**:
```bash
pip install arcticdb
```

### 2. Polars (Fastest Processing)
**Advantages**:
- Much faster than pandas for large datasets (10-50x improvement)
- Lazy evaluation for memory efficiency
- Excellent for cumulative sum operations needed in dollar-volume bars
- Multi-threaded by default

**Best for**: Processing millions of ticks efficiently

**Installation**:
```bash
pip install polars
```

### 3. DuckDB (SQL-Based Processing)
**Advantages**:
- In-process SQL database optimized for analytics
- Can process data larger than RAM
- Fast aggregations and window functions
- Direct parquet file queries

**Best for**: SQL-based dollar volume calculations

**Installation**:
```bash
pip install duckdb
```

### 4. NumPy/Numba (Custom High-Performance)
**Advantages**:
- JIT compilation for Python loops
- Near C-speed for custom algorithms
- Memory-efficient array operations

**Best for**: Custom sampling algorithms

**Installation**:
```bash
pip install numpy numba
```

### 5. MLFinLab/FinRL (Pre-built Financial ML)
**Advantages**:
- Pre-implemented dollar bars and volume bars
- Based on "Advances in Financial Machine Learning" (López de Prado)
- Ready-to-use implementation

**Best for**: Quick implementation without custom code

**Installation**:
```bash
pip install mlfinlab
```

## Implementation Approach

### Basic Algorithm
1. Calculate dollar volume for each tick (price × volume)
2. Cumulative sum of dollar volumes
3. Sample when cumulative sum exceeds threshold
4. Reset and repeat

### Example with Polars (Most Efficient)

```python
import polars as pl

def create_dollar_bars(df: pl.DataFrame, dollar_threshold: float) -> pl.DataFrame:
    """
    Create dollar bars from tick data using Polars

    Args:
        df: DataFrame with columns ['timestamp', 'price', 'volume']
        dollar_threshold: Dollar volume threshold for each bar

    Returns:
        DataFrame with OHLCV dollar bars
    """

    # Calculate dollar volume for each tick
    df = df.with_columns(
        (pl.col('price') * pl.col('volume')).alias('dollar_volume')
    )

    # Calculate cumulative dollar volume
    df = df.with_columns(
        pl.col('dollar_volume').cumsum().alias('cum_dollar_volume')
    )

    # Identify bar boundaries (when threshold is exceeded)
    df = df.with_columns(
        (pl.col('cum_dollar_volume') // dollar_threshold).alias('bar_id')
    )

    # Aggregate to create bars
    dollar_bars = df.group_by('bar_id').agg([
        pl.col('timestamp').first().alias('timestamp'),
        pl.col('price').first().alias('open'),
        pl.col('price').max().alias('high'),
        pl.col('price').min().alias('low'),
        pl.col('price').last().alias('close'),
        pl.col('volume').sum().alias('volume'),
        pl.col('dollar_volume').sum().alias('dollar_volume'),
        pl.len().alias('tick_count')
    ])

    return dollar_bars
```

### Example with DuckDB

```python
import duckdb

def create_dollar_bars_sql(tick_file: str, dollar_threshold: float):
    """
    Create dollar bars using DuckDB SQL

    Args:
        tick_file: Path to parquet file with tick data
        dollar_threshold: Dollar volume threshold for each bar

    Returns:
        DataFrame with dollar bars
    """

    query = f"""
    WITH tick_data AS (
        SELECT
            timestamp,
            price,
            volume,
            price * volume as dollar_volume
        FROM read_parquet('{tick_file}')
    ),
    cumulative AS (
        SELECT
            *,
            SUM(dollar_volume) OVER (ORDER BY timestamp) as cum_dollar_volume,
            FLOOR(SUM(dollar_volume) OVER (ORDER BY timestamp) / {dollar_threshold}) as bar_id
        FROM tick_data
    )
    SELECT
        bar_id,
        MIN(timestamp) as timestamp,
        FIRST(price) as open,
        MAX(price) as high,
        MIN(price) as low,
        LAST(price) as close,
        SUM(volume) as volume,
        SUM(dollar_volume) as dollar_volume,
        COUNT(*) as tick_count
    FROM cumulative
    GROUP BY bar_id
    ORDER BY bar_id
    """

    conn = duckdb.connect()
    return conn.execute(query).df()
```

### Example with Numba (Custom High-Performance)

```python
import numpy as np
from numba import jit

@jit(nopython=True)
def create_dollar_bars_numba(timestamps, prices, volumes, threshold):
    """
    Create dollar bars using Numba JIT compilation

    Args:
        timestamps: Array of timestamps
        prices: Array of prices
        volumes: Array of volumes
        threshold: Dollar volume threshold

    Returns:
        Tuple of bar arrays (open, high, low, close, volume, bar_timestamps)
    """
    n = len(prices)
    bars = []

    cum_dollar_volume = 0.0
    bar_start_idx = 0

    for i in range(n):
        dollar_volume = prices[i] * volumes[i]
        cum_dollar_volume += dollar_volume

        if cum_dollar_volume >= threshold:
            # Create bar
            bar_prices = prices[bar_start_idx:i+1]
            bar_volumes = volumes[bar_start_idx:i+1]

            bars.append({
                'timestamp': timestamps[bar_start_idx],
                'open': bar_prices[0],
                'high': np.max(bar_prices),
                'low': np.min(bar_prices),
                'close': bar_prices[-1],
                'volume': np.sum(bar_volumes)
            })

            # Reset
            cum_dollar_volume = 0.0
            bar_start_idx = i + 1

    return bars
```

## Performance Recommendations

### Data Scale Guidelines

| Data Size | Recommended Tool | Processing Time (approx) |
|-----------|-----------------|-------------------------|
| < 1M ticks | Pandas | Seconds |
| 1-10M ticks | Polars | Seconds |
| 10-100M ticks | Polars/DuckDB | Minutes |
| > 100M ticks | Arctic + Polars chunks | Minutes to hours |
| Billions of ticks | Distributed (Dask/Ray) | Hours |

### Optimization Tips

1. **Pre-sort data** by timestamp if not already sorted
2. **Use appropriate data types**:
   - Use `float32` instead of `float64` when precision allows
   - Use categorical types for symbols
3. **Process in chunks** for very large datasets:
   ```python
   chunk_size = 10_000_000
   for chunk in pl.read_csv_batched('ticks.csv', batch_size=chunk_size):
       process_chunk(chunk)
   ```
4. **Cache intermediate results** if resampling multiple times
5. **Consider approximate algorithms** for real-time processing

## Storage Solutions for Tick Data

### Recommended Storage Systems

| Solution | Best For | Pros | Cons |
|----------|----------|------|------|
| **ArcticDB** | Financial tick data | Optimized for time-series, fast queries | Python-specific |
| **ClickHouse** | Real-time analytics | Extremely fast aggregations | Complex setup |
| **TimescaleDB** | PostgreSQL users | SQL interface, reliable | Slower than specialized solutions |
| **Parquet files** | Static datasets | Portable, compressed | No real-time updates |
| **InfluxDB** | IoT/monitoring data | Purpose-built for time-series | Less financial features |

### Storage Example with ArcticDB

```python
from arcticdb import Arctic

# Initialize Arctic connection
arctic = Arctic("lmdb://tick_data")

# Create a library for tick data
lib = arctic.get_library('ticks', create_if_missing=True)

# Write tick data
lib.write('AAPL', tick_df, metadata={'source': 'exchange'})

# Read tick data with time range
df = lib.read('AAPL', date_range=(start_date, end_date))
```

## Real-time Processing Solutions

### Streaming Frameworks

1. **Bytewax**: Python-native stream processing
   ```python
   from bytewax import operators as op

   def dollar_volume_window(tick_stream, threshold):
       return (
           tick_stream
           | op.map(lambda x: {**x, 'dollar_vol': x['price'] * x['volume']})
           | op.stateful_map(accumulate_until_threshold)
           | op.filter(lambda x: x is not None)
       )
   ```

2. **Apache Flink**: Distributed stream processing for massive scale

3. **Redpanda**: Kafka-compatible, lower latency

## Complete Pipeline Example

```python
import polars as pl
from arcticdb import Arctic
from datetime import datetime, timedelta

class DollarBarPipeline:
    def __init__(self, arctic_uri: str, dollar_threshold: float):
        self.arctic = Arctic(arctic_uri)
        self.lib = self.arctic.get_library('tick_data', create_if_missing=True)
        self.dollar_threshold = dollar_threshold

    def ingest_ticks(self, symbol: str, tick_df: pl.DataFrame):
        """Store raw tick data"""
        self.lib.write(f'{symbol}_ticks', tick_df)

    def create_dollar_bars(self, symbol: str, start_date: datetime, end_date: datetime):
        """Create dollar bars for a symbol and date range"""

        # Read tick data
        tick_df = self.lib.read(
            f'{symbol}_ticks',
            date_range=(start_date, end_date)
        )

        # Convert to Polars if needed
        if not isinstance(tick_df, pl.DataFrame):
            tick_df = pl.from_pandas(tick_df)

        # Create dollar bars
        dollar_bars = self._compute_dollar_bars(tick_df)

        # Store dollar bars
        self.lib.write(f'{symbol}_dollar_bars', dollar_bars)

        return dollar_bars

    def _compute_dollar_bars(self, df: pl.DataFrame) -> pl.DataFrame:
        """Internal method to compute dollar bars"""

        # Add dollar volume column
        df = df.with_columns(
            (pl.col('price') * pl.col('volume')).alias('dollar_volume')
        )

        # Calculate cumulative dollar volume and bar IDs
        df = df.with_columns([
            pl.col('dollar_volume').cumsum().alias('cum_dollar_volume'),
        ]).with_columns(
            (pl.col('cum_dollar_volume') // self.dollar_threshold).alias('bar_id')
        )

        # Create OHLCV bars
        return df.group_by('bar_id').agg([
            pl.col('timestamp').first().alias('timestamp'),
            pl.col('price').first().alias('open'),
            pl.col('price').max().alias('high'),
            pl.col('price').min().alias('low'),
            pl.col('price').last().alias('close'),
            pl.col('volume').sum().alias('volume'),
            pl.col('dollar_volume').sum().alias('dollar_volume'),
            pl.len().alias('tick_count'),
            (pl.col('price').last() - pl.col('price').first()).alias('price_change')
        ]).sort('bar_id')

# Usage
pipeline = DollarBarPipeline('lmdb://./tick_storage', dollar_threshold=1_000_000)

# Ingest ticks
tick_data = pl.read_csv('ticks.csv')
pipeline.ingest_ticks('AAPL', tick_data)

# Create dollar bars
bars = pipeline.create_dollar_bars(
    'AAPL',
    datetime(2024, 1, 1),
    datetime(2024, 1, 31)
)
```

## Benchmarks

### Processing Speed Comparison (10M ticks)

| Tool | Time (seconds) | Memory (GB) | Notes |
|------|---------------|-------------|-------|
| Pandas | 45-60 | 8-12 | Single-threaded |
| Polars | 2-5 | 3-5 | Multi-threaded by default |
| DuckDB | 3-7 | 2-4 | Excellent for SQL users |
| Numba | 1-3 | 2-3 | Requires custom implementation |
| MLFinLab | 20-30 | 6-8 | Convenient but slower |

## Best Practices

1. **Choose the right tool for your scale**:
   - Development/Research: MLFinLab for convenience
   - Production < 100M ticks: Polars
   - Production > 100M ticks: Arctic + Polars/DuckDB

2. **Optimize your pipeline**:
   - Profile your code to find bottlenecks
   - Use appropriate chunk sizes
   - Consider parallel processing for multiple symbols

3. **Monitor resource usage**:
   - Track memory consumption
   - Monitor disk I/O for large datasets
   - Use lazy evaluation when possible

4. **Validate your bars**:
   - Ensure no data loss during aggregation
   - Verify bar statistics make sense
   - Compare with known implementations

## Conclusion

For most use cases, the combination of:
- **ArcticDB** for storage
- **Polars** for processing
- **MLFinLab** for validation

provides the best balance of performance, ease of use, and reliability for dollar-volume sampling on tick data.

The choice ultimately depends on your specific requirements:
- Data volume
- Real-time vs batch processing
- Team expertise
- Infrastructure constraints

Start with Polars for processing and scale up to distributed solutions only when necessary.