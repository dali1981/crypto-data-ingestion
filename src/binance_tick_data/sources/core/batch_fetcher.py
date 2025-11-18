"""Generic incremental batch fetcher - works with any API."""

from datetime import datetime
from typing import Iterator, List, Dict, Any, Callable, Optional
import logging
from .interfaces import APIClient, DataTransformer, RateLimiter
from .exceptions import RateLimitError, APIError


class IncrementalBatchFetcher:
    """
    Generic incremental batch fetcher - works with ANY API.

    Encapsulates:
    - Batch loop logic
    - Rate limiting
    - Error handling with retry
    - Progress tracking
    - Cutoff time checking

    Zero exchange-specific code - fully reusable with Binance, Coinbase, Kraken, etc.
    """

    def __init__(
        self,
        client: APIClient,
        transformer: DataTransformer,
        rate_limiter: RateLimiter,
        api_weight: int = 1,
        batch_size: int = 1000,
        cursor_increment: int = 1,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize batch fetcher with collaborators.

        Args:
            client: API client implementation
            transformer: Data transformer implementation
            rate_limiter: Rate limiter implementation
            api_weight: API weight/cost of each request
            batch_size: Number of records per request
            cursor_increment: Value to add to cursor for next iteration (default: 1)
            logger: Optional logger instance
        """
        self.client = client
        self.transformer = transformer
        self.rate_limiter = rate_limiter
        self.api_weight = api_weight
        self.batch_size = batch_size
        self.cursor_increment = cursor_increment
        self.logger = logger or logging.getLogger(__name__)
        self._batch_count = 0
        self._total_records = 0

    def fetch_until_cutoff(
        self,
        fetch_func: Callable,
        start_cursor: Any,
        cutoff_time: datetime,
        **fetch_kwargs
    ) -> Iterator[List[Dict]]:
        """
        Generic batch fetching loop.

        Args:
            fetch_func: API-specific fetch function (e.g., client.fetch_agg_trades)
            start_cursor: Starting cursor value (trade ID, timestamp, etc.)
            cutoff_time: Stop fetching when reaching this time
            **fetch_kwargs: Additional args for fetch_func

        Yields:
            Batches of transformed data
        """
        cutoff_ts_ms = int(cutoff_time.timestamp() * 1000)
        current_cursor = start_cursor

        while True:
            # Rate limit before API call
            self.rate_limiter.wait_if_needed(self.api_weight)

            # Fetch batch with retry logic
            try:
                raw_batch = fetch_func(
                    **fetch_kwargs,
                    cursor=current_cursor,
                    limit=self.batch_size
                )
            except RateLimitError:
                self.rate_limiter.handle_rate_limit_error(retry_after=None)
                continue  # Retry
            except APIError as e:
                self.logger.error(f"API error: {e}")
                return
            except Exception as e:
                self.logger.error(f"Unexpected error: {e}")
                return

            if not raw_batch:
                self.logger.info("No more data available from API")
                break

            # Transform batch
            transformed_batch = self.transformer.transform_batch(raw_batch)

            if not transformed_batch:
                self.logger.info("No transformed data in batch")
                break

            # Check cutoff time
            last_timestamp = self.transformer.extract_timestamp(transformed_batch[-1])
            if last_timestamp > cutoff_ts_ms:
                # Filter to cutoff
                transformed_batch = [
                    item for item in transformed_batch
                    if self.transformer.extract_timestamp(item) <= cutoff_ts_ms
                ]
                if not transformed_batch:
                    self.logger.info(f"Reached cutoff time ({cutoff_time})")
                    break

            # Update cursor for next iteration
            current_cursor = self.transformer.extract_cursor(transformed_batch[-1]) + self.cursor_increment

            # Update progress
            self._batch_count += 1
            self._total_records += len(transformed_batch)

            # Log progress
            first_ts = self.transformer.extract_timestamp(transformed_batch[0])
            last_ts = self.transformer.extract_timestamp(transformed_batch[-1])
            first_time = datetime.fromtimestamp(first_ts / 1000)
            last_time = datetime.fromtimestamp(last_ts / 1000)

            self.logger.info(
                f"Batch {self._batch_count}: {first_time} to {last_time} "
                f"({len(transformed_batch)} records, {self._total_records} total)"
            )

            # Yield batch
            yield transformed_batch

            # Break if reached cutoff
            if last_timestamp >= cutoff_ts_ms:
                self.logger.info(
                    f"Completed: {self._batch_count} batches, "
                    f"{self._total_records} records fetched"
                )
                break
