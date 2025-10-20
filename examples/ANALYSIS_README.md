# Binance Tick Data Analysis with Fractional Differencing

## Overview

This analysis demonstrates how to load Binance tick data and compute fractional differences to make the price series more stationary while preserving memory.

## Files

### Scripts
- **`data_analysis.py`** - Python script that performs the full analysis
- **`data_analysis.ipynb`** - Jupyter notebook version (run from project root)

### Generated Outputs
- **`btc_price_returns.png`** - Price and returns time series
- **`btc_fracdiff_series.png`** - Fractionally differenced series for d=0.2, 0.3, 0.4
- **`btc_distributions.png`** - Histogram distributions with mean lines
- **`btc_qq_plots.png`** - Q-Q plots to check normality
- **`btc_fracdiff_analysis.csv`** - Exported data with all computed series

## Running the Analysis

### Python Script (Recommended)
```bash
uv run python examples/data_analysis.py
```

### Jupyter Notebook
```bash
# Start from project root
jupyter notebook examples/data_analysis.ipynb
```

## What is Fractional Differencing?

Fractional differencing is a technique to make time series stationary while preserving memory:

- **d=0**: Original series (non-stationary, full memory)
- **0 < d < 1**: Fractionally differenced (balance between stationarity and memory)
- **d=1**: First difference (stationary but loses all memory)

### Why Use Fractional Differencing?

1. **Machine Learning**: ML models often require stationary features
2. **Memory Preservation**: Unlike first differencing (d=1), fractional differencing preserves some of the long-term dependencies
3. **Stationarity**: Helps achieve stationarity without completely destroying the signal
4. **Feature Engineering**: Creates additional features that capture different aspects of price dynamics

## Results Interpretation

### d=0.2 (Light Differencing)
- **Preserves most memory** - Similar to original price
- **Minimal stationarity** - Still has strong trends
- **Use case**: When you want near-original signal with slight stabilization

### d=0.3 (Moderate Differencing)
- **Good balance** - Balanced stationarity and memory
- **Moderate mean reversion** - Reduced trends
- **Use case**: General purpose for most ML applications

### d=0.4 (Strong Differencing)
- **More stationary** - Closer to white noise
- **Less memory** - Reduced long-term dependencies
- **Use case**: When stationarity is critical

## Summary Statistics

The script outputs summary statistics including:
- **Mean**: Center of the distribution
- **Std**: Volatility/spread
- **Skew**: Asymmetry (negative = left tail, positive = right tail)
- **Kurt**: Tail heaviness (high values = more extreme events)

### Observations from BTC Data

From the analysis output:
- **Returns** have extremely high kurtosis (~10,340) indicating heavy tails and extreme events
- **Fractional differences** show decreasing memory as d increases
- **Distributions** become more centered around zero as d increases
- **Q-Q plots** show deviations from normality, especially in the tails

## Exported Data

The CSV file contains:
- `datetime`: Timestamp index
- `price`: Original BTC price
- `returns`: Price returns (pct_change)
- `frac_diff_0.2`: Fractionally differenced series (d=0.2)
- `frac_diff_0.3`: Fractionally differenced series (d=0.3)
- `frac_diff_0.4`: Fractionally differenced series (d=0.4)

Note: NaN values appear at the beginning due to windowing required for fractional differencing.

## Mathematical Formula

The fractional difference of order d is computed as:

```
X_d(t) = Σ(k=0 to ∞) w_k * X(t-k)
```

Where the weights are:
```
w_k = (-1)^k * Γ(d+1) / (Γ(k+1) * Γ(d-k+1))
```

In practice, we truncate weights below a threshold (default: 1e-5) to avoid excessive computation.

## Next Steps

1. **Optimize d value**: Use ADF test to find the minimum d that achieves stationarity
2. **Feature engineering**: Use fractional differences as ML features
3. **Backtesting**: Test trading strategies on differenced series
4. **Cross-asset analysis**: Compare fractional differences across different cryptocurrencies

## References

- [Advances in Financial Machine Learning](https://www.wiley.com/en-us/Advances+in+Financial+Machine+Learning-p-9781119482086) by Marcos López de Prado
- [Fractionally Differentiated Features](https://quantdare.com/fractionally-differentiated-features/)
