# Kedro Integration Guide

This guide shows how to integrate the Binance tick data with a Kedro project for ML/data science pipelines.

## Database Location

- **Path:** `/path/to/binance-tick-data/binance_pipeline.duckdb`
- **Size:** 8.5 MB
- **Schema:** `binance_data`
- **Data:** 110,000 BTCUSDT trades (Oct 1-19, 2025)

## Quick Start

### 1. Install Dependencies

Add to your Kedro project's `requirements.txt`:

```txt
# Binance tick data library
binance-tick-data @ file:///path/to/binance-tick-data

# Or install from the directory
# cd /path/to/binance-tick-data && uv pip install -e .

# DuckDB support for Kedro
duckdb>=1.4.1
```

### 2. Configure Data Catalog

Add to `conf/base/catalog.yml`:

```yaml
# Raw trades from DuckDB
binance_agg_trades:
  type: pandas.SQLQueryDataset
  sql: "SELECT * FROM binance_data.agg_trades WHERE symbol = 'BTCUSDT'"
  credentials: duckdb_credentials
  layer: raw

# Preprocessed trades (memory dataset)
trades_preprocessed:
  type: MemoryDataset

# Dollar volume bars (saved to Parquet)
binance_dollar_bars:
  type: pandas.ParquetDataset
  filepath: data/02_intermediate/dollar_volume_bars.parquet
  layer: intermediate

# OHLCV candles
binance_ohlcv_1h:
  type: pandas.ParquetDataset
  filepath: data/02_intermediate/ohlcv_1h.parquet
  layer: intermediate

# Engineered features
binance_features:
  type: pandas.ParquetDataset
  filepath: data/03_primary/features.parquet
  layer: primary

# Train/test split
binance_train_test:
  type: pickle.PickleDataset
  filepath: data/05_model_input/train_test_split.pkl
  layer: model_input
```

### 3. Configure Credentials

Add to `conf/local/credentials.yml`:

```yaml
duckdb_credentials:
  con: "duckdb:////path/to/binance-tick-data/binance_pipeline.duckdb"
```

### 4. Configure Parameters

Add to `conf/base/parameters.yml`:

```yaml
dollar_bars:
  target_bars_per_day: 50

ohlcv_interval: "1H"

test_size: 0.2

symbol: "BTCUSDT"
lookback_days: 18
```

## Pipeline Example

### Nodes (`src/<project>/pipelines/data_processing/nodes.py`)

```python
import pandas as pd
import numpy as np
from binance_tick_data import (
    create_dollar_volume_bars,
    calculate_optimal_threshold,
)

def load_trades_from_duckdb(df: pd.DataFrame) -> pd.DataFrame:
    """Preprocess raw trades from DuckDB."""
    # Convert types (DuckDB returns VARCHAR)
    df['price'] = df['price'].astype(float)
    df['quantity'] = df['quantity'].astype(float)
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

    # Add derived columns
    df['dollar_volume'] = df['price'] * df['quantity']
    df['side'] = df['is_buyer_maker'].apply(lambda x: 'sell' if x else 'buy')

    return df

def create_dollar_bars(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Create dollar volume bars."""
    threshold = calculate_optimal_threshold(
        df,
        target_bars_per_day=params['target_bars_per_day'],
        price_col='price',
        volume_col='quantity',
        timestamp_col='timestamp'
    )

    bars = create_dollar_volume_bars(
        df,
        threshold=threshold,
        price_col='price',
        volume_col='quantity',
        timestamp_col='timestamp'
    )

    return bars

def engineer_features(bars: pd.DataFrame) -> pd.DataFrame:
    """Create features from dollar volume bars."""
    features = bars.copy()

    # Returns
    features['returns'] = features['close'].pct_change()
    features['log_returns'] = np.log(features['close'] / features['close'].shift(1))

    # Volume
    features['volume_ma_20'] = features['volume'].rolling(20).mean()
    features['volume_ratio'] = features['volume'] / features['volume_ma_20']

    # Volatility
    features['volatility_20'] = features['returns'].rolling(20).std()

    # Momentum
    features['momentum_20'] = features['close'].pct_change(20)

    # VWAP
    features['vwap_deviation'] = (features['close'] - features['vwap']) / features['vwap']

    # Time features
    features['hour'] = features['timestamp'].dt.hour
    features['day_of_week'] = features['timestamp'].dt.dayofweek

    return features.dropna()

def split_train_test(features: pd.DataFrame, test_size: float) -> dict:
    """Time-series split."""
    split_idx = int(len(features) * (1 - test_size))
    return {
        'train': features.iloc[:split_idx],
        'test': features.iloc[split_idx:]
    }
```

### Pipeline (`src/<project>/pipelines/data_processing/pipeline.py`)

```python
from kedro.pipeline import Pipeline, node, pipeline
from .nodes import (
    load_trades_from_duckdb,
    create_dollar_bars,
    engineer_features,
    split_train_test,
)

def create_pipeline(**kwargs) -> Pipeline:
    return pipeline([
        node(
            func=load_trades_from_duckdb,
            inputs="binance_agg_trades",
            outputs="trades_preprocessed",
            name="preprocess_trades",
        ),
        node(
            func=create_dollar_bars,
            inputs=["trades_preprocessed", "params:dollar_bars"],
            outputs="binance_dollar_bars",
            name="create_dollar_volume_bars",
        ),
        node(
            func=engineer_features,
            inputs="binance_dollar_bars",
            outputs="binance_features",
            name="engineer_features",
        ),
        node(
            func=split_train_test,
            inputs=["binance_features", "params:test_size"],
            outputs="binance_train_test",
            name="split_train_test",
        ),
    ])
```

## Running the Pipeline

```bash
# From your Kedro project root
kedro run

# Run specific pipeline
kedro run --pipeline data_processing

# Run with parameters override
kedro run --params "dollar_bars.target_bars_per_day=100"

# Visualize pipeline
kedro viz
```

## Alternative: Direct Library Usage

You can also use the `binance_tick_data` library directly in nodes:

```python
def load_trades_directly(db_path: str, symbol: str, days: int) -> pd.DataFrame:
    """Load trades using the library."""
    from binance_tick_data import BinanceDataRepository

    with BinanceDataRepository(db_path=db_path, read_only=True) as repo:
        df = repo.get_agg_trades_by_date_range(
            symbol=symbol,
            days=days,
            as_dataframe=True
        )

    return df
```

Catalog entry:

```yaml
binance_trades_direct:
  type: PartialDataset
  dataset:
    type: pandas.ParquetDataset
    filepath: data/01_raw/trades.parquet
  function_kwargs:
    db_path: "/path/to/binance-tick-data/binance_pipeline.duckdb"
    symbol: "BTCUSDT"
    days: 18
```

## Data Layers in Kedro

Recommended layer structure:

```
01_raw/              # Raw trades from DuckDB
02_intermediate/     # Dollar bars, OHLCV candles
03_primary/          # Features
04_feature/          # Advanced features
05_model_input/      # Train/test splits
06_models/           # Trained models
07_model_output/     # Predictions
08_reporting/        # Reports, visualizations
```

## Exporting Data for Kedro

If you prefer to export data from DuckDB to Parquet first:

```python
from binance_tick_data import BinanceDataRepository

with BinanceDataRepository(read_only=True) as repo:
    repo.export_to_parquet(
        symbol='BTCUSDT',
        output_path='<kedro_project>/data/01_raw/binance_trades.parquet',
        table='agg_trades'
    )
```

Then use in catalog:

```yaml
binance_trades_raw:
  type: pandas.ParquetDataset
  filepath: data/01_raw/binance_trades.parquet
  layer: raw
```

## Tips

1. **Use read_only=True** for DuckDB connections to avoid locks
2. **Convert types early** - DuckDB returns VARCHAR for price/quantity
3. **Handle timestamps** - DuckDB stores as milliseconds integers
4. **Use Parquet** for intermediate datasets (faster I/O than CSV)
5. **Memory datasets** for small intermediate results
6. **Version your data** with Kedro's versioning feature

## See Also

- [binance_tick_data API Reference](API_REFERENCE.md)
- [Kedro Documentation](https://docs.kedro.org/)
- [DuckDB Kedro Integration](https://docs.kedro.org/en/stable/data/data_catalog_yaml_examples.html#sql-datasets)
