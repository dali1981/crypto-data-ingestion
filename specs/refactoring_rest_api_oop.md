# OOP Refactoring Plan: `rest_api.py`

**Date:** 2025-11-07
**Status:** Proposed
**Author:** Architecture Review
**Target File:** `src/binance_tick_data/sources/rest_api.py`

---

## Executive Summary

Current `rest_api.py` violates SOLID principles with 70% code duplication, poor testability, and tight coupling between DLT orchestration, API calls, and business logic. This refactoring proposes a **4-layer OOP architecture** that:

- ✅ Achieves 5/5 SOLID compliance
- ✅ Reduces code by 69% (648 → ~200 lines)
- ✅ Eliminates 70% duplication
- ✅ Enables unit testing of all components
- ✅ Supports multi-exchange extensibility (Coinbase, Kraken, etc.)
- ✅ Maintains backward compatibility (no user-facing changes)

---

## Current Architecture Problems

### SOLID Violations

| Principle | Current Violation | Impact |
|-----------|-------------------|---------|
| **Single Responsibility** | `_fetch_agg_trades()` does 6 things: API calls, rate limiting, transformation, logging, error handling, progress tracking | 160-line unmaintainable functions |
| **Open/Closed** | Cannot extend to other exchanges without rewriting | Not extensible |
| **Liskov Substitution** | No abstractions - everything is concrete | Cannot swap implementations |
| **Interface Segregation** | Monolithic functions with too many concerns | Hard to test individual pieces |
| **Dependency Inversion** | High-level DLT depends on low-level `binance.client.Client` | Tight coupling |

### Code Quality Issues

| Issue | Description | Location | Severity |
|-------|-------------|----------|----------|
| **Massive duplication** | `_fetch_agg_trades()` and `_fetch_candles()` share 70% identical code | Lines 88-248, 348-486 | **P0 Critical** |
| **Overly long functions** | 160-line generator functions violate SRP | Lines 88-248 | **P0 Critical** |
| **Magic numbers** | Hardcoded timeouts (60), batch sizes (1000), weights (1, 2) | Throughout | **P1 High** |
| **Poor testability** | Cannot unit test rate limiting, transformation, or batch logic independently | All generators | **P1 High** |
| **Weak type hints** | `Iterator[dict]` should be `Iterator[List[Dict[str, Any]]]` | Lines 90, 353 | **P2 Medium** |

### Layer Confusion

**Current (Everything Mixed Together):**
```
┌─────────────────────────────────────────────┐
│  DLT Resources (orchestration)              │
│  ├─ API calls (binance-specific)            │
│  ├─ Rate limiting (reusable)                │
│  ├─ Error handling (reusable)               │
│  ├─ Transformation (binance-specific)       │
│  └─ Progress tracking (reusable)            │
└─────────────────────────────────────────────┘
```

**Problem:** Cannot reuse logic with other exchanges, cannot test components independently.

---

## Proposed OOP Architecture

### 4-Layer Design

```
┌───────────────────────────────────────────────────────────┐
│ Layer 4: DLT Integration (Orchestration)                  │
│ ├─ BinanceDLTResourceFactory                              │
│ └─ Wires up: client → transformer → fetcher → yield data  │
└───────────────────────────────────────────────────────────┘
                           ↓
┌───────────────────────────────────────────────────────────┐
│ Layer 3: Generic Batch Fetcher (Reusable Logic)           │
│ ├─ IncrementalBatchFetcher                                │
│ ├─ ProgressTracker                                        │
│ └─ Works with ANY exchange API                            │
└───────────────────────────────────────────────────────────┘
                           ↓
┌───────────────────────────────────────────────────────────┐
│ Layer 2: Binance Implementations (Exchange-Specific)      │
│ ├─ BinanceAPIClient (wraps python-binance)                │
│ ├─ BinanceAggTradeTransformer                             │
│ ├─ BinanceCandleTransformer                               │
│ └─ constants.py (intervals, weights)                      │
└───────────────────────────────────────────────────────────┘
                           ↓
┌───────────────────────────────────────────────────────────┐
│ Layer 1: Abstract Core (Protocols/ABCs)                   │
│ ├─ RateLimiter (Protocol)                                 │
│ ├─ APIClient (ABC)                                        │
│ ├─ DataTransformer (ABC, Generic)                         │
│ └─ Works with ANY exchange: Binance, Coinbase, Kraken     │
└───────────────────────────────────────────────────────────┘
```

---

## Layer 1: Abstract Core (Reusable with ANY Exchange)

**Location:** `sources/core/interfaces.py`

```python
"""Abstract interfaces for exchange-agnostic data fetching."""
from abc import ABC, abstractmethod
from typing import Protocol, Optional, Any, List, Generic, TypeVar

TRaw = TypeVar('TRaw')  # Raw API response type
TTransformed = TypeVar('TTransformed')  # Transformed schema type


class RateLimiter(Protocol):
    """Rate limiting strategy - works with any API."""

    def wait_if_needed(self, weight: int) -> None:
        """Block until rate limit allows request."""
        ...

    def handle_rate_limit_error(self, retry_after: Optional[int] = None) -> None:
        """Handle 429 rate limit error."""
        ...


class APIClient(ABC):
    """Generic REST API client interface."""

    @abstractmethod
    def fetch_batch(self, request: 'APIRequest') -> 'APIResponse':
        """Fetch a batch of data from the API."""
        ...

    @property
    @abstractmethod
    def timeout(self) -> int:
        """Request timeout in seconds."""
        ...


class DataTransformer(ABC, Generic[TRaw, TTransformed]):
    """Transform raw API data to target schema."""

    @abstractmethod
    def transform_batch(self, raw_data: List[TRaw]) -> List[TTransformed]:
        """Transform a batch of raw data."""
        ...

    @abstractmethod
    def extract_cursor(self, item: TTransformed) -> Any:
        """Extract cursor value for incremental loading."""
        ...

    @abstractmethod
    def extract_timestamp(self, item: TTransformed) -> int:
        """Extract timestamp in milliseconds."""
        ...
```

**Benefits:**
- Works with Binance, Coinbase, Kraken, or any exchange
- Swap rate limiting strategies (token bucket, sliding window, etc.)
- Swap transformers for different schemas
- Test with mock implementations

---

## Layer 2: Binance Implementations

### 2.1 BinanceAPIClient

**Location:** `sources/binance/client.py`

```python
"""Binance-specific API client implementation."""
from binance.client import Client
from binance.exceptions import BinanceAPIException
from typing import Optional, List, Dict
from ..core.interfaces import APIClient


class BinanceAPIClient(APIClient):
    """Binance-specific API client wrapping python-binance."""

    def __init__(self, api_key: str, api_secret: str, timeout: int = 60):
        """Initialize Binance client."""
        self._client = Client(
            api_key,
            api_secret,
            requests_params={'timeout': timeout}
        )
        self._timeout = timeout

    @property
    def timeout(self) -> int:
        """Request timeout in seconds."""
        return self._timeout

    def fetch_agg_trades(
        self,
        symbol: str,
        from_id: Optional[int] = None,
        start_time: Optional[int] = None,
        limit: int = 1000
    ) -> List[Dict]:
        """Fetch aggregated trades from Binance."""
        if from_id is not None:
            return self._client.get_aggregate_trades(
                symbol=symbol, limit=limit, fromId=from_id
            )
        else:
            return self._client.get_aggregate_trades(
                symbol=symbol, limit=limit, startTime=start_time
            )

    def fetch_candles(
        self,
        symbol: str,
        interval: str,
        start_time: int,
        end_time: int,
        limit: int = 1000
    ) -> List[List]:
        """Fetch candlestick data from Binance."""
        return self._client.get_historical_klines(
            symbol=symbol,
            interval=interval,
            start_str=start_time,
            end_str=end_time,
            limit=limit
        )
```

### 2.2 BinanceAggTradeTransformer

**Location:** `sources/binance/transformers.py`

```python
"""Binance data transformers."""
from datetime import datetime, timezone
from typing import Dict, List
from ..core.interfaces import DataTransformer


class BinanceAggTradeTransformer(DataTransformer[Dict, Dict]):
    """Transform Binance aggregated trades to target schema."""

    def __init__(self, symbol: str):
        """Initialize transformer for a specific symbol."""
        self.symbol = symbol

    def transform_batch(self, raw_trades: List[Dict]) -> List[Dict]:
        """Transform a batch of raw trades."""
        return [self._transform_single(t) for t in raw_trades]

    def _transform_single(self, trade: Dict) -> Dict:
        """Transform a single trade record."""
        dt = datetime.fromtimestamp(trade["T"] / 1000, tz=timezone.utc)
        return {
            "agg_trade_id": trade["a"],
            "price": trade["p"],
            "quantity": trade["q"],
            "first_trade_id": trade["f"],
            "last_trade_id": trade["l"],
            "timestamp": trade["T"],
            "is_buyer_maker": trade["m"],
            "is_best_match": trade["M"],
            "symbol": self.symbol,
            "date": dt.date().isoformat(),
        }

    def extract_cursor(self, item: Dict) -> int:
        """Extract cursor for incremental loading."""
        return item["agg_trade_id"]

    def extract_timestamp(self, item: Dict) -> int:
        """Extract timestamp in milliseconds."""
        return item["timestamp"]


class BinanceCandleTransformer(DataTransformer[List, Dict]):
    """Transform Binance candles to target schema."""

    def __init__(self, symbol: str):
        """Initialize transformer for a specific symbol."""
        self.symbol = symbol

    def transform_batch(self, raw_candles: List[List]) -> List[Dict]:
        """Transform a batch of raw candles."""
        return [self._transform_single(c) for c in raw_candles]

    def _transform_single(self, candle: List) -> Dict:
        """Transform a single candle record."""
        open_dt = datetime.fromtimestamp(candle[0] / 1000, tz=timezone.utc)
        return {
            "symbol": self.symbol,
            "open_time": candle[0],
            "open": candle[1],
            "high": candle[2],
            "low": candle[3],
            "close": candle[4],
            "volume": candle[5],
            "close_time": candle[6],
            "quote_volume": candle[7],
            "trades": candle[8],
            "taker_buy_base": candle[9],
            "taker_buy_quote": candle[10],
            "date": open_dt.date().isoformat(),
        }

    def extract_cursor(self, item: Dict) -> int:
        """Extract cursor for incremental loading."""
        return item["open_time"]

    def extract_timestamp(self, item: Dict) -> int:
        """Extract timestamp in milliseconds."""
        return item["close_time"]
```

### 2.3 Constants

**Location:** `sources/binance/constants.py`

```python
"""Binance-specific constants."""

# API configuration
API_TIMEOUT = 60  # seconds
BATCH_SIZE = 1000  # records per request

# API weights (for rate limiting)
API_WEIGHTS = {
    "agg_trades": 1,
    "klines": 2,
}

# Interval name mapping
INTERVAL_MAP = {
    "1s": "1SECOND",
    "1m": "1MINUTE",
    "3m": "3MINUTE",
    "5m": "5MINUTE",
    "15m": "15MINUTE",
    "30m": "30MINUTE",
    "1h": "1HOUR",
    "2h": "2HOUR",
    "4h": "4HOUR",
    "6h": "6HOUR",
    "8h": "8HOUR",
    "12h": "12HOUR",
    "1d": "1DAY",
    "3d": "3DAY",
    "1w": "1WEEK",
    "1M": "1MONTH",
}
```

---

## Layer 3: Generic Batch Fetcher (Reusable)

**Location:** `sources/core/batch_fetcher.py`

```python
"""Generic incremental batch fetcher - works with any API."""
from datetime import datetime
from typing import Iterator, List, Dict, Any, Callable, Optional
import logging
from .interfaces import APIClient, DataTransformer, RateLimiter
from .exceptions import RateLimitError, APIError


class IncrementalBatchFetcher:
    """
    Generic incremental batch fetcher - works with ANY API.

    Encapsulates:
    - Batch loop logic
    - Rate limiting
    - Error handling with retry
    - Progress tracking
    - Cutoff time checking

    Zero Binance-specific code - fully reusable.
    """

    def __init__(
        self,
        client: APIClient,
        transformer: DataTransformer,
        rate_limiter: RateLimiter,
        api_weight: int = 1,
        batch_size: int = 1000,
        logger: Optional[logging.Logger] = None
    ):
        """Initialize batch fetcher with collaborators."""
        self.client = client
        self.transformer = transformer
        self.rate_limiter = rate_limiter
        self.api_weight = api_weight
        self.batch_size = batch_size
        self.logger = logger or logging.getLogger(__name__)
        self._batch_count = 0
        self._total_records = 0

    def fetch_until_cutoff(
        self,
        fetch_func: Callable,  # API-specific fetch method
        start_cursor: Any,
        cutoff_time: datetime,
        **fetch_kwargs
    ) -> Iterator[List[Dict]]:
        """
        Generic batch fetching loop.

        Args:
            fetch_func: API-specific fetch function (e.g., client.fetch_agg_trades)
            start_cursor: Starting cursor value (trade ID, timestamp, etc.)
            cutoff_time: Stop fetching when reaching this time
            **fetch_kwargs: Additional args for fetch_func

        Yields:
            Batches of transformed data
        """
        cutoff_ts_ms = int(cutoff_time.timestamp() * 1000)
        current_cursor = start_cursor

        while True:
            # Rate limit before API call
            self.rate_limiter.wait_if_needed(self.api_weight)

            # Fetch batch with retry logic
            try:
                raw_batch = fetch_func(
                    **fetch_kwargs,
                    cursor=current_cursor,
                    limit=self.batch_size
                )
            except RateLimitError:
                self.rate_limiter.handle_rate_limit_error(retry_after=None)
                continue  # Retry
            except APIError as e:
                self.logger.error(f"API error: {e}")
                return

            if not raw_batch:
                self.logger.info("No more data available from API")
                break

            # Transform batch
            transformed_batch = self.transformer.transform_batch(raw_batch)

            # Check cutoff time
            last_timestamp = self.transformer.extract_timestamp(transformed_batch[-1])
            if last_timestamp > cutoff_ts_ms:
                # Filter to cutoff
                transformed_batch = [
                    item for item in transformed_batch
                    if self.transformer.extract_timestamp(item) <= cutoff_ts_ms
                ]
                if not transformed_batch:
                    self.logger.info(f"Reached cutoff time ({cutoff_time})")
                    break

            # Update cursor for next iteration
            current_cursor = self.transformer.extract_cursor(transformed_batch[-1]) + 1

            # Update progress
            self._batch_count += 1
            self._total_records += len(transformed_batch)

            # Log progress
            first_ts = self.transformer.extract_timestamp(transformed_batch[0])
            last_ts = self.transformer.extract_timestamp(transformed_batch[-1])
            first_time = datetime.fromtimestamp(first_ts / 1000)
            last_time = datetime.fromtimestamp(last_ts / 1000)

            self.logger.info(
                f"Batch {self._batch_count}: {first_time} to {last_time} "
                f"({len(transformed_batch)} records, {self._total_records} total)"
            )

            # Yield batch
            yield transformed_batch

            # Break if reached cutoff
            if last_timestamp > cutoff_ts_ms:
                self.logger.info(
                    f"Completed: {self._batch_count} batches, "
                    f"{self._total_records} records fetched"
                )
                break
```

**Key Benefits:**
- Zero Binance-specific code
- Works with Coinbase, Kraken, etc. by swapping client and transformer
- Testable in isolation with mock client/transformer
- Encapsulates ALL batch logic (no duplication)

---

## Layer 4: DLT Integration (Thin Orchestration)

**Location:** `sources/rest_api.py` (refactored)

```python
"""DLT resources for Binance data - refactored to use OOP architecture."""
import dlt
import logging
from typing import Iterator, Optional, List, Dict
from datetime import datetime, timedelta, timezone

from ..config import BinanceConfig
from ..utils.rate_limiter import BinanceRateLimiter
from .binance.client import BinanceAPIClient
from .binance.transformers import BinanceAggTradeTransformer, BinanceCandleTransformer
from .binance.constants import API_WEIGHTS, INTERVAL_MAP
from .core.batch_fetcher import IncrementalBatchFetcher

logger = logging.getLogger(__name__)

# Global rate limiter (shared across all symbols)
_rate_limiter = BinanceRateLimiter()


class BinanceDLTResourceFactory:
    """Factory for creating DLT resources with Binance data."""

    def __init__(self, config: BinanceConfig, rate_limiter: BinanceRateLimiter):
        """Initialize factory with config and rate limiter."""
        self.config = config
        self.rate_limiter = rate_limiter

    def create_agg_trades_resource(self, symbol: str, start_date: str) -> dlt.resource:
        """Create DLT resource for aggregated trades."""

        @dlt.resource(
            name=f"agg_trades_{symbol.lower()}",
            table_name=symbol.upper(),
            write_disposition="append",
            primary_key="agg_trade_id",
            columns={"date": {"partition": True}},
        )
        def _fetch_agg_trades(
            incremental: dlt.sources.incremental[int] = dlt.sources.incremental(
                "agg_trade_id", initial_value=None
            ),
        ) -> Iterator[List[Dict]]:
            """Fetch aggregated trades with incremental loading."""

            # Create collaborators (dependency injection)
            client = BinanceAPIClient(self.config.api_key, self.config.api_secret)
            transformer = BinanceAggTradeTransformer(symbol)
            fetcher = IncrementalBatchFetcher(
                client=client,
                transformer=transformer,
                rate_limiter=self.rate_limiter,
                api_weight=API_WEIGHTS["agg_trades"]
            )

            # Calculate cutoff
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)

            # Determine start cursor
            if incremental.last_value is not None:
                # Incremental run
                start_cursor = incremental.last_value + 1
                start_ts = None
                logger.info(f"[{symbol}] Resuming from {start_cursor}")
            else:
                # Initial run
                start_cursor = None
                start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)
                logger.info(f"[{symbol}] Starting from {start_date}")

            # Fetch data (all complexity hidden in fetcher!)
            yield from fetcher.fetch_until_cutoff(
                fetch_func=lambda **kw: client.fetch_agg_trades(
                    symbol=symbol,
                    from_id=kw.get('cursor') if kw.get('cursor') else None,
                    start_time=start_ts if start_cursor is None else None,
                    limit=kw['limit']
                ),
                start_cursor=start_cursor,
                cutoff_time=cutoff_time
            )

        return _fetch_agg_trades

    def create_candles_resource(
        self, symbol: str, start_date: str, interval: str
    ) -> dlt.resource:
        """Create DLT resource for candlestick data."""
        # Similar implementation - omitted for brevity
        # Uses BinanceCandleTransformer instead
        ...


# Update existing source functions to use factory
@dlt.source
def binance_historical_data(
    config: BinanceConfig,
    symbols: Optional[List[str]] = None,
    start_date: Optional[str] = None,
):
    """DLT source for historical Binance data."""
    symbols = symbols or config.symbols
    start_date = start_date or config.historical_start_date

    factory = BinanceDLTResourceFactory(config, _rate_limiter)

    return [
        factory.create_agg_trades_resource(symbol, start_date)
        for symbol in symbols
    ]
```

**Result:** DLT resources reduced from 160 lines → **~50 lines** (68% reduction)

---

## File Structure

```
src/binance_tick_data/sources/
├── core/                          # Reusable abstractions (Layer 1)
│   ├── __init__.py
│   ├── interfaces.py              # ABCs: RateLimiter, APIClient, DataTransformer
│   ├── batch_fetcher.py           # IncrementalBatchFetcher
│   ├── progress_tracker.py        # ProgressTracker helper
│   └── exceptions.py              # RateLimitError, APIError
│
├── binance/                       # Binance implementations (Layer 2)
│   ├── __init__.py
│   ├── client.py                  # BinanceAPIClient
│   ├── transformers.py            # BinanceAggTradeTransformer, BinanceCandleTransformer
│   └── constants.py               # INTERVAL_MAP, API_WEIGHTS
│
├── rest_api.py                    # DLT integration (Layer 4) - ~200 lines total
└── websocket.py                   # (existing, could be refactored similarly)
```

---

## Implementation Phases

### Phase 1: Create Abstract Core (No Breaking Changes)
**Duration:** 2-3 hours
**Risk:** Low

1. Create `sources/core/interfaces.py` with ABCs/Protocols:
   - `RateLimiter` (Protocol)
   - `APIClient` (ABC)
   - `DataTransformer` (ABC, Generic)

2. Create `sources/core/batch_fetcher.py`:
   - `IncrementalBatchFetcher` class
   - `ProgressTracker` helper

3. Create `sources/core/exceptions.py`:
   - `RateLimitError`, `APIError`

**Output:** Reusable abstractions that work with ANY exchange

---

### Phase 2: Extract Binance Implementations (No Breaking Changes)
**Duration:** 3-4 hours
**Risk:** Low

1. Create `sources/binance/constants.py`:
   - Move `INTERVAL_MAP` from `rest_api.py`
   - Define `API_WEIGHTS`, `API_TIMEOUT`, `BATCH_SIZE`

2. Create `sources/binance/client.py`:
   - `BinanceAPIClient` class
   - Methods: `fetch_agg_trades()`, `fetch_candles()`

3. Create `sources/binance/transformers.py`:
   - `BinanceAggTradeTransformer`
   - `BinanceCandleTransformer`

4. Update `utils/rate_limiter.py`:
   - Make `BinanceRateLimiter` implement `RateLimiter` Protocol

**Output:** Binance logic separated, ready for Coinbase/Kraken

---

### Phase 3: Refactor `rest_api.py` (Internal Changes Only)
**Duration:** 4-5 hours
**Risk:** Medium (needs testing)

1. Create `BinanceDLTResourceFactory` class

2. Refactor `_fetch_agg_trades()` to use:
   - `BinanceAPIClient` for API calls
   - `BinanceAggTradeTransformer` for transformation
   - `IncrementalBatchFetcher` for batch logic

3. Refactor `_fetch_candles()` similarly

4. Update `binance_historical_data()`, `binance_daily_candles()`, `binance_intraday_candles()` sources

**Output:** DLT resources become thin orchestrators (~50 lines each)

**Migration:** External API unchanged - pipelines continue working

---

### Phase 4: Add Unit Tests
**Duration:** 3-4 hours
**Risk:** Low

1. Write tests for each component:
   - `tests/unit/sources/core/test_batch_fetcher.py`
   - `tests/unit/sources/binance/test_client.py`
   - `tests/unit/sources/binance/test_transformers.py`

2. Update integration tests

3. Ensure backward compatibility

**Output:** >90% test coverage

---

### Phase 5: Update Documentation
**Duration:** 1-2 hours
**Risk:** Low

1. Update `sources/__init__.py` exports
2. Update `docs/API_REFERENCE.md`
3. Update `CLAUDE.md` with new architecture
4. Add architecture diagram to README

**Output:** Complete documentation

---

## Code Metrics Improvement

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| **Lines in `rest_api.py`** | 648 | ~200 | **69% reduction** |
| **Code duplication** | 70% | <5% | **Near elimination** |
| **Avg function length** | 160 lines | 50 lines | **68% shorter** |
| **Testable components** | 0 classes | 7 classes | **∞ improvement** |
| **SOLID compliance** | 0/5 principles | 5/5 principles | **100% compliant** |
| **Cyclomatic complexity** | High (nested loops, conditions) | Low (single responsibility) | **Significant reduction** |

---

## SOLID Compliance Achieved

### ✅ Single Responsibility Principle
- `BinanceAPIClient`: API calls only
- `BinanceAggTradeTransformer`: Transformation only
- `IncrementalBatchFetcher`: Batch logic only
- `BinanceDLTResourceFactory`: Wiring/orchestration only

### ✅ Open/Closed Principle
- Add Coinbase: Create `CoinbaseAPIClient` + `CoinbaseTradeTransformer`
- Add Kraken: Create `KrakenAPIClient` + `KrakenTradeTransformer`
- **Zero changes** to `IncrementalBatchFetcher`

### ✅ Liskov Substitution Principle
- Any `APIClient` can replace another
- Any `DataTransformer` can replace another
- Any `RateLimiter` can replace another

### ✅ Interface Segregation Principle
- Small, focused interfaces: `RateLimiter`, `APIClient`, `DataTransformer`
- No fat interfaces forcing unnecessary dependencies

### ✅ Dependency Inversion Principle
- DLT resources depend on abstractions (`APIClient`, `RateLimiter`)
- Not concrete Binance classes
- Enables dependency injection for testing

---

## Future Extensibility

### Example 1: Add Coinbase Exchange Support

```python
# sources/coinbase/client.py
class CoinbaseAPIClient(APIClient):
    def fetch_trades(self, product_id: str, after: int, limit: int) -> List[Dict]:
        # Coinbase-specific API call
        ...

# sources/coinbase/transformers.py
class CoinbaseTradeTransformer(DataTransformer):
    def transform_batch(self, raw_trades: List[Dict]) -> List[Dict]:
        # Coinbase schema → our schema
        ...

# Reuse IncrementalBatchFetcher - no changes needed!
fetcher = IncrementalBatchFetcher(coinbase_client, coinbase_transformer, rate_limiter)
```

### Example 2: Swap Rate Limiting Strategy

```python
# Testing with no rate limiting
no_limit = NoOpRateLimiter()
fetcher = IncrementalBatchFetcher(client, transformer, no_limit)

# Production with token bucket
token_bucket = TokenBucketRateLimiter(rate=1200, period=60)
fetcher = IncrementalBatchFetcher(client, transformer, token_bucket)
```

### Example 3: Custom Transformers for ML

```python
# Transform to different schema for ML pipeline
class BinanceMLTransformer(DataTransformer):
    def transform_batch(self, raw_trades):
        # Add technical indicators, normalize prices, etc.
        return [self._add_features(t) for t in raw_trades]
```

---

## Testing Strategy

### Unit Tests (Individual Components)

```python
# Test transformer in isolation
def test_binance_trade_transformer():
    transformer = BinanceAggTradeTransformer("BTCUSDT")
    raw = {"a": 123, "p": "50000", "q": "0.1", "T": 1234567890000, ...}
    result = transformer.transform_batch([raw])
    assert result[0]["agg_trade_id"] == 123
    assert result[0]["symbol"] == "BTCUSDT"

# Test batch fetcher with mock client
def test_batch_fetcher_with_mock_client():
    mock_client = Mock(spec=APIClient)
    mock_transformer = Mock(spec=DataTransformer)
    mock_rate_limiter = Mock(spec=RateLimiter)

    mock_client.fetch_agg_trades.return_value = [...]
    mock_transformer.transform_batch.return_value = [...]

    fetcher = IncrementalBatchFetcher(mock_client, mock_transformer, mock_rate_limiter)

    batches = list(fetcher.fetch_until_cutoff(...))

    assert len(batches) > 0
    mock_rate_limiter.wait_if_needed.assert_called()
```

### Integration Tests (End-to-End)

```python
def test_binance_historical_data_integration():
    """Test full pipeline with real Binance client."""
    config = BinanceConfig(symbols=["BTCUSDT"], historical_start_date="2024-11-01")
    source = binance_historical_data(config)

    pipeline = dlt.pipeline(...)
    load_info = pipeline.run(source)

    assert load_info.has_failed_jobs is False
```

---

## Migration Strategy

### Option A: Non-Breaking (Dual Implementation)
**Pros:** Zero risk, users migrate at their own pace
**Cons:** Temporary code duplication

- Keep old functions in `rest_api.py` (mark as deprecated)
- Add new class-based implementations alongside
- Users migrate at their own pace

### Option B: Direct Refactor (Recommended) ⭐
**Pros:** Clean codebase immediately
**Cons:** Requires thorough testing

- Replace implementation inside existing functions
- External API stays same: `binance_historical_data()`, etc.
- No user-facing changes - pipelines continue working

**Recommendation:** Option B - refactor internals, keep external API unchanged

---

## Risks and Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Breaking existing pipelines** | High | Keep external API unchanged, test thoroughly |
| **Performance regression** | Medium | Benchmark before/after, ensure no extra overhead |
| **Incomplete test coverage** | Medium | Aim for >90% coverage, include integration tests |
| **Rate limiter compatibility** | Low | Make `BinanceRateLimiter` implement Protocol |
| **DLT incremental state** | Low | Use same state keys as before |

---

## Success Criteria

- ✅ All existing pipelines work without modification
- ✅ Unit tests for all new classes (>90% coverage)
- ✅ Integration tests pass
- ✅ Code duplication <5%
- ✅ SOLID compliance 5/5
- ✅ Can add Coinbase support in <4 hours

---

## Timeline

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 1: Abstract Core | 2-3 hours | None |
| Phase 2: Binance Implementations | 3-4 hours | Phase 1 |
| Phase 3: Refactor `rest_api.py` | 4-5 hours | Phase 1, 2 |
| Phase 4: Unit Tests | 3-4 hours | Phase 3 |
| Phase 5: Documentation | 1-2 hours | Phase 4 |
| **Total** | **13-18 hours** | Sequential |

---

## Conclusion

This refactoring transforms `rest_api.py` from a monolithic, tightly-coupled module to a clean, testable, extensible OOP architecture. The benefits are substantial:

- **Code Quality:** 69% reduction in LOC, near-zero duplication
- **Maintainability:** Small, focused classes with single responsibilities
- **Testability:** Every component testable in isolation
- **Extensibility:** Add Coinbase/Kraken in hours, not days
- **SOLID Compliance:** All 5 principles achieved

The migration path is low-risk with backward compatibility maintained. External API remains unchanged - users see no difference except improved reliability and performance.

**Recommendation:** Proceed with implementation using Option B (direct refactor, keep external API).

---

**Status:** Awaiting approval to proceed with implementation.