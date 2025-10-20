# Dollar Volume Sampling

Dollar volume sampling is an information-driven approach to creating bars from tick data. Unlike traditional time-based bars, dollar volume bars aggregate ticks based on the dollar volume traded, making them adaptive to market activity.

## Table of Contents
1. [Why Dollar Volume Bars?](#why-dollar-volume-bars)
2. [Quick Start](#quick-start)
3. [Usage Examples](#usage-examples)
4. [API Reference](#api-reference)
5. [Advanced Features](#advanced-features)
6. [Best Practices](#best-practices)

## Why Dollar Volume Bars?

Dollar volume bars offer several advantages over time-based bars:

### Statistical Benefits
- **Better normality**: Returns are more normally distributed
- **Reduced autocorrelation**: Lower serial correlation in returns
- **Information-driven**: Bars form when significant trading occurs
- **Adaptive sampling**: More bars during high activity, fewer during quiet periods

### Practical Benefits
- **Market microstructure**: Better captures market dynamics
- **Event detection**: Natural alignment with market events
- **Risk management**: More stable volatility estimates
- **Strategy development**: Better backtesting properties

## Quick Start

### Basic Usage

```python
from binance_tick_data import create_dollar_volume_bars
import pandas as pd

# Load your tick data (must have 'timestamp', 'price', 'volume' columns)
tick_data = pd.read_csv('tick_data.csv')

# Create dollar volume bars (auto-calculated threshold)
bars = create_dollar_volume_bars(tick_data, ticks_per_bar=100)

print(f"Created {len(bars)} bars from {len(tick_data)} ticks")
print(bars.head())
```

### With Fixed Threshold

```python
# Create bars with specific dollar volume threshold
bars = create_dollar_volume_bars(
    tick_data,
    threshold=1_000_000  # $1M per bar
)
```

### Adaptive Threshold

```python
# Threshold adapts to recent market activity
bars = create_dollar_volume_bars(
    tick_data,
    ticks_per_bar=100,
    adaptive=True,
    lookback_bars=20
)
```

## Usage Examples

### Example 1: Basic Dollar Volume Bars

```python
from binance_tick_data import create_dollar_volume_bars, BinanceDataRepository
from datetime import datetime, timedelta

# Load tick data from repository
repo = BinanceDataRepository()
end_date = datetime.now()
start_date = end_date - timedelta(hours=24)

tick_data = repo.get_trades(
    symbol='BTCUSDT',
    start_date=start_date,
    end_date=end_date
)

# Create dollar volume bars
bars = create_dollar_volume_bars(tick_data, ticks_per_bar=100)

# Access OHLCV data
print(bars[['timestamp', 'open', 'high', 'low', 'close', 'volume']].head())
```

### Example 2: Statistical Analysis

```python
from binance_tick_data import DollarVolumeSampler

# Create sampler
sampler = DollarVolumeSampler(ticks_per_bar=100)
bars = sampler.create_bars(tick_data)

# Get statistics
stats = sampler.get_bar_statistics(bars)

print(f"Number of bars: {stats['n_bars']}")
print(f"Average ticks per bar: {stats['avg_ticks_per_bar']:.1f}")
print(f"Returns std: {stats['returns_std']:.4%}")
print(f"Skewness: {stats['returns_skew']:.3f}")
print(f"Kurtosis: {stats['returns_kurtosis']:.3f}")
```

### Example 3: Optimal Threshold Calculation

```python
from binance_tick_data import calculate_optimal_threshold, create_dollar_volume_bars

# Calculate threshold for target number of bars
target_bars = 500
threshold = calculate_optimal_threshold(tick_data, target_bars=target_bars)

print(f"Optimal threshold for {target_bars} bars: ${threshold:,.2f}")

# Create bars with this threshold
bars = create_dollar_volume_bars(tick_data, threshold=threshold)
print(f"Created {len(bars)} bars (target was {target_bars})")
```

### Example 4: Custom Column Names

```python
# If your data has different column names
bars = create_dollar_volume_bars(
    df=your_data,
    price_col='last_price',
    volume_col='quantity',
    timestamp_col='trade_time',
    ticks_per_bar=100
)
```

### Example 5: Integration with Trading Strategy

```python
from binance_tick_data import DollarVolumeSampler
import pandas as pd

# Initialize sampler
sampler = DollarVolumeSampler(ticks_per_bar=100)

# Create bars
bars = sampler.create_bars(tick_data)

# Calculate technical indicators
bars['sma_20'] = bars['close'].rolling(20).mean()
bars['sma_50'] = bars['close'].rolling(50).mean()
bars['returns'] = bars['close'].pct_change()

# Generate signals
bars['signal'] = 0
bars.loc[bars['sma_20'] > bars['sma_50'], 'signal'] = 1  # Buy signal
bars.loc[bars['sma_20'] < bars['sma_50'], 'signal'] = -1  # Sell signal

print(bars[['timestamp', 'close', 'sma_20', 'sma_50', 'signal']].tail(10))
```

## API Reference

### `create_dollar_volume_bars()`

Convenience function for quick bar creation.

```python
def create_dollar_volume_bars(
    df: pd.DataFrame,
    threshold: Optional[float] = None,
    ticks_per_bar: int = 100,
    price_col: str = 'price',
    volume_col: str = 'volume',
    timestamp_col: str = 'timestamp',
    adaptive: bool = False,
    lookback_bars: int = 20
) -> pd.DataFrame
```

**Parameters:**
- `df`: DataFrame with tick data
- `threshold`: Fixed dollar volume threshold. If None, calculated from `ticks_per_bar`
- `ticks_per_bar`: Target number of ticks per bar (default: 100)
- `price_col`: Name of price column (default: 'price')
- `volume_col`: Name of volume column (default: 'volume')
- `timestamp_col`: Name of timestamp column (default: 'timestamp')
- `adaptive`: Use adaptive threshold (default: False)
- `lookback_bars`: Lookback period for adaptive threshold (default: 20)

**Returns:**
DataFrame with columns:
- `bar_id`: Bar identifier (0, 1, 2, ...)
- `timestamp`: First timestamp in bar (bar open time)
- `timestamp_close`: Last timestamp in bar (bar close time)
- `open`: First price in bar
- `high`: Highest price in bar
- `low`: Lowest price in bar
- `close`: Last price in bar
- `volume`: Total volume in bar
- `dollar_volume`: Total dollar volume in bar
- `tick_count`: Number of ticks in bar
- `vwap`: Volume-weighted average price
- `price_std`: Standard deviation of prices
- `price_change`: Close - Open
- `duration_seconds`: Time duration of the bar in seconds
- `ticks_per_second`: Trading intensity (tick rate)
- `dollar_volume_per_second`: Dollar volume intensity
- `time_since_last_bar`: Time gap from previous bar (seconds)

### `DollarVolumeSampler`

Class for advanced control over bar creation.

```python
class DollarVolumeSampler:
    def __init__(
        self,
        threshold: Optional[float] = None,
        ticks_per_bar: int = 100,
        adaptive: bool = False,
        lookback_bars: int = 20
    )

    def create_bars(
        self,
        df: pd.DataFrame,
        price_col: str = 'price',
        volume_col: str = 'volume',
        timestamp_col: str = 'timestamp'
    ) -> pd.DataFrame

    def get_bar_statistics(
        self,
        bars: pd.DataFrame
    ) -> Dict[str, Any]
```

**Methods:**

#### `create_bars()`
Create dollar volume bars from tick data.

#### `get_bar_statistics()`
Calculate statistical properties of bars.

**Returns:**
Dictionary with:
- `n_bars`: Number of bars
- `avg_ticks_per_bar`: Average ticks per bar
- `std_ticks_per_bar`: Standard deviation of ticks per bar
- `avg_volume`: Average volume per bar
- `avg_dollar_volume`: Average dollar volume per bar
- `returns_mean`: Mean return
- `returns_std`: Standard deviation of returns
- `returns_skew`: Skewness of returns
- `returns_kurtosis`: Kurtosis of returns

### `calculate_optimal_threshold()`

Calculate optimal threshold for target number of bars.

```python
def calculate_optimal_threshold(
    df: pd.DataFrame,
    target_bars: int,
    price_col: str = 'price',
    volume_col: str = 'volume'
) -> float
```

**Parameters:**
- `df`: DataFrame with tick data
- `target_bars`: Desired number of bars
- `price_col`: Name of price column
- `volume_col`: Name of volume column

**Returns:**
Calculated threshold value

## Time-Based Metrics

Dollar volume bars now include comprehensive time-based metrics that reveal important trading patterns:

### Why Time Metrics Matter

While dollar volume bars provide information-driven sampling, the **time dimension** reveals crucial market microstructure insights:

1. **Trading Intensity** (`ticks_per_second`):
   - High values indicate aggressive trading or news events
   - Low values suggest consolidation or lack of interest
   - Useful for volatility prediction and risk management

2. **Dollar Volume Velocity** (`dollar_volume_per_second`):
   - Measures the speed of capital flow
   - High velocity often precedes price movements
   - Critical for liquidity assessment

3. **Bar Duration** (`duration_seconds`):
   - Short bars = high activity periods
   - Long bars = quiet/consolidation periods
   - Inversely correlated with market activity

4. **Inter-bar Gaps** (`time_since_last_bar`):
   - Large gaps indicate market regime changes
   - Useful for detecting session breaks or news events
   - Helps identify liquidity droughts

### Example: Analyzing Trading Intensity

```python
from binance_tick_data import create_dollar_volume_bars
import matplotlib.pyplot as plt

# Create bars with time metrics
bars = create_dollar_volume_bars(tick_data, ticks_per_bar=100)

# Analyze trading intensity patterns
fig, axes = plt.subplots(3, 1, figsize=(14, 10))

# Price with bar durations as color
scatter = axes[0].scatter(range(len(bars)), bars['close'],
                         c=bars['duration_seconds'], cmap='coolwarm')
axes[0].set_title('Price (colored by bar duration)')
plt.colorbar(scatter, ax=axes[0], label='Duration (seconds)')

# Trading intensity over time
axes[1].plot(bars['ticks_per_second'], color='green', alpha=0.7)
axes[1].set_title('Trading Intensity (ticks/second)')
axes[1].axhline(bars['ticks_per_second'].mean(), color='red', linestyle='--',
                label=f"Mean: {bars['ticks_per_second'].mean():.2f}")
axes[1].legend()

# Dollar volume velocity
axes[2].plot(bars['dollar_volume_per_second'], color='orange', alpha=0.7)
axes[2].set_title('Dollar Volume Velocity ($/second)')
axes[2].set_yscale('log')

plt.tight_layout()
plt.show()

# Identify high-activity periods
high_intensity = bars[bars['ticks_per_second'] > bars['ticks_per_second'].quantile(0.9)]
print(f"High intensity periods: {len(high_intensity)} bars")
print(f"Average price change during high intensity: {high_intensity['price_change'].mean():.4f}")
```

### Example: Market Regime Detection

```python
# Detect market regimes using time metrics
bars['regime'] = 'normal'

# High activity regime
high_activity_threshold = bars['ticks_per_second'].quantile(0.75)
bars.loc[bars['ticks_per_second'] > high_activity_threshold, 'regime'] = 'high_activity'

# Low activity regime
low_activity_threshold = bars['ticks_per_second'].quantile(0.25)
bars.loc[bars['ticks_per_second'] < low_activity_threshold, 'regime'] = 'low_activity'

# Analyze regime characteristics
regime_stats = bars.groupby('regime').agg({
    'price_change': ['mean', 'std'],
    'duration_seconds': 'mean',
    'dollar_volume': 'mean',
    'ticks_per_second': 'mean'
})

print("Market Regime Characteristics:")
print(regime_stats)
```

### Example: Liquidity Analysis

```python
# Identify liquidity droughts
bars['liquidity_score'] = (
    bars['dollar_volume_per_second'] /
    bars['dollar_volume_per_second'].rolling(20).mean()
)

# Flag low liquidity periods
low_liquidity = bars[bars['liquidity_score'] < 0.5]
print(f"Low liquidity periods: {len(low_liquidity)} bars")

# Check for gaps in trading
large_gaps = bars[bars['time_since_last_bar'] > bars['time_since_last_bar'].quantile(0.95)]
print(f"Large trading gaps: {len(large_gaps)}")
print(f"Average gap duration: {large_gaps['time_since_last_bar'].mean():.1f} seconds")
```

### Trading Strategy Integration

```python
# Use time metrics for entry/exit signals
def generate_signals(bars):
    """Generate trading signals using time-based metrics."""
    signals = pd.DataFrame(index=bars.index)

    # Entry signal: High intensity + positive momentum
    signals['entry'] = (
        (bars['ticks_per_second'] > bars['ticks_per_second'].rolling(20).mean()) &
        (bars['price_change'] > 0) &
        (bars['dollar_volume_per_second'] > bars['dollar_volume_per_second'].rolling(20).mean())
    )

    # Exit signal: Declining intensity
    signals['exit'] = (
        bars['ticks_per_second'] < bars['ticks_per_second'].rolling(20).mean() * 0.7
    )

    return signals

signals = generate_signals(bars)
print(f"Entry signals: {signals['entry'].sum()}")
print(f"Exit signals: {signals['exit'].sum()}")
```

### Key Insights from Time Metrics

1. **Pre-event Detection**: Sudden increases in `ticks_per_second` often precede major price moves
2. **Volatility Correlation**: `duration_seconds` inversely correlates with realized volatility
3. **Liquidity Windows**: `dollar_volume_per_second` identifies optimal execution windows
4. **Session Patterns**: `time_since_last_bar` reveals market open/close and lunch break patterns
5. **News Impact**: Spikes in all time metrics coincide with news releases

## Advanced Features

### Adaptive Threshold

The adaptive threshold feature automatically adjusts the bar size based on recent market activity:

```python
bars = create_dollar_volume_bars(
    tick_data,
    ticks_per_bar=100,
    adaptive=True,
    lookback_bars=20  # Use last 20 bars for adaptation
)

# Inspect threshold changes
import matplotlib.pyplot as plt
plt.plot(bars['threshold_used'])
plt.title('Adaptive Threshold Over Time')
plt.xlabel('Bar Number')
plt.ylabel('Dollar Volume Threshold')
plt.show()
```

**How it works:**
1. Starts with initial threshold (calculated from `ticks_per_bar`)
2. After each bar, calculates exponentially weighted average of recent bar sizes
3. Adjusts threshold to match recent market activity
4. Results in more stable tick counts per bar

**Use cases:**
- Markets with changing volatility
- Multi-day datasets
- Intraday patterns (open/close more active)

### Integration with Repository

```python
from binance_tick_data import BinanceDataRepository, create_dollar_volume_bars
from datetime import datetime, timedelta

# Initialize repository
repo = BinanceDataRepository()

# Get data
end_date = datetime.now()
start_date = end_date - timedelta(days=7)

tick_data = repo.get_trades(
    symbol='BTCUSDT',
    start_date=start_date,
    end_date=end_date
)

# Create bars
bars = create_dollar_volume_bars(tick_data, ticks_per_bar=100)

# Store bars back to database (optional)
repo.conn.execute("""
    CREATE TABLE IF NOT EXISTS dollar_bars_btcusdt AS
    SELECT * FROM bars
""")
```

## Best Practices

### Choosing Threshold

**Rule of thumb:**
- High-frequency strategies: 50-100 ticks per bar
- Medium-frequency: 100-500 ticks per bar
- Low-frequency: 500-1000+ ticks per bar

**By market:**
- Crypto (volatile): Lower ticks per bar (50-100)
- Crypto (stable): Higher ticks per bar (200-500)
- Equities: 100-500 ticks per bar
- Forex: 200-1000 ticks per bar

### Data Quality

Always validate your tick data before creating bars:

```python
# Check for required columns
required = ['timestamp', 'price', 'volume']
assert all(col in tick_data.columns for col in required)

# Check for missing values
assert not tick_data[['price', 'volume']].isna().any().any()

# Check for valid values
assert (tick_data['price'] > 0).all()
assert (tick_data['volume'] >= 0).all()

# Sort by timestamp
tick_data = tick_data.sort_values('timestamp')
```

### Performance Tips

**For large datasets:**
1. Use chunking for very large files
2. Consider using Polars instead of Pandas (10-50x faster)
3. Use fixed threshold instead of adaptive for speed

**Memory optimization:**
```python
# Process in chunks for huge datasets
chunk_size = 1_000_000
all_bars = []

for chunk in pd.read_csv('huge_file.csv', chunksize=chunk_size):
    bars = create_dollar_volume_bars(chunk, threshold=fixed_threshold)
    all_bars.append(bars)

final_bars = pd.concat(all_bars, ignore_index=True)
```

### Statistical Analysis

Compare dollar volume bars with time-based bars:

```python
from scipy import stats

# Create both types of bars
dollar_bars = create_dollar_volume_bars(tick_data, ticks_per_bar=100)
time_bars = tick_data.resample('1min', on='timestamp').agg({
    'price': ['first', 'max', 'min', 'last'],
    'volume': 'sum'
})

# Calculate returns
dollar_returns = dollar_bars['close'].pct_change().dropna()
time_returns = time_bars['price']['last'].pct_change().dropna()

# Test for normality
_, dollar_p = stats.jarque_bera(dollar_returns)
_, time_p = stats.jarque_bera(time_returns)

print(f"Dollar bars normality p-value: {dollar_p:.4f}")
print(f"Time bars normality p-value: {time_p:.4f}")
print(f"Dollar bars more normal: {dollar_p > time_p}")
```

## Troubleshooting

### Common Errors

**DataError: Missing required columns**
```python
# Solution: Ensure data has correct column names
tick_data = tick_data.rename(columns={
    'trade_price': 'price',
    'trade_volume': 'volume',
    'trade_time': 'timestamp'
})
```

**InsufficientDataError: DataFrame is empty**
```python
# Solution: Check data loading
if tick_data.empty:
    raise ValueError("No data loaded")
```

**DataQualityError: Data contains NaN values**
```python
# Solution: Handle missing values
tick_data = tick_data.dropna(subset=['price', 'volume'])
```

### Getting Help

- Check examples: `examples/dollar_volume_bars_example.py`
- Review notebook: `specs/dollar_volume_sampling.ipynb`
- GitHub issues: Report bugs and feature requests

## References

1. López de Prado, M. (2018). *Advances in Financial Machine Learning*. Wiley. Chapter 2: Financial Data Structures.

2. Easley, D., López de Prado, M., & O'Hara, M. (2012). "Flow Toxicity and Liquidity in a High-frequency World." *The Review of Financial Studies*, 25(5), 1457-1493.

3. Market microstructure literature on information-driven sampling

---

**Version:** 0.1.0
**Last Updated:** 2025-10-20
**Author:** Binance Tick Data Library
