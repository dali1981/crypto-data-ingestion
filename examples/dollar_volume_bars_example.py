"""
Dollar Volume Bars Example

This script demonstrates how to use the dollar volume sampling feature
to create information-driven bars from tick data.

Examples:
    # Run basic example:
    $ uv run python examples/dollar_volume_bars_example.py

    # Run with custom parameters:
    $ uv run python examples/dollar_volume_bars_example.py --symbol BTCUSDT --ticks-per-bar 200
"""

import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from binance_tick_data import (
    BinanceDataRepository,
    create_dollar_volume_bars,
    DollarVolumeSampler,
    calculate_optimal_threshold,
)

# Set style for plots
sns.set_style('whitegrid')
plt.rcParams['figure.figsize'] = (14, 8)


def generate_sample_tick_data(n_ticks: int = 10000, seed: int = 42) -> pd.DataFrame:
    """
    Generate synthetic tick data for demonstration.

    Args:
        n_ticks: Number of ticks to generate
        seed: Random seed for reproducibility

    Returns:
        DataFrame with tick data
    """
    np.random.seed(seed)

    # Generate timestamps
    start_time = datetime(2024, 1, 1, 9, 0, 0)
    time_deltas = np.random.exponential(1, n_ticks).cumsum()
    timestamps = [start_time + timedelta(seconds=td) for td in time_deltas]

    # Generate prices (random walk)
    initial_price = 45000.0  # BTC-like price
    returns = np.random.normal(0, 0.001, n_ticks)
    price_mult = np.exp(returns.cumsum())
    prices = initial_price * price_mult

    # Generate volumes (log-normal)
    volumes = np.random.lognormal(8, 1.5, n_ticks)
    volumes = np.clip(volumes, 0.001, 100).astype(float)

    return pd.DataFrame({
        'timestamp': timestamps,
        'price': prices,
        'volume': volumes
    })


def example_1_basic_usage():
    """Example 1: Basic dollar volume bars creation."""
    print("\n" + "="*80)
    print("EXAMPLE 1: Basic Dollar Volume Bars")
    print("="*80)

    # Generate sample data
    tick_data = generate_sample_tick_data(n_ticks=10000)
    print(f"\nGenerated {len(tick_data):,} ticks")
    print(f"Date range: {tick_data['timestamp'].min()} to {tick_data['timestamp'].max()}")
    print(f"Price range: ${tick_data['price'].min():.2f} to ${tick_data['price'].max():.2f}")

    # Create dollar volume bars with auto-calculated threshold
    print("\n--- Creating dollar volume bars (auto threshold) ---")
    bars = create_dollar_volume_bars(tick_data, ticks_per_bar=100)

    print(f"\nCreated {len(bars)} bars")
    print(f"Average ticks per bar: {bars['tick_count'].mean():.1f}")
    print(f"Average dollar volume per bar: ${bars['dollar_volume'].mean():,.2f}")

    print("\nFirst 5 bars:")
    print(bars[['timestamp', 'open', 'high', 'low', 'close', 'volume', 'tick_count']].head())

    return tick_data, bars


def example_2_fixed_threshold():
    """Example 2: Using a fixed dollar volume threshold."""
    print("\n" + "="*80)
    print("EXAMPLE 2: Fixed Dollar Volume Threshold")
    print("="*80)

    tick_data = generate_sample_tick_data(n_ticks=10000)

    # Create bars with specific threshold
    threshold = 50_000_000  # $50M per bar
    print(f"\nUsing fixed threshold: ${threshold:,}")

    bars = create_dollar_volume_bars(tick_data, threshold=threshold)

    print(f"\nCreated {len(bars)} bars")
    print(f"Average ticks per bar: {bars['tick_count'].mean():.1f} ± {bars['tick_count'].std():.1f}")
    print(f"Min ticks per bar: {bars['tick_count'].min()}")
    print(f"Max ticks per bar: {bars['tick_count'].max()}")

    return tick_data, bars


def example_3_adaptive_threshold():
    """Example 3: Adaptive threshold that adjusts to market activity."""
    print("\n" + "="*80)
    print("EXAMPLE 3: Adaptive Dollar Volume Threshold")
    print("="*80)

    tick_data = generate_sample_tick_data(n_ticks=10000)

    # Create bars with adaptive threshold
    print("\nCreating bars with adaptive threshold...")
    bars = create_dollar_volume_bars(
        tick_data,
        ticks_per_bar=100,
        adaptive=True,
        lookback_bars=20
    )

    print(f"\nCreated {len(bars)} adaptive bars")
    print(f"Threshold range: ${bars['threshold_used'].min():,.2f} to ${bars['threshold_used'].max():,.2f}")
    print(f"Average threshold: ${bars['threshold_used'].mean():,.2f}")

    # Plot threshold adaptation
    plt.figure(figsize=(12, 4))
    plt.plot(bars['threshold_used'].values)
    plt.title('Adaptive Threshold Over Time')
    plt.xlabel('Bar Number')
    plt.ylabel('Dollar Volume Threshold ($)')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig('analysis_output/adaptive_threshold.png', dpi=150, bbox_inches='tight')
    print("\nSaved: analysis_output/adaptive_threshold.png")
    plt.close()

    return tick_data, bars


def example_4_statistical_analysis():
    """Example 4: Analyzing statistical properties of dollar volume bars."""
    print("\n" + "="*80)
    print("EXAMPLE 4: Statistical Analysis")
    print("="*80)

    tick_data = generate_sample_tick_data(n_ticks=10000)

    # Create bars
    sampler = DollarVolumeSampler(ticks_per_bar=100)
    bars = sampler.create_bars(tick_data)

    # Get statistics
    stats = sampler.get_bar_statistics(bars)

    print("\nBar Statistics:")
    print(f"  Number of bars: {stats['n_bars']}")
    print(f"  Avg ticks per bar: {stats['avg_ticks_per_bar']:.1f} ± {stats['std_ticks_per_bar']:.1f}")
    print(f"  Avg volume per bar: {stats['avg_volume']:.2f}")
    print(f"  Avg dollar volume: ${stats['avg_dollar_volume']:,.2f}")

    print("\nReturn Statistics:")
    print(f"  Mean return: {stats['returns_mean']:.4%}")
    print(f"  Std deviation: {stats['returns_std']:.4%}")
    print(f"  Skewness: {stats['returns_skew']:.3f}")
    print(f"  Kurtosis: {stats['returns_kurtosis']:.3f}")

    # Calculate returns for visualization
    bars['returns'] = bars['close'].pct_change()

    # Create statistical plots
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # 1. Tick count distribution
    axes[0, 0].hist(bars['tick_count'], bins=30, edgecolor='black', alpha=0.7, color='skyblue')
    axes[0, 0].axvline(stats['avg_ticks_per_bar'], color='red', linestyle='--',
                      label=f"Mean: {stats['avg_ticks_per_bar']:.1f}")
    axes[0, 0].set_title('Tick Count Distribution')
    axes[0, 0].set_xlabel('Ticks per Bar')
    axes[0, 0].set_ylabel('Frequency')
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)

    # 2. Returns distribution
    axes[0, 1].hist(bars['returns'].dropna(), bins=30, edgecolor='black', alpha=0.7, color='lightcoral')
    axes[0, 1].axvline(0, color='red', linestyle='--')
    axes[0, 1].set_title('Returns Distribution')
    axes[0, 1].set_xlabel('Returns')
    axes[0, 1].set_ylabel('Frequency')
    axes[0, 1].grid(True, alpha=0.3)

    # 3. Price over time
    axes[1, 0].plot(bars['close'], linewidth=0.8, color='green')
    axes[1, 0].set_title('Close Price Over Bars')
    axes[1, 0].set_xlabel('Bar Number')
    axes[1, 0].set_ylabel('Price ($)')
    axes[1, 0].grid(True, alpha=0.3)

    # 4. Volume per bar
    axes[1, 1].bar(range(len(bars)), bars['dollar_volume'], alpha=0.7, color='orange')
    axes[1, 1].set_title('Dollar Volume per Bar')
    axes[1, 1].set_xlabel('Bar Number')
    axes[1, 1].set_ylabel('Dollar Volume ($)')
    axes[1, 1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('analysis_output/dollar_bars_statistics.png', dpi=150, bbox_inches='tight')
    print("\nSaved: analysis_output/dollar_bars_statistics.png")
    plt.close()

    return bars, stats


def example_5_optimal_threshold():
    """Example 5: Calculate optimal threshold for target number of bars."""
    print("\n" + "="*80)
    print("EXAMPLE 5: Optimal Threshold Calculation")
    print("="*80)

    tick_data = generate_sample_tick_data(n_ticks=10000)

    # Calculate optimal threshold for 500 bars
    target_bars = 500
    threshold = calculate_optimal_threshold(tick_data, target_bars=target_bars)

    print(f"\nTarget: {target_bars} bars from {len(tick_data)} ticks")
    print(f"Calculated optimal threshold: ${threshold:,.2f}")

    # Create bars with this threshold
    bars = create_dollar_volume_bars(tick_data, threshold=threshold)

    print(f"\nResult: Created {len(bars)} bars")
    print(f"Difference from target: {len(bars) - target_bars} bars ({((len(bars) - target_bars) / target_bars * 100):.1f}%)")

    return bars


def example_6_real_data_integration():
    """Example 6: Using dollar volume bars with real Binance data."""
    print("\n" + "="*80)
    print("EXAMPLE 6: Real Data Integration")
    print("="*80)

    try:
        # Try to load real data from repository
        repo = BinanceDataRepository(db_path="binance_pipeline.duckdb", read_only=True)

        # Get recent tick data
        end_date = datetime.now()
        start_date = end_date - timedelta(hours=1)

        print(f"\nFetching tick data from {start_date} to {end_date}...")
        tick_data = repo.get_trades(
            symbol='BTCUSDT',
            start_date=start_date,
            end_date=end_date
        )

        if tick_data.empty:
            print("No data found in database. Using synthetic data instead.")
            tick_data = generate_sample_tick_data(n_ticks=10000)
        else:
            print(f"Loaded {len(tick_data):,} trades from database")

            # Rename columns to match expected format
            if 'p' in tick_data.columns:
                tick_data = tick_data.rename(columns={'p': 'price', 'q': 'volume', 'T': 'timestamp'})

    except Exception as e:
        print(f"Could not load real data ({e}). Using synthetic data instead.")
        tick_data = generate_sample_tick_data(n_ticks=10000)

    # Create dollar volume bars
    print("\nCreating dollar volume bars...")
    bars = create_dollar_volume_bars(tick_data, ticks_per_bar=100)

    print(f"\nCreated {len(bars)} dollar volume bars")
    print(f"Average ticks per bar: {bars['tick_count'].mean():.1f}")

    # Save to CSV
    output_path = Path("analysis_output/dollar_bars_real_data.csv")
    output_path.parent.mkdir(exist_ok=True)
    bars.to_csv(output_path, index=False)
    print(f"\nSaved bars to: {output_path}")

    return bars


def example_7_candlestick_chart():
    """Example 7: Create candlestick chart from dollar volume bars."""
    print("\n" + "="*80)
    print("EXAMPLE 7: Candlestick Visualization")
    print("="*80)

    tick_data = generate_sample_tick_data(n_ticks=10000)
    bars = create_dollar_volume_bars(tick_data, ticks_per_bar=200)

    print(f"\nCreated {len(bars)} bars for visualization")

    # Create candlestick chart
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={'height_ratios': [3, 1]})

    # Limit to first 50 bars for clarity
    bars_to_plot = bars.head(50)

    # Candlestick chart
    for idx, row in bars_to_plot.iterrows():
        color = 'green' if row['close'] > row['open'] else 'red'

        # High-low line
        ax1.plot([idx, idx], [row['low'], row['high']], color='black', linewidth=1)

        # Open-close rectangle
        height = abs(row['close'] - row['open'])
        bottom = min(row['open'], row['close'])
        ax1.bar(idx, height, bottom=bottom, width=0.6, color=color, alpha=0.8, edgecolor='black')

    ax1.set_xlim(-1, len(bars_to_plot))
    ax1.set_xlabel('Bar Number')
    ax1.set_ylabel('Price ($)')
    ax1.set_title('Dollar Volume Bars - OHLC Candlestick Chart')
    ax1.grid(True, alpha=0.3)

    # Volume bars
    colors = ['green' if c > o else 'red' for c, o in zip(bars_to_plot['close'], bars_to_plot['open'])]
    ax2.bar(range(len(bars_to_plot)), bars_to_plot['volume'], color=colors, alpha=0.8)
    ax2.set_xlabel('Bar Number')
    ax2.set_ylabel('Volume')
    ax2.set_title('Volume per Bar')
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('analysis_output/dollar_bars_candlestick.png', dpi=150, bbox_inches='tight')
    print("\nSaved: analysis_output/dollar_bars_candlestick.png")
    plt.close()


def main():
    """Run all examples."""
    print("\n" + "="*80)
    print("DOLLAR VOLUME BARS - COMPREHENSIVE EXAMPLES")
    print("="*80)

    # Create output directory
    Path("analysis_output").mkdir(exist_ok=True)

    # Run examples
    try:
        example_1_basic_usage()
        example_2_fixed_threshold()
        example_3_adaptive_threshold()
        example_4_statistical_analysis()
        example_5_optimal_threshold()
        example_6_real_data_integration()
        example_7_candlestick_chart()

        print("\n" + "="*80)
        print("ALL EXAMPLES COMPLETED SUCCESSFULLY")
        print("="*80)
        print("\nGenerated outputs:")
        print("  - analysis_output/adaptive_threshold.png")
        print("  - analysis_output/dollar_bars_statistics.png")
        print("  - analysis_output/dollar_bars_candlestick.png")
        print("  - analysis_output/dollar_bars_real_data.csv")

    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
