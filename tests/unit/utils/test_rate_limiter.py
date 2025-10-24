"""Unit tests for BinanceRateLimiter."""

import pytest
import time
from unittest.mock import Mock, patch
from binance_tick_data.utils.rate_limiter import BinanceRateLimiter


class TestBinanceRateLimiter:
    """Test suite for BinanceRateLimiter."""

    def test_initialization(self):
        """Test rate limiter initialization with default values."""
        limiter = BinanceRateLimiter()

        assert limiter.capacity == 1000
        assert limiter.refill_rate == pytest.approx(16.67, rel=0.01)
        assert limiter.tokens == 1000
        assert limiter.binance_used_weight == 0
        assert limiter.throttle_factor == 1.0

    def test_initialization_custom_values(self):
        """Test rate limiter initialization with custom values."""
        limiter = BinanceRateLimiter(
            capacity=500,
            refill_rate=10.0,
            warning_threshold=0.7,
            critical_threshold=0.85
        )

        assert limiter.capacity == 500
        assert limiter.refill_rate == 10.0
        assert limiter.warning_threshold == 0.7
        assert limiter.critical_threshold == 0.85

    def test_wait_if_needed_with_available_tokens(self):
        """Test that wait_if_needed doesn't block when tokens are available."""
        limiter = BinanceRateLimiter(capacity=100, refill_rate=10.0)

        start_time = time.time()
        limiter.wait_if_needed(weight=10)
        elapsed = time.time() - start_time

        # Should not block (elapsed time should be minimal)
        assert elapsed < 0.1
        # Tokens should be consumed
        assert limiter.tokens == pytest.approx(90.0, rel=0.1)

    def test_wait_if_needed_blocks_when_insufficient_tokens(self):
        """Test that wait_if_needed blocks when insufficient tokens."""
        limiter = BinanceRateLimiter(capacity=10, refill_rate=10.0)

        # Consume all tokens
        limiter.tokens = 0

        start_time = time.time()
        limiter.wait_if_needed(weight=5)
        elapsed = time.time() - start_time

        # Should block for approximately 0.5 seconds (5 tokens / 10 per second)
        assert elapsed >= 0.4  # Allow some margin
        assert elapsed < 0.7

    def test_token_refill(self):
        """Test that tokens refill over time."""
        limiter = BinanceRateLimiter(capacity=100, refill_rate=10.0)

        # Consume tokens
        limiter.tokens = 50
        limiter.last_refill_time = time.time()

        # Wait and trigger refill
        time.sleep(0.5)
        limiter.wait_if_needed(weight=1)

        # Should have refilled approximately 5 tokens (0.5s * 10/s)
        # 50 + 5 - 1 (consumed) = 54
        assert limiter.tokens >= 53
        assert limiter.tokens <= 56

    def test_update_from_headers(self):
        """Test updating rate limiter from API response headers."""
        limiter = BinanceRateLimiter()

        headers = {
            'X-MBX-USED-WEIGHT-1M': '600'
        }

        limiter.update_from_headers(headers)

        assert limiter.binance_used_weight == 600

    def test_update_from_headers_invalid_value(self):
        """Test handling invalid header values gracefully."""
        limiter = BinanceRateLimiter()

        headers = {
            'X-MBX-USED-WEIGHT-1M': 'invalid'
        }

        # Should not raise exception
        limiter.update_from_headers(headers)

        # Should keep default value
        assert limiter.binance_used_weight == 0

    def test_calculate_throttle_factor_below_warning(self):
        """Test throttle factor when usage is below warning threshold."""
        limiter = BinanceRateLimiter(warning_threshold=0.8)

        limiter.binance_used_weight = 900  # 75% of 1200
        limiter.binance_limit = 1200

        factor = limiter._calculate_throttle_factor()

        assert factor == 1.0  # No throttling

    def test_calculate_throttle_factor_warning_level(self):
        """Test throttle factor at warning threshold (80%-90%)."""
        limiter = BinanceRateLimiter(
            warning_threshold=0.8,
            critical_threshold=0.9
        )

        limiter.binance_used_weight = 1000  # 83% of 1200
        limiter.binance_limit = 1200

        factor = limiter._calculate_throttle_factor()

        assert factor == 0.50  # Throttle to 50%

    def test_calculate_throttle_factor_critical_level(self):
        """Test throttle factor at critical threshold (90%+)."""
        limiter = BinanceRateLimiter(critical_threshold=0.9)

        limiter.binance_used_weight = 1100  # 92% of 1200
        limiter.binance_limit = 1200

        factor = limiter._calculate_throttle_factor()

        assert factor == 0.25  # Throttle to 25%

    def test_adaptive_throttling_affects_wait_time(self):
        """Test that adaptive throttling increases effective wait time."""
        limiter = BinanceRateLimiter(capacity=100, refill_rate=100.0, critical_threshold=0.9)

        # Set to critical throttle level
        limiter.binance_used_weight = 1100
        limiter.binance_limit = 1200

        # Consume all tokens
        limiter.tokens = 0

        start_time = time.time()
        limiter.wait_if_needed(weight=10)
        elapsed = time.time() - start_time

        # With 0.25 throttle factor, effective weight is 10/0.25 = 40
        # Should wait 40/100 = 0.4 seconds
        assert elapsed >= 0.35
        assert elapsed < 0.6

    def test_handle_429_exponential_backoff(self):
        """Test exponential backoff on 429 errors."""
        limiter = BinanceRateLimiter()

        # First 429
        start_time = time.time()
        limiter.handle_429()
        elapsed = time.time() - start_time

        assert elapsed >= 2.0
        assert elapsed < 2.5
        assert limiter.backoff_seconds == 2
        assert limiter.backoff_count == 1

        # Second 429
        start_time = time.time()
        limiter.handle_429()
        elapsed = time.time() - start_time

        assert elapsed >= 4.0
        assert elapsed < 4.5
        assert limiter.backoff_seconds == 4
        assert limiter.backoff_count == 2

        # Third 429
        start_time = time.time()
        limiter.handle_429()
        elapsed = time.time() - start_time

        assert elapsed >= 8.0
        assert elapsed < 8.5
        assert limiter.backoff_seconds == 8

    def test_handle_429_max_backoff(self):
        """Test that backoff doesn't exceed maximum."""
        limiter = BinanceRateLimiter(max_backoff=10)

        # Set backoff to near max
        limiter.backoff_seconds = 8
        limiter.backoff_count = 3

        start_time = time.time()
        limiter.handle_429()
        elapsed = time.time() - start_time

        # Should cap at 10 seconds
        assert elapsed >= 10.0
        assert elapsed < 10.5
        assert limiter.backoff_seconds == 10

    def test_backoff_reset_on_successful_request(self):
        """Test that backoff resets after successful request with headers."""
        limiter = BinanceRateLimiter()

        # Trigger some backoff
        limiter.backoff_count = 3
        limiter.backoff_seconds = 8

        # Successful request with headers
        headers = {'X-MBX-USED-WEIGHT-1M': '500'}
        limiter.update_from_headers(headers)

        assert limiter.backoff_count == 0
        assert limiter.backoff_seconds == 0

    def test_reset(self):
        """Test reset functionality."""
        limiter = BinanceRateLimiter()

        # Modify state
        limiter.tokens = 50
        limiter.binance_used_weight = 800
        limiter.throttle_factor = 0.5
        limiter.backoff_count = 2
        limiter.request_count = 100

        # Reset
        limiter.reset()

        assert limiter.tokens == limiter.capacity
        assert limiter.binance_used_weight == 0
        assert limiter.throttle_factor == 1.0
        assert limiter.backoff_count == 0
        assert limiter.request_count == 0

    def test_thread_safety(self):
        """Test that rate limiter is thread-safe."""
        import threading

        limiter = BinanceRateLimiter(capacity=1000, refill_rate=100.0)

        results = []
        def worker():
            for _ in range(10):
                limiter.wait_if_needed(weight=1)
            results.append(True)

        # Create multiple threads
        threads = [threading.Thread(target=worker) for _ in range(5)]

        # Start all threads
        for t in threads:
            t.start()

        # Wait for completion
        for t in threads:
            t.join()

        # All threads should complete successfully
        assert len(results) == 5

        # Total tokens consumed: 5 threads * 10 requests = 50
        # Some tokens should have refilled during execution
        assert limiter.tokens < limiter.capacity

    @patch('binance_tick_data.utils.rate_limiter.logger')
    def test_logging_at_interval(self, mock_logger):
        """Test that status is logged at specified interval."""
        limiter = BinanceRateLimiter(log_interval=5)

        # Make requests
        for i in range(10):
            limiter.wait_if_needed(weight=1)

        # Should have logged twice (at request 5 and 10)
        assert mock_logger.debug.call_count >= 2

    @patch('binance_tick_data.utils.rate_limiter.logger')
    def test_logging_during_throttle(self, mock_logger):
        """Test that throttling is logged."""
        limiter = BinanceRateLimiter(log_interval=5, warning_threshold=0.8)

        # Set to warning level
        limiter.binance_used_weight = 1000
        limiter.binance_limit = 1200

        # Make 5 requests to trigger logging
        for i in range(5):
            limiter.wait_if_needed(weight=1)

        # Should have logged info about throttling
        assert mock_logger.info.call_count >= 1
        assert any('throttling' in str(call) for call in mock_logger.info.call_args_list)

    def test_weight_parameter(self):
        """Test that different weights are handled correctly."""
        limiter = BinanceRateLimiter(capacity=100, refill_rate=10.0)

        # Request with weight 5
        limiter.wait_if_needed(weight=5)
        assert limiter.tokens == pytest.approx(95.0, rel=0.1)

        # Request with weight 10
        limiter.wait_if_needed(weight=10)
        assert limiter.tokens == pytest.approx(85.0, rel=0.1)

    def test_capacity_limit(self):
        """Test that tokens don't exceed capacity."""
        limiter = BinanceRateLimiter(capacity=100, refill_rate=100.0)

        # Wait long enough for many tokens to refill
        time.sleep(2.0)

        # Trigger refill
        limiter.wait_if_needed(weight=1)

        # Should not exceed capacity
        assert limiter.tokens <= limiter.capacity
