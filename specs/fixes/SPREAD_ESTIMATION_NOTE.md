# Spread Estimation - Important Note

## Key Insight

**The `effective_spread_mean` metric does NOT measure the true bid-ask spread.**

## What It Actually Measures

The analyzer compares average prices of recent buy vs sell trades:

```python
avg_buy_price  = mean(last 5 buy trades)
avg_sell_price = mean(last 5 sell trades)
spread_estimate = avg_buy_price - avg_sell_price
```

This captures:
- ✅ True bid-ask spread (~$0.01 for BTCUSDT)
- ❌ **Price movement between trades** (dominant component)
- ❌ Market impact
- ❌ Volatility

## For BTCUSDT @ $110,000

| Metric | True Spread | Our Estimate | Ratio |
|--------|-------------|--------------|-------|
| **Absolute** | $0.01 - $0.02 | ~$11 | **550x larger** |
| **Basis Points** | 0.0009 - 0.0018 bps | ~1 bp | **555x larger** |
| **Reason** | Bid-ask difference | Price drift + spread | Measures different things |

## Why This Happens

**Without order book data**, we cannot see the actual quotes:

```
❌ What we DON'T have:
Bid: $110,000.00  |  Ask: $110,000.01  <- True spread = $0.01

✅ What we DO have:
Trade 1 (BUY):  $110,000.50
Trade 2 (SELL): $110,001.20
Trade 3 (BUY):  $110,002.00
...
```

We're comparing trades that happened at different times, capturing price movement.

## Better Name for This Metric

Instead of "spread", think of it as:
- **Price Dispersion** - How scattered are buy/sell prices?
- **Trading Cost Proxy** - Rough estimate of round-trip cost
- **Market Impact Estimate** - Includes slippage and spread

## When to Use It

### ✅ Good Uses:
- **Relative comparisons**: "Spread doubled → liquidity dropped"
- **Regime detection**: "Spread spiking → volatility event"
- **Cost estimation**: Rough upper bound on trading costs

### ❌ Bad Uses:
- **Absolute spread**: "Exchange should have 0.001 bps spread"
- **Comparison to specs**: "This doesn't match Binance's quoted spread"
- **Precise liquidity**: "Market is exactly X bps wide"

## How to Get TRUE Spread

### Option 1: Order Book Data (Recommended)

```python
# Use depth stream to get actual bid/ask quotes
from binance_tick_data.analyzers.liquidity import OrderBookLiquidityAnalyzer

analyzer = OrderBookLiquidityAnalyzer()
# Feed order book snapshots to get real spread
```

### Option 2: Trade Reversals

Look for immediate buy→sell or sell→buy transitions:

```python
# If trades flip sides quickly, the price difference is closer to true spread
Time    Side  Price
10:00   BUY   $110,000.50
10:00   SELL  $110,000.51  <- Spread ≈ $0.01 (close to true!)
```

### Option 3: Minimum Price Increment

The tick size is the lower bound:

```python
# For BTCUSDT:
tick_size = $0.01
minimum_spread = 1 tick = $0.01 (0.0009 bps)
typical_spread = 1-2 ticks = $0.01-$0.02
```

## Code Location

- **Implementation**: `src/binance_tick_data/analyzers/liquidity.py`
- **Lines**: 113-141 (spread estimation), 191-213 (metrics)
- **Documentation**: `docs/LIQUIDITY_ANALYZER_EXPLAINED.md` (detailed)

## Summary

| Question | Answer |
|----------|--------|
| **Is 1 bp realistic for BTCUSDT?** | No - true spread is ~0.001 bps |
| **Why so high?** | Includes price movement over time |
| **Is the code wrong?** | No - it's working as designed |
| **What should I call it?** | "Price dispersion" or "trading cost proxy" |
| **Can I still use it?** | Yes - for relative analysis, not absolute spread |

---

**Bottom line:** The metric is useful for comparing liquidity across time, but it's **NOT** the quoted bid-ask spread you'd see on an exchange.

**Last Updated:** 2025-10-20
**Related Files:**
- `docs/LIQUIDITY_ANALYZER_EXPLAINED.md` - Full technical explanation
- `src/binance_tick_data/analyzers/liquidity.py` - Implementation
