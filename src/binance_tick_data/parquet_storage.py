"""Parquet-based storage for Binance tick data.

Alternative to DuckDB for very large datasets.
Stores data as partitioned Parquet files for efficient querying.
"""

from typing import List, Optional, Union
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import duckdb


class ParquetStorage:
    """
    Store and query Binance data using Parquet files.

    Data is partitioned by symbol and date for efficient queries:
    data/
      ├── symbol=BTCUSDT/
      │   ├── date=2024-01-01/
      │   │   └── data.parquet
      │   └── date=2024-01-02/
      │       └── data.parquet
      └── symbol=ETHUSDT/
          └── ...
    """

    def __init__(self, base_path: Union[str, Path] = "data/parquet"):
        """
        Initialize Parquet storage.

        Args:
            base_path: Base directory for Parquet files
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def write_data(
        self,
        df: pd.DataFrame,
        table_name: str = "agg_trades",
        partition_cols: List[str] = None,
    ):
        """
        Write DataFrame to partitioned Parquet files.

        Args:
            df: DataFrame to write
            table_name: Table name (agg_trades, trades, etc.)
            partition_cols: Columns to partition by (default: ['symbol', 'date'])
        """
        if partition_cols is None:
            partition_cols = ['symbol', 'date']

        # Add date column if partitioning by date
        if 'date' in partition_cols and 'date' not in df.columns:
            df['date'] = pd.to_datetime(df['timestamp'], unit='ms').dt.date

        output_path = self.base_path / table_name

        # Write with Parquet partitioning
        df.to_parquet(
            output_path,
            engine='pyarrow',
            compression='zstd',  # Excellent compression
            partition_cols=partition_cols,
            index=False,
        )

        print(f"✓ Data written to {output_path}")

    def read_data(
        self,
        table_name: str = "agg_trades",
        symbol: Optional[str] = None,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        columns: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Read data from Parquet files with optional filtering.

        Args:
            table_name: Table name
            symbol: Filter by symbol
            start_date: Start date filter
            end_date: End date filter
            columns: Specific columns to read (None = all)

        Returns:
            DataFrame with filtered data
        """
        path = self.base_path / table_name

        if not path.exists():
            raise FileNotFoundError(f"No data found at {path}")

        # Build filters
        filters = []

        if symbol:
            filters.append(('symbol', '==', symbol))

        if start_date:
            if isinstance(start_date, str):
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            elif isinstance(start_date, datetime):
                start_date = start_date.date()
            filters.append(('date', '>=', start_date))

        if end_date:
            if isinstance(end_date, str):
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            elif isinstance(end_date, datetime):
                end_date = end_date.date()
            filters.append(('date', '<=', end_date))

        # Read with filters (PyArrow will skip irrelevant partitions)
        df = pd.read_parquet(
            path,
            engine='pyarrow',
            columns=columns,
            filters=filters if filters else None,
        )

        return df

    def query_with_duckdb(
        self,
        query: str,
        table_name: str = "agg_trades",
    ) -> pd.DataFrame:
        """
        Query Parquet files using DuckDB SQL.

        Args:
            query: SQL query (reference table as 'data')
            table_name: Table name

        Returns:
            Query results as DataFrame
        """
        path = self.base_path / table_name / "**/*.parquet"

        # DuckDB can query Parquet files directly without loading into memory
        conn = duckdb.connect(":memory:")

        # Register Parquet files as a table
        full_query = f"""
            CREATE VIEW data AS
            SELECT * FROM read_parquet('{path}');

            {query}
        """

        result = conn.execute(full_query).df()
        conn.close()

        return result

    def get_ohlcv(
        self,
        symbol: str,
        interval: str = "1m",
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        table_name: str = "agg_trades",
    ) -> pd.DataFrame:
        """
        Compute OHLCV data from trades.

        Args:
            symbol: Trading symbol
            interval: Time interval (1T, 5T, 1H, 1D)
            start_date: Start date
            end_date: End date
            table_name: Table name

        Returns:
            OHLCV DataFrame
        """
        # Read data
        df = self.read_data(
            table_name=table_name,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
        )

        if df.empty:
            return pd.DataFrame()

        # Convert timestamp to datetime
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        df['price'] = df['price'].astype(float)
        df['quantity'] = df['quantity'].astype(float)

        # Resample to create OHLCV
        df.set_index('datetime', inplace=True)

        ohlcv = df.resample(interval).agg({
            'price': ['first', 'max', 'min', 'last'],
            'quantity': 'sum',
            'agg_trade_id': 'count'
        })

        ohlcv.columns = ['open', 'high', 'low', 'close', 'volume', 'trades']
        ohlcv = ohlcv.dropna()

        return ohlcv.reset_index()

    def list_symbols(self, table_name: str = "agg_trades") -> List[str]:
        """Get list of available symbols."""
        path = self.base_path / table_name

        if not path.exists():
            return []

        # List symbol partitions
        symbols = []
        for symbol_dir in path.iterdir():
            if symbol_dir.is_dir() and symbol_dir.name.startswith('symbol='):
                symbol = symbol_dir.name.split('=')[1]
                symbols.append(symbol)

        return sorted(symbols)

    def get_date_range(
        self,
        symbol: str,
        table_name: str = "agg_trades"
    ) -> Optional[tuple]:
        """Get available date range for a symbol."""
        path = self.base_path / table_name / f"symbol={symbol}"

        if not path.exists():
            return None

        dates = []
        for date_dir in path.iterdir():
            if date_dir.is_dir() and date_dir.name.startswith('date='):
                date_str = date_dir.name.split('=')[1]
                dates.append(date_str)

        if not dates:
            return None

        return (min(dates), max(dates))

    def get_storage_stats(self) -> dict:
        """Get storage statistics."""
        import os

        stats = {}

        for table_dir in self.base_path.iterdir():
            if table_dir.is_dir():
                total_size = 0
                file_count = 0

                for root, dirs, files in os.walk(table_dir):
                    for file in files:
                        if file.endswith('.parquet'):
                            file_path = os.path.join(root, file)
                            total_size += os.path.getsize(file_path)
                            file_count += 1

                stats[table_dir.name] = {
                    'size_mb': total_size / (1024 * 1024),
                    'file_count': file_count,
                }

        return stats


def convert_duckdb_to_parquet(
    db_path: str = "dlt_binance.duckdb",
    output_path: str = "data/parquet",
    table_name: str = "agg_trades",
    dataset: str = "binance_historical",
):
    """
    Convert DuckDB database to partitioned Parquet files.

    Args:
        db_path: Path to DuckDB database
        output_path: Output directory for Parquet files
        table_name: Table name to convert
        dataset: Dataset name in DuckDB
    """
    print(f"Converting {dataset}.{table_name} to Parquet...")

    conn = duckdb.connect(db_path, read_only=True)

    # Read data in chunks
    query = f"SELECT * FROM {dataset}.{table_name}"
    df = conn.execute(query).df()

    print(f"  Loaded {len(df):,} records")

    # Add date column
    df['date'] = pd.to_datetime(df['timestamp'], unit='ms').dt.date

    # Write to partitioned Parquet
    storage = ParquetStorage(output_path)
    storage.write_data(df, table_name, partition_cols=['symbol', 'date'])

    conn.close()

    # Show stats
    stats = storage.get_storage_stats()
    if table_name in stats:
        print(f"  Output: {stats[table_name]['size_mb']:.2f} MB in {stats[table_name]['file_count']} files")


# Example usage
if __name__ == "__main__":
    # Example: Convert DuckDB to Parquet
    print("Parquet Storage Example\n" + "=" * 60)

    # Check if DuckDB exists
    import os
    if os.path.exists("dlt_binance.duckdb"):
        print("\n1. Converting DuckDB to Parquet...")
        convert_duckdb_to_parquet()

        print("\n2. Reading from Parquet...")
        storage = ParquetStorage()

        # List symbols
        symbols = storage.list_symbols()
        print(f"\n   Available symbols: {symbols}")

        if symbols:
            symbol = symbols[0]
            print(f"\n3. Querying {symbol} data...")

            # Get last 7 days
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)

            df = storage.read_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
            )

            print(f"   Retrieved {len(df):,} records")

            # Get OHLCV
            print(f"\n4. Generating OHLCV (1H)...")
            ohlcv = storage.get_ohlcv(
                symbol=symbol,
                interval="1H",
                start_date=start_date,
                end_date=end_date,
            )

            print(f"   Generated {len(ohlcv)} candles")
            if not ohlcv.empty:
                print("\n   Last 5 candles:")
                print(ohlcv.tail())

            # Storage stats
            print(f"\n5. Storage Statistics:")
            stats = storage.get_storage_stats()
            for table, info in stats.items():
                print(f"   {table}: {info['size_mb']:.2f} MB ({info['file_count']} files)")
    else:
        print("\n✗ No DuckDB database found. Run historical pipeline first:")
        print("  uv run python pipelines/historical_pipeline.py --symbols BTCUSDT")
