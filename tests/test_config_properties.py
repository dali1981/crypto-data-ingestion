"""
Test configuration properties for backward compatibility and encapsulation.

These tests ensure that:
1. Properties provide convenient access to internal fields
2. Changes to internal structure don't break external code
3. Both direct and property-based access work correctly
"""

import pytest
from pathlib import Path
from binance_tick_data.db_config import (
    DatabaseConfig,
    TableConfig,
    AppConfig,
    get_config,
    load_config
)


class TestDatabaseConfigProperties:
    """Test DatabaseConfig properties and encapsulation."""

    def test_schema_property(self):
        """Test schema property returns schema_name."""
        config = DatabaseConfig(schema_name="test_schema")
        assert config.schema == "test_schema"
        assert config.schema == config.schema_name

    def test_catalog_property(self):
        """Test catalog property returns catalog_name."""
        config = DatabaseConfig(catalog_name="test_catalog")
        assert config.catalog == "test_catalog"
        assert config.catalog == config.catalog_name

    def test_path_property(self):
        """Test path property returns absolute Path object."""
        config = DatabaseConfig(db_path="test.duckdb")
        assert isinstance(config.path, Path)
        assert config.path.is_absolute()
        assert config.path.name == "test.duckdb"

    def test_full_schema_path_with_catalog(self):
        """Test full_schema_path includes catalog when present."""
        config = DatabaseConfig(
            catalog_name="my_catalog",
            schema_name="my_schema"
        )
        assert config.full_schema_path == "my_catalog.my_schema"

    def test_full_schema_path_without_catalog(self):
        """Test full_schema_path excludes empty catalog."""
        config = DatabaseConfig(
            catalog_name="",
            schema_name="my_schema"
        )
        assert config.full_schema_path == "my_schema"

    def test_get_table_path(self):
        """Test get_table_path returns fully qualified name."""
        config = DatabaseConfig(
            catalog_name="catalog",
            schema_name="schema"
        )
        assert config.get_table_path("my_table") == "catalog.schema.my_table"

    def test_db_exists(self):
        """Test db_exists checks file existence."""
        # Non-existent file
        config = DatabaseConfig(db_path="/tmp/nonexistent_db.duckdb")
        assert not config.db_exists()

        # Use a path we know exists
        config = DatabaseConfig(db_path=__file__)  # This test file exists
        assert config.db_exists()

    def test_backward_compatibility_access(self):
        """Test that both old and new access patterns work."""
        config = DatabaseConfig(
            db_path="test.db",
            catalog_name="cat",
            schema_name="sch"
        )

        # New property access
        assert config.schema == "sch"
        assert config.catalog == "cat"

        # Direct field access still works
        assert config.schema_name == "sch"
        assert config.catalog_name == "cat"
        assert config.db_path == "test.db"


class TestAppConfigProperties:
    """Test AppConfig convenience properties."""

    def test_db_path_property(self):
        """Test db_path convenience property."""
        config = AppConfig()
        assert config.db_path == config.database.db_path

    def test_schema_property(self):
        """Test schema convenience property."""
        config = AppConfig()
        assert config.schema == config.database.schema_name

    def test_catalog_property(self):
        """Test catalog convenience property."""
        config = AppConfig()
        assert config.catalog == config.database.catalog_name

    def test_get_table_path_method(self):
        """Test get_table_path convenience method."""
        config = AppConfig()
        table_path = config.get_table_path("test_table")
        expected = config.database.get_table_path("test_table")
        assert table_path == expected

    def test_nested_access_patterns(self):
        """Test various nested access patterns work."""
        config = AppConfig()

        # Pattern 1: Top-level convenience
        assert config.db_path is not None
        assert config.schema is not None
        assert config.catalog is not None

        # Pattern 2: Through database object
        assert config.database.schema is not None
        assert config.database.catalog is not None
        assert config.database.path is not None

        # Pattern 3: Direct field access
        assert config.database.db_path is not None
        assert config.database.schema_name is not None
        assert config.database.catalog_name is not None


class TestTableConfig:
    """Test TableConfig structure."""

    def test_default_table_names(self):
        """Test default table names are set."""
        config = TableConfig()
        assert config.agg_trades == "agg_trades"
        assert config.trades == "trades"
        assert config.order_book_snapshots == "order_book_snapshots"
        assert config.klines == "klines"

    def test_list_data_tables(self):
        """Test list_data_tables returns all tables."""
        config = TableConfig()
        tables = config.list_data_tables()
        assert "agg_trades" in tables
        assert "trades" in tables
        assert "order_book_snapshots" in tables
        assert len(tables) == 9  # All data tables


class TestConfigLoading:
    """Test configuration loading and global config."""

    def test_get_config_returns_appconfig(self):
        """Test get_config returns AppConfig instance."""
        config = get_config()
        assert isinstance(config, AppConfig)

    def test_get_config_singleton(self):
        """Test get_config returns same instance."""
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2

    def test_get_config_reload(self):
        """Test get_config reload parameter."""
        config1 = get_config()
        config2 = get_config(reload=True)
        # After reload, should have same values but potentially new instance
        assert config2.database.db_path == config1.database.db_path

    def test_load_config_returns_new_instance(self):
        """Test load_config returns new instance each time."""
        config1 = load_config()
        config2 = load_config()
        assert isinstance(config1, AppConfig)
        assert isinstance(config2, AppConfig)
        # Different instances
        assert config1 is not config2


class TestNotebookUsagePatterns:
    """Test common notebook usage patterns work correctly."""

    def test_notebook_pattern_config_info(self):
        """Test pattern: print config info in notebook."""
        config = get_config()

        # This pattern should work
        db_path = config.database.db_path
        schema = config.database.schema
        catalog = config.database.catalog

        assert db_path is not None
        assert schema is not None
        assert catalog is not None

    def test_notebook_pattern_table_paths(self):
        """Test pattern: get table paths in notebook."""
        config = get_config()

        # These patterns should work
        agg_trades_path = config.get_table_path('agg_trades')
        trades_path = config.database.get_table_path('trades')

        assert 'agg_trades' in agg_trades_path
        assert 'trades' in trades_path
        assert '.' in agg_trades_path  # Has schema qualification

    def test_notebook_pattern_repository_init(self):
        """Test pattern: initialize repository with config."""
        config = get_config()

        # This pattern should work
        db_path = config.database.db_path
        read_only = config.database.read_only

        assert isinstance(db_path, str)
        assert isinstance(read_only, bool)

    def test_notebook_pattern_multiple_access_styles(self):
        """Test that notebooks can use various access styles."""
        config = get_config()

        # All these should return same value
        schema1 = config.schema
        schema2 = config.database.schema
        schema3 = config.database.schema_name

        assert schema1 == schema2 == schema3

        # All these should return same value
        catalog1 = config.catalog
        catalog2 = config.database.catalog
        catalog3 = config.database.catalog_name

        assert catalog1 == catalog2 == catalog3


class TestRepositoryProperties:
    """Test BinanceDataRepository properties."""

    def test_repository_db_path_property(self):
        """Test repository db_path property."""
        from binance_tick_data.repository_v2 import BinanceDataRepository

        config = AppConfig()
        repo = BinanceDataRepository(config=config)

        assert repo.db_path == config.database.db_path

    def test_repository_read_only_property(self):
        """Test repository read_only property."""
        from binance_tick_data.repository_v2 import BinanceDataRepository

        config = AppConfig()
        repo = BinanceDataRepository(config=config)

        assert repo.read_only == config.database.read_only

    def test_repository_uses_global_config(self):
        """Test repository uses global config when none provided."""
        from binance_tick_data.repository_v2 import BinanceDataRepository

        repo = BinanceDataRepository()

        # Should have db_path and read_only from global config
        assert repo.db_path is not None
        assert isinstance(repo.read_only, bool)


class TestEncapsulation:
    """Test that internal changes don't break external code."""

    def test_internal_field_rename_doesnt_break_properties(self):
        """Test properties shield from internal field name changes."""
        config = DatabaseConfig(
            schema_name="my_schema",
            catalog_name="my_catalog"
        )

        # Even if we renamed schema_name internally,
        # the property would still work
        assert config.schema == "my_schema"
        assert config.catalog == "my_catalog"

    def test_multiple_ways_to_access_same_data(self):
        """Test multiple access patterns for same data work."""
        config = AppConfig()

        # Database path accessible multiple ways
        path1 = config.db_path
        path2 = config.database.db_path

        assert path1 == path2

        # Schema accessible multiple ways
        schema1 = config.schema
        schema2 = config.database.schema
        schema3 = config.database.schema_name

        assert schema1 == schema2 == schema3

    def test_properties_are_read_only(self):
        """Test that properties are read-only (no setter)."""
        config = DatabaseConfig()

        # Properties should not have setters
        with pytest.raises(AttributeError):
            config.schema = "new_schema"

        with pytest.raises(AttributeError):
            config.catalog = "new_catalog"

        with pytest.raises(AttributeError):
            config.path = Path("/new/path")
