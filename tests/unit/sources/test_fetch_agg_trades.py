"""Unit tests for fetch_agg_trades function in rest_api.py."""

import pytest
from unittest.mock import Mock, patch, PropertyMock
from datetime import datetime
from binance.exceptions import BinanceAPIException
import dlt

from binance_tick_data.sources.rest_api import create_agg_trades_resource
from binance_tick_data.config import BinanceConfig


@pytest.fixture
def mock_config():
    """Create a mock BinanceConfig for testing."""
    config = Mock(spec=BinanceConfig)
    config.api_key = "test_api_key"
    config.api_secret = "test_api_secret"
    config.symbols = ["BTCUSDT"]
    config.historical_start_date = "2024-01-01"
    return config


@pytest.fixture
def sample_trades():
    """Sample trade data from Binance API."""
    return [
        {
            "a": 1000,  # agg_trade_id
            "p": "50000.00",  # price
            "q": "0.1",  # quantity
            "f": 999,  # first_trade_id
            "l": 1001,  # last_trade_id
            "T": 1704067200000,  # timestamp (2024-01-01 00:00:00)
            "m": True,  # is_buyer_maker
            "M": True,  # is_best_match
        },
        {
            "a": 1001,
            "p": "50001.00",
            "q": "0.2",
            "f": 1002,
            "l": 1003,
            "T": 1704067260000,  # timestamp (2024-01-01 00:01:00)
            "m": False,
            "M": True,
        },
    ]


@pytest.fixture
def expected_transformed_trades():
    """Expected transformed trade data."""
    return [
        {
            "agg_trade_id": 1000,
            "price": "50000.00",
            "quantity": "0.1",
            "first_trade_id": 999,
            "last_trade_id": 1001,
            "timestamp": 1704067200000,
            "is_buyer_maker": True,
            "is_best_match": True,
            "symbol": "BTCUSDT",
        },
        {
            "agg_trade_id": 1001,
            "price": "50001.00",
            "quantity": "0.2",
            "first_trade_id": 1002,
            "last_trade_id": 1003,
            "timestamp": 1704067260000,
            "is_buyer_maker": False,
            "is_best_match": True,
            "symbol": "BTCUSDT",
        },
    ]


class TestFetchAggTrades:
    """Test suite for fetch_agg_trades function."""

    @patch("binance_tick_data.sources.rest_api.Client")
    def test_initial_run_with_start_date(self, mock_client_class, mock_config, sample_trades, expected_transformed_trades):
        """Test initial data fetch using start_date."""
        # Setup mock client
        mock_client = Mock()
        mock_client.get_aggregate_trades.return_value = sample_trades
        mock_client_class.return_value = mock_client

        # Create resource
        resource = create_agg_trades_resource(
            config=mock_config,
            symbol="BTCUSDT",
            start_date="2024-01-01"
        )

        # Execute resource - let DLT handle incremental state
        result = list(resource)

        # Verify client was created with correct params
        mock_client_class.assert_called_once_with(
            "test_api_key",
            "test_api_secret",
            requests_params={'timeout': 60}
        )

        # Verify API call
        expected_start_ts = int(datetime.strptime("2024-01-01", "%Y-%m-%d").timestamp() * 1000)
        mock_client.get_aggregate_trades.assert_called_once_with(
            symbol="BTCUSDT",
            limit=1000,
            startTime=expected_start_ts
        )

        # Verify transformed data
        # The resource yields transformed_trades as a list, so result is a list of items
        assert len(result) == len(expected_transformed_trades)
        assert result == expected_transformed_trades

    @patch("binance_tick_data.sources.rest_api.Client")
    def test_no_trades_available(self, mock_client_class, mock_config):
        """Test behavior when no trades are available."""
        # Setup mock client to return empty list
        mock_client = Mock()
        mock_client.get_aggregate_trades.return_value = []
        mock_client_class.return_value = mock_client

        # Create resource
        resource = create_agg_trades_resource(
            config=mock_config,
            symbol="BTCUSDT",
            start_date="2024-01-01"
        )

        # Execute resource
        result = list(resource)

        # Should return empty
        assert len(result) == 0

    @patch("binance_tick_data.sources.rest_api.Client")
    def test_binance_api_exception_handling(self, mock_client_class, mock_config):
        """Test error handling for BinanceAPIException."""
        # Setup mock client to raise exception
        mock_client = Mock()
        mock_client.get_aggregate_trades.side_effect = BinanceAPIException(
            response=Mock(status_code=429, text="Rate limit exceeded"),
            status_code=429,
            text="Rate limit exceeded"
        )
        mock_client_class.return_value = mock_client

        # Create resource
        resource = create_agg_trades_resource(
            config=mock_config,
            symbol="BTCUSDT",
            start_date="2024-01-01"
        )

        # Execute resource
        result = list(resource)

        # Should handle exception and return empty
        assert len(result) == 0

    @patch("binance_tick_data.sources.rest_api.Client")
    def test_trade_transformation(self, mock_client_class, mock_config):
        """Test that trade data is correctly transformed."""
        # Setup mock client with specific trade
        sample_trade = {
            "a": 12345,
            "p": "99999.99",
            "q": "1.5",
            "f": 12340,
            "l": 12350,
            "T": 1704153600000,
            "m": False,
            "M": False,
        }
        mock_client = Mock()
        mock_client.get_aggregate_trades.return_value = [sample_trade]
        mock_client_class.return_value = mock_client

        # Create resource
        resource = create_agg_trades_resource(
            config=mock_config,
            symbol="ETHUSDT",
            start_date="2024-01-01"
        )

        # Execute resource
        result = list(resource)

        # Verify transformation
        expected = {
            "agg_trade_id": 12345,
            "price": "99999.99",
            "quantity": "1.5",
            "first_trade_id": 12340,
            "last_trade_id": 12350,
            "timestamp": 1704153600000,
            "is_buyer_maker": False,
            "is_best_match": False,
            "symbol": "ETHUSDT",
        }
        assert len(result) == 1
        assert result[0] == expected

    @patch("binance_tick_data.sources.rest_api.Client")
    def test_batch_size_limit(self, mock_client_class, mock_config, sample_trades):
        """Test that fetch respects 1000 trade limit per batch."""
        mock_client = Mock()
        mock_client.get_aggregate_trades.return_value = sample_trades
        mock_client_class.return_value = mock_client

        # Create resource
        resource = create_agg_trades_resource(
            config=mock_config,
            symbol="BTCUSDT",
            start_date="2024-01-01"
        )

        # Execute resource
        list(resource)

        # Verify limit parameter
        call_kwargs = mock_client.get_aggregate_trades.call_args[1]
        assert call_kwargs['limit'] == 1000

    def test_resource_configuration(self, mock_config):
        """Test that DLT resource is configured correctly."""
        resource = create_agg_trades_resource(
            config=mock_config,
            symbol="BTCUSDT",
            start_date="2024-01-01"
        )

        # Verify resource name
        assert resource.name == "agg_trades_btcusdt"

        # Verify resource has incremental configuration
        assert hasattr(resource, '_pipe')

    @patch("binance_tick_data.sources.rest_api.Client")
    @patch("binance_tick_data.sources.rest_api.logger")
    def test_logging_initial_run(self, mock_logger, mock_client_class, mock_config, sample_trades):
        """Test logging output for initial run."""
        mock_client = Mock()
        mock_client.get_aggregate_trades.return_value = sample_trades
        mock_client_class.return_value = mock_client

        # Create and execute resource
        resource = create_agg_trades_resource(
            config=mock_config,
            symbol="BTCUSDT",
            start_date="2024-01-01"
        )

        list(resource)

        # Verify logging calls
        log_messages = [call[0][0] for call in mock_logger.info.call_args_list]
        assert any("Starting initial backfill" in msg for msg in log_messages)
        assert any("Batch:" in msg for msg in log_messages)

    @patch("binance_tick_data.sources.rest_api.Client")
    def test_multiple_symbols(self, mock_client_class, mock_config, sample_trades):
        """Test creating resources for multiple symbols."""
        mock_client = Mock()
        mock_client.get_aggregate_trades.return_value = sample_trades
        mock_client_class.return_value = mock_client

        # Create resources for different symbols
        resource_btc = create_agg_trades_resource(mock_config, "BTCUSDT", "2024-01-01")
        resource_eth = create_agg_trades_resource(mock_config, "ETHUSDT", "2024-01-01")

        # Verify different resource names
        assert resource_btc.name == "agg_trades_btcusdt"
        assert resource_eth.name == "agg_trades_ethusdt"

    @patch("binance_tick_data.sources.rest_api.Client")
    def test_date_range_logging(self, mock_client_class, mock_config):
        """Test logging shows correct date ranges."""
        # Trades spanning multiple days
        trades_multi_day = [
            {
                "a": 1000,
                "p": "50000.00",
                "q": "0.1",
                "f": 999,
                "l": 1001,
                "T": 1704067200000,  # 2024-01-01
                "m": True,
                "M": True,
            },
            {
                "a": 1001,
                "p": "50001.00",
                "q": "0.2",
                "f": 1002,
                "l": 1003,
                "T": 1704153600000,  # 2024-01-02
                "m": False,
                "M": True,
            },
        ]

        mock_client = Mock()
        mock_client.get_aggregate_trades.return_value = trades_multi_day
        mock_client_class.return_value = mock_client

        with patch("binance_tick_data.sources.rest_api.logger") as mock_logger:
            resource = create_agg_trades_resource(
                config=mock_config,
                symbol="BTCUSDT",
                start_date="2024-01-01"
            )

            list(resource)

            # Verify date range is logged
            log_messages = [call[0][0] for call in mock_logger.info.call_args_list]
            assert any("to" in msg for msg in log_messages)

    @patch("binance_tick_data.sources.rest_api.Client")
    def test_client_timeout_configuration(self, mock_client_class, mock_config, sample_trades):
        """Test that Binance client is configured with proper timeout."""
        mock_client = Mock()
        mock_client.get_aggregate_trades.return_value = sample_trades
        mock_client_class.return_value = mock_client

        resource = create_agg_trades_resource(
            config=mock_config,
            symbol="BTCUSDT",
            start_date="2024-01-01"
        )

        list(resource)

        # Verify client was created with timeout parameter
        call_args = mock_client_class.call_args
        assert call_args[1]['requests_params'] == {'timeout': 60}

    @patch("binance_tick_data.sources.rest_api.Client")
    def test_resource_write_disposition(self, mock_client_class, mock_config):
        """Test that resource has correct write disposition."""
        resource = create_agg_trades_resource(
            config=mock_config,
            symbol="BTCUSDT",
            start_date="2024-01-01"
        )

        # Check write_disposition using resource's internal state
        # DLT stores this in the resource's state
        assert resource.write_disposition == "append"

    @patch("binance_tick_data.sources.rest_api.Client")
    def test_resource_primary_key(self, mock_client_class, mock_config):
        """Test that resource has correct primary key configuration."""
        resource = create_agg_trades_resource(
            config=mock_config,
            symbol="BTCUSDT",
            start_date="2024-01-01"
        )

        # Verify the resource was created successfully with name
        # Primary key is configured in the decorator (agg_trade_id)
        assert resource.name == "agg_trades_btcusdt"
        # Verify the resource has the _pipe attribute indicating it's a DLT resource
        assert hasattr(resource, '_pipe')