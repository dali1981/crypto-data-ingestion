"""
Centralized database configuration using Pydantic and OmegaConf.

This module provides type-safe configuration with validation, preventing
the issue of different scripts pointing to different database locations.
"""

import os
from pathlib import Path
from typing import Optional, Dict
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from omegaconf import OmegaConf
import logging

logger = logging.getLogger(__name__)


class DatabaseConfig(BaseModel):
    """Database connection configuration."""

    db_path: str = Field(
        default="binance_pipeline.duckdb",
        description="Path to DuckDB database file"
    )
    catalog_name: str = Field(
        default="binance_pipeline",
        description="Database catalog name"
    )
    schema_name: str = Field(
        default="binance_data",
        description="Database schema name"
    )
    read_only: bool = Field(
        default=True,
        description="Open database in read-only mode (default: True for safe concurrent access)"
    )

    @field_validator('db_path')
    @classmethod
    def validate_db_path(cls, v: str) -> str:
        """Ensure database path is a string."""
        return str(v)

    @property
    def full_schema_path(self) -> str:
        """Get the full schema path for queries."""
        # Only include catalog if it's not empty or None
        if self.catalog_name and self.catalog_name.strip():
            return f"{self.catalog_name}.{self.schema_name}"
        return self.schema_name

    @property
    def schema(self) -> str:
        """
        Get schema name (backward compatibility property).

        Returns the schema_name for convenient access.
        """
        return self.schema_name

    @property
    def catalog(self) -> str:
        """
        Get catalog name (backward compatibility property).

        Returns the catalog_name for convenient access.
        """
        return self.catalog_name

    @property
    def path(self) -> Path:
        """
        Get database path as Path object.

        Returns absolute path to database file.
        """
        return Path(self.db_path).absolute()

    def get_table_path(self, table_name: str) -> str:
        """Get the fully qualified table name."""
        return f"{self.full_schema_path}.{table_name}"

    def db_exists(self) -> bool:
        """Check if database file exists."""
        return Path(self.db_path).exists()


class TableConfig(BaseModel):
    """Configuration for database tables."""

    # Core data tables
    agg_trades: str = "agg_trades"
    trades: str = "trades"
    order_book_snapshots: str = "order_book_snapshots"
    klines: str = "klines"

    # Derived/computed tables
    dollar_bars: str = "dollar_bars"
    volume_bars: str = "volume_bars"
    tick_bars: str = "tick_bars"

    # Real-time tables
    realtime_trades: str = "realtime_trades"
    realtime_order_book: str = "realtime_order_book"

    def list_data_tables(self) -> list:
        """List all data tables (excluding metadata)."""
        return [
            self.agg_trades,
            self.trades,
            self.order_book_snapshots,
            self.klines,
            self.dollar_bars,
            self.volume_bars,
            self.tick_bars,
            self.realtime_trades,
            self.realtime_order_book,
        ]


class BarThresholdsConfig(BaseModel):
    """Configuration for bar sampling thresholds."""

    # Dollar bar thresholds by symbol (in USD)
    dollar_bars: Dict[str, float] = Field(
        default={
            "BTCUSDT": 1_000_000,
            "ETHUSDT": 500_000,
            "BNBUSDT": 100_000,
            "default": 100_000,
        }
    )

    # Volume bar thresholds by symbol (in base asset units)
    volume_bars: Dict[str, float] = Field(
        default={
            "BTCUSDT": 10.0,
            "ETHUSDT": 100.0,
            "BNBUSDT": 1000.0,
            "default": 1000.0,
        }
    )

    # Tick bar sizes by symbol (number of ticks)
    tick_bars: Dict[str, int] = Field(
        default={
            "BTCUSDT": 1000,
            "ETHUSDT": 1000,
            "BNBUSDT": 500,
            "default": 500,
        }
    )

    def get_dollar_threshold(self, symbol: str) -> float:
        """Get dollar bar threshold for a symbol."""
        return self.dollar_bars.get(symbol, self.dollar_bars.get("default", 100_000))

    def get_volume_threshold(self, symbol: str) -> float:
        """Get volume bar threshold for a symbol."""
        return self.volume_bars.get(symbol, self.volume_bars.get("default", 1000.0))

    def get_tick_size(self, symbol: str) -> int:
        """Get tick bar size for a symbol."""
        return self.tick_bars.get(symbol, self.tick_bars.get("default", 500))


class PipelineConfig(BaseModel):
    """Configuration for data pipeline processing."""

    default_batch_size: int = Field(
        default=10000,
        description="Default batch size for processing"
    )
    bar_thresholds: BarThresholdsConfig = Field(
        default_factory=BarThresholdsConfig
    )


class AppConfig(BaseSettings):
    """
    Main application configuration.

    Supports loading from:
    1. config.yaml file
    2. Environment variables (prefixed with BINANCE_)
    3. Default values
    """

    model_config = SettingsConfigDict(
        env_prefix="BINANCE_",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="allow",  # Allow extra fields for forward compatibility
    )

    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    tables: TableConfig = Field(default_factory=TableConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)

    @property
    def db_path(self) -> str:
        """
        Convenience property for database path.

        Returns the database path, making it easier to access from config.
        """
        return self.database.db_path

    @property
    def schema(self) -> str:
        """
        Convenience property for schema name.

        Returns the schema name from database config.
        """
        return self.database.schema_name

    @property
    def catalog(self) -> str:
        """
        Convenience property for catalog name.

        Returns the catalog name from database config.
        """
        return self.database.catalog_name

    def get_table_path(self, table_name: str) -> str:
        """
        Convenience method to get fully qualified table path.

        Args:
            table_name: Name of the table

        Returns:
            Fully qualified table path (catalog.schema.table)
        """
        return self.database.get_table_path(table_name)

    @classmethod
    def from_yaml(cls, config_path: str | Path) -> "AppConfig":
        """Load configuration from YAML file."""
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        # Load YAML using OmegaConf
        omega_conf = OmegaConf.load(config_path)

        # Convert to dict and create Pydantic model
        config_dict = OmegaConf.to_container(omega_conf, resolve=True)
        return cls(**config_dict)

    @classmethod
    def from_yaml_or_default(cls, config_path: Optional[str | Path] = None) -> "AppConfig":
        """
        Load configuration from YAML file if it exists, otherwise use defaults.

        Looks for config in the following order:
        1. Provided config_path
        2. ./config.yaml
        3. ./config/binance.yaml
        4. Default values
        """
        if config_path:
            path = Path(config_path)
            if path.exists():
                logger.info(f"Loading config from: {path}")
                return cls.from_yaml(path)

        # Try default locations
        default_paths = [
            Path("config.yaml"),
            Path("config/binance.yaml"),
            Path("binance_config.yaml"),
        ]

        for path in default_paths:
            if path.exists():
                logger.info(f"Loading config from: {path}")
                return cls.from_yaml(path)

        # No config file found, use defaults
        logger.info("No config file found, using defaults with environment overrides")
        return cls()

    def save_yaml(self, output_path: str | Path):
        """Save configuration to YAML file."""
        output_path = Path(output_path)

        # Convert Pydantic model to dict
        config_dict = self.model_dump()

        # Convert to OmegaConf and save
        omega_conf = OmegaConf.create(config_dict)
        OmegaConf.save(omega_conf, output_path)
        logger.info(f"Configuration saved to: {output_path}")

    def validate_setup(self) -> Dict[str, any]:
        """Validate configuration and database setup."""
        status = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "info": {}
        }

        # Check database file
        if not self.database.db_exists():
            status["warnings"].append(
                f"Database file '{self.database.db_path}' does not exist. "
                "It will be created on first write."
            )

        # Info about configuration
        status["info"]["database_path"] = self.database.db_path
        status["info"]["schema_path"] = self.database.full_schema_path
        status["info"]["using_env_vars"] = any(
            key.startswith("BINANCE_") for key in os.environ
        )

        # Check for environment variable overrides
        env_overrides = []
        for key in os.environ:
            if key.startswith("BINANCE_"):
                env_overrides.append(f"{key}={os.environ[key]}")

        if env_overrides:
            status["info"]["env_overrides"] = env_overrides

        return status


def load_config(config_path: Optional[str | Path] = None) -> AppConfig:
    """
    Convenience function to load configuration.

    Usage:
        config = load_config()  # Use defaults/env vars
        config = load_config("my_config.yaml")  # Load from file
    """
    return AppConfig.from_yaml_or_default(config_path)


# Global configuration instance (lazy loaded)
_global_config: Optional[AppConfig] = None


def get_config(reload: bool = False) -> AppConfig:
    """
    Get the global configuration instance.

    Args:
        reload: Force reload configuration from file/environment

    Returns:
        AppConfig instance
    """
    global _global_config

    if _global_config is None or reload:
        _global_config = load_config()

    return _global_config


def set_config(config: AppConfig):
    """Set the global configuration instance."""
    global _global_config
    _global_config = config