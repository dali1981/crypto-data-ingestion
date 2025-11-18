# Contributing to Binance Tick Data Library

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to this project.

## 🎯 Areas for Contribution

We welcome contributions in these areas:

### 1. **New Data Sources**
- Additional Binance endpoints (klines, book ticker, liquidations)
- Other exchanges (Coinbase, Kraken, OKX, Bybit)
- Historical data from alternative sources

### 2. **Storage Backends**
- ClickHouse integration
- TimescaleDB support
- Redis for streaming buffers
- S3/MinIO for cloud storage

### 3. **Data Quality**
- Enhanced duplicate detection algorithms
- More sophisticated gap-filling strategies
- Data validation rules
- Anomaly detection

### 4. **Performance Optimization**
- Parallel data fetching
- Connection pooling
- Batch optimization
- Memory efficiency improvements

### 5. **Documentation**
- Tutorials and guides
- Usage examples
- Architecture documentation
- API reference improvements

## 🚀 Getting Started

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/YOUR_USERNAME/binance-tick-data.git
cd binance-tick-data
```

### 2. Set Up Development Environment

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install in editable mode with dev dependencies
uv pip install -e ".[dev]"

# Verify installation
uv run pytest tests/test_imports.py
```

### 3. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

## 💻 Development Workflow

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/unit/sources/test_fetch_agg_trades.py

# Run with coverage
uv run pytest --cov=binance_tick_data --cov-report=html

# Run only fast tests (skip integration)
uv run pytest -m "not integration"
```

### Code Style

We follow PEP 8 with some modifications:

```bash
# Format code with black (line length 100)
black src/ tests/ --line-length 100

# Check with flake8
flake8 src/ tests/ --max-line-length=100

# Type checking with mypy
mypy src/binance_tick_data
```

**Key conventions:**
- Use type hints for all function signatures
- Docstrings for all public functions (Google style)
- Prefer explicit over implicit
- Keep functions focused and testable

### Adding a New Data Source

1. **Create source module** in `src/binance_tick_data/sources/`
2. **Define Pydantic schema** in `sources/schemas.py`
3. **Add dlt resource** with proper decorators
4. **Write tests** in `tests/unit/sources/`
5. **Update documentation**

Example:

```python
# src/binance_tick_data/sources/klines.py
import dlt
from .schemas import KlineSchema

@dlt.resource(
    name="klines_{symbol}",
    write_disposition="append",
    primary_key=["open_time", "symbol"],
)
def fetch_klines(symbol: str, interval: str = "1m"):
    """Fetch historical kline/candlestick data."""
    # Implementation here
    pass
```

### Adding Tests

All new features must include tests:

```python
# tests/unit/sources/test_klines.py
import pytest
from binance_tick_data.sources import fetch_klines

def test_fetch_klines_basic():
    """Test basic kline fetching."""
    result = fetch_klines("BTCUSDT", interval="1h")
    assert result is not None
    # More assertions...

@pytest.mark.integration
def test_fetch_klines_integration():
    """Test kline fetching with real API."""
    # Integration test...
    pass
```

## 📋 Pull Request Process

### 1. Before Submitting

- [ ] All tests pass (`uv run pytest`)
- [ ] Code is formatted (`black src/ tests/`)
- [ ] Type hints are added
- [ ] Docstrings are complete
- [ ] Documentation is updated
- [ ] CHANGELOG.md is updated

### 2. Commit Messages

Follow conventional commits:

```
feat: add kline data source with 15m intervals
fix: resolve duplicate detection in gap filler
docs: update API reference for BinanceConfig
test: add integration tests for rate limiter
refactor: extract batch fetching into base class
```

### 3. PR Description Template

```markdown
## Description
Brief description of what this PR does

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
Describe how you tested your changes

## Checklist
- [ ] Tests pass locally
- [ ] Code is formatted
- [ ] Documentation updated
- [ ] CHANGELOG updated
```

## 🏗️ Architecture Guidelines

### OOP Principles (SOLID)

The codebase follows SOLID principles. When adding features:

1. **Single Responsibility**: Each class/function has one job
2. **Open/Closed**: Extend via inheritance, not modification
3. **Liskov Substitution**: Derived classes should be substitutable
4. **Interface Segregation**: Use Protocol classes for interfaces
5. **Dependency Injection**: Pass dependencies, don't create them

Example:

```python
# Good: Dependency injection
class DataFetcher:
    def __init__(self, client: APIClient, rate_limiter: RateLimiter):
        self.client = client
        self.rate_limiter = rate_limiter

# Bad: Creating dependencies
class DataFetcher:
    def __init__(self):
        self.client = BinanceClient()  # Hard dependency
```

### Error Handling

Use the error hierarchy in `errors.py`:

```python
from binance_tick_data.errors import (
    BinanceDataError,
    APIError,
    RateLimitError,
    DataQualityError
)

# Raise specific errors
if rate_limit_exceeded:
    raise RateLimitError("Rate limit exceeded, retry after 60s")
```

### Configuration

- **Pipeline config**: Use `BinanceConfig` (legacy)
- **Database config**: Use `get_config()` (modern)
- **Never hardcode** paths or credentials

## 🧪 Testing Guidelines

### Test Structure

```
tests/
├── unit/              # Fast, isolated tests
│   ├── sources/       # Data source tests
│   ├── utils/         # Utility function tests
│   └── cli/           # CLI command tests
└── integration/       # Slower, end-to-end tests
```

### Writing Good Tests

```python
# Good: Clear, specific, isolated
def test_rate_limiter_respects_limit():
    """Rate limiter should delay calls exceeding limit."""
    limiter = BinanceRateLimiter(max_requests=10, window=60)

    # First 10 calls should be immediate
    for _ in range(10):
        assert limiter.wait_if_needed(weight=1) == 0

    # 11th call should wait
    assert limiter.wait_if_needed(weight=1) > 0

# Bad: Vague, multiple assertions, unclear purpose
def test_rate_limiter():
    limiter = BinanceRateLimiter()
    assert limiter is not None
    limiter.wait_if_needed(1)
    # What are we testing?
```

### Mocking External APIs

Use `pytest` fixtures and `unittest.mock`:

```python
from unittest.mock import patch, Mock

@patch('binance_tick_data.sources.binance.client.Client')
def test_fetch_without_api_call(mock_client):
    """Test fetching logic without hitting real API."""
    mock_client.return_value.get_aggregate_trades.return_value = [
        {"id": 1, "price": "50000", "quantity": "0.1"}
    ]

    result = fetch_agg_trades("BTCUSDT")
    assert len(result) == 1
```

## 📝 Documentation

### Docstring Format (Google Style)

```python
def fetch_data(symbol: str, start_date: str, limit: int = 1000) -> List[Dict]:
    """Fetch historical trade data for a symbol.

    Args:
        symbol: Trading pair symbol (e.g., 'BTCUSDT')
        start_date: Start date in ISO format ('2024-01-01')
        limit: Maximum number of records to fetch (default: 1000)

    Returns:
        List of trade dictionaries with keys: id, price, quantity, timestamp

    Raises:
        APIError: If Binance API request fails
        RateLimitError: If rate limit is exceeded

    Example:
        >>> trades = fetch_data('BTCUSDT', '2024-01-01', limit=100)
        >>> len(trades)
        100
    """
    pass
```

### Update Documentation Files

When adding features, update:

- `README.md` - User-facing quick start
- `docs/QUICK_START.md` - Detailed installation guide
- `docs/API_REFERENCE.md` - API documentation
- Relevant spec files in `specs/`

## 🐛 Reporting Bugs

### Bug Report Template

```markdown
**Describe the bug**
A clear description of what the bug is.

**To Reproduce**
Steps to reproduce:
1. Run command `binance download ...`
2. See error

**Expected behavior**
What you expected to happen

**Actual behavior**
What actually happened

**Environment**
- OS: [e.g., Ubuntu 22.04]
- Python version: [e.g., 3.11]
- Library version: [e.g., 1.0.0]

**Additional context**
- Error messages
- Logs
- Stack traces
```

## 🎓 Learning Resources

### Project-Specific
- [Architecture Documentation](docs/SOLUTION_SUMMARY.md)
- [Data Quality System](docs/JOBS_QUICK_START.md)
- [Dagster Pipeline](dagster_pipeline/README.md)

### External
- [dlt Documentation](https://dlthub.com/docs)
- [DuckDB Python API](https://duckdb.org/docs/api/python/overview)
- [Binance API Docs](https://binance-docs.github.io/apidocs/spot/en/)
- [Pydantic Documentation](https://docs.pydantic.dev/)

## 💬 Communication

- **Questions**: Open a GitHub Discussion
- **Bugs**: Open an Issue with bug report template
- **Feature Requests**: Open an Issue with feature template
- **Security Issues**: Email maintainers directly (not public issues)

## 📜 Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on what's best for the community
- Show empathy towards others

## ✅ Review Process

PRs are reviewed for:

1. **Functionality**: Does it work as intended?
2. **Tests**: Are there adequate tests?
3. **Code Quality**: Is it readable and maintainable?
4. **Documentation**: Is it properly documented?
5. **Architecture**: Does it fit the design?

Expect 1-3 review cycles for most PRs.

---

Thank you for contributing! 🚀
