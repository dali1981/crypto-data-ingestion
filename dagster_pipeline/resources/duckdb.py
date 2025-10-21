"""DuckDB resource for Dagster."""

from dagster import ConfigurableResource
import duckdb
from pathlib import Path
from ..config import DB_PATH, DATASET_NAME


class DuckDBResource(ConfigurableResource):
    """DuckDB connection resource."""

    db_path: str = DB_PATH
    dataset_name: str = DATASET_NAME
    read_only: bool = False

    def get_connection(self):
        """Get DuckDB connection instance."""
        return duckdb.connect(self.db_path, read_only=self.read_only)

    def database_exists(self) -> bool:
        """Check if database file exists."""
        return Path(self.db_path).exists()

    def get_table_count(self, table_name: str) -> int:
        """Get row count for a table."""
        if not self.database_exists():
            return 0

        try:
            conn = self.get_connection()
            result = conn.execute(f"""
                SELECT COUNT(*)
                FROM {self.dataset_name}.{table_name}
            """).fetchone()
            conn.close()
            return result[0] if result else 0
        except Exception:
            return 0


# Default resource instance
duckdb_resource = DuckDBResource(
    db_path=DB_PATH,
    dataset_name=DATASET_NAME,
    read_only=False
)
