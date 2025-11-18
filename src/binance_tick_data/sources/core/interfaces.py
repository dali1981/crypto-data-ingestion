"""Abstract interfaces for exchange-agnostic data fetching."""

from abc import ABC, abstractmethod
from typing import Protocol, Optional, Any, List, Generic, TypeVar

TRaw = TypeVar('TRaw')  # Raw API response type
TTransformed = TypeVar('TTransformed')  # Transformed schema type


class RateLimiter(Protocol):
    """Rate limiting strategy - works with any API."""

    def wait_if_needed(self, weight: int) -> None:
        """
        Block until rate limit allows request.

        Args:
            weight: API weight/cost of the request
        """
        ...

    def handle_rate_limit_error(self, retry_after: Optional[int] = None) -> None:
        """
        Handle 429 rate limit error.

        Args:
            retry_after: Seconds to wait before retrying (from API response)
        """
        ...


class APIClient(ABC):
    """Generic REST API client interface."""

    @abstractmethod
    def fetch_batch(self, **kwargs) -> Any:
        """
        Fetch a batch of data from the API.

        Args:
            **kwargs: API-specific parameters

        Returns:
            Raw API response
        """
        ...

    @property
    @abstractmethod
    def timeout(self) -> int:
        """Request timeout in seconds."""
        ...


class DataTransformer(ABC, Generic[TRaw, TTransformed]):
    """Transform raw API data to target schema."""

    @abstractmethod
    def transform_batch(self, raw_data: List[TRaw]) -> List[TTransformed]:
        """
        Transform a batch of raw data.

        Args:
            raw_data: List of raw API responses

        Returns:
            List of transformed records
        """
        ...

    @abstractmethod
    def extract_cursor(self, item: TTransformed) -> Any:
        """
        Extract cursor value for incremental loading.

        Args:
            item: Transformed data item

        Returns:
            Cursor value (trade ID, timestamp, etc.)
        """
        ...

    @abstractmethod
    def extract_timestamp(self, item: TTransformed) -> int:
        """
        Extract timestamp in milliseconds.

        Args:
            item: Transformed data item

        Returns:
            Timestamp in milliseconds since epoch
        """
        ...
