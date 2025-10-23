"""Configuration management for Binance tick data ingestion."""

from dataclasses import dataclass, field
from typing import List
from pathlib import Path


@dataclass
class BinanceConfig:
    """Configuration for Binance data ingestion."""

    # Trading symbols to track (format: BTCUSDT, ETHUSDT, etc.)
    symbols: List[str] = field(default_factory=lambda: [
        "BTCUSDT",
        "ETHUSDT",
        "BNBUSDT",
    ])

    # API configuration
    api_key: str = ""  # Optional, for higher rate limits
    api_secret: str = ""  # Optional

    # Data storage
    data_dir: Path = field(default_factory=lambda: Path("./data"))
    pipeline_name: str = "binance_tick_data"

    # Historical data settings
    historical_start_date: str = "2024-01-01"  # Format: YYYY-MM-DD
    historical_batch_size: int = 1000  # Number of records per API call (Binance limit)
    historical_max_records: int = None  # Max total records for testing (None = unlimited)

    # Incremental loading settings
    incremental_batch_size: int = 50000  # Max records per incremental run (prevents long-running jobs)

    # Real-time streaming settings
    stream_buffer_size: int = 100  # Buffer size before flushing to storage
    reconnect_delay: int = 5  # Seconds to wait before reconnecting WebSocket

    # Rate limiting
    max_requests_per_minute: int = 1200  # Binance limit for REST API

    def __post_init__(self):
        """Ensure data directory exists."""
        self.data_dir = Path(self.data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)


# Default configuration instance
default_config = BinanceConfig()


def get_config() -> BinanceConfig:
    """Get the default configuration."""
    return default_config
