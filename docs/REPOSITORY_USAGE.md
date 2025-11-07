# Repository Usage Guide

## Two Repository Implementations

The library has two repository implementations:

### 1. `repository.py` - Full-Featured (Recommended for Notebooks)

**Import:**
```python
from binance_tick_data.repository import BinanceDataRepository
```

**Initialization:**
```python
from binance_tick_data.db_config import get_config

config = get_config()
repo = BinanceDataRepository(
    db_path=config.database.db_path,
    dataset_name=config.database.schema_name,
    read_only=True
)
```

**Features:**
- ✅ `get_agg_trades()` - Get aggregated trades
- ✅ `get_agg_trades_by_date_range()` - Get trades by date range
- ✅ `get_symbol_stats()` - Get comprehensive statistics
- ✅ `get_volume_profile()` - Get volume distribution
- ✅ `get_ohlcv()` - Get OHLCV candles
- ✅ `get_order_book_snapshot()` - Get order book snapshots
- ✅ `export_to_parquet()` - Export to Parquet format
- ✅ `export_to_csv()` - Export to CSV format
- ✅ All analysis methods

**Use Cases:**
- Jupyter notebooks (comprehensive analysis)
- Data exploration
- Feature engineering
- Reporting and visualization

### 2. `repository_v2.py` - Config-Based (Newer, Simplified)

**Import:**
```python
from binance_tick_data.repository_v2 import BinanceDataRepository
```

**Initialization:**
```python
# Uses global config automatically
repo = BinanceDataRepository()

# Or with custom config
from binance_tick_data.db_config import load_config
config = load_config('my_config.yaml')
repo = BinanceDataRepository(config=config)
```

**Features:**
- ✅ `get_agg_trades()` - Get aggregated trades
- ✅ `get_agg_trades_by_date_range()` - Get trades by date range
- ✅ `get_ohlcv()` - Get OHLCV candles
- ✅ `get_data_summary()` - Get data summary
- ✅ `get_realtime_trades()` - Get recent streaming trades
- ✅ `get_live_orderbook()` - Get live order book
- ✅ `get_streaming_stats()` - Get streaming statistics
- ❌ `get_symbol_stats()` - Not implemented
- ❌ `get_volume_profile()` - Not implemented
- ❌ `export_to_parquet()` - Not implemented
- ❌ `export_to_csv()` - Not implemented

**Use Cases:**
- Production code (centralized config)
- Real-time streaming applications
- Simpler initialization
- When you don't need all analysis methods

## Comparison

| Feature | repository.py | repository_v2.py |
|---------|--------------|------------------|
| **Initialization** | Parameters | Config object |
| **Symbol Stats** | ✅ | ❌ |
| **Volume Profile** | ✅ | ❌ |
| **Export Methods** | ✅ | ❌ |
| **Streaming Data** | Basic | ✅ Advanced |
| **Config Management** | Manual | ✅ Centralized |
| **Use in Notebooks** | ✅ Recommended | Limited |

## Recommendations

### For Notebooks
**Use `repository.py`** - It has all the analysis methods needed for comprehensive demonstrations.

```python
from binance_tick_data.repository import BinanceDataRepository
from binance_tick_data.db_config import get_config

config = get_config()
repo = BinanceDataRepository(
    db_path=config.database.db_path,
    dataset_name=config.database.schema_name,
    read_only=True
)

# All methods available
stats = repo.get_symbol_stats('BTCUSDT')
volume_profile = repo.get_volume_profile('BTCUSDT', price_bins=50)
repo.export_to_parquet('BTCUSDT', 'output.parquet')
```

### For Production/Services
**Use `repository_v2.py`** - Simpler config-based initialization.

```python
from binance_tick_data.repository_v2 import BinanceDataRepository

# Uses global config from config.yaml
repo = BinanceDataRepository()

# Works with centralized configuration
trades = repo.get_agg_trades('BTCUSDT', days=7)
ohlcv = repo.get_ohlcv('BTCUSDT', interval='1h')
```

## Migration Path

Eventually, `repository_v2.py` will replace `repository.py`. To prepare:

1. **Short term** - Use `repository.py` for notebooks (has all methods)
2. **Medium term** - Add missing methods to `repository_v2.py`
3. **Long term** - Migrate all code to `repository_v2.py`

## Context Manager Usage

Both support context managers for automatic cleanup:

```python
# repository.py
with BinanceDataRepository(db_path=path, dataset_name=schema) as repo:
    data = repo.get_agg_trades('BTCUSDT')

# repository_v2.py
with BinanceDataRepository() as repo:
    data = repo.get_agg_trades('BTCUSDT')
```

## Properties Available

Both repositories expose these properties:

```python
repo.db_path        # Database path
repo.read_only      # Read-only mode status

# repository.py also has:
repo.dataset_name   # Schema name
repo.catalog        # Catalog name (if set)

# repository_v2.py also has:
repo.config         # Full AppConfig object
```

## When to Use Which?

**Choose `repository.py` if you need:**
- Symbol statistics (`get_symbol_stats`)
- Volume profile analysis (`get_volume_profile`)
- Data export (`export_to_parquet`, `export_to_csv`)
- Order book snapshots (`get_order_book_snapshot`)
- Complete feature set for analysis

**Choose `repository_v2.py` if you need:**
- Centralized configuration management
- Real-time streaming features
- Simpler initialization
- Config-driven architecture
- You don't need analysis methods

---

**Current Status:** Notebooks use `repository.py` for full feature access
