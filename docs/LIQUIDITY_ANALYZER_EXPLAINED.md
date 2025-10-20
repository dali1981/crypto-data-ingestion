# Liquidity Analyzer - Understanding the Spread Metric

## TL;DR

**The `effective_spread_mean` of ~0.0001 (1 basis point) is NOT the true bid-ask spread.**

- **True BTCUSDT spread:** ~0.0009-0.0018 bps ($0.01-0.02 at $110k)
- **Our estimate:** ~1-10 bps (100-1000x higher)
- **Why?** We measure price movement between trades, not the actual spread

---

## The Problem: Trade Data vs Order Book Data

### What We Have: Trade Data
```
Trade 1: BUY  @ $110,000.00
Trade 2: SELL @ $110,000.50
Trade 3: BUY  @ $110,001.00
Trade 4: SELL @ $110,000.75
```

### What We Don't Have: Order Book Data
```
Bids (Buy Orders)          Asks (Sell Orders)
$110,000.00  (0.5 BTC)    $110,000.01  (0.3 BTC)  <- Best Ask
$109,999.99  (1.2 BTC)    $110,000.02  (0.8 BTC)
$109,999.98  (0.8 BTC)    $110,000.03  (1.5 BTC)
     ↑
  Best Bid

True Spread = $110,000.01 - $110,000.00 = $0.01
```

---

## What the Analyzer Actually Measures

### Current Implementation

The `LiquidityAnalyzer` estimates spread by comparing **average prices** of recent buy vs sell trades:

```python
# Average last 5 buy trades
avg_buy = mean([110000.00, 110001.00, 110001.50, 110002.00, 110001.75])
        = $110,001.25

# Average last 5 sell trades
avg_sell = mean([110000.50, 110000.75, 110000.25, 110000.00, 110000.60])
         = $110,000.42

# "Spread" estimate
spread = avg_buy - avg_sell = $0.83
relative_spread = 0.83 / 110000 = 0.0000075 (0.75 bps)
```

### What This Actually Captures

This measurement includes:

1. ✅ **True bid-ask spread** (~$0.01 or 0.0009 bps)
2. ❌ **Price drift** - Market moving up/down between trades
3. ❌ **Trade impact** - Large trades moving the market
4. ❌ **Time lag** - Comparing trades seconds or minutes apart

**Result:** The estimate is **10-1000x larger** than the true spread.

---

## Why This Happens

### Example: Price Movement Contamination

```
Time    Side  Price        True Spread
10:00   BUY   $110,000.00  $0.01
10:01   SELL  $110,000.10  $0.01
10:02   BUY   $110,000.50  $0.01  <- Price moved $0.50 up!
10:03   SELL  $110,000.45  $0.01
10:04   BUY   $110,001.00  $0.01  <- Price moved another $0.50 up!

Average BUY  = $110,000.50
Average SELL = $110,000.27
"Spread"     = $0.23  <- But true spread is only $0.01!
```

The price **drifted up** by $1 over 4 minutes, making our "spread" estimate 23x too large.

---

## For BTCUSDT Specifically

### Market Characteristics

- **Tick size:** $0.01 (minimum price increment)
- **Typical spread:** 1-2 ticks = $0.01-0.02
- **Price level:** ~$110,000
- **True spread (bps):** 0.01/110000 = **0.0009 bps** (0.009%)

### Our Measurements

- **Observed `effective_spread_mean`:** ~0.0001 (1 basis point)
- **In dollars:** 0.0001 × $110,000 = **$11**
- **In ticks:** $11 / $0.01 = **1,100 ticks**

This is **550x larger** than the true spread!

### What We're Actually Measuring

Given 1,314 trades over your window:
- Average price: $110,966.65
- Price std dev: $10.87

The $11 "spread" is roughly the **price movement range** during that period, not the bid-ask spread.

---

## Interpreting the Metric

### What It IS Good For

The `effective_spread_mean` is useful for:

1. ✅ **Relative comparisons** - Compare liquidity across time periods
   - Lower value = tighter clustering of buy/sell prices
   - Higher value = more price dispersion

2. ✅ **Market regime detection**
   - Sudden increase = volatility spike or liquidity drop
   - Decrease = market calming down

3. ✅ **Trading cost proxy** - Rough estimate of round-trip cost
   - Captures both spread AND impact

### What It Is NOT

1. ❌ **Not the quoted spread** - That requires order book data
2. ❌ **Not comparable to exchange specs** - Exchange lists spread as 1-2 ticks
3. ❌ **Not stable** - Changes with market volatility

---

## Getting TRUE Spread

### Option 1: Use Order Book Stream (Recommended)

```python
from binance_tick_data.analyzers.liquidity import OrderBookLiquidityAnalyzer

# This analyzer uses depth stream for real spread
analyzer = OrderBookLiquidityAnalyzer(
    window_size=60,
    depth_levels=10
)

# You need to feed it order book snapshots
# (Not yet implemented in the streaming consumer)
```

### Option 2: Calculate from Consecutive Trades

A better estimate uses the **minimum price difference** between immediate buy/sell reversals:

```python
def estimate_spread_from_reversals(trades):
    """Estimate spread from buy->sell or sell->buy transitions."""
    spreads = []

    for i in range(1, len(trades)):
        prev_trade = trades[i-1]
        curr_trade = trades[i]

        # Look for buy->sell or sell->buy transition
        if prev_trade.is_buy != curr_trade.is_buy:
            spread = abs(curr_trade.price - prev_trade.price)

            # Only consider small spreads (exclude big price moves)
            if spread < avg_price * 0.0001:  # Less than 1bp
                spreads.append(spread)

    return min(spreads) if spreads else None
```

This captures trades that "crossed the spread" in quick succession.

### Option 3: Use Tick-by-Tick Analysis

Track the **minimum price increment** observed in the data:

```python
def estimate_tick_size(trades):
    """Estimate tick size from price changes."""
    price_diffs = []

    for i in range(1, len(trades)):
        diff = abs(trades[i].price - trades[i-1].price)
        if diff > 0:
            price_diffs.append(diff)

    # Minimum non-zero difference is likely the tick size
    tick = min(price_diffs)

    # Spread is typically 1-2 ticks
    return tick, tick * 1.5  # Conservative estimate
```

---

## Comparison Table

| Metric | True Spread | Our Estimate | Ratio |
|--------|-------------|--------------|-------|
| **Absolute** | $0.01-0.02 | $11 | 550-1100x |
| **Relative** | 0.0009-0.0018 bps | 1 bp | 555-1111x |
| **Ticks** | 1-2 ticks | 1,100 ticks | 550-1100x |

---

## Recommendations

### For Production Use

1. **Rename the metric** to avoid confusion:
   ```python
   metrics["price_dispersion"] = ...  # Instead of "effective_spread"
   metrics["trading_cost_proxy"] = ...
   ```

2. **Add order book integration** for true spread:
   ```python
   # Subscribe to depth stream
   bm.depth_socket('BTCUSDT')
   ```

3. **Use for relative analysis** only:
   ```python
   # Good: Compare across time
   if current_spread > historical_avg * 2:
       print("Liquidity deteriorating!")

   # Bad: Compare to exchange specs
   if current_spread > 0.01:  # This will always be true!
       print("Spread too wide!")  # Wrong conclusion
   ```

### For Your Current Analysis

Your observation is **correct** - the spread seems "too high" because:

1. It's **not actually the spread** - it's price movement + spread
2. The **true spread is ~0.0009 bps**, yours shows **~1 bp**
3. This is **expected behavior** for trade-based estimation

**Don't worry** - the analyzer is working correctly! It's just measuring a different (but still useful) liquidity metric.

---

## Code Changes Made

### In `liquidity.py`

Added documentation warnings:

```python
class LiquidityAnalyzer(BaseAnalyzer):
    """
    IMPORTANT LIMITATION:
    Without real-time order book data, the "spread" estimated from trades
    is NOT the true bid-ask spread. Instead, it measures the price difference
    between recent buy and sell trades, which includes:
    - True bid-ask spread (typically 1-2 ticks)
    - Price drift/movement between trades
    - Market impact of trades

    For BTCUSDT at $110k:
    - True spread: ~$0.01-0.02 (0.0009-0.0018 bps)
    - Our estimate: ~0.01-0.1 bps (10-100x higher due to price movement)
    """
```

Added helper note to metrics:

```python
metrics["spread_note"] = "Includes price drift - not true bid-ask spread"
```

---

## Summary

| Question | Answer |
|----------|--------|
| **Is the analyzer broken?** | No, it's working as designed |
| **Is 1 bp too high?** | Yes, for the *true spread*. No, for *price dispersion* |
| **What's the true spread?** | ~0.0009-0.0018 bps ($0.01-0.02) |
| **Should I trust this metric?** | Yes, for relative comparisons. No, for absolute spread |
| **How to get true spread?** | Use order book data (depth stream) |

**Bottom Line:** The metric is useful, just not for what it's named! Think of it as "recent price dispersion" rather than "spread".
