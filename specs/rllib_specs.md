# RLlib Integration Specification

## Overview

This document specifies how to integrate the Binance live streaming infrastructure with Ray RLlib for reinforcement learning-based trading algorithms.

## Architecture

```
Binance WebSocket → RealtimeConsumer → RingBuffer → Gym Environment → RLlib Algorithm
                         ↓
                    Analyzers (features)
                         ↓
                    Observation Space
                         ↓
                    RL Agent (PPO/SAC/etc)
```

## Components

### 1. Existing Infrastructure (Already Built)

#### RealtimeConsumer
- **Location**: `src/binance_tick_data/consumers/realtime_consumer.py:23`
- **Purpose**: Streams live trade and order book data from Binance WebSocket
- **Features**:
  - Multi-symbol support
  - RingBuffer for recent trades (configurable size)
  - Order book depth streaming (100ms or 1000ms updates)
  - Pluggable analyzer architecture
  - Automatic reconnection with exponential backoff

#### Available Analyzers (Feature Extractors)
- **OrderFlowAnalyzer** (`src/binance_tick_data/analyzers/order_flow.py`)
  - Buy/sell volume ratios
  - Net order flow
  - Buy/sell pressure indicators

- **LiquidityAnalyzer** (`src/binance_tick_data/analyzers/liquidity.py`)
  - Effective spread estimation
  - Price impact metrics
  - Market depth indicators

- **VolumeProfileAnalyzer** (`src/binance_tick_data/analyzers/volume_profile.py`)
  - Price level concentrations
  - Volume at price (VAP)
  - Point of control (POC)

- **OrderBookLiquidityAnalyzer** (`src/binance_tick_data/analyzers/liquidity.py`)
  - TRUE bid-ask spread from order book
  - Order book imbalance
  - Weighted mid-price

#### RingBuffer
- **Location**: `src/binance_tick_data/streaming/ring_buffer.py`
- **Purpose**: Efficient fixed-size circular buffer for recent data
- **Methods**:
  - `get_recent(n)`: Get last N items
  - `get_all()`: Get all buffered items
  - `get_since_time(timestamp)`: Get items after timestamp

#### Dollar Volume Sampling
- **Location**: `src/binance_tick_data/dollar_volume_sampling.py`
- **Purpose**: Convert tick data to information-driven bars
- **Use case**: Time aggregation for RL (train on bars instead of ticks)

### 2. Components to Build

#### Gym Environment Wrapper

**File**: `src/binance_tick_data/rl/trading_env.py`

```python
"""
Gym environment for live trading on Binance streams.

Features:
- Wraps RealtimeConsumer for live data
- Extracts features from Analyzers
- Implements standard Gym API (reset, step, etc.)
- Tracks position and PnL
- Handles async/sync bridge
"""

import gymnasium as gym
import numpy as np
from gymnasium import spaces
import asyncio
import threading
from typing import Dict, Any, Tuple

from ..consumers import RealtimeConsumer, ConsumerConfig
from ..analyzers import OrderFlowAnalyzer, LiquidityAnalyzer, VolumeProfileAnalyzer


class BinanceTradingEnv(gym.Env):
    """
    Gym environment for reinforcement learning on live Binance data.

    Observation Space:
        Box(20,) containing:
        - [0]: Current price
        - [1]: Total volume (recent window)
        - [2]: Buy volume ratio
        - [3]: Sell volume ratio
        - [4]: Net order flow
        - [5]: Effective spread
        - [6]: Price impact
        - [7]: Best bid
        - [8]: Best ask
        - [9]: Spread percentage
        - [10]: Order book imbalance
        - [11-15]: Volume profile features
        - [16]: Current position (-1, 0, 1)
        - [17]: Unrealized PnL
        - [18]: Realized PnL
        - [19]: Time since last action

    Action Space:
        Discrete(3):
        - 0: Sell (go short or close long)
        - 1: Hold (no change)
        - 2: Buy (go long or close short)

    Reward:
        - Realized PnL when closing position
        - Small reward/penalty for unrealized PnL while holding
        - Transaction cost penalty
    """

    metadata = {'render_modes': ['human']}

    def __init__(self, env_config: Dict[str, Any] = None):
        """
        Initialize environment.

        Args:
            env_config: Configuration dict containing:
                - symbol: Trading pair (default: "BTCUSDT")
                - buffer_size: RingBuffer size (default: 1000)
                - stream_orderbook: Enable order book (default: True)
                - orderbook_update_speed: "100ms" or "1000ms" (default: "100ms")
                - feature_window: Window size for analyzers (default: 100)
                - transaction_cost: Trading fee percentage (default: 0.001)
                - max_position_size: Max position (default: 1.0)
        """
        super().__init__()

        config = env_config or {}

        # Environment parameters
        self.symbol = config.get('symbol', 'BTCUSDT')
        self.buffer_size = config.get('buffer_size', 1000)
        self.feature_window = config.get('feature_window', 100)
        self.transaction_cost = config.get('transaction_cost', 0.001)
        self.max_position_size = config.get('max_position_size', 1.0)

        # Define spaces
        self.action_space = spaces.Discrete(3)  # 0=sell, 1=hold, 2=buy
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(20,),
            dtype=np.float32
        )

        # Initialize consumer
        consumer_config = ConsumerConfig(
            symbols=[self.symbol],
            buffer_size=self.buffer_size,
            stream_orderbook=config.get('stream_orderbook', True),
            orderbook_update_speed=config.get('orderbook_update_speed', '100ms'),
            orderbook_depth_levels=config.get('orderbook_depth_levels', 20),
        )
        self.consumer = RealtimeConsumer(consumer_config)

        # Initialize analyzers
        self.order_flow = OrderFlowAnalyzer(window_size=self.feature_window)
        self.liquidity = LiquidityAnalyzer(window_size=self.feature_window)
        self.volume_profile = VolumeProfileAnalyzer(window_size=self.feature_window)

        self.consumer.register_analyzer(self.order_flow)
        self.consumer.register_analyzer(self.liquidity)
        self.consumer.register_analyzer(self.volume_profile)

        # Trading state
        self.position = 0.0  # -1.0 to 1.0
        self.entry_price = None
        self.realized_pnl = 0.0
        self.unrealized_pnl = 0.0
        self.steps_since_action = 0

        # Stream management
        self._stream_thread = None
        self._stream_loop = None
        self._stream_started = False

    def _start_stream(self):
        """Start WebSocket stream in background thread."""
        if self._stream_started:
            return

        def run_stream():
            self._stream_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._stream_loop)
            self._stream_loop.run_until_complete(self.consumer.start())

        self._stream_thread = threading.Thread(target=run_stream, daemon=True)
        self._stream_thread.start()

        # Wait for stream to initialize
        import time
        time.sleep(2)

        self._stream_started = True

    def _get_observation(self) -> np.ndarray:
        """
        Extract features from live stream.

        Returns:
            Feature vector as numpy array
        """
        # Get recent trades
        try:
            recent_trades = self.consumer.get_recent_trades(
                self.symbol,
                n=self.feature_window
            )
        except KeyError:
            # Stream not ready yet
            return np.zeros(self.observation_space.shape, dtype=np.float32)

        if len(recent_trades) < 10:
            # Not enough data yet
            return np.zeros(self.observation_space.shape, dtype=np.float32)

        # Get analyzer metrics
        order_flow_metrics = self.order_flow.get_metrics()
        liquidity_metrics = self.liquidity.get_metrics()
        volume_profile_metrics = self.volume_profile.get_metrics()

        # Get order book
        try:
            orderbook = self.consumer.get_orderbook(self.symbol)
        except (KeyError, ValueError):
            orderbook = None

        # Build feature vector
        features = []

        # Price features
        current_price = float(recent_trades[-1].price)
        features.append(current_price)

        # Volume features
        total_volume = sum(float(t.qty) for t in recent_trades)
        features.append(total_volume)

        # Order flow features (indices 2-4)
        features.append(order_flow_metrics.get('buy_volume_ratio', 0.5))
        features.append(order_flow_metrics.get('sell_volume_ratio', 0.5))
        features.append(order_flow_metrics.get('net_flow', 0.0))

        # Liquidity features (indices 5-6)
        features.append(liquidity_metrics.get('effective_spread_mean', 0.0) or 0.0)
        features.append(liquidity_metrics.get('price_impact', 0.0) or 0.0)

        # Order book features (indices 7-10)
        if orderbook and orderbook['bids'] and orderbook['asks']:
            best_bid = orderbook['bids'][0][0]
            best_ask = orderbook['asks'][0][0]
            spread_pct = (best_ask - best_bid) / current_price if current_price > 0 else 0

            # Order book imbalance
            bid_volume = sum(level[1] for level in orderbook['bids'][:5])
            ask_volume = sum(level[1] for level in orderbook['asks'][:5])
            total_ob_volume = bid_volume + ask_volume
            imbalance = (bid_volume - ask_volume) / total_ob_volume if total_ob_volume > 0 else 0

            features.extend([best_bid, best_ask, spread_pct, imbalance])
        else:
            features.extend([current_price, current_price, 0.0, 0.0])

        # Volume profile features (indices 11-15)
        # Use price buckets to create histogram-like features
        vp_levels = volume_profile_metrics.get('price_levels', [])
        if len(vp_levels) >= 5:
            # Top 5 volume levels (normalized)
            top_levels = sorted(vp_levels, key=lambda x: x[1], reverse=True)[:5]
            for price_level, volume in top_levels:
                features.append(volume)
        else:
            features.extend([0.0] * 5)

        # Trading state features (indices 16-19)
        features.append(self.position)
        features.append(self.unrealized_pnl)
        features.append(self.realized_pnl)
        features.append(float(self.steps_since_action))

        # Ensure correct shape
        features = features[:20]
        while len(features) < 20:
            features.append(0.0)

        return np.array(features, dtype=np.float32)

    def reset(self, seed=None, options=None) -> Tuple[np.ndarray, Dict]:
        """
        Reset environment state (but keep stream running).

        Args:
            seed: Random seed
            options: Additional options

        Returns:
            Initial observation and info dict
        """
        super().reset(seed=seed)

        # Start stream if not already running
        if not self._stream_started:
            self._start_stream()

        # Reset trading state
        self.position = 0.0
        self.entry_price = None
        self.realized_pnl = 0.0
        self.unrealized_pnl = 0.0
        self.steps_since_action = 0

        obs = self._get_observation()
        info = {'symbol': self.symbol}

        return obs, info

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """
        Execute action and return result.

        Args:
            action: 0=sell, 1=hold, 2=buy

        Returns:
            observation, reward, terminated, truncated, info
        """
        # Get current state
        obs = self._get_observation()

        # Get current price
        try:
            recent_trades = self.consumer.get_recent_trades(self.symbol, n=1)
            if not recent_trades:
                # No data yet
                return obs, 0.0, False, False, {'error': 'no_data'}
            current_price = float(recent_trades[-1].price)
        except KeyError:
            return obs, 0.0, False, False, {'error': 'stream_not_ready'}

        # Convert action to position change
        # action: 0=sell (-1), 1=hold (0), 2=buy (+1)
        target_position = float(action - 1) * self.max_position_size

        # Calculate reward
        reward = 0.0
        position_changed = False

        # If position is changing
        if abs(target_position - self.position) > 0.01:
            position_changed = True

            # Close existing position if any
            if abs(self.position) > 0.01 and self.entry_price is not None:
                # Calculate realized PnL
                pnl = (current_price - self.entry_price) * self.position

                # Apply transaction cost
                transaction_cost = abs(self.position) * current_price * self.transaction_cost
                pnl -= transaction_cost

                self.realized_pnl += pnl
                reward += pnl

            # Open new position
            if abs(target_position) > 0.01:
                self.entry_price = current_price

                # Transaction cost for opening
                transaction_cost = abs(target_position) * current_price * self.transaction_cost
                reward -= transaction_cost
            else:
                self.entry_price = None

            self.position = target_position
            self.steps_since_action = 0
        else:
            # Holding existing position
            self.steps_since_action += 1

        # Calculate unrealized PnL
        if abs(self.position) > 0.01 and self.entry_price is not None:
            self.unrealized_pnl = (current_price - self.entry_price) * self.position

            # Small reward for unrealized gains (encourages holding winners)
            reward += self.unrealized_pnl * 0.001
        else:
            self.unrealized_pnl = 0.0

        # Penalty for holding too long without action
        if self.steps_since_action > 100:
            reward -= 0.01

        terminated = False  # Live trading never terminates naturally
        truncated = False

        info = {
            'position': self.position,
            'realized_pnl': self.realized_pnl,
            'unrealized_pnl': self.unrealized_pnl,
            'price': current_price,
            'action': action,
            'position_changed': position_changed,
        }

        return obs, reward, terminated, truncated, info

    def render(self, mode='human'):
        """Render current state (optional)."""
        if mode == 'human':
            print(f"\nPosition: {self.position:.2f}")
            print(f"Realized PnL: ${self.realized_pnl:.2f}")
            print(f"Unrealized PnL: ${self.unrealized_pnl:.2f}")

    def close(self):
        """Cleanup resources."""
        if self._stream_started and self._stream_loop:
            asyncio.run_coroutine_threadsafe(
                self.consumer.stop(),
                self._stream_loop
            )
```

#### Training Script

**File**: `src/binance_tick_data/rl/train_live.py`

```python
"""
Train RLlib algorithm on live Binance stream.

Usage:
    uv run python -m binance_tick_data.rl.train_live --algo ppo --symbol BTCUSDT
"""

import ray
from ray import tune
from ray.rllib.algorithms.ppo import PPOConfig
from ray.rllib.algorithms.sac import SACConfig
from ray.tune.registry import register_env
import argparse
from pathlib import Path

from .trading_env import BinanceTradingEnv


def env_creator(env_config):
    """Create environment instance for RLlib."""
    return BinanceTradingEnv(env_config)


def train_ppo(config: dict, num_iterations: int = 100):
    """
    Train PPO algorithm on live stream.

    Args:
        config: Environment configuration
        num_iterations: Number of training iterations
    """
    # Register environment
    register_env("binance_trading", env_creator)

    # Configure PPO
    algo_config = (
        PPOConfig()
        .environment("binance_trading", env_config=config)
        .framework("torch")
        .rollouts(
            num_rollout_workers=1,
            num_envs_per_worker=1,
            rollout_fragment_length=200,
        )
        .training(
            train_batch_size=4000,
            sgd_minibatch_size=128,
            num_sgd_iter=10,
            lr=3e-4,
            gamma=0.99,
            lambda_=0.95,
            clip_param=0.2,
            vf_clip_param=10.0,
            entropy_coeff=0.01,
        )
        .resources(
            num_gpus=0,  # Set to 1 if GPU available
        )
        .evaluation(
            evaluation_interval=10,
            evaluation_duration=10,
        )
    )

    # Build algorithm
    print("Building PPO algorithm...")
    algo = algo_config.build()

    # Training loop
    print(f"\nStarting training for {num_iterations} iterations...")
    print("=" * 80)

    best_reward = float('-inf')
    checkpoint_dir = Path("checkpoints/ppo")
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    for i in range(num_iterations):
        result = algo.train()

        episode_reward = result.get('episode_reward_mean', 0)
        episode_len = result.get('episode_len_mean', 0)

        print(f"\nIteration {i+1}/{num_iterations}")
        print(f"  Episode reward mean: {episode_reward:.2f}")
        print(f"  Episode length mean: {episode_len:.2f}")
        print(f"  Policy loss: {result.get('info', {}).get('learner', {}).get('default_policy', {}).get('learner_stats', {}).get('policy_loss', 0):.4f}")

        # Save checkpoint if best so far
        if episode_reward > best_reward:
            best_reward = episode_reward
            checkpoint_path = algo.save(checkpoint_dir)
            print(f"  ✅ New best! Checkpoint saved: {checkpoint_path}")

        # Periodic checkpoint
        if (i + 1) % 10 == 0:
            checkpoint_path = algo.save(checkpoint_dir)
            print(f"  📁 Checkpoint saved: {checkpoint_path}")

    print("\n" + "=" * 80)
    print(f"Training complete! Best reward: {best_reward:.2f}")

    # Cleanup
    algo.stop()


def train_sac(config: dict, num_iterations: int = 100):
    """
    Train SAC algorithm on live stream.

    SAC is better for continuous learning and exploration.

    Args:
        config: Environment configuration
        num_iterations: Number of training iterations
    """
    register_env("binance_trading", env_creator)

    # Configure SAC
    algo_config = (
        SACConfig()
        .environment("binance_trading", env_config=config)
        .framework("torch")
        .rollouts(num_rollout_workers=1)
        .training(
            train_batch_size=256,
            lr=3e-4,
            gamma=0.99,
            tau=0.005,
            target_entropy="auto",
            n_step=1,
        )
        .resources(num_gpus=0)
    )

    algo = algo_config.build()

    # Training loop (similar to PPO)
    print(f"\nStarting SAC training for {num_iterations} iterations...")

    for i in range(num_iterations):
        result = algo.train()
        print(f"Iteration {i+1}: Reward={result.get('episode_reward_mean', 0):.2f}")

        if (i + 1) % 10 == 0:
            checkpoint_path = algo.save("checkpoints/sac")
            print(f"  Checkpoint saved: {checkpoint_path}")

    algo.stop()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Train RL algorithm on live Binance stream"
    )
    parser.add_argument(
        '--algo',
        type=str,
        choices=['ppo', 'sac'],
        default='ppo',
        help='Algorithm to use (default: ppo)'
    )
    parser.add_argument(
        '--symbol',
        type=str,
        default='BTCUSDT',
        help='Trading symbol (default: BTCUSDT)'
    )
    parser.add_argument(
        '--iterations',
        type=int,
        default=100,
        help='Number of training iterations (default: 100)'
    )
    parser.add_argument(
        '--buffer-size',
        type=int,
        default=1000,
        help='RingBuffer size (default: 1000)'
    )
    parser.add_argument(
        '--feature-window',
        type=int,
        default=100,
        help='Analyzer window size (default: 100)'
    )

    args = parser.parse_args()

    # Initialize Ray
    ray.init(ignore_reinit_error=True)

    # Environment configuration
    env_config = {
        'symbol': args.symbol,
        'buffer_size': args.buffer_size,
        'feature_window': args.feature_window,
        'stream_orderbook': True,
        'orderbook_update_speed': '100ms',
        'transaction_cost': 0.001,  # 0.1% fee
        'max_position_size': 1.0,
    }

    print("\n" + "=" * 80)
    print(f"Training Configuration")
    print("=" * 80)
    print(f"Algorithm: {args.algo.upper()}")
    print(f"Symbol: {args.symbol}")
    print(f"Iterations: {args.iterations}")
    print(f"Buffer size: {args.buffer_size}")
    print(f"Feature window: {args.feature_window}")
    print("=" * 80 + "\n")

    # Train
    try:
        if args.algo == 'ppo':
            train_ppo(env_config, args.iterations)
        elif args.algo == 'sac':
            train_sac(env_config, args.iterations)
    finally:
        ray.shutdown()


if __name__ == "__main__":
    main()
```

## Implementation Phases

### Phase 1: Historical Training (Recommended First)

**Purpose**: Train on existing historical data before attempting live training.

**File**: `src/binance_tick_data/rl/historical_env.py`

```python
"""
Historical replay environment for offline training.

Trains on your existing 110K BTCUSDT trades much faster than real-time.
"""

import gymnasium as gym
import numpy as np
from gymnasium import spaces
import pandas as pd

from ..repository_v2 import BinanceDataRepository
from ..dollar_volume_sampling import create_dollar_volume_bars


class HistoricalTradingEnv(gym.Env):
    """
    Replay historical data for fast offline training.

    Advantages over live training:
    - 1000x faster (process 110K trades in minutes vs days)
    - Reproducible (same data every episode)
    - No API rate limits
    - Perfect for hyperparameter tuning
    """

    def __init__(self, env_config=None):
        config = env_config or {}

        self.action_space = spaces.Discrete(3)
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(20,),
            dtype=np.float32
        )

        # Load historical data
        repo = BinanceDataRepository()
        symbol = config.get('symbol', 'BTCUSDT')

        # Get all historical data
        with repo:
            df = repo.query_all(symbol, output_format='pandas')

        # Convert to dollar volume bars
        self.bars = create_dollar_volume_bars(
            df,
            ticks_per_bar=config.get('ticks_per_bar', 100)
        )

        # Current position in dataset
        self.current_idx = 0
        self.position = 0.0
        self.entry_price = None
        self.pnl = 0.0

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)

        # Random start position for variation
        max_start = len(self.bars) - 1000
        self.current_idx = np.random.randint(0, max_start) if max_start > 0 else 0

        self.position = 0.0
        self.entry_price = None
        self.pnl = 0.0

        return self._get_observation(), {}

    def _get_observation(self):
        # Extract features from current bar
        if self.current_idx >= len(self.bars):
            return np.zeros(20, dtype=np.float32)

        bar = self.bars.iloc[self.current_idx]

        # Simple features (expand based on your needs)
        features = [
            bar['close'],
            bar['volume'],
            bar['high'] - bar['low'],  # range
            bar['close'] - bar['open'],  # price change
            # ... add more features
        ]

        # Pad to 20
        while len(features) < 20:
            features.append(0.0)

        return np.array(features[:20], dtype=np.float32)

    def step(self, action):
        # Similar logic to live env but using historical bars
        obs = self._get_observation()

        if self.current_idx >= len(self.bars) - 1:
            return obs, 0.0, True, False, {}  # Episode ends

        current_price = self.bars.iloc[self.current_idx]['close']

        # Action logic (same as live env)
        target_position = float(action - 1)
        reward = 0.0

        # ... calculate reward based on position change ...

        # Move to next bar
        self.current_idx += 1

        terminated = self.current_idx >= len(self.bars) - 1

        return self._get_observation(), reward, terminated, False, {}
```

**Usage**:
```bash
# Train on historical data first (much faster)
uv run python -m binance_tick_data.rl.train_historical --iterations 1000

# Then fine-tune on live stream
uv run python -m binance_tick_data.rl.train_live --iterations 100 --checkpoint checkpoints/historical/best
```

### Phase 2: Live Fine-Tuning

Use the `train_live.py` script with a pre-trained checkpoint:

```python
# Load historical checkpoint
algo = PPOConfig().build()
algo.restore("checkpoints/historical/best")

# Continue training on live stream
for i in range(100):
    result = algo.train()  # Now using live data
```

### Phase 3: Paper Trading Validation

**File**: `src/binance_tick_data/rl/paper_trading.py`

```python
"""
Paper trading validation - test trained policy without real execution.
"""

def paper_trade(checkpoint_path: str, duration_seconds: int = 3600):
    """
    Run trained policy on live stream without executing trades.

    Args:
        checkpoint_path: Path to trained checkpoint
        duration_seconds: How long to run (default: 1 hour)
    """
    # Load trained algo
    algo = PPOConfig().build()
    algo.restore(checkpoint_path)

    # Create live environment
    env = BinanceTradingEnv({'symbol': 'BTCUSDT'})
    obs, info = env.reset()

    import time
    start_time = time.time()

    trades = []

    while time.time() - start_time < duration_seconds:
        # Get action from policy
        action = algo.compute_single_action(obs)

        # Execute in paper mode
        obs, reward, term, trunc, info = env.step(action)

        # Log trade
        if info.get('position_changed'):
            trades.append({
                'time': time.time(),
                'action': action,
                'price': info['price'],
                'position': info['position'],
                'pnl': info['realized_pnl'],
            })
            print(f"Paper trade: {action} at ${info['price']:.2f}, PnL=${info['realized_pnl']:.2f}")

        time.sleep(1)  # Check every second

    # Analysis
    total_pnl = sum(t['pnl'] for t in trades)
    print(f"\nPaper trading complete!")
    print(f"Total trades: {len(trades)}")
    print(f"Total PnL: ${total_pnl:.2f}")

    return trades
```

## Key Technical Challenges & Solutions

### Challenge 1: Async/Sync Bridge

**Problem**: RealtimeConsumer is async, Gym is sync.

**Solution**: Run consumer in background thread (implemented in `BinanceTradingEnv.__init__`)

```python
def _start_stream(self):
    """Start WebSocket stream in background thread."""
    def run_stream():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.consumer.start())

    thread = threading.Thread(target=run_stream, daemon=True)
    thread.start()
```

### Challenge 2: Training Speed vs Data Speed

**Problem**: Live data arrives at 100+ trades/sec, training is slower.

**Solutions**:
1. **Use dollar volume bars** instead of raw ticks (reduce data rate)
2. **Buffer replay**: Train on buffered historical data from RingBuffer
3. **Async training**: Let data accumulate while training on batches

**Recommendation**: Use historical training first (Phase 1), then fine-tune on live.

### Challenge 3: Non-Stationarity

**Problem**: Markets change, RL assumes stationary environment.

**Solutions**:
1. **Online learning**: Continuously update policy
2. **Recency weighting**: Prioritize recent experiences
3. **Meta-learning**: Train to adapt quickly
4. **Regime detection**: Switch policies based on market state

**Implementation**: Use PPO with continuous training (no separate train/eval)

### Challenge 4: Reward Engineering

**Problem**: Defining "good" trading behavior.

**Recommendations**:
- **Sharpe ratio**: Reward risk-adjusted returns
- **Max drawdown penalty**: Penalize large losses
- **Transaction costs**: Include realistic fees
- **Hold penalty**: Prevent "do nothing" policy

**Example** (in `step()` method):
```python
# Reward = PnL - transaction_costs - holding_penalty
reward = realized_pnl - abs(position_change) * price * 0.001 - 0.01
```

## Dependencies

Add to `pyproject.toml`:

```toml
[project.dependencies]
ray = {extras = ["rllib"], version = "^2.10.0"}
gymnasium = "^0.29.0"
torch = "^2.0.0"  # or tensorflow
```

Install:
```bash
uv add 'ray[rllib]' gymnasium torch
```

## Example Workflow

### Step 1: Train Offline
```bash
# Fast training on historical data
uv run python -m binance_tick_data.rl.train_historical \
    --symbol BTCUSDT \
    --iterations 1000 \
    --ticks-per-bar 100
```

### Step 2: Fine-tune on Live Stream
```bash
# Fine-tune with live data
uv run python -m binance_tick_data.rl.train_live \
    --algo ppo \
    --symbol BTCUSDT \
    --iterations 100 \
    --checkpoint checkpoints/historical/best
```

### Step 3: Paper Trade Validation
```bash
# Validate on live stream without executing
uv run python -m binance_tick_data.rl.paper_trade \
    --checkpoint checkpoints/live/best \
    --duration 3600  # 1 hour
```

### Step 4: Deploy (Future)
```bash
# Real trading (NOT IMPLEMENTED - requires exchange integration)
uv run python -m binance_tick_data.rl.deploy \
    --checkpoint checkpoints/live/best \
    --max-position 0.01  # BTC
```

## Performance Considerations

### Data Throughput
- **Live stream**: ~100 trades/second for BTCUSDT
- **RingBuffer**: Efficiently stores recent 1000 trades
- **Analyzers**: Update incrementally (O(1) per trade)
- **Observation extraction**: ~1ms per step

### Training Speed
- **Historical**: Can process 110K trades in ~10 minutes
- **Live**: Limited by real-time data arrival
- **Recommendation**: Train offline first, then fine-tune live

### Memory Usage
- **RingBuffer**: ~10KB per 1000 trades
- **RLlib replay buffer**: ~100MB for 100K transitions
- **Model size**: ~1-10MB (PPO/SAC networks)

## Existing Code References

Your current infrastructure that enables this:

1. **RealtimeConsumer** (`src/binance_tick_data/consumers/realtime_consumer.py:23`)
   - Handles WebSocket streaming
   - RingBuffer management
   - Analyzer integration

2. **Analyzers** (`src/binance_tick_data/analyzers/`)
   - OrderFlowAnalyzer: Buy/sell pressure
   - LiquidityAnalyzer: Spread metrics
   - VolumeProfileAnalyzer: Price levels
   - Use as RL observation features

3. **RingBuffer** (`src/binance_tick_data/streaming/ring_buffer.py`)
   - Efficient recent data storage
   - `get_recent(n)` for sampling

4. **Dollar Volume Bars** (`src/binance_tick_data/dollar_volume_sampling.py`)
   - Time aggregation for RL
   - Reduces data rate 100x

5. **Historical Data** (`src/binance_tick_data/repository_v2.py`)
   - 110K trades already available
   - Perfect for offline training

## Next Steps

1. **Install dependencies**: `uv add 'ray[rllib]' gymnasium torch`
2. **Create RL package**: `mkdir -p src/binance_tick_data/rl`
3. **Implement environment**: Copy `BinanceTradingEnv` code above
4. **Train on historical data**: Fast offline training
5. **Validate with paper trading**: Test on live stream
6. **Fine-tune live**: Online learning with real data

## References

- **RLlib Documentation**: https://docs.ray.io/en/latest/rllib/
- **Gymnasium API**: https://gymnasium.farama.org/
- **PPO Paper**: https://arxiv.org/abs/1707.06347
- **SAC Paper**: https://arxiv.org/abs/1801.01290

## Notes

- **Start simple**: Train on historical data first
- **Validate thoroughly**: Paper trade before real execution
- **Monitor performance**: Track Sharpe ratio, max drawdown
- **Iterate quickly**: Use dollar volume bars to speed up training
- **Risk management**: Always include transaction costs and position limits
