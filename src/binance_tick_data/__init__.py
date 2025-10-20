"""Binance tick data ingestion library."""

from .config import BinanceConfig, get_config
from .sources import (
    binance_historical_data,
    binance_realtime_data,
)
from .repository import BinanceDataRepository
from .parquet_storage import ParquetStorage
from .pipelines import run_historical_pipeline, run_realtime_pipeline

__version__ = "0.1.0"

__all__ = [
    "BinanceConfig",
    "get_config",
    "binance_historical_data",
    "binance_realtime_data",
    "BinanceDataRepository",
    "ParquetStorage",
    "run_historical_pipeline",
    "run_realtime_pipeline",
]
