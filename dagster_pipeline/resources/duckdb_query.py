"""Read-only DuckDB query resource for Dagster.

Used for querying Parquet files via DuckDB views.
Read-only mode allows concurrent access from multiple workers.
"""

from dagster import ConfigurableResource
import duckdb
import pandas as pd
from pathlib import Path
from dagster_pipeline.config import DB_PATH, DATASET_NAME


class DuckDBQueryResource(ConfigurableResource):
    """
    Read-only DuckDB resource for querying Parquet files.

    Benefits:
    - No file locks (read-only mode)
    - Multiple workers can query concurrently
    - Queries Parquet files directly (no loading)
    - Uses DuckDB views created by I/O manager
    """

    db_path: str = DB_PATH
    dataset_name: str = DATASET_NAME

    def query(self, sql: str) -> pd.DataFrame:
        """
        Execute SQL query and return DataFrame.

        Args:
            sql: SQL query string

        Returns:
            Query results as DataFrame
        """
        # Use read-only connection (allows concurrent access)
        conn = duckdb.connect(self.db_path, read_only=True)
        try:
            result = conn.execute(sql).df()
            return result
        finally:
            conn.close()

    def query_parquet(self, parquet_path: str, sql: str) -> pd.DataFrame:
        """
        Query Parquet files directly without DuckDB views.

        Args:
            parquet_path: Path pattern to Parquet files (e.g., 'data/parquet/**/*.parquet')
            sql: SQL query (use 'data' as table name)

        Returns:
            Query results as DataFrame
        """
        # In-memory connection (no file lock)
        conn = duckdb.connect(":memory:")
        try:
            # Register Parquet files as a table
            full_query = f"""
                CREATE VIEW data AS
                SELECT * FROM read_parquet('{parquet_path}');

                {sql}
            """
            result = conn.execute(full_query).df()
            return result
        finally:
            conn.close()

    def table_exists(self, table_name: str) -> bool:
        """Check if a table/view exists."""
        conn = duckdb.connect(self.db_path, read_only=True)
        try:
            result = conn.execute(f"""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema = '{self.dataset_name}'
                AND table_name = '{table_name}'
            """).fetchone()
            return result[0] > 0 if result else False
        except Exception:
            return False
        finally:
            conn.close()

    def get_row_count(self, table_name: str) -> int:
        """Get row count for a table."""
        try:
            result = self.query(f"SELECT COUNT(*) FROM {self.dataset_name}.{table_name}")
            return int(result.iloc[0, 0]) if not result.empty else 0
        except Exception:
            return 0


# Default resource instance
duckdb_query_resource = DuckDBQueryResource(
    db_path=DB_PATH,
    dataset_name=DATASET_NAME
)
