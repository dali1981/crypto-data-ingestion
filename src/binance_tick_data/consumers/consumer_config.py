"""
Configuration schemas for real-time streaming consumers and analyzers.

Uses Pydantic for type-safe configuration with validation and defaults.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class ConsumerConfig(BaseModel):
    """
    Configuration for real-time consumer.

    Controls buffer sizes, update intervals, and connection settings.
    """

    # Buffer settings
    buffer_size: int = Field(
        default=10000,
        description="Ring buffer size per symbol (number of trades to keep in memory)",
        gt=0,
    )

    # Update settings
    update_interval: float = Field(
        default=0.1,
        description="Callback interval in seconds",
        gt=0.0,
        le=60.0,
    )

    # Symbols to consume
    symbols: List[str] = Field(
        default=["BTCUSDT"],
        description="Trading pairs to monitor",
        min_length=1,
    )

    # Connection settings
    reconnect_delay: int = Field(
        default=5,
        description="Reconnect delay in seconds after connection failure",
        ge=1,
        le=300,
    )

    max_reconnect_attempts: int = Field(
        default=10,
        description="Maximum reconnection attempts (0 for unlimited)",
        ge=0,
    )

    # Performance settings
    batch_callback: bool = Field(
        default=True,
        description="Batch trades for callbacks (more efficient)",
    )

    batch_size: int = Field(
        default=100,
        description="Trades per callback batch",
        gt=0,
        le=10000,
    )

    # WebSocket settings
    ping_interval: int = Field(
        default=20,
        description="WebSocket ping interval in seconds",
        ge=10,
    )

    ping_timeout: int = Field(
        default=10,
        description="WebSocket ping timeout in seconds",
        ge=5,
    )

    # Order book settings
    stream_orderbook: bool = Field(
        default=False,
        description="Enable order book depth streaming",
    )

    orderbook_update_speed: str = Field(
        default="100ms",
        description="Order book update speed: '100ms' or '1000ms'",
        pattern="^(100ms|1000ms)$",
    )

    orderbook_depth_levels: int = Field(
        default=20,
        description="Number of depth levels to track (5, 10, or 20)",
        ge=5,
        le=20,
    )


class AnalyzerConfig(BaseModel):
    """Base configuration for analyzers."""

    enabled: bool = Field(
        default=True,
        description="Whether analyzer is active",
    )

    window_size: int = Field(
        default=60,
        description="Analysis window in seconds",
        gt=0,
        le=3600,
    )


class OrderFlowConfig(AnalyzerConfig):
    """Order flow analyzer configuration."""

    compute_toxicity: bool = Field(
        default=True,
        description="Compute order flow toxicity metrics",
    )

    persistence_test: bool = Field(
        default=True,
        description="Perform trade direction persistence tests",
    )

    imbalance_threshold: float = Field(
        default=0.1,
        description="Threshold for flagging significant order imbalance",
        ge=0.0,
        le=1.0,
    )


class LiquidityConfig(AnalyzerConfig):
    """Liquidity analyzer configuration."""

    depth_levels: int = Field(
        default=10,
        description="Order book depth levels to analyze",
        ge=1,
        le=100,
    )

    spread_method: str = Field(
        default="mid",
        description="Spread calculation method: 'mid', 'best', or 'effective'",
        pattern="^(mid|best|effective)$",
    )

    min_spread_threshold: float = Field(
        default=0.0001,
        description="Minimum spread (as fraction) to consider valid",
        ge=0.0,
    )


class VolumeProfileConfig(AnalyzerConfig):
    """Volume profile analyzer configuration."""

    price_bins: int = Field(
        default=50,
        description="Number of price bins for volume histogram",
        ge=10,
        le=500,
    )

    vwap_decay: float = Field(
        default=0.99,
        description="VWAP exponential decay factor (0-1, higher = slower decay)",
        gt=0.0,
        le=1.0,
    )

    value_area_percent: float = Field(
        default=0.70,
        description="Percent of volume for value area calculation",
        gt=0.0,
        le=1.0,
    )


class TradeIntensityConfig(AnalyzerConfig):
    """Trade intensity analyzer configuration."""

    burst_zscore_threshold: float = Field(
        default=3.0,
        description="Z-score threshold for volume burst detection",
        gt=0.0,
    )

    ewma_alpha: float = Field(
        default=0.05,
        description="Exponential weighting factor for arrival rate (0-1)",
        gt=0.0,
        le=1.0,
    )


class PriceImpactConfig(AnalyzerConfig):
    """Price impact analyzer configuration."""

    regression_window: int = Field(
        default=100,
        description="Number of trades for regression analysis",
        ge=10,
        le=10000,
    )

    impact_decay_periods: int = Field(
        default=10,
        description="Number of periods to analyze impact decay",
        ge=1,
        le=100,
    )


class MetricsConfig(BaseModel):
    """Metrics aggregator configuration."""

    windows: List[int] = Field(
        default=[1, 5, 30, 60],
        description="Window sizes in seconds for aggregations",
        min_length=1,
    )

    publish_interval: float = Field(
        default=1.0,
        description="Metric publication interval in seconds",
        gt=0.0,
        le=60.0,
    )

    max_history: int = Field(
        default=3600,
        description="Maximum history to keep in seconds",
        gt=0,
    )


class PublisherConfig(BaseModel):
    """Event publisher configuration."""

    backend: str = Field(
        default="memory",
        description="Backend type: 'memory' or 'redis'",
        pattern="^(memory|redis)$",
    )

    redis_url: Optional[str] = Field(
        default=None,
        description="Redis connection URL (required if backend='redis')",
    )

    max_queue_size: int = Field(
        default=10000,
        description="Maximum messages in queue before blocking",
        gt=0,
    )

    batch_publish: bool = Field(
        default=True,
        description="Batch messages for efficient publishing",
    )

    batch_interval: float = Field(
        default=0.1,
        description="Batch interval in seconds",
        gt=0.0,
    )


class StreamingConfig(BaseModel):
    """Complete streaming system configuration."""

    consumer: ConsumerConfig = Field(
        default_factory=ConsumerConfig,
        description="Real-time consumer configuration",
    )

    order_flow: OrderFlowConfig = Field(
        default_factory=OrderFlowConfig,
        description="Order flow analyzer configuration",
    )

    liquidity: LiquidityConfig = Field(
        default_factory=LiquidityConfig,
        description="Liquidity analyzer configuration",
    )

    volume_profile: VolumeProfileConfig = Field(
        default_factory=VolumeProfileConfig,
        description="Volume profile analyzer configuration",
    )

    trade_intensity: TradeIntensityConfig = Field(
        default_factory=TradeIntensityConfig,
        description="Trade intensity analyzer configuration",
    )

    price_impact: PriceImpactConfig = Field(
        default_factory=PriceImpactConfig,
        description="Price impact analyzer configuration",
    )

    metrics: MetricsConfig = Field(
        default_factory=MetricsConfig,
        description="Metrics aggregator configuration",
    )

    publisher: PublisherConfig = Field(
        default_factory=PublisherConfig,
        description="Event publisher configuration",
    )

    class Config:
        """Pydantic configuration."""

        extra = "forbid"  # Raise error on unknown fields
        validate_assignment = True  # Validate on field assignment


def load_streaming_config(config_dict: dict) -> StreamingConfig:
    """
    Load streaming configuration from dictionary.

    Args:
        config_dict: Configuration dictionary (typically from YAML)

    Returns:
        Validated StreamingConfig instance

    Raises:
        ValidationError: If configuration is invalid
    """
    return StreamingConfig(**config_dict.get("streaming", {}))
