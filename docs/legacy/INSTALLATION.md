# Installation Guide

## Quick Setup

```bash
# 1. Clone or navigate to the project
cd dlt-starter

# 2. Install in editable mode (recommended for development)
uv pip install -e .

# 3. Verify installation
python -c "from binance_tick_data import BinanceDataRepository; print('✅ Installed!')"
```

## Project Structure

```
dlt-starter/
├── src/
│   └── binance_tick_data/        # Main package (installed as module)
│       ├── __init__.py
│       ├── config.py
│       ├── repository.py         # Data access layer
│       ├── parquet_storage.py    # Parquet storage
│       ├── utils.py
│       └── sources/
│           ├── __init__.py
│           ├── rest_api.py       # Historical data
│           ├── websocket.py      # Real-time data
│           └── schemas.py
│
├── pipelines/                    # Pipeline scripts
│   ├── historical_pipeline.py
│   └── realtime_pipeline.py
│
├── examples/                     # Usage examples
│   ├── simple_read.py
│   ├── client_examples.py
│   ├── notebook_example.py
│   └── ...
│
├── pyproject.toml               # Package configuration
├── config.toml                  # dlt configuration
└── README.md

Data files (created after running):
├── dlt_binance.duckdb          # Database
└── data/                       # Optional Parquet storage
```

## Why `src/` Layout?

The `src/` layout is a Python packaging best practice:

1. **Prevents accidental imports** - Can't import uninstalled package
2. **Tests the installed package** - Ensures distribution works
3. **Cleaner namespace** - Separates source from test/docs
4. **Standard practice** - Widely adopted in Python community

## Editable Install (`-e`)

Installing with `-e` (editable mode) means:

✅ **Changes are immediate** - Edit code, no reinstall needed
✅ **Import from anywhere** - `from binance_tick_data import ...` works
✅ **Development workflow** - Perfect for active development

```bash
# Install in editable mode
uv pip install -e .

# Now you can import from anywhere
python
>>> from binance_tick_data.repository import BinanceDataRepository
>>> print("Works!")
```

## Using the Package

### From Scripts

```python
# examples/my_script.py
from binance_tick_data.repository import BinanceDataRepository

with BinanceDataRepository() as repo:
    df = repo.get_agg_trades_by_date_range("BTCUSDT", days=7)
    print(f"Retrieved {len(df):,} trades")
```

### From Jupyter Notebook

```python
# In any notebook
from binance_tick_data.repository import BinanceDataRepository
from binance_tick_data import BinanceConfig

# Use the library
with BinanceDataRepository() as repo:
    stats = repo.get_symbol_stats("BTCUSDT")
    print(stats)
```

### From Anywhere

```bash
# Run from any directory
cd ~/my_projects/trading_analysis/
python my_analysis.py  # Can import binance_tick_data
```

## Uninstall

```bash
uv pip uninstall binance-tick-data
```

## Reinstall

```bash
# After pulling updates or major changes
uv pip install -e . --force-reinstall
```

## Troubleshooting

### Import Error: "No module named 'binance_tick_data'"

**Solution**: Install the package
```bash
uv pip install -e .
```

### "Package not found" during install

**Solution**: Make sure you're in the project root directory
```bash
cd /path/to/dlt-starter
uv pip install -e .
```

### Changes not reflected

**Solution**: Restart Python interpreter or Jupyter kernel
```python
# In Jupyter
%reload_ext autoreload
%autoreload 2
```

## Development Workflow

```bash
# 1. Install in editable mode
uv pip install -e .

# 2. Make changes to src/binance_tick_data/*.py
vim src/binance_tick_data/repository.py

# 3. Changes are immediately available (no reinstall!)
python examples/simple_read.py

# 4. Add new dependencies
uv add some-package

# 5. Test everything
python test_setup.py
```

## Distribution (Optional)

To distribute your library:

```bash
# Build wheel
uv build

# Install from wheel
uv pip install dist/binance_tick_data-0.1.0-py3-none-any.whl

# Or publish to PyPI (if you want)
uv publish
```

## Next Steps

1. ✅ Verify installation: `python -c "import binance_tick_data; print('OK')"`
2. Download data: `uv run python pipelines/historical_pipeline.py --symbols BTCUSDT --max-records 10000`
3. Run examples: `uv run python examples/simple_read.py`
4. Read: `examples/README.md` for usage examples

---

**Installation complete!** 🎉

You can now `import binance_tick_data` from anywhere.
