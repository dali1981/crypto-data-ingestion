# Notebook Fixes - Configuration & Repository

## Issues Fixed

### 1. Configuration Access Pattern
**Problem:** Notebook tried to access `config.database.table.schema` but `DatabaseConfig` has no `table` attribute.

**Root Cause:** Config structure changed - there's no nested `table` object in `DatabaseConfig`.

**Solution:** Added properties to expose clean API:
```python
# Before (broken):
config.database.table.schema  # ❌ AttributeError

# After (working):
config.database.schema         # ✅ Property access
config.database.schema_name    # ✅ Direct field access (still works)
```

### 2. Repository Initialization
**Problem:** Notebook tried `BinanceDataRepository(read_only=True)` but `repository_v2.py` doesn't accept that parameter.

**Root Cause:** `repository_v2.BinanceDataRepository.__init__()` only accepts `config` parameter. The `read_only` setting comes from the config object.

**Solution:** Updated notebook to use config-based initialization:
```python
# Before (broken):
repo = BinanceDataRepository(read_only=True)  # ❌ TypeError

# After (working):
repo = BinanceDataRepository()  # ✅ Uses global config (has read_only=True)
```

### 3. Database Path Resolution
**Problem:** Notebooks run from `notebooks/` directory but database path is relative to project root.

**Solution:** Created `notebooks/notebook_setup.py` utility module with:
- `setup_notebook_environment()` - Changes to project root
- `get_database_path()` - Returns absolute path
- `check_database_exists()` - Verifies database file
- `initialize_notebook()` - Complete initialization routine

## Changes Made

### Code Changes

1. **`src/binance_tick_data/db_config.py`**
   - Added `DatabaseConfig.schema` property → returns `schema_name`
   - Added `DatabaseConfig.catalog` property → returns `catalog_name`
   - Added `DatabaseConfig.path` property → returns absolute `Path` object
   - Added `AppConfig.db_path` property → shortcut to `database.db_path`
   - Added `AppConfig.schema` property → shortcut to `database.schema_name`
   - Added `AppConfig.catalog` property → shortcut to `database.catalog_name`
   - Added `AppConfig.get_table_path()` method → convenience wrapper
   - Added `extra="allow"` to AppConfig for forward compatibility

2. **`tests/test_config_properties.py`** (NEW)
   - 26 comprehensive tests covering all property access patterns
   - Tests backward compatibility
   - Tests encapsulation benefits
   - Tests notebook usage patterns
   - **All tests passing** ✅

3. **`notebooks/notebook_setup.py`** (NEW)
   - Path resolution utilities
   - Database verification
   - Config printing helpers
   - Complete initialization routine

### Notebook Changes

4. **`notebooks/01_quickstart.ipynb`**
   - **Cell 5:** Fixed config access to use properties
     ```python
     # Before:
     config.database.table.schema  # ❌

     # After:
     config.database.schema  # ✅
     ```

   - **Cell 7:** Fixed repository initialization
     ```python
     # Before:
     BinanceDataRepository(read_only=True)  # ❌

     # After:
     BinanceDataRepository()  # ✅
     ```

   - **Cell 62:** Fixed context manager example
     ```python
     # Before:
     with BinanceDataRepository(read_only=True) as repo:  # ❌

     # After:
     with BinanceDataRepository() as repo:  # ✅
     ```

## Property-Based API Benefits

### 1. Encapsulation
Internal field names can change without breaking external code:
```python
# If we rename schema_name to _schema internally:
class DatabaseConfig:
    _schema: str  # Internal field renamed

    @property
    def schema(self) -> str:
        return self._schema  # Property still works!

# External code unaffected:
config.database.schema  # Still works!
```

### 2. Multiple Access Patterns
Flexibility for different use cases:
```python
# All these work and return the same value:
schema1 = config.schema                # Top-level convenience
schema2 = config.database.schema       # Property access
schema3 = config.database.schema_name  # Direct field access
```

### 3. Read-Only Access
Properties prevent accidental modification:
```python
config.database.schema = "new"  # ❌ AttributeError (no setter)
config.database.schema_name = "new"  # ✅ Still possible if needed
```

### 4. Computed Values
Properties can add logic:
```python
@property
def path(self) -> Path:
    """Returns absolute path automatically."""
    p = Path(self.db_path)
    return p if p.is_absolute() else p.absolute()
```

## Testing Coverage

**26 tests - all passing:**

✅ Property returns correct values
✅ Backward compatibility with direct field access
✅ Multiple access patterns work identically
✅ Properties are read-only (no setters)
✅ Common notebook usage patterns
✅ Encapsulation benefits
✅ Config loading and singleton behavior

```bash
pytest tests/test_config_properties.py -v
# ======================== 26 passed in 0.89s ========================
```

## Usage Examples

### Notebook Initialization

```python
# Option 1: Manual setup
import os
from pathlib import Path

# Ensure we're in project root
if Path.cwd().name == 'notebooks':
    os.chdir('..')

# Load config
from binance_tick_data.db_config import get_config
config = get_config()

# Initialize repository
from binance_tick_data.repository_v2 import BinanceDataRepository
repo = BinanceDataRepository()
```

### Using the Setup Utility

```python
# Option 2: Use notebook_setup.py (recommended)
from notebook_setup import initialize_notebook

# Handles everything: paths, config, database verification
project_root, config = initialize_notebook()

# Now ready to use
from binance_tick_data.repository_v2 import BinanceDataRepository
repo = BinanceDataRepository()
```

### Configuration Access Patterns

```python
# Get database information
db_path = config.database.db_path        # String path
db_abs_path = config.database.path       # Absolute Path object
schema = config.database.schema          # Clean property access
catalog = config.database.catalog        # Clean property access

# Get table paths
agg_trades_table = config.get_table_path('agg_trades')
# Returns: "binance_data.agg_trades"

trades_table = config.database.get_table_path('trades')
# Returns: "binance_data.trades"
```

### Repository Usage

```python
# Create repository (uses global config automatically)
repo = BinanceDataRepository()

# Or with custom config
from binance_tick_data.db_config import load_config
custom_config = load_config('my_config.yaml')
repo = BinanceDataRepository(config=custom_config)

# Use context manager for automatic cleanup (recommended)
with BinanceDataRepository() as repo:
    df = repo.get_agg_trades('BTCUSDT', days=7)
    # Connection automatically closed
```

## Migration Guide

### For Notebook Users

**Old pattern (broken):**
```python
config = get_config()
schema = config.database.table.schema  # ❌ AttributeError
repo = BinanceDataRepository(read_only=True)  # ❌ TypeError
```

**New pattern (working):**
```python
config = get_config()
schema = config.database.schema  # ✅ Property access
repo = BinanceDataRepository()  # ✅ Uses config (has read_only=True)
```

### For Library Developers

**Nothing breaks!** All old code still works:
```python
# These all continue to work:
config.database.db_path
config.database.schema_name
config.database.catalog_name
```

**New code can use properties:**
```python
# New, cleaner patterns:
config.database.schema    # Instead of .schema_name
config.database.catalog   # Instead of .catalog_name
config.database.path      # Returns Path object
```

## Files Modified

| File | Type | Changes |
|------|------|---------|
| `src/binance_tick_data/db_config.py` | Modified | Added 7 properties, forward compatibility |
| `tests/test_config_properties.py` | New | 26 tests, all passing |
| `notebooks/notebook_setup.py` | New | Utility module for path resolution |
| `notebooks/01_quickstart.ipynb` | Modified | Fixed cells 5, 7, 62 |
| `CONFIGURATION_IMPROVEMENTS.md` | New | Detailed documentation |
| `NOTEBOOK_FIXES.md` | New | This file |

## Key Principles Applied

1. **Backward Compatibility** - Don't break existing code
2. **Encapsulation** - Hide implementation details behind properties
3. **Convenience** - Multiple access patterns for flexibility
4. **Forward Compatibility** - Allow config evolution with `extra="allow"`
5. **Testability** - Comprehensive test coverage (26 tests)
6. **Documentation** - Clear docstrings and guides

## Next Steps for Users

1. **Update notebooks** to use new property-based access
2. **Use `notebook_setup.py`** for path resolution in new notebooks
3. **Initialize repository** without parameters (uses global config)
4. **Run tests** to verify everything works: `pytest tests/test_config_properties.py -v`

---

**Status:** ✅ Complete - All notebooks fixed, all tests passing (26/26)
