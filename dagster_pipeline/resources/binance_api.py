"""Binance API resource for Dagster."""

from dagster import ConfigurableResource
from binance.client import Client as BinanceClient
from typing import Optional


class BinanceAPIResource(ConfigurableResource):
    """Binance REST API client resource."""

    api_key: str = ""
    api_secret: str = ""

    def get_client(self) -> BinanceClient:
        """Get Binance API client instance."""
        return BinanceClient(self.api_key, self.api_secret)

    def test_connection(self) -> bool:
        """Test API connection."""
        try:
            client = self.get_client()
            client.ping()
            return True
        except Exception:
            return False


# Default resource instance
binance_api_resource = BinanceAPIResource(
    api_key="",  # Set via environment variables
    api_secret=""
)
