# Streaming Data Integration Plan: Market Microstructure Research Platform

**Version:** 1.0
**Date:** 2025-10-20
**Status:** Approved - In Implementation

## Executive Summary

Build a hybrid streaming architecture that combines direct WebSocket consumption with DuckDB querying for real-time market microstructure analysis. The system will support high throughput (1000+ trades/sec), scalability across multiple symbols, and provide a research-friendly interface for market microstructure studies.

## Architecture Overview

### System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    BINANCE EXCHANGE                              │
└──────────────────────────┬──────────────────────────────────────┘
                           │ WebSocket Stream
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│              Real-Time Stream Consumer                            │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  Connection Pool (Multi-Symbol WebSockets)              │     │
│  │  - Direct subscription bypassing dlt                    │     │
│  │  - Async event loop (non-blocking)                      │     │
│  │  - Target: >5000 trades/sec per symbol                 │     │
│  └────────────────┬───────────────────────────────────────┘     │
└───────────────────┼──────────────────────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
        ▼                       ▼
┌───────────────────┐   ┌──────────────────┐
│  Ring Buffer      │   │  Event Publisher │
│  (Hot Path)       │   │  (Pub/Sub)       │
│  - Last 10k trades│   │  - In-memory     │
│  - In-memory      │   │  - Optional Redis│
│  - <10ms access   │   │  - Subscribers   │
└───────┬───────────┘   └────────┬─────────┘
        │                        │
        │         ┌──────────────┘
        │         │
        ▼         ▼
┌──────────────────────────────────────┐
│    Market Microstructure Analyzers    │
│  ┌────────────┬──────────┬─────────┐ │
│  │Order Flow  │Liquidity │Volume   │ │
│  │Analyzer    │Analyzer  │Profile  │ │
│  └────────────┴──────────┴─────────┘ │
│  ┌────────────┬──────────────────────┐│
│  │Trade       │Price Impact          ││
│  │Intensity   │Analyzer               ││
│  └────────────┴──────────────────────┘│
└────────────────┬──────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────┐
│    Metrics Aggregator                │
│  - Rolling windows (1s, 5s, 30s, 1m) │
│  - VWAP, volatility, trade count     │
│  - Numpy ring buffers                │
└────────────────┬──────────────────────┘
                 │
     ┌───────────┴──────────┐
     │                      │
     ▼                      ▼
┌──────────────┐   ┌────────────────────┐
│ DuckDB Query │   │ Live Visualizations│
│ (Warm/Cold)  │   │ - Jupyter          │
│ - Last hour  │   │ - CLI Monitor      │
│ - Historical │   │ - Dashboards       │
└──────────────┘   └────────────────────┘
```

## 1. Real-Time Stream Consumer Service

**File:** `src/binance_tick_data/consumers/realtime_consumer.py`

### Key Features
- Direct WebSocket subscription bypassing dlt for ultra-low latency
- In-memory circular buffer for last N trades (configurable, default: 10,000)
- Async event loop for non-blocking processing
- Connection pooling for multiple symbols
- Pluggable analyzer interface for extensibility
- Automatic reconnection with exponential backoff

### API Design
```python
class RealtimeConsumer:
    def __init__(self, config: ConsumerConfig):
        """Initialize consumer with configuration"""

    async def start(self, symbols: List[str]):
        """Start consuming from WebSocket for given symbols"""

    async def stop(self):
        """Gracefully shutdown consumer"""

    def register_analyzer(self, analyzer: BaseAnalyzer):
        """Register analyzer to process trades"""

    def get_recent_trades(self, symbol: str, n: int = 100) -> List[Trade]:
        """Get last N trades from hot buffer"""

    def subscribe_to_events(self, callback: Callable):
        """Subscribe to trade events"""
```

### Performance Targets
- Latency: <50ms from WebSocket receive to analyzer callback
- Throughput: >5000 trades/sec per symbol
- Memory: <100MB for 10k trades per symbol

## 2. Market Microstructure Analyzers

**Directory:** `src/binance_tick_data/analyzers/`

### 2.1 Base Analyzer Interface

**File:** `base_analyzer.py`

```python
class BaseAnalyzer(ABC):
    @abstractmethod
    async def on_trade(self, trade: Trade) -> Optional[Dict[str, Any]]:
        """Process single trade, return metrics if computed"""

    @abstractmethod
    async def on_window_close(self, window_end: datetime) -> Dict[str, Any]:
        """Called when time window closes, compute aggregated metrics"""

    @abstractmethod
    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current state of metrics"""

    def reset(self):
        """Reset analyzer state"""
```

### 2.2 Order Flow Analyzer

**File:** `analyzers/order_flow.py`

**Metrics Computed:**
- Buy/sell trade count and volume ratio
- Aggressor side imbalance (buy-initiated vs sell-initiated)
- Order flow toxicity (adverse selection)
- Trade direction persistence (runs test)
- Cumulative order imbalance

**Window Sizes:** 1s, 5s, 30s, 60s rolling

### 2.3 Liquidity Analyzer

**File:** `analyzers/liquidity.py`

**Metrics Computed:**
- Bid-ask spread (absolute and relative)
- Market depth at multiple levels (top 5, 10, 20 levels)
- Liquidity score (depth / volatility)
- Spread volatility
- Depth imbalance (bid depth vs ask depth)

**Data Sources:**
- Order book snapshots from WebSocket
- Trade prices for spread estimation

### 2.4 Volume Profile Analyzer

**File:** `analyzers/volume_profile.py`

**Metrics Computed:**
- Real-time VWAP (volume-weighted average price)
- Volume clustering by price bins
- POC (Point of Control - price with most volume)
- Value area (70% of volume range)
- Volume delta (buy volume - sell volume)

**Implementation:**
- Price binning with configurable granularity
- Efficient histogram updates
- Rolling VWAP with decay factor

### 2.5 Trade Intensity Analyzer

**File:** `analyzers/trade_intensity.py`

**Metrics Computed:**
- Trade arrival rate (trades per second)
- Volume arrival rate (base currency per second)
- Inter-arrival time distribution (Poisson test)
- Volume burst detection (z-score based)
- Trade size distribution moments

**Statistical Methods:**
- Rolling statistics with exponential weighting
- Outlier detection for burst identification
- Time series decomposition (trend, seasonal, residual)

### 2.6 Price Impact Analyzer

**File:** `analyzers/price_impact.py`

**Metrics Computed:**
- Immediate price impact (trade size vs price change)
- Persistent price impact (decay analysis)
- Kyle's lambda (price impact coefficient)
- Amihud illiquidity ratio
- Correlation between trade size and returns

**Implementation:**
- Sliding window regression
- Exponentially weighted linear regression
- Volatility-adjusted impact metrics

## 3. Streaming Metrics Aggregator

**File:** `src/binance_tick_data/streaming/metrics_aggregator.py`

### Features
- Multiple time window support (1s, 5s, 30s, 1m, 5m)
- Efficient data structures (numpy ring buffers, pandas rolling)
- Computed metrics aggregated from all analyzers
- Configurable publication intervals
- Memory-efficient storage with automatic cleanup

### API Design
```python
class MetricsAggregator:
    def __init__(self, window_sizes: List[int], publish_interval: float):
        """Initialize with window sizes in seconds"""

    def add_metric(self, metric_name: str, value: float, timestamp: datetime):
        """Add metric value for all windows"""

    def get_window_metrics(self, window_size: int) -> Dict[str, pd.Series]:
        """Get all metrics for specific window"""

    def get_latest_summary(self) -> Dict[str, Dict[str, float]]:
        """Get latest aggregated metrics across all windows"""
```

### Computed Aggregations
- Mean, median, std, min, max
- Percentiles (5th, 25th, 75th, 95th)
- Rate of change
- Z-scores for anomaly detection

## 4. Dual-Mode Data Access Layer

**Enhancement to:** `src/binance_tick_data/repository_v2.py`

### New Methods to Add

```python
class BinanceDataRepository:
    def get_recent_window(
        self,
        symbol: str,
        seconds: int = 60,
        as_dataframe: bool = True
    ) -> Union[pd.DataFrame, List[Tuple]]:
        """Get trades from last N seconds - optimized for repeated calls"""

    def stream_trades_since(
        self,
        symbol: str,
        timestamp: datetime,
        batch_size: int = 1000
    ) -> Iterator[pd.DataFrame]:
        """Stream trades incrementally since timestamp"""

    def get_live_orderbook(
        self,
        symbol: str,
        depth: int = 10
    ) -> Dict[str, Any]:
        """Get most recent order book snapshot"""

    def get_realtime_vwap(
        self,
        symbol: str,
        window_seconds: int = 60
    ) -> float:
        """Compute VWAP for recent window"""

    def get_streaming_stats(
        self,
        symbol: str,
        window_seconds: int = 60
    ) -> Dict[str, float]:
        """Get real-time market statistics"""
```

### Query Optimization
- Query result caching with TTL (1-5 seconds)
- Prepared statements for repeated queries
- Index hints for time-range queries
- Connection pooling for concurrent access

## 5. Real-Time Event Publisher

**File:** `src/binance_tick_data/streaming/event_publisher.py`

### Architecture
- In-memory pub/sub as default (zero external dependencies)
- Optional Redis Streams for distributed consumers
- Topic-based routing (by symbol, metric type)
- Backpressure handling for slow subscribers
- Message batching for efficiency

### API Design
```python
class EventPublisher:
    def __init__(self, backend: str = "memory"):
        """Initialize with 'memory' or 'redis' backend"""

    def publish(self, topic: str, message: Dict[str, Any]):
        """Publish message to topic"""

    def subscribe(self, topic: str, callback: Callable):
        """Subscribe to topic with callback"""

    def unsubscribe(self, topic: str, callback: Callable):
        """Unsubscribe from topic"""

    async def publish_batch(self, messages: List[Tuple[str, Dict]]):
        """Publish multiple messages efficiently"""
```

### Message Format
```python
{
    "symbol": "BTCUSDT",
    "timestamp": "2025-10-20T12:34:56.789Z",
    "source": "order_flow_analyzer",
    "metrics": {
        "buy_sell_ratio": 1.23,
        "buy_volume": 145.67,
        "sell_volume": 118.32,
        "order_imbalance": 0.105
    },
    "window": "60s"
}
```

## 6. Jupyter/Analysis Integration

### 6.1 Real-Time Analysis Notebook

**File:** `examples/realtime_analysis.ipynb`

**Sections:**
1. Setup and Connection
2. Live Price and Trade Feed
3. Order Flow Heatmap (updating every 5s)
4. Liquidity Visualization (bid-ask spread, depth)
5. VWAP and Volume Profile
6. Trade Intensity Analysis
7. Price Impact Regression
8. Custom Analysis Examples

**Technologies:**
- `matplotlib.animation` for live updating plots
- `plotly` for interactive dashboards
- `ipywidgets` for controls (symbol selection, window size)

### 6.2 CLI Monitoring Tool

**File:** `examples/realtime_monitoring.py`

**Features:**
- Terminal-based dashboard (using `rich` library)
- Multi-symbol monitoring in table format
- Color-coded alerts for anomalies
- Scrolling trade feed
- Key metrics summary panel
- Export snapshot to JSON/CSV

**Command:**
```bash
uv run python examples/realtime_monitoring.py --symbols BTCUSDT ETHUSDT --refresh 1
```

### 6.3 Custom Analyzer Example

**File:** `examples/custom_analyzer_example.py`

Shows how to:
1. Extend `BaseAnalyzer`
2. Implement custom metric computation
3. Register with `RealtimeConsumer`
4. Subscribe to published events
5. Export results

## Implementation Timeline

### Phase 1: Core Infrastructure (Days 1-2)

#### Day 1
- [ ] Create directory structure
- [ ] Implement `ring_buffer.py` with benchmarks
- [ ] Create `base_analyzer.py` abstract interface
- [ ] Define `consumer_config.py` with Pydantic schemas
- [ ] Unit tests for ring buffer

#### Day 2
- [ ] Implement `realtime_consumer.py` core logic
- [ ] Add WebSocket connection pooling
- [ ] Implement analyzer registration system
- [ ] Add streaming query methods to `BinanceDataRepository`
- [ ] Integration tests with mock WebSocket

### Phase 2: Basic Analyzers (Days 3-4)

#### Day 3
- [ ] Implement `order_flow.py` analyzer
  - Buy/sell ratio
  - Order imbalance
  - Trade direction persistence
- [ ] Implement `liquidity.py` analyzer
  - Bid-ask spread
  - Market depth
  - Liquidity score
- [ ] Unit tests for both analyzers

#### Day 4
- [ ] Implement `volume_profile.py` analyzer
  - VWAP computation
  - Volume clustering
  - POC and value area
- [ ] Build `metrics_aggregator.py`
  - Multiple window support
  - Rolling statistics
  - Efficient storage
- [ ] Integration tests with sample data

### Phase 3: Event System (Day 5)

- [ ] Build `event_publisher.py` with in-memory pub/sub
- [ ] Add topic routing and subscription management
- [ ] Implement backpressure handling
- [ ] Add optional Redis Streams integration
- [ ] Create subscriber interface
- [ ] Performance testing (message throughput)

### Phase 4: Analysis Tools (Days 6-7)

#### Day 6
- [ ] Create `realtime_analysis.ipynb`
  - Live updating plots
  - Order flow heatmap
  - VWAP visualization
- [ ] Build CLI monitoring tool
  - Terminal dashboard
  - Multi-symbol support
  - Color-coded display

#### Day 7
- [ ] Add example custom analyzer
- [ ] Create usage guides and tutorials
- [ ] Add docstrings to all public APIs
- [ ] Create architecture diagrams

### Phase 5: Advanced Analyzers (Days 8-9)

#### Day 8
- [ ] Implement `trade_intensity.py` analyzer
  - Arrival rate modeling
  - Poisson test
  - Burst detection
- [ ] Implement `price_impact.py` analyzer
  - Kyle's lambda
  - Amihud ratio
  - Impact decay analysis
- [ ] Unit and integration tests

#### Day 9
- [ ] Add correlation analysis between metrics
- [ ] Implement anomaly detection
- [ ] Performance optimization
  - Profiling with cProfile
  - Bottleneck identification
  - Code optimization
- [ ] Memory leak testing

### Phase 6: Testing & Documentation (Day 10)

- [ ] End-to-end integration tests
  - Live data testing
  - Simulated data testing
  - Failure scenario testing
- [ ] Performance benchmarking
  - Throughput measurement
  - Latency profiling
  - Memory usage analysis
- [ ] Complete API documentation
  - Docstrings for all classes/methods
  - Type hints throughout
  - Usage examples
- [ ] Tutorial notebooks
  - Getting started guide
  - Advanced usage patterns
  - Troubleshooting guide

## Configuration Schema

### Consumer Configuration

**File:** `src/binance_tick_data/consumers/consumer_config.py`

```python
from pydantic import BaseModel, Field
from typing import List, Optional

class ConsumerConfig(BaseModel):
    """Configuration for real-time consumer"""

    # Buffer settings
    buffer_size: int = Field(default=10000, description="Ring buffer size per symbol")

    # Update settings
    update_interval: float = Field(default=0.1, description="Callback interval in seconds")

    # Symbols to consume
    symbols: List[str] = Field(default=["BTCUSDT"], description="Trading pairs to monitor")

    # Connection settings
    reconnect_delay: int = Field(default=5, description="Reconnect delay in seconds")
    max_reconnect_attempts: int = Field(default=10, description="Max reconnection attempts")

    # Performance settings
    batch_callback: bool = Field(default=True, description="Batch trades for callbacks")
    batch_size: int = Field(default=100, description="Trades per callback batch")

class AnalyzerConfig(BaseModel):
    """Base configuration for analyzers"""
    enabled: bool = True
    window_size: int = Field(default=60, description="Analysis window in seconds")

class OrderFlowConfig(AnalyzerConfig):
    """Order flow analyzer configuration"""
    compute_toxicity: bool = True
    persistence_test: bool = True

class LiquidityConfig(AnalyzerConfig):
    """Liquidity analyzer configuration"""
    depth_levels: int = Field(default=10, description="Order book depth levels to analyze")
    spread_method: str = Field(default="mid", description="Spread calculation method")

class VolumeProfileConfig(AnalyzerConfig):
    """Volume profile analyzer configuration"""
    price_bins: int = Field(default=50, description="Number of price bins for volume histogram")
    vwap_decay: float = Field(default=0.99, description="VWAP exponential decay factor")

class MetricsConfig(BaseModel):
    """Metrics aggregator configuration"""
    windows: List[int] = Field(default=[1, 5, 30, 60], description="Window sizes in seconds")
    publish_interval: float = Field(default=1.0, description="Metric publication interval")

class PublisherConfig(BaseModel):
    """Event publisher configuration"""
    backend: str = Field(default="memory", description="Backend type: 'memory' or 'redis'")
    redis_url: Optional[str] = Field(default=None, description="Redis connection URL")
    max_queue_size: int = Field(default=10000, description="Max messages in queue")

class StreamingConfig(BaseModel):
    """Complete streaming configuration"""
    consumer: ConsumerConfig = ConsumerConfig()
    order_flow: OrderFlowConfig = OrderFlowConfig()
    liquidity: LiquidityConfig = LiquidityConfig()
    volume_profile: VolumeProfileConfig = VolumeProfileConfig()
    metrics: MetricsConfig = MetricsConfig()
    publisher: PublisherConfig = PublisherConfig()
```

### Configuration File

**File:** `config.yaml` (additions)

```yaml
streaming:
  consumer:
    buffer_size: 10000
    update_interval: 0.1
    symbols:
      - BTCUSDT
      - ETHUSDT
      - BNBUSDT
    reconnect_delay: 5
    max_reconnect_attempts: 10
    batch_callback: true
    batch_size: 100

  order_flow:
    enabled: true
    window_size: 60
    compute_toxicity: true
    persistence_test: true

  liquidity:
    enabled: true
    window_size: 60
    depth_levels: 10
    spread_method: "mid"

  volume_profile:
    enabled: true
    window_size: 60
    price_bins: 50
    vwap_decay: 0.99

  metrics:
    windows: [1, 5, 30, 60]
    publish_interval: 1.0

  publisher:
    backend: "memory"  # or "redis"
    redis_url: "redis://localhost:6379"
    max_queue_size: 10000
```

## Performance Characteristics

### Throughput Targets
| Component | Target | Measurement |
|-----------|--------|-------------|
| WebSocket ingestion | 5000+ trades/sec | Per symbol |
| Ring buffer writes | <1μs | Per write |
| Analyzer callback | <5ms | Per trade |
| Metrics aggregation | <10ms | Per window close |
| Event publication | <1ms | Per message |
| Database query (hot) | <10ms | Recent window |

### Memory Profile
| Component | Memory Usage | Notes |
|-----------|--------------|-------|
| Ring buffer | ~8MB | 10k trades × 800 bytes/trade |
| Per analyzer | ~2-5MB | Depends on window size |
| Metrics aggregator | ~10MB | All windows, all metrics |
| Event publisher queue | ~5MB | 10k message queue |
| **Total per symbol** | **~30MB** | Scales linearly |

### Latency Budget
```
WebSocket receive        →  0-5ms
Ring buffer write        →  <1ms
Analyzer processing      →  2-5ms
Metrics aggregation      →  5-10ms
Event publication        →  1-2ms
Subscriber callback      →  <5ms (user code)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
End-to-end latency       →  15-30ms
```

## Dependencies

### Required
- `numpy>=1.26.0` ✓ (already present)
- `pandas>=2.3.0` ✓ (already present)
- `python-binance>=1.0.30` ✓ (already present)
- `websockets>=15.0.0` ✓ (already present)
- `pydantic>=2.12.0` ✓ (already present)
- `scipy>=1.15.0` ✓ (already present)

### Optional
- `redis>=5.0.0` (for distributed pub/sub)
- `asyncio-throttle>=1.0.0` (for rate limiting)
- `plotly>=6.3.0` ✓ (already present, for dashboards)
- `rich>=13.0.0` (for CLI dashboard)
- `ipywidgets>=8.0.0` (for notebook controls)

### Development
- `pytest>=7.0.0` (for testing)
- `pytest-asyncio>=0.21.0` (for async tests)
- `pytest-benchmark>=4.0.0` (for performance tests)
- `memory-profiler>=0.61.0` (for memory profiling)

## Expected Outcomes

### 1. Real-Time Consumer
- ✓ Processing 1000+ trades/sec per symbol
- ✓ <30ms end-to-end latency
- ✓ Automatic reconnection and error recovery
- ✓ Multi-symbol support with connection pooling
- ✓ Memory efficient (<30MB per symbol)

### 2. Market Microstructure Analyzers
- ✓ 5 core analyzers (order flow, liquidity, volume, intensity, impact)
- ✓ Extensible base class for custom analyzers
- ✓ Configurable window sizes and parameters
- ✓ Unit tested with >90% coverage

### 3. Event System
- ✓ In-memory pub/sub with zero dependencies
- ✓ Optional Redis backend for distributed systems
- ✓ Topic-based routing
- ✓ Backpressure handling

### 4. Data Access
- ✓ Dual-mode access (hot buffer + DuckDB)
- ✓ Streaming queries for incremental data
- ✓ Query caching for repeated access
- ✓ Compatible with existing repository API

### 5. Analysis Tools
- ✓ Live Jupyter notebook with updating visualizations
- ✓ CLI monitoring tool with rich terminal UI
- ✓ Example custom analyzers
- ✓ Export capabilities (JSON, CSV, Parquet)

### 6. Documentation
- ✓ Complete API documentation with type hints
- ✓ Architecture diagrams
- ✓ Tutorial notebooks (beginner to advanced)
- ✓ Troubleshooting guide
- ✓ Performance tuning guide

## Future Enhancements

### Short-term (Next Sprint)
1. Advanced price impact models (permanent vs temporary)
2. Machine learning integration for pattern detection
3. Multi-exchange support (aggregate liquidity)
4. Historical backtesting mode
5. Alert system with configurable triggers

### Medium-term (2-3 Months)
1. Distributed processing with Ray or Dask
2. GPU acceleration for computationally intensive analyzers
3. Time-series forecasting integration
4. Advanced visualization dashboard (Dash/Streamlit)
5. REST API for external consumers

### Long-term (6+ Months)
1. Market regime detection and classification
2. Causal inference for market microstructure
3. High-frequency trading strategy framework
4. Reinforcement learning for optimal execution
5. Full market simulator for strategy testing

## Risk Mitigation

### Technical Risks
| Risk | Mitigation |
|------|------------|
| WebSocket disconnections | Automatic reconnection with exponential backoff |
| Memory leaks | Circular buffers with fixed size, regular profiling |
| High CPU usage | Async I/O, batch processing, profiling |
| Data loss | Dual write (buffer + database), checkpointing |
| Slow analyzers | Timeout enforcement, async execution |

### Operational Risks
| Risk | Mitigation |
|------|------------|
| Binance API rate limits | Built-in rate limiting, backoff strategies |
| Data quality issues | Validation, anomaly detection, alerting |
| Configuration errors | Pydantic validation, sensible defaults |
| Version incompatibility | Semantic versioning, compatibility tests |

## Success Metrics

### Performance
- [ ] Achieve >5000 trades/sec throughput per symbol
- [ ] Maintain <30ms end-to-end latency (p95)
- [ ] Memory usage <30MB per symbol
- [ ] Zero data loss during 24hr test run

### Functionality
- [ ] All 5 core analyzers implemented and tested
- [ ] Live notebook with 7+ visualization examples
- [ ] CLI tool with multi-symbol monitoring
- [ ] Custom analyzer example working end-to-end

### Quality
- [ ] Test coverage >85%
- [ ] All public APIs documented
- [ ] Performance benchmarks passing
- [ ] No memory leaks in 24hr test

### Usability
- [ ] Complete getting started guide
- [ ] 3+ tutorial notebooks
- [ ] Troubleshooting guide
- [ ] Example configurations for common use cases

## Conclusion

This streaming data integration plan creates a production-ready market microstructure research platform while maintaining full compatibility with the existing dlt-based data collection system. The hybrid architecture provides flexibility to analyze both real-time and historical data efficiently, with a focus on research-friendly APIs and extensibility.

The modular design allows incremental implementation and testing, with each phase delivering tangible value. The system is designed to scale from single-symbol research on a laptop to multi-symbol production deployments on cloud infrastructure.

---

**Next Steps:**
1. Review and approve this plan
2. Set up development branch
3. Begin Phase 1 implementation
4. Schedule daily check-ins for progress tracking

**Questions or Concerns:**
Please contact the development team or file an issue on GitHub.
