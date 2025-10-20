"""
Example: Creating Dollar-Volume Bars with New System

This demonstrates:
1. Using centralized configuration from config.yaml
2. Proper error handling with actionable messages
3. Creating dollar-volume bars
4. Comparing tick data vs dollar bars
"""

from binance_tick_data import BinanceDataRepository, NoDataFoundError
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt


def main():
    print("=" * 80)
    print("Dollar-Volume Bar Example")
    print("=" * 80)

    try:
        with BinanceDataRepository() as repo:
            symbol = "BTCUSDT"
            start_time = datetime(2025, 10, 1)

            # 1. Get tick data
            print(f"\n1. Loading tick data for {symbol}...")
            ticks = repo.get_agg_trades(
                symbol=symbol,
                start_time=start_time,
                limit=50000
            )
            print(f"   ✓ Loaded {len(ticks):,} ticks")

            # Convert to proper types
            ticks['price'] = ticks['price'].astype(float)
            ticks['quantity'] = ticks['quantity'].astype(float)

            # 2. Create dollar bars
            print(f"\n2. Creating dollar-volume bars...")
            dollar_bars = repo.create_dollar_bars(
                symbol=symbol,
                start_time=start_time,
                use_polars=True  # Use Polars for speed
            )

            # Convert to pandas for display
            if hasattr(dollar_bars, 'to_pandas'):
                dollar_bars_pd = dollar_bars.to_pandas()
            else:
                dollar_bars_pd = dollar_bars

            print(f"   ✓ Created {len(dollar_bars_pd)} dollar bars")
            print(f"   ✓ Average ticks per bar: {len(ticks) / len(dollar_bars_pd):.1f}")

            # 3. Statistics
            print(f"\n3. Dollar Bar Statistics:")
            print(f"   Tick count per bar:")
            print(f"     Mean: {dollar_bars_pd['tick_count'].mean():.1f}")
            print(f"     Min:  {dollar_bars_pd['tick_count'].min()}")
            print(f"     Max:  {dollar_bars_pd['tick_count'].max()}")
            print(f"     Std:  {dollar_bars_pd['tick_count'].std():.1f}")

            print(f"\n   Dollar volume per bar:")
            print(f"     Mean: ${dollar_bars_pd['dollar_volume'].mean():,.0f}")
            print(f"     Min:  ${dollar_bars_pd['dollar_volume'].min():,.0f}")
            print(f"     Max:  ${dollar_bars_pd['dollar_volume'].max():,.0f}")

            # 4. Sample bars
            print(f"\n4. Sample Dollar Bars:")
            sample = dollar_bars_pd[['timestamp', 'open', 'high', 'low', 'close', 'volume', 'tick_count']].head(5)
            # Convert timestamps to readable format
            sample_display = sample.copy()
            sample_display['timestamp'] = pd.to_datetime(sample_display['timestamp'], unit='ms')
            print(sample_display.to_string(index=False))

            # 5. Visualization
            print(f"\n5. Creating visualizations...")

            fig, axes = plt.subplots(3, 1, figsize=(14, 10))

            # Plot 1: Tick count distribution
            axes[0].hist(dollar_bars_pd['tick_count'], bins=30, edgecolor='black', alpha=0.7)
            axes[0].set_title('Tick Count Distribution per Dollar Bar', fontsize=12, fontweight='bold')
            axes[0].set_xlabel('Ticks per Bar')
            axes[0].set_ylabel('Frequency')
            axes[0].axvline(dollar_bars_pd['tick_count'].mean(), color='red', linestyle='--',
                           label=f"Mean: {dollar_bars_pd['tick_count'].mean():.1f}")
            axes[0].legend()
            axes[0].grid(True, alpha=0.3)

            # Plot 2: Dollar volume distribution
            axes[1].hist(dollar_bars_pd['dollar_volume'], bins=30, edgecolor='black', alpha=0.7, color='green')
            axes[1].set_title('Dollar Volume Distribution per Bar', fontsize=12, fontweight='bold')
            axes[1].set_xlabel('Dollar Volume')
            axes[1].set_ylabel('Frequency')
            axes[1].axvline(dollar_bars_pd['dollar_volume'].mean(), color='red', linestyle='--',
                           label=f"Mean: ${dollar_bars_pd['dollar_volume'].mean():,.0f}")
            axes[1].legend()
            axes[1].grid(True, alpha=0.3)

            # Plot 3: Price bars (OHLC simplified)
            x = range(min(50, len(dollar_bars_pd)))
            bars_to_plot = dollar_bars_pd.head(50)

            for i, row in bars_to_plot.iterrows():
                color = 'green' if row['close'] > row['open'] else 'red'
                axes[2].plot([i, i], [row['low'], row['high']], color='black', linewidth=1)
                axes[2].plot([i, i], [row['open'], row['close']], color=color, linewidth=4, alpha=0.8)

            axes[2].set_title(f'Dollar Bars - Price (First 50 bars)', fontsize=12, fontweight='bold')
            axes[2].set_xlabel('Bar Number')
            axes[2].set_ylabel('Price (USDT)')
            axes[2].grid(True, alpha=0.3)

            plt.tight_layout()
            plt.savefig('dollar_bars_analysis.png', dpi=150, bbox_inches='tight')
            print(f"   ✓ Saved: dollar_bars_analysis.png")
            plt.close()

            # 6. Comparison with regular time bars
            print(f"\n6. Comparison with Time-Based Bars:")

            # Get 1-minute OHLCV
            time_bars = repo.get_ohlcv(
                symbol=symbol,
                interval="1m",
                start_time=start_time,
                end_time=datetime.fromtimestamp(ticks['timestamp'].max() / 1000)
            )

            print(f"   Dollar bars:  {len(dollar_bars_pd)} bars")
            print(f"   Time bars:    {len(time_bars)} bars (1-minute)")
            print(f"   Ratio:        {len(time_bars) / len(dollar_bars_pd):.2f}x more time bars")

            # Compare return statistics
            dollar_bars_pd['returns'] = dollar_bars_pd['close'].pct_change()
            time_bars['returns'] = time_bars['close'].pct_change()

            print(f"\n   Return Statistics:")
            print(f"                    Dollar Bars    Time Bars")
            print(f"   Mean:            {dollar_bars_pd['returns'].mean():.6f}    {time_bars['returns'].mean():.6f}")
            print(f"   Std Dev:         {dollar_bars_pd['returns'].std():.6f}    {time_bars['returns'].std():.6f}")
            print(f"   Skewness:        {dollar_bars_pd['returns'].skew():.4f}       {time_bars['returns'].skew():.4f}")
            print(f"   Kurtosis:        {dollar_bars_pd['returns'].kurtosis():.4f}       {time_bars['returns'].kurtosis():.4f}")

            print(f"\n   💡 Dollar bars typically have:")
            print(f"      • More uniform information content per bar")
            print(f"      • Better statistical properties (lower kurtosis)")
            print(f"      • Reduced serial correlation")

            # 7. Export
            print(f"\n7. Exporting data...")
            dollar_bars_pd.to_csv('dollar_bars.csv', index=False)
            print(f"   ✓ Saved: dollar_bars.csv")

            print(f"\n{'='*80}")
            print("✅ Complete!")
            print("=" * 80)
            print(f"\nGenerated files:")
            print(f"  • dollar_bars_analysis.png")
            print(f"  • dollar_bars.csv")

    except NoDataFoundError as e:
        print(f"\n{e}")
        print("\n💡 To fix this:")
        print("   1. Check your data range in the database")
        print("   2. Run data ingestion first if needed")
        print("   3. Adjust the start_time in this script")

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
