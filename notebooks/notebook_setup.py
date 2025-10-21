"""
Notebook setup utilities for handling paths and configuration.

This module provides helper functions to ensure notebooks work
regardless of which directory they're run from.
"""

import sys
from pathlib import Path
import os


def setup_notebook_environment():
    """
    Set up the notebook environment for proper imports and database access.

    This function:
    1. Finds the project root directory
    2. Changes to the project root
    3. Adds src to Python path if needed
    4. Returns the project root path

    Returns:
        Path: The project root directory
    """
    # Get current notebook directory
    current_dir = Path.cwd()

    # Find project root (contains pyproject.toml or src directory)
    project_root = current_dir
    while project_root != project_root.parent:
        if (project_root / 'pyproject.toml').exists() or \
           (project_root / 'src' / 'binance_tick_data').exists():
            break
        project_root = project_root.parent

    # Change to project root
    if current_dir != project_root:
        os.chdir(project_root)
        print(f"📁 Changed directory to project root: {project_root}")

    # Add src to path if needed
    src_path = project_root / 'src'
    if src_path.exists() and str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
        print(f"📦 Added to Python path: {src_path}")

    return project_root


def get_database_path(config=None):
    """
    Get the absolute path to the database.

    Args:
        config: Optional AppConfig object. If None, loads default config.

    Returns:
        Path: Absolute path to the database file
    """
    if config is None:
        from binance_tick_data.db_config import get_config
        config = get_config()

    db_path = Path(config.database.db_path)

    # If relative path, make it absolute from project root
    if not db_path.is_absolute():
        project_root = Path.cwd()
        db_path = (project_root / db_path).absolute()

    return db_path


def check_database_exists(config=None):
    """
    Check if the database exists and print status.

    Args:
        config: Optional AppConfig object

    Returns:
        bool: True if database exists, False otherwise
    """
    db_path = get_database_path(config)
    exists = db_path.exists()

    if exists:
        size_mb = db_path.stat().st_size / 1024 / 1024
        print(f"✅ Database found: {db_path}")
        print(f"   Size: {size_mb:.2f} MB")
    else:
        print(f"⚠️  Database not found: {db_path}")
        print(f"   The database will be created on first write.")

    return exists


def print_config_info(config):
    """
    Print configuration information in a readable format.

    Args:
        config: AppConfig object
    """
    print("Configuration Information")
    print("=" * 60)
    print(f"Database path: {config.database.db_path}")
    print(f"  Absolute: {get_database_path(config)}")
    print(f"Schema: {config.database.schema}")
    print(f"Catalog: {config.database.catalog}")
    print(f"Read-only: {config.database.read_only}")
    print(f"\nFully qualified paths:")
    print(f"  Aggregated trades: {config.get_table_path('agg_trades')}")
    print(f"  Trades: {config.get_table_path('trades')}")
    print(f"  Order book: {config.get_table_path('order_book_snapshots')}")
    print()


def initialize_notebook():
    """
    Complete notebook initialization routine.

    This is the main function to call at the start of any notebook.
    It handles:
    - Path setup
    - Configuration loading
    - Database verification
    - Import verification

    Returns:
        tuple: (project_root, config) - Project root path and loaded config
    """
    print("Initializing notebook environment...")
    print()

    # Setup paths
    project_root = setup_notebook_environment()
    print()

    # Load config
    from binance_tick_data.db_config import get_config
    config = get_config()

    # Print config
    print_config_info(config)

    # Check database
    check_database_exists(config)
    print()

    # Verify imports
    try:
        from binance_tick_data.repository_v2 import BinanceDataRepository
        from binance_tick_data.dollar_volume_sampling import DollarVolumeSampler
        print("✅ All imports successful")
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   Make sure the package is installed: uv sync")

    print()
    print("=" * 60)
    print("✨ Notebook environment ready!")
    print("=" * 60)
    print()

    return project_root, config
