# Getting Started with Real-Time Streaming

A step-by-step guide to using the streaming platform for market microstructure research.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start (5 minutes)](#quick-start-5-minutes)
3. [Understanding the Architecture](#understanding-the-architecture)
4. [Basic Usage Patterns](#basic-usage-patterns)
5. [Working with Analyzers](#working-with-analyzers)
6. [Advanced Topics](#advanced-topics)
7. [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Dependencies

All dependencies are already installed in your environment:

```bash
# Verify installation
uv run python -c "import binance_tick_data; print('✓ Ready to go!')"
```

### Optional Dependencies

For CLI monitoring dashboard:
```bash
uv add rich
```

### Python Version

- Python 3.12 (recommended)
- Python 3.10+ supported

## Quick Start (5 minutes)

### Step 1: Run the Simple Example

```bash
cd /path/to/binance-tick-data
uv run python examples/simple_streaming_example.py
```

This will:
- Connect to Binance WebSocket
- Stream BTCUSDT trades for 60 seconds
- Run 3 analyzers (order flow, liquidity, volume profile)
- Print metrics every 10 seconds
- Show final statistics

**Expected Output:**
```
INFO - Starting simple streaming example...
INFO - Registered 3 analyzers
INFO - Starting consumer...
INFO - Consumer started! Receiving trades...

================================================================================
Metrics Report - 2025-10-20 15:30:00
================================================================================

ORDER_FLOW ANALYZER
----------------------------------------
  buy_count                         :          156
  sell_count                        :          144
  total_trades                      :          300
  order_imbalance                   :       0.0400
  ...
```

### Step 2: Try the CLI Dashboard (if rich installed)

```bash
uv run python examples/realtime_monitoring.py --symbols BTCUSDT
```

Press `Ctrl+C` to stop.

### Step 3: Open the Jupyter Notebook

```bash
jupyter notebook examples/realtime_analysis.ipynb
```

Run cells sequentially to see live analysis and visualizations.

## Understanding the Architecture

### Core Components

```
┌─────────────────┐
│ RealtimeConsumer│  ← Manages WebSocket connections
└────────┬────────┘
         │
    ┌────┴─────┬──────────┬───────────┐
    ▼          ▼          ▼           ▼
┌──────┐  ┌─────────┐ ┌───────┐  ┌──────┐
│Order │  │Liquidity│ │Volume │  │Custom│  ← Pluggable analyzers
│Flow  │  │         │ │Profile│  │      │
└──┬───┘  └────┬────┘ └───┬───┘  └──┬───┘
   │           │          │         │
   └───────────┴──────────┴─────────┘
               │
               ▼
       ┌───────────────┐
       │ Your Analysis │  ← Get metrics, create visualizations
       └───────────────┘
```

### Data Flow

1. **WebSocket** receives trades from Binance
2. **Ring Buffer** stores recent trades in memory (O(1) access)
3. **Analyzers** process trades and compute metrics
4. **Metrics Aggregator** provides rolling window statistics
5. **Event Publisher** broadcasts metrics to subscribers

## Basic Usage Patterns

### Pattern 1: Simple Streaming

Collect data and analyze offline:

```python
import asyncio
from binance_tick_data.consumers import RealtimeConsumer, ConsumerConfig
from binance_tick_data.analyzers import OrderFlowAnalyzer

async def collect_data():
    # Setup
    config = ConsumerConfig(symbols=["BTCUSDT"])
    consumer = RealtimeConsumer(config)
    analyzer = OrderFlowAnalyzer(window_size=60)
    consumer.register_analyzer(analyzer)

    # Collect
    await consumer.start()
    await asyncio.sleep(300)  # 5 minutes

    # Get results
    metrics = analyzer.get_current_metrics()
    print(f"Order imbalance: {metrics['order_imbalance']}")

    await consumer.stop()

asyncio.run(collect_data())
```

### Pattern 2: Multi-Symbol Monitoring

Monitor multiple symbols simultaneously:

```python
config = ConsumerConfig(symbols=["BTCUSDT", "ETHUSDT", "BNBUSDT"])
consumer = RealtimeConsumer(config)

# Register analyzer for each
for symbol in config.symbols:
    consumer.register_analyzer(OrderFlowAnalyzer(window_size=60))

await consumer.start()
# ... monitor ...
```

### Pattern 3: Real-Time Callbacks

Get notified of each trade:

```python
def on_trade(symbol: str, trade):
    print(f"[{symbol}] {trade.price} @ {trade.qty}")

consumer.subscribe_to_trades(on_trade)
await consumer.start()
```

### Pattern 4: Repository Queries

Query historical and recent data:

```python
from binance_tick_data import BinanceDataRepository

with BinanceDataRepository() as repo:
    # Get last 60 seconds
    recent = repo.get_recent_window("BTCUSDT", seconds=60)

    # Real-time VWAP
    vwap = repo.get_realtime_vwap("BTCUSDT", window_seconds=60)

    # Statistics
    stats = repo.get_streaming_stats("BTCUSDT", window_seconds=60)
    print(f"Buy/Sell ratio: {stats['buy_sell_ratio']}")
```

## Working with Analyzers

### Available Analyzers

#### 1. Order Flow Analyzer

```python
from binance_tick_data.analyzers import OrderFlowAnalyzer

analyzer = OrderFlowAnalyzer(
    window_size=60,           # 60 second windows
    compute_toxicity=True,    # Calculate flow toxicity
    persistence_test=True,    # Run persistence test
    imbalance_threshold=0.1   # Alert if |imbalance| > 10%
)

consumer.register_analyzer(analyzer)
```

**Key Metrics:**
- `buy_count`, `sell_count` - Trade counts
- `order_imbalance` - Normalized (buy - sell) / total
- `buy_sell_ratio` - Buy count / sell count
- `flow_toxicity` - Adverse selection measure (0-1)
- `direction_persistence` - Runs test z-score

#### 2. Liquidity Analyzer

```python
from binance_tick_data.analyzers import LiquidityAnalyzer

analyzer = LiquidityAnalyzer(
    window_size=60,
    spread_method="mid",      # or "best", "effective"
)

consumer.register_analyzer(analyzer)
```

**Key Metrics:**
- `effective_spread_mean` - Estimated spread
- `liquidity_score` - Trade frequency / volatility
- `trade_arrival_rate` - Trades per second
- `price_std` - Price volatility

#### 3. Volume Profile Analyzer

```python
from binance_tick_data.analyzers import VolumeProfileAnalyzer

analyzer = VolumeProfileAnalyzer(
    window_size=60,
    price_bins=50,           # Number of price bins
    vwap_decay=0.99,         # VWAP decay factor
    value_area_percent=0.70  # 70% volume range
)

consumer.register_analyzer(analyzer)
```

**Key Metrics:**
- `vwap` - Volume weighted average price
- `volume_delta` - Buy volume - sell volume
- `poc_price` - Point of control (max volume price)
- `value_area_low`, `value_area_high` - 70% volume range

### Creating Custom Analyzers

See `examples/custom_analyzer_example.py` for complete examples.

**Basic Template:**

```python
from binance_tick_data.analyzers import BaseAnalyzer
from binance_tick_data.sources.schemas import Trade
from datetime import datetime
from typing import Dict, Optional, Any

class MyAnalyzer(BaseAnalyzer):
    def __init__(self, window_size: int = 60):
        super().__init__(name="my_analyzer", window_size=window_size)
        # Initialize your state
        self.counter = 0

    async def on_trade(self, trade: Trade) -> Optional[Dict[str, Any]]:
        """Called for each trade"""
        self.counter += 1
        # Process trade
        # Return None or per-trade metrics
        return None

    async def on_window_close(self, window_end: datetime) -> Dict[str, Any]:
        """Called when window closes"""
        metrics = {"total_trades": self.counter}
        # Reset state
        self.counter = 0
        return metrics

    def get_current_metrics(self) -> Dict[str, Any]:
        """Get metrics mid-window"""
        return {"current_count": self.counter}
```

## Advanced Topics

### Metrics Aggregation

Use `MetricsAggregator` for rolling window statistics:

```python
from binance_tick_data.streaming import MetricsAggregator

aggregator = MetricsAggregator(
    window_sizes=[10, 30, 60],  # Multiple windows
    publish_interval=1.0         # Update every second
)

# Add metrics
aggregator.add_metric("vwap", 50000.0, timestamp)

# Get statistics for 60s window
stats = aggregator.get_window_statistics("vwap", window_size=60)
print(f"Mean: {stats['mean']}, Std: {stats['std']}")
print(f"95th percentile: {stats['p95']}")

# Get time series
df = aggregator.get_time_series("vwap", window_size=300)
```

### Event Publishing

Use `EventPublisher` for pub/sub pattern:

```python
from binance_tick_data.streaming import EventPublisher

# In-memory publisher (single process)
publisher = EventPublisher(backend="memory")

# Subscribe
def handle_metrics(message):
    print(f"Received: {message['data']}")

publisher.subscribe("btc_metrics", handle_metrics)

# Publish
publisher.publish("btc_metrics", {
    "symbol": "BTCUSDT",
    "vwap": 50000.0,
    "volume": 125.5
})

# Redis publisher (distributed, optional)
publisher = EventPublisher(
    backend="redis",
    redis_url="redis://localhost:6379"
)
```

### Configuration Management

Edit `config.yaml`:

```yaml
streaming:
  consumer:
    buffer_size: 10000        # Trades per symbol
    symbols:
      - BTCUSDT
      - ETHUSDT
    reconnect_delay: 5        # Seconds

  order_flow:
    enabled: true
    window_size: 60
    compute_toxicity: true

  # ... other analyzers
```

Load configuration:

```python
from binance_tick_data.consumers import load_streaming_config

with open("config.yaml") as f:
    import yaml
    config_dict = yaml.safe_load(f)

streaming_config = load_streaming_config(config_dict)
```

## Troubleshooting

### Issue: Consumer won't connect

**Symptoms:**
```
Error: WebSocket connection failed
```

**Solutions:**
1. Check internet connection
2. Verify Binance API is accessible: `ping api.binance.com`
3. Check firewall settings for WebSocket (port 443)
4. Try different symbol: `ETHUSDT` instead of `BTCUSDT`

### Issue: No data received

**Symptoms:**
```
INFO - Consumer started
# ... but no trades
```

**Solutions:**
1. Check symbol name is correct (uppercase, no spaces)
2. Verify market is active (not maintenance)
3. Check `get_statistics()` for connection status:
```python
stats = consumer.get_statistics()
print(stats['symbols_data'])
```

### Issue: High memory usage

**Symptoms:**
Memory usage grows over time

**Solutions:**
1. Reduce `buffer_size` in config (default: 10000)
2. Disable unused analyzers
3. Reduce `window_sizes` in metrics aggregator
4. Clear aggregator periodically:
```python
aggregator.clear_all()
```

### Issue: ModuleNotFoundError

**Symptoms:**
```
ModuleNotFoundError: No module named 'binance_tick_data'
```

**Solutions:**
```bash
# Ensure you're in the project directory
cd /path/to/binance-tick-data

# Sync dependencies
uv sync

# Run with uv
uv run python examples/simple_streaming_example.py
```

### Issue: Slow performance

**Symptoms:**
High CPU usage, slow metric updates

**Solutions:**
1. Increase `update_interval` (default: 0.1s)
2. Reduce number of symbols
3. Simplify analyzer logic
4. Use `batch_callback=True` in consumer config
5. Profile analyzer code:
```python
import cProfile
cProfile.run('analyzer.on_trade(trade)')
```

### Issue: WebSocket disconnections

**Symptoms:**
```
WARNING - WebSocket error: Connection lost
INFO - Reconnecting in 5s...
```

**Solutions:**
1. This is normal - auto-reconnection handles it
2. Increase `max_reconnect_attempts` if needed
3. Check network stability
4. Adjust `ping_interval` in config

## Next Steps

### Learn More

- **Architecture**: `specs/STREAMING_INTEGRATION_PLAN.md`
- **Implementation**: `specs/STREAMING_IMPLEMENTATION_SUMMARY.md`
- **API Reference**: See docstrings in source files
- **Quick Reference**: `README_STREAMING.md`

### Examples to Try

1. **Simple streaming**: `examples/simple_streaming_example.py`
2. **Custom analyzers**: `examples/custom_analyzer_example.py`
3. **CLI dashboard**: `examples/realtime_monitoring.py` (requires `rich`)
4. **Jupyter notebook**: `examples/realtime_analysis.ipynb`

### Build Your Own

1. Create custom analyzer for your strategy
2. Integrate with your backtesting framework
3. Build alerts based on metrics
4. Create custom visualizations
5. Export data for further analysis

## Common Patterns Cheat Sheet

### Quick Data Collection
```python
# Collect 5 minutes of data
await consumer.start()
await asyncio.sleep(300)
metrics = analyzer.get_current_metrics()
await consumer.stop()
```

### Continuous Monitoring
```python
# Run indefinitely
await consumer.start()
try:
    while True:
        await asyncio.sleep(10)
        print(analyzer.get_current_metrics())
except KeyboardInterrupt:
    pass
finally:
    await consumer.stop()
```

### Get Recent Trades
```python
# From buffer (fast)
recent = consumer.get_recent_trades("BTCUSDT", n=100)

# From database (more history)
with BinanceDataRepository() as repo:
    recent = repo.get_recent_window("BTCUSDT", seconds=300)
```

### Real-Time Statistics
```python
with BinanceDataRepository() as repo:
    stats = repo.get_streaming_stats("BTCUSDT", window_seconds=60)
    print(f"Trades: {stats['trade_count']}")
    print(f"VWAP: {stats['vwap']}")
    print(f"Buy/Sell: {stats['buy_sell_ratio']}")
```

## Support

- **Issues**: File on GitHub
- **Documentation**: See `specs/` directory
- **Examples**: See `examples/` directory
- **Questions**: Check inline documentation (docstrings)

---

**Happy Streaming! 🚀**

Ready to analyze markets in real-time!
