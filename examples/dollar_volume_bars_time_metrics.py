"""
Dollar Volume Bars with Time Metrics Analysis

This script demonstrates the enhanced time-based metrics in dollar volume bars
and shows how they can be used for market microstructure analysis.

Run:
    uv run python examples/dollar_volume_bars_time_metrics.py
"""

import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from binance_tick_data import create_dollar_volume_bars, DollarVolumeSampler

# Set style
sns.set_style('whitegrid')
plt.rcParams['figure.figsize'] = (14, 10)


def generate_realistic_tick_data(n_ticks: int = 10000, seed: int = 42) -> pd.DataFrame:
    """
    Generate tick data with realistic trading patterns including:
    - Variable trading intensity
    - News events (bursts of activity)
    - Session patterns (open/close more active)
    """
    np.random.seed(seed)

    # Start time
    start_time = datetime(2024, 1, 1, 9, 0, 0)

    # Generate variable time intervals (realistic trading pattern)
    timestamps = []
    current_time = start_time

    for i in range(n_ticks):
        # Session patterns: more active at open/close
        hour = current_time.hour
        if hour in [9, 10, 15, 16]:  # Market open/close hours
            avg_interval = 0.5  # Faster trading
        elif hour in [12, 13]:  # Lunch hours
            avg_interval = 3.0  # Slower trading
        else:
            avg_interval = 1.0  # Normal trading

        # Add random news events (5% chance of burst)
        if np.random.random() < 0.05:
            avg_interval *= 0.1  # 10x faster during news

        # Generate interval
        interval = np.random.exponential(avg_interval)
        current_time += timedelta(seconds=interval)
        timestamps.append(current_time)

    # Generate correlated price and volume (more volume during volatile periods)
    initial_price = 45000.0
    prices = []
    volumes = []

    current_price = initial_price
    for i, ts in enumerate(timestamps):
        # Price changes
        volatility = 0.001

        # Increase volatility during active hours
        hour = ts.hour
        if hour in [9, 10, 15, 16]:
            volatility *= 2

        # Random walk
        return_val = np.random.normal(0, volatility)
        current_price *= (1 + return_val)
        prices.append(current_price)

        # Volume correlated with volatility
        base_volume = np.random.lognormal(5, 1.5)
        if abs(return_val) > 0.002:  # High volatility
            base_volume *= 5
        volumes.append(base_volume)

    return pd.DataFrame({
        'timestamp': timestamps,
        'price': prices,
        'volume': volumes
    })


def analyze_time_metrics(bars: pd.DataFrame):
    """Comprehensive analysis of time-based metrics."""

    print("\n" + "="*80)
    print("TIME METRICS ANALYSIS")
    print("="*80)

    # Basic statistics
    print("\n--- Bar Duration Statistics ---")
    print(f"Average duration: {bars['duration_seconds'].mean():.1f} seconds")
    print(f"Median duration: {bars['duration_seconds'].median():.1f} seconds")
    print(f"Min duration: {bars['duration_seconds'].min():.1f} seconds")
    print(f"Max duration: {bars['duration_seconds'].max():.1f} seconds")

    print("\n--- Trading Intensity Statistics ---")
    print(f"Average tick rate: {bars['ticks_per_second'].mean():.2f} ticks/second")
    print(f"Peak tick rate: {bars['ticks_per_second'].max():.2f} ticks/second")
    print(f"Minimum tick rate: {bars['ticks_per_second'].min():.2f} ticks/second")

    print("\n--- Dollar Volume Velocity ---")
    print(f"Average $/second: ${bars['dollar_volume_per_second'].mean():,.0f}")
    print(f"Peak $/second: ${bars['dollar_volume_per_second'].max():,.0f}")

    print("\n--- Inter-bar Gaps ---")
    gaps = bars['time_since_last_bar'].dropna()
    print(f"Average gap: {gaps.mean():.1f} seconds")
    print(f"Largest gap: {gaps.max():.1f} seconds")
    print(f"Number of gaps > 60s: {(gaps > 60).sum()}")


def plot_time_metrics(bars: pd.DataFrame):
    """Create comprehensive visualizations of time metrics."""

    fig, axes = plt.subplots(4, 2, figsize=(16, 14))

    # 1. Price with duration as color
    scatter = axes[0, 0].scatter(range(len(bars)), bars['close'],
                                c=bars['duration_seconds'], cmap='coolwarm',
                                alpha=0.6, s=20)
    axes[0, 0].set_title('Price Colored by Bar Duration')
    axes[0, 0].set_xlabel('Bar Number')
    axes[0, 0].set_ylabel('Price ($)')
    plt.colorbar(scatter, ax=axes[0, 0], label='Duration (s)')

    # 2. Trading intensity over time
    axes[0, 1].plot(bars['ticks_per_second'], color='green', alpha=0.7, linewidth=0.8)
    axes[0, 1].axhline(bars['ticks_per_second'].mean(), color='red',
                      linestyle='--', alpha=0.5,
                      label=f"Mean: {bars['ticks_per_second'].mean():.2f}")
    axes[0, 1].set_title('Trading Intensity (Ticks per Second)')
    axes[0, 1].set_xlabel('Bar Number')
    axes[0, 1].set_ylabel('Ticks/Second')
    axes[0, 1].legend()
    axes[0, 1].grid(True, alpha=0.3)

    # 3. Dollar volume velocity
    axes[1, 0].plot(bars['dollar_volume_per_second'], color='orange', alpha=0.7, linewidth=0.8)
    axes[1, 0].set_title('Dollar Volume Velocity')
    axes[1, 0].set_xlabel('Bar Number')
    axes[1, 0].set_ylabel('$/Second')
    axes[1, 0].set_yscale('log')
    axes[1, 0].grid(True, alpha=0.3)

    # 4. Duration distribution
    axes[1, 1].hist(bars['duration_seconds'], bins=30, edgecolor='black', alpha=0.7, color='skyblue')
    axes[1, 1].axvline(bars['duration_seconds'].median(), color='red', linestyle='--',
                      label=f"Median: {bars['duration_seconds'].median():.1f}s")
    axes[1, 1].set_title('Bar Duration Distribution')
    axes[1, 1].set_xlabel('Duration (seconds)')
    axes[1, 1].set_ylabel('Frequency')
    axes[1, 1].legend()
    axes[1, 1].grid(True, alpha=0.3)

    # 5. Inter-bar gaps
    gaps = bars['time_since_last_bar'].dropna()
    axes[2, 0].plot(gaps, color='purple', alpha=0.7, linewidth=0.8)
    axes[2, 0].set_title('Time Between Bars (Trading Gaps)')
    axes[2, 0].set_xlabel('Bar Number')
    axes[2, 0].set_ylabel('Gap (seconds)')
    axes[2, 0].grid(True, alpha=0.3)

    # 6. Intensity vs Price Change
    axes[2, 1].scatter(bars['ticks_per_second'], bars['price_change'],
                      alpha=0.5, s=20, color='teal')
    axes[2, 1].set_title('Trading Intensity vs Price Change')
    axes[2, 1].set_xlabel('Ticks per Second')
    axes[2, 1].set_ylabel('Price Change ($)')
    axes[2, 1].axhline(0, color='red', linestyle='-', alpha=0.3)
    axes[2, 1].grid(True, alpha=0.3)

    # 7. Correlation matrix of time metrics
    time_cols = ['duration_seconds', 'ticks_per_second', 'dollar_volume_per_second',
                'tick_count', 'price_change', 'volume']
    corr_matrix = bars[time_cols].corr()
    sns.heatmap(corr_matrix, annot=True, fmt='.2f', cmap='coolwarm',
                center=0, ax=axes[3, 0], cbar_kws={'label': 'Correlation'})
    axes[3, 0].set_title('Time Metrics Correlation Matrix')

    # 8. Rolling intensity with price
    ax1 = axes[3, 1]
    ax2 = ax1.twinx()

    ax1.plot(bars.index, bars['close'], color='blue', alpha=0.7, label='Price')
    ax2.plot(bars.index, bars['ticks_per_second'].rolling(10).mean(),
            color='red', alpha=0.7, label='Avg Intensity (10-bar)')

    ax1.set_xlabel('Bar Number')
    ax1.set_ylabel('Price ($)', color='blue')
    ax2.set_ylabel('Ticks/Second (10-bar avg)', color='red')
    ax1.tick_params(axis='y', labelcolor='blue')
    ax2.tick_params(axis='y', labelcolor='red')
    ax1.set_title('Price vs Rolling Trading Intensity')
    ax1.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('analysis_output/dollar_bars_time_metrics.png', dpi=150, bbox_inches='tight')
    print("\nSaved: analysis_output/dollar_bars_time_metrics.png")
    plt.show()


def detect_market_regimes(bars: pd.DataFrame):
    """Detect and analyze different market regimes using time metrics."""

    print("\n" + "="*80)
    print("MARKET REGIME DETECTION")
    print("="*80)

    # Calculate regime indicators
    bars = bars.copy()

    # Intensity-based regimes
    intensity_75 = bars['ticks_per_second'].quantile(0.75)
    intensity_25 = bars['ticks_per_second'].quantile(0.25)

    bars['regime'] = 'normal'
    bars.loc[bars['ticks_per_second'] > intensity_75, 'regime'] = 'high_activity'
    bars.loc[bars['ticks_per_second'] < intensity_25, 'regime'] = 'low_activity'

    # Analyze regimes
    regime_stats = bars.groupby('regime').agg({
        'price_change': ['mean', 'std'],
        'duration_seconds': 'mean',
        'dollar_volume': 'mean',
        'ticks_per_second': 'mean',
        'volume': 'mean'
    }).round(2)

    print("\nRegime Statistics:")
    print(regime_stats)

    # Count regime occurrences
    regime_counts = bars['regime'].value_counts()
    print(f"\nRegime Distribution:")
    for regime, count in regime_counts.items():
        pct = count / len(bars) * 100
        print(f"  {regime}: {count} bars ({pct:.1f}%)")

    # Identify potential news events (extreme intensity)
    news_threshold = bars['ticks_per_second'].quantile(0.95)
    potential_news = bars[bars['ticks_per_second'] > news_threshold]

    print(f"\nPotential News Events: {len(potential_news)} bars")
    print(f"Average |price change| during news: ${abs(potential_news['price_change']).mean():.2f}")
    print(f"Average volume during news: {potential_news['volume'].mean():.0f}")

    return bars


def analyze_liquidity_patterns(bars: pd.DataFrame):
    """Analyze liquidity patterns using time metrics."""

    print("\n" + "="*80)
    print("LIQUIDITY ANALYSIS")
    print("="*80)

    # Calculate liquidity metrics
    bars = bars.copy()

    # Rolling average for comparison
    window = 20
    bars['avg_intensity'] = bars['ticks_per_second'].rolling(window, min_periods=1).mean()
    bars['avg_dollar_velocity'] = bars['dollar_volume_per_second'].rolling(window, min_periods=1).mean()

    # Liquidity score
    bars['liquidity_score'] = (
        bars['dollar_volume_per_second'] / bars['avg_dollar_velocity'].replace(0, 1)
    )

    # Identify liquidity conditions
    low_liquidity = bars[bars['liquidity_score'] < 0.5]
    high_liquidity = bars[bars['liquidity_score'] > 1.5]

    print(f"\nLiquidity Conditions:")
    print(f"  Low liquidity periods: {len(low_liquidity)} bars ({len(low_liquidity)/len(bars)*100:.1f}%)")
    print(f"  High liquidity periods: {len(high_liquidity)} bars ({len(high_liquidity)/len(bars)*100:.1f}%)")

    # Trading gaps analysis
    gaps = bars['time_since_last_bar'].dropna()
    large_gaps = bars[bars['time_since_last_bar'] > gaps.quantile(0.95)]

    print(f"\nTrading Gaps:")
    print(f"  Total gaps > 95th percentile: {len(large_gaps)}")
    print(f"  Average large gap: {large_gaps['time_since_last_bar'].mean():.1f} seconds")
    print(f"  Maximum gap: {gaps.max():.1f} seconds")

    # Analyze price impact during different liquidity conditions
    print(f"\nPrice Impact Analysis:")
    print(f"  Avg |price change| in low liquidity: ${abs(low_liquidity['price_change']).mean():.2f}")
    print(f"  Avg |price change| in high liquidity: ${abs(high_liquidity['price_change']).mean():.2f}")
    print(f"  Volatility in low liquidity: {low_liquidity['price_change'].std():.4f}")
    print(f"  Volatility in high liquidity: {high_liquidity['price_change'].std():.4f}")

    return bars


def main():
    """Run comprehensive time metrics analysis."""

    print("\n" + "="*80)
    print("DOLLAR VOLUME BARS - TIME METRICS ANALYSIS")
    print("="*80)

    # Create output directory
    Path("analysis_output").mkdir(exist_ok=True)

    # Generate realistic tick data
    print("\nGenerating realistic tick data with variable trading patterns...")
    tick_data = generate_realistic_tick_data(n_ticks=10000)

    print(f"Generated {len(tick_data):,} ticks")
    print(f"Time range: {tick_data['timestamp'].min()} to {tick_data['timestamp'].max()}")
    print(f"Total duration: {(tick_data['timestamp'].max() - tick_data['timestamp'].min()).total_seconds()/3600:.1f} hours")

    # Create dollar volume bars with time metrics
    print("\nCreating dollar volume bars with time metrics...")
    bars = create_dollar_volume_bars(tick_data, ticks_per_bar=100)

    print(f"\nCreated {len(bars)} bars from {len(tick_data):,} ticks")
    print(f"Columns: {list(bars.columns)}")

    # Perform analyses
    analyze_time_metrics(bars)
    plot_time_metrics(bars)
    bars_with_regimes = detect_market_regimes(bars)
    bars_with_liquidity = analyze_liquidity_patterns(bars)

    # Save enhanced bars to CSV
    output_file = Path("analysis_output/dollar_bars_with_time_metrics.csv")
    bars_with_liquidity.to_csv(output_file, index=False)
    print(f"\nSaved enhanced bars to: {output_file}")

    # Print sample of time metrics
    print("\n" + "="*80)
    print("SAMPLE TIME METRICS (First 5 bars)")
    print("="*80)

    time_columns = ['timestamp', 'timestamp_close', 'close', 'tick_count',
                   'duration_seconds', 'ticks_per_second', 'dollar_volume_per_second',
                   'time_since_last_bar']

    print(bars[time_columns].head().to_string(index=False))

    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)
    print("\nKey Insights:")
    print("1. Bar duration inversely correlates with market activity")
    print("2. High tick rates often precede significant price movements")
    print("3. Dollar volume velocity helps identify optimal execution windows")
    print("4. Inter-bar gaps reveal market regime transitions")
    print("5. Time metrics enhance traditional OHLCV analysis significantly")

    return bars


if __name__ == "__main__":
    bars = main()