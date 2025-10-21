# Notebooks

Interactive Jupyter notebooks demonstrating the Binance tick data library features.

---

## 📓 Available Notebooks

### 1. Data Analysis (`data_analysis.ipynb`)
**Topic**: Fractional Differencing Analysis

**What you'll learn**:
- Loading tick data from DuckDB
- Price and returns visualization
- Fractional differencing (d=0.2, 0.3, 0.4)
- Statistical analysis and distribution comparison
- Q-Q plots for normality testing

**Level**: Advanced
**Duration**: 15-20 minutes
**Prerequisites**: Understanding of time series analysis

**Key sections**:
- Data loading with `BinanceDataRepository`
- Fractional differencing implementation
- Distribution analysis
- Summary statistics
- Data export

---

### 2. Dollar Volume Bars Demo (`dollar_volume_bars_demo.ipynb`)
**Topic**: Dollar Volume Sampling with Time Metrics

**What you'll learn**:
- Creating dollar volume bars from tick data
- Understanding time-based metrics
- Market regime detection
- Liquidity analysis
- Trading signal generation
- Comparison with time-based bars

**Level**: Intermediate
**Duration**: 20-30 minutes
**Prerequisites**: Basic understanding of market microstructure

**Key sections**:
- Basic dollar volume bar creation
- Time metrics exploration (duration, ticks/sec, velocity)
- Market regime classification
- Liquidity score calculation
- Trading signal generation from intensity
- Statistical comparison with time bars
- Adaptive threshold demonstration

**Highlights**:
- 10 comprehensive sections
- Multiple visualizations
- Real-world trading applications
- Performance comparison analysis

---

### 3. Dollar Volume Sampling (`dollar_volume_sampling.ipynb`)
**Topic**: Dollar Volume Sampling Technical Specification

**What you'll learn**:
- Technical implementation details
- Sampling algorithm explanation
- Threshold calculation methods
- Performance characteristics

**Level**: Advanced
**Duration**: 10-15 minutes
**Prerequisites**: Understanding of sampling techniques

**Note**: This is a technical specification notebook. For practical usage, see `dollar_volume_bars_demo.ipynb`.

---

### 4. Real-time Analysis (`realtime_analysis.ipynb`)
**Topic**: Live Streaming and Real-time Data Processing

**What you'll learn**:
- Using `RealtimeConsumer` for live data
- Order book streaming
- Real-time analyzers
- Live metric calculation
- WebSocket data handling

**Level**: Intermediate
**Duration**: 15-20 minutes
**Prerequisites**: Understanding of async programming (helpful but not required)

**Key sections**:
- Setting up real-time consumer
- Streaming trade data
- Order book depth analysis
- Real-time spread calculation
- Custom analyzer integration

---

## 🚀 Quick Start

### Running Notebooks

```bash
# From project root
cd notebooks
jupyter notebook

# Or with uv
uv run jupyter notebook

# Or with JupyterLab
uv run jupyter lab
```

### Recommended Learning Path

**For Beginners**:
1. Start with `dollar_volume_bars_demo.ipynb` - Most accessible, practical examples
2. Then explore `realtime_analysis.ipynb` - Live data streaming
3. Finally `data_analysis.ipynb` - Advanced analysis techniques

**For API Learning**:
- See `examples/client_examples.py` - 10 practical code examples
- See `docs/API_REFERENCE.md` - Complete API documentation

**For Streaming**:
1. `realtime_analysis.ipynb` - Interactive examples
2. `examples/orderbook_streaming_example.py` - Live order book
3. `docs/GETTING_STARTED_STREAMING.md` - Complete guide

---

## 📚 Documentation

### Main Documentation
- **API Reference**: `../docs/API_REFERENCE.md` - Complete method reference
- **Quick Start**: `../docs/QUICK_START.md` - Getting started guide
- **Streaming Guide**: `../docs/GETTING_STARTED_STREAMING.md` - Real-time data

### Feature-Specific Docs
- **Dollar Volume Sampling**: `../docs/DOLLAR_VOLUME_SAMPLING.md`
- **Liquidity Analysis**: `../docs/LIQUIDITY_ANALYZER_EXPLAINED.md`
- **RLlib Integration**: `../specs/rllib_specs.md`

### Code Examples
- **Client Examples**: `../examples/client_examples.py` - 10 usage patterns
- **Streaming Examples**: `../examples/` directory
  - `simple_streaming_example.py`
  - `orderbook_streaming_example.py`
  - `realtime_monitoring.py`
  - `custom_analyzer_example.py`

---

## 🛠️ Prerequisites

### Required Data

Most notebooks require data in the DuckDB database. To populate:

```bash
# Download recent data (last 24 hours)
uv run python jobs/03_fill_gaps.py --symbol BTCUSDT --recent

# Or download larger date range
uv run python jobs/03_fill_gaps.py --symbol BTCUSDT --start-date 2025-10-01
```

### Dependencies

All dependencies are already installed if you ran:
```bash
uv sync
```

Key packages used in notebooks:
- `pandas` - Data manipulation
- `numpy` - Numerical operations
- `matplotlib` - Plotting
- `seaborn` - Statistical visualization
- `scipy` - Statistical functions
- `binance_tick_data` - This library

---

## 💡 Tips

### Performance
- Start with small date ranges (1-7 days) for faster execution
- Use `limit` parameter when exploring data
- Convert price/volume to float for calculations

### Data Types
```python
# Price and quantity are stored as strings
df['price'] = df['price'].astype(float)
df['quantity'] = df['quantity'].astype(float)

# Calculate dollar volume
df['dollar_volume'] = df['price'] * df['quantity']
```

### Error Handling
If you see "Database not found":
1. Check database path (default: `binance_pipeline.duckdb`)
2. Run data download scripts (see Prerequisites above)
3. Verify with: `ls -lh *.duckdb`

If notebooks fail to load:
1. Make sure you're in the `notebooks/` directory
2. Install Jupyter: `uv add jupyter`
3. Run: `uv run jupyter notebook`

---

## 📊 Notebook Outputs

All notebooks include:
- ✅ Markdown explanations
- ✅ Executable code cells
- ✅ Visual outputs (charts, plots)
- ✅ Statistical summaries
- ✅ Export examples

Some notebooks may show large outputs. These are preserved to show expected results.

---

## 🔗 Related Resources

### Examples Directory (`../examples/`)
Python scripts for various use cases:
- `client_examples.py` - 10 API usage patterns
- `dollar_volume_bars_example.py` - Dollar volume bar examples
- `orderbook_streaming_example.py` - Live order book
- `realtime_monitoring.py` - Real-time dashboard
- And more...

### Tests Directory (`../tests/`)
See how features are tested:
- `test_dollar_volume_sampling.py` - 37 tests
- `test_time_metrics.py` - 29 tests
- `test_imports.py` - Package verification

---

## 📝 Contributing

Found an issue or have a suggestion for a new notebook?
- Check existing examples first
- Consider if it fits better as a Python script in `examples/`
- Ensure notebooks are self-contained and well-documented

---

## Summary

| Notebook | Topic | Level | Duration |
|----------|-------|-------|----------|
| `data_analysis.ipynb` | Fractional Differencing | Advanced | 15-20min |
| `dollar_volume_bars_demo.ipynb` | Dollar Volume Sampling | Intermediate | 20-30min |
| `dollar_volume_sampling.ipynb` | Technical Specification | Advanced | 10-15min |
| `realtime_analysis.ipynb` | Live Streaming | Intermediate | 15-20min |

**Total Learning Time**: ~60-85 minutes to explore all notebooks

---

**Ready to start?** Open `dollar_volume_bars_demo.ipynb` for the most comprehensive introduction!
