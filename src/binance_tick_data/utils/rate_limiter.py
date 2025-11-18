"""Rate limiter for Binance API calls using token bucket algorithm."""

import time
import logging
import threading
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class BinanceRateLimiter:
    """
    Adaptive rate limiter for Binance API using token bucket algorithm.

    Features:
    - Token bucket allows bursts up to capacity
    - Monitors API response headers for real-time limit tracking
    - Adaptive throttling when approaching limits
    - Exponential backoff on 429 errors

    Binance Limits:
    - 1200 weight per minute per IP
    - aggTrades endpoint weight: 1

    This limiter targets 1000 weight/minute (83% of limit) for safety buffer.
    """

    def __init__(
        self,
        capacity: int = 1000,
        refill_rate: float = 16.67,  # ~1000 per minute
        warning_threshold: float = 0.8,
        critical_threshold: float = 0.9,
    ):
        """
        Initialize rate limiter.

        Args:
            capacity: Maximum tokens (weight) available (default: 1000)
            refill_rate: Tokens added per second (default: 16.67 = 1000/60)
            warning_threshold: Throttle at this fraction of Binance limit (default: 0.8 = 960/1200)
            critical_threshold: Heavy throttle at this fraction (default: 0.9 = 1080/1200)
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold

        # Token bucket state
        self.tokens = float(capacity)
        self.last_refill_time = time.time()
        self.lock = threading.Lock()

        # Adaptive throttling state
        self.binance_used_weight = 0
        self.binance_limit = 1200
        self.throttle_factor = 1.0

        # Exponential backoff state
        self.backoff_seconds = 0
        self.backoff_count = 0
        self.max_backoff = 60

        # Logging state
        self.request_count = 0
        self.log_interval = 10

    def _refill_tokens(self) -> None:
        """Refill tokens based on time elapsed since last refill."""
        now = time.time()
        elapsed = now - self.last_refill_time

        # Add tokens based on elapsed time
        new_tokens = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + new_tokens)
        self.last_refill_time = now

    def _calculate_throttle_factor(self) -> float:
        """Calculate throttle factor based on Binance's reported usage."""
        if self.binance_used_weight == 0:
            return 1.0

        usage_ratio = self.binance_used_weight / self.binance_limit

        if usage_ratio >= self.critical_threshold:
            # At 90%+: slow to 25% speed
            return 0.25
        elif usage_ratio >= self.warning_threshold:
            # At 80%-90%: slow to 50% speed
            return 0.50
        else:
            # Below 80%: full speed
            return 1.0

    def wait_if_needed(self, weight: int = 1) -> None:
        """
        Block until sufficient tokens are available for the request.

        Args:
            weight: API weight cost of the request (default: 1 for aggTrades)
        """
        with self.lock:
            self._refill_tokens()

            # Update throttle factor based on Binance usage
            self.throttle_factor = self._calculate_throttle_factor()

            # Effective cost accounting for throttling
            effective_weight = weight / self.throttle_factor

            # Wait until we have enough tokens
            while self.tokens < effective_weight:
                sleep_time = (effective_weight - self.tokens) / self.refill_rate

                # Release lock during sleep
                self.lock.release()
                time.sleep(sleep_time)
                self.lock.acquire()

                self._refill_tokens()

            # Consume tokens
            self.tokens -= effective_weight
            self.request_count += 1

            # Log every N requests
            if self.request_count % self.log_interval == 0:
                self._log_status()

    def update_from_headers(self, headers: Dict[str, str]) -> None:
        """
        Update rate limiter state from Binance API response headers.

        Args:
            headers: Response headers from Binance API
        """
        with self.lock:
            # Extract weight used from headers
            used_weight_key = 'X-MBX-USED-WEIGHT-1M'
            if used_weight_key in headers:
                try:
                    self.binance_used_weight = int(headers[used_weight_key])

                    # Reset backoff on successful request
                    if self.backoff_count > 0:
                        logger.info("Rate limit recovered, resetting backoff")
                        self.backoff_count = 0
                        self.backoff_seconds = 0

                except (ValueError, TypeError):
                    logger.warning(f"Could not parse {used_weight_key}: {headers[used_weight_key]}")

    def handle_rate_limit_error(self, retry_after: Optional[int] = None) -> None:
        """
        Handle rate limit error with exponential backoff.

        Implements the RateLimiter Protocol interface.

        Args:
            retry_after: Seconds to wait before retrying (from API response, optional)
        """
        self.handle_429(retry_after)

    def handle_429(self, retry_after: Optional[int] = None) -> None:
        """
        Handle 429 (rate limit exceeded) error with exponential backoff.

        Backoff sequence: 2s, 4s, 8s, 16s, 32s, max 60s
        If retry_after is provided, use that instead.

        Args:
            retry_after: Seconds to wait before retrying (from API response, optional)
        """
        with self.lock:
            if retry_after is not None:
                self.backoff_seconds = retry_after
            else:
                # Calculate backoff time
                if self.backoff_count == 0:
                    self.backoff_seconds = 2
                else:
                    self.backoff_seconds = min(self.backoff_seconds * 2, self.max_backoff)

            self.backoff_count += 1

            logger.warning(
                f"Rate limited by Binance (429), backing off for {self.backoff_seconds}s "
                f"(attempt {self.backoff_count})"
            )

        # Sleep outside lock
        time.sleep(self.backoff_seconds)

    def _log_status(self) -> None:
        """Log current rate limiter status."""
        usage_pct = (self.binance_used_weight / self.binance_limit) * 100

        if self.throttle_factor < 1.0:
            logger.info(
                f"Rate limit: {self.binance_used_weight}/{self.binance_limit} weight/min "
                f"({usage_pct:.1f}%), throttling to {self.throttle_factor*100:.0f}% speed"
            )
        else:
            logger.debug(
                f"Rate limit: {self.binance_used_weight}/{self.binance_limit} weight/min "
                f"({usage_pct:.1f}%)"
            )

    def reset(self) -> None:
        """Reset rate limiter state (useful for testing)."""
        with self.lock:
            self.tokens = float(self.capacity)
            self.last_refill_time = time.time()
            self.binance_used_weight = 0
            self.throttle_factor = 1.0
            self.backoff_seconds = 0
            self.backoff_count = 0
            self.request_count = 0
