"""Resource definitions for Dagster pipeline."""

from .binance_api import BinanceAPIResource, binance_api_resource
from .duckdb import DuckDBResource, duckdb_resource
from .duckdb_query import DuckDBQueryResource, duckdb_query_resource
from .parquet_io_manager import ParquetIOManager, parquet_io_manager

__all__ = [
    "BinanceAPIResource",
    "binance_api_resource",
    "DuckDBResource",
    "duckdb_resource",
    "DuckDBQueryResource",
    "duckdb_query_resource",
    "ParquetIOManager",
    "parquet_io_manager",
]
