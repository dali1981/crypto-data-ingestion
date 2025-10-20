"""
Binance Tick Data Analysis with Fractional Differencing

This script demonstrates:
1. Loading tick data from DuckDB
2. Visualizing price data
3. Computing fractional differences (d=0.2, 0.3, 0.4)
4. Plotting fractionally differenced series
5. Analyzing distributions
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

from binance_tick_data.repository import BinanceDataRepository

plt.style.use('seaborn-v0_8-darkgrid')


def get_weights(d, size):
    """Compute weights for fractional differencing."""
    w = [1.0]
    for k in range(1, size):
        w.append(-w[-1] * (d - k + 1) / k)
    return np.array(w[::-1])


def frac_diff(series, d, threshold=1e-5):
    """
    Compute fractionally differenced series.
    
    Args:
        series: pandas Series
        d: differencing order (0 < d < 1)
        threshold: minimum weight to include
    
    Returns:
        Fractionally differenced series
    """
    weights = get_weights(d, len(series))
    weights = weights[np.abs(weights) > threshold]
    result = np.convolve(series.values, weights, mode='valid')
    index = series.index[-len(result):]
    return pd.Series(result, index=index)


def main():
    print("=" * 80)
    print("Binance Tick Data Analysis with Fractional Differencing")
    print("=" * 80)
    
    # 1. Load data
    print("\n1. Loading data from database...")
    with BinanceDataRepository() as repo:
        df = repo.get_agg_trades(
            symbol="BTCUSDT",
            start_time=datetime(2025, 10, 1)
        )
    
    print(f"   Loaded {len(df):,} trades")
    
    # 2. Prepare data
    print("\n2. Preparing data...")
    df['price'] = df['price'].astype(float)
    df['quantity'] = df['quantity'].astype(float)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.sort_values('datetime').reset_index(drop=True)
    
    # Keep only unique timestamps for the index
    df = df.drop_duplicates(subset=['datetime'], keep='first')
    
    price_series = df.set_index('datetime')['price']
    print(f"   Price range: ${price_series.min():,.2f} - ${price_series.max():,.2f}")
    print(f"   Unique timestamps: {len(price_series)}")
    
    # 3. Compute returns
    returns = price_series.pct_change().dropna()
    
    # 4. Compute fractional differences
    print("\n3. Computing fractional differences...")
    d_values = [0.2, 0.3, 0.4]
    frac_diffs = {}
    
    for d in d_values:
        print(f"   Computing d={d}...")
        frac_diffs[d] = frac_diff(price_series, d)
        print(f"      Mean: {frac_diffs[d].mean():.2f}, Std: {frac_diffs[d].std():.2f}")
    
    first_diff = price_series.diff().dropna()
    
    # 5. Plot price and returns
    print("\n4. Creating visualizations...")
    print("   Plotting price and returns...")
    fig, axes = plt.subplots(2, 1, figsize=(14, 8))
    
    axes[0].plot(price_series.index, price_series.values, linewidth=0.5, alpha=0.7)
    axes[0].set_title('BTC/USDT Price', fontsize=14, fontweight='bold')
    axes[0].set_ylabel('Price (USDT)', fontsize=12)
    axes[0].grid(True, alpha=0.3)
    
    axes[1].plot(returns.index, returns.values, linewidth=0.5, alpha=0.7, color='orange')
    axes[1].set_title('Price Returns', fontsize=14, fontweight='bold')
    axes[1].set_ylabel('Returns', fontsize=12)
    axes[1].set_xlabel('Time', fontsize=12)
    axes[1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('btc_price_returns.png', dpi=150, bbox_inches='tight')
    print("      Saved: btc_price_returns.png")
    plt.close()
    
    # 6. Plot fractionally differenced series
    print("   Plotting fractionally differenced series...")
    fig, axes = plt.subplots(4, 1, figsize=(14, 12))
    colors = ['green', 'blue', 'purple']
    
    axes[0].plot(price_series.index, price_series.values, linewidth=0.5, alpha=0.7, color='black')
    axes[0].set_title('Original Price (d=0)', fontsize=12, fontweight='bold')
    axes[0].set_ylabel('Price', fontsize=10)
    axes[0].grid(True, alpha=0.3)
    
    for i, d in enumerate(d_values):
        series = frac_diffs[d]
        axes[i+1].plot(series.index, series.values, linewidth=0.5, alpha=0.7, color=colors[i])
        axes[i+1].set_title(f'Fractional Difference (d={d})', fontsize=12, fontweight='bold')
        axes[i+1].set_ylabel('Value', fontsize=10)
        axes[i+1].axhline(y=0, color='red', linestyle='--', alpha=0.3, linewidth=1)
        axes[i+1].grid(True, alpha=0.3)
    
    axes[-1].set_xlabel('Time', fontsize=10)
    plt.tight_layout()
    plt.savefig('btc_fracdiff_series.png', dpi=150, bbox_inches='tight')
    print("      Saved: btc_fracdiff_series.png")
    plt.close()
    
    # 7. Plot distributions
    print("   Plotting distributions...")
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes = axes.flatten()
    
    # Returns distribution
    axes[0].hist(returns.values, bins=100, alpha=0.7, color='black', edgecolor='black')
    axes[0].set_title('Returns Distribution', fontsize=12, fontweight='bold')
    axes[0].set_xlabel('Returns', fontsize=10)
    axes[0].set_ylabel('Frequency', fontsize=10)
    axes[0].axvline(x=0, color='red', linestyle='--', alpha=0.5)
    axes[0].axvline(x=returns.mean(), color='green', linestyle='--', alpha=0.5, 
                    label=f'Mean={returns.mean():.6f}')
    axes[0].legend()
    
    # Fractional differences distributions
    for i, d in enumerate(d_values):
        series = frac_diffs[d]
        axes[i+1].hist(series.values, bins=100, alpha=0.7, color=colors[i], edgecolor=colors[i])
        axes[i+1].set_title(f'Frac Diff Distribution (d={d})', fontsize=12, fontweight='bold')
        axes[i+1].set_xlabel('Value', fontsize=10)
        axes[i+1].set_ylabel('Frequency', fontsize=10)
        axes[i+1].axvline(x=0, color='red', linestyle='--', alpha=0.5)
        axes[i+1].axvline(x=series.mean(), color='green', linestyle='--', alpha=0.5, 
                         label=f'Mean={series.mean():.2f}')
        axes[i+1].legend()
    
    plt.tight_layout()
    plt.savefig('btc_distributions.png', dpi=150, bbox_inches='tight')
    print("      Saved: btc_distributions.png")
    plt.close()
    
    # 8. Q-Q plots
    print("   Plotting Q-Q plots...")
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    axes = axes.flatten()
    
    # Returns Q-Q plot
    stats.probplot(returns.values, dist="norm", plot=axes[0])
    axes[0].set_title('Returns Q-Q Plot', fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3)
    
    # Fractional differences Q-Q plots
    for i, d in enumerate(d_values):
        series = frac_diffs[d]
        stats.probplot(series.values, dist="norm", plot=axes[i+1])
        axes[i+1].set_title(f'Frac Diff Q-Q Plot (d={d})', fontsize=12, fontweight='bold')
        axes[i+1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('btc_qq_plots.png', dpi=150, bbox_inches='tight')
    print("      Saved: btc_qq_plots.png")
    plt.close()
    
    # 9. Summary statistics
    print("\n5. Summary Statistics:")
    print("=" * 80)
    summary_data = []
    
    summary_data.append({
        'd': 0.0,
        'Type': 'Returns',
        'Mean': returns.mean(),
        'Std': returns.std(),
        'Skew': returns.skew(),
        'Kurt': returns.kurt()
    })
    
    for d in d_values:
        series = frac_diffs[d]
        summary_data.append({
            'd': d,
            'Type': f'Frac Diff (d={d})',
            'Mean': series.mean(),
            'Std': series.std(),
            'Skew': series.skew(),
            'Kurt': series.kurt()
        })
    
    summary_df = pd.DataFrame(summary_data)
    print(summary_df.to_string(index=False))
    
    # 10. Export data (concat aligned series)
    print("\n6. Exporting data...")
    
    # Create a combined dataframe
    export_df = pd.concat([
        price_series.rename('price'),
        returns.rename('returns'),
        frac_diffs[0.2].rename('frac_diff_0.2'),
        frac_diffs[0.3].rename('frac_diff_0.3'),
        frac_diffs[0.4].rename('frac_diff_0.4')
    ], axis=1)
    
    output_file = 'btc_fracdiff_analysis.csv'
    export_df.to_csv(output_file)
    print(f"   Saved: {output_file}")
    print(f"   Shape: {export_df.shape}")
    
    print("\n" + "=" * 80)
    print("Analysis Complete!")
    print("=" * 80)
    print("\nGenerated files:")
    print("  - btc_price_returns.png")
    print("  - btc_fracdiff_series.png")
    print("  - btc_distributions.png")
    print("  - btc_qq_plots.png")
    print("  - btc_fracdiff_analysis.csv")


if __name__ == "__main__":
    main()
