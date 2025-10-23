"""Parquet I/O Manager for Dagster assets.

Stores assets as partitioned Parquet files and creates DuckDB views for querying.
This enables concurrent writes (each worker writes to separate files).
"""

from dagster import (
    IOManager,
    InputContext,
    OutputContext,
    io_manager,
)
import pandas as pd
import duckdb
from pathlib import Path
from datetime import datetime
from typing import Union
from dagster_pipeline.config import DB_PATH


class ParquetIOManager(IOManager):
    """
    I/O Manager that stores assets as Parquet files.

    Benefits:
    - No file locks (each partition writes to separate file)
    - Efficient partitioning by symbol and date
    - DuckDB can query Parquet directly (no loading)
    - Time-travel: historical files preserved
    """

    def __init__(self, base_path: str = "data/parquet", duckdb_path: str = DB_PATH):
        self.base_path = Path(base_path)
        self.duckdb_path = duckdb_path
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_path(self, context: Union[OutputContext, InputContext]) -> Path:
        """Get storage path for an asset."""
        # Use asset key as table name
        asset_name = "_".join(context.asset_key.path)

        # For outputs, include timestamp in filename for append behavior
        if isinstance(context, OutputContext):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            return self.base_path / asset_name / f"data_{timestamp}.parquet"
        else:
            # For inputs, read all files in directory
            return self.base_path / asset_name

    def handle_output(self, context: OutputContext, obj: pd.DataFrame):
        """
        Store asset output as Parquet file.

        Args:
            context: Output context with asset metadata
            obj: DataFrame to store
        """
        if obj is None or (isinstance(obj, pd.DataFrame) and obj.empty):
            context.log.info("No data to store")
            return

        # Convert to DataFrame if needed
        if not isinstance(obj, pd.DataFrame):
            if isinstance(obj, dict):
                # Handle dict outputs (like from raw_agg_trades)
                context.log.info(f"Received dict output with keys: {obj.keys()}")
                # Store metadata only, actual data already in Parquet via dlt
                return
            context.log.warning(f"Unexpected output type: {type(obj)}")
            return

        path = self._get_path(context)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Add date column for partitioning if timestamp exists
        if 'timestamp' in obj.columns:
            obj['date'] = pd.to_datetime(obj['timestamp'], unit='ms').dt.date

        # Write to Parquet with compression
        obj.to_parquet(
            path,
            engine='pyarrow',
            compression='zstd',
            index=False,
        )

        context.log.info(f"Stored {len(obj):,} rows to {path}")

        # Create/update DuckDB view
        self._update_duckdb_view(context)

    def load_input(self, context: InputContext) -> pd.DataFrame:
        """
        Load asset input from Parquet files.

        Args:
            context: Input context with asset metadata

        Returns:
            DataFrame with asset data
        """
        path = self._get_path(context)

        if not path.exists():
            context.log.warning(f"No data found at {path}")
            return pd.DataFrame()

        # Read all Parquet files in directory
        pattern = str(path / "*.parquet")

        try:
            df = pd.read_parquet(pattern, engine='pyarrow')
            context.log.info(f"Loaded {len(df):,} rows from {path}")
            return df
        except Exception as e:
            context.log.error(f"Failed to load from {path}: {e}")
            return pd.DataFrame()

    def _update_duckdb_view(self, context: OutputContext):
        """
        Create or update DuckDB view over Parquet files.

        This allows querying Parquet files using SQL without loading into memory.
        """
        try:
            asset_name = "_".join(context.asset_key.path)
            parquet_path = self.base_path / asset_name / "*.parquet"

            # Connect to DuckDB
            conn = duckdb.connect(self.duckdb_path)

            # Create schema if needed
            conn.execute("CREATE SCHEMA IF NOT EXISTS binance_data;")

            # Create view over Parquet files
            view_query = f"""
                CREATE OR REPLACE VIEW binance_data.{asset_name} AS
                SELECT * FROM read_parquet('{parquet_path}')
            """
            conn.execute(view_query)

            context.log.info(f"Updated DuckDB view: binance_data.{asset_name}")

            conn.close()

        except Exception as e:
            context.log.warning(f"Failed to create DuckDB view: {e}")


@io_manager
def parquet_io_manager(init_context):
    """Factory function for ParquetIOManager with default configuration."""
    base_path = init_context.resource_config.get("base_path", "data/parquet") if init_context.resource_config else "data/parquet"
    duckdb_path = init_context.resource_config.get("duckdb_path", DB_PATH) if init_context.resource_config else DB_PATH

    return ParquetIOManager(
        base_path=base_path,
        duckdb_path=duckdb_path,
    )
