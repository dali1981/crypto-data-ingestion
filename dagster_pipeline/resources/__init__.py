"""Resource definitions for Dagster pipeline."""

from .binance_api import BinanceAPIResource, binance_api_resource
from .duckdb import DuckDBResource, duckdb_resource

__all__ = [
    "BinanceAPIResource",
    "binance_api_resource",
    "DuckDBResource",
    "duckdb_resource",
]
