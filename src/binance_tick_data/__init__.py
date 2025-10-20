"""Binance tick data ingestion library."""

# Legacy imports (deprecated, use new modules)
from .config import BinanceConfig, get_config as get_legacy_config
from .sources import (
    binance_historical_data,
    binance_realtime_data,
)
from .repository import BinanceDataRepository as LegacyBinanceDataRepository
from .parquet_storage import ParquetStorage
from .pipelines import run_historical_pipeline, run_realtime_pipeline

# New configuration system (recommended)
from .db_config import (
    AppConfig,
    DatabaseConfig,
    TableConfig,
    PipelineConfig,
    BarThresholdsConfig,
    load_config,
    get_config,
    set_config,
)

# New repository with proper error handling (recommended)
from .repository_v2 import BinanceDataRepository

# Error hierarchy
from .errors import (
    BinanceDataError,
    DatabaseError,
    DatabaseNotFoundError,
    DatabaseConnectionError,
    TableNotFoundError,
    SchemaNotFoundError,
    DataError,
    NoDataFoundError,
    InvalidSymbolError,
    DataQualityError,
    InsufficientDataError,
    ConfigurationError,
    InvalidConfigurationError,
    APIError,
    RateLimitError,
    QueryError,
    InvalidDateRangeError,
)

# Dollar volume sampling
from .dollar_volume_sampling import (
    DollarVolumeSampler,
    create_dollar_volume_bars,
    calculate_optimal_threshold,
)

__version__ = "0.1.0"

__all__ = [
    # Legacy (kept for backwards compatibility)
    "BinanceConfig",
    "get_legacy_config",
    "binance_historical_data",
    "binance_realtime_data",
    "LegacyBinanceDataRepository",
    "ParquetStorage",
    "run_historical_pipeline",
    "run_realtime_pipeline",

    # New configuration system
    "AppConfig",
    "DatabaseConfig",
    "TableConfig",
    "PipelineConfig",
    "BarThresholdsConfig",
    "load_config",
    "get_config",
    "set_config",

    # New repository
    "BinanceDataRepository",

    # Errors
    "BinanceDataError",
    "DatabaseError",
    "DatabaseNotFoundError",
    "DatabaseConnectionError",
    "TableNotFoundError",
    "SchemaNotFoundError",
    "DataError",
    "NoDataFoundError",
    "InvalidSymbolError",
    "DataQualityError",
    "InsufficientDataError",
    "ConfigurationError",
    "InvalidConfigurationError",
    "APIError",
    "RateLimitError",
    "QueryError",
    "InvalidDateRangeError",

    # Dollar volume sampling
    "DollarVolumeSampler",
    "create_dollar_volume_bars",
    "calculate_optimal_threshold",
]
