"""Core exceptions for data fetching."""


class RateLimitError(Exception):
    """Raised when API rate limit is exceeded."""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = None):
        """
        Initialize rate limit error.

        Args:
            message: Error message
            retry_after: Seconds to wait before retrying
        """
        super().__init__(message)
        self.retry_after = retry_after


class APIError(Exception):
    """Raised when API request fails."""

    def __init__(self, message: str, status_code: int = None):
        """
        Initialize API error.

        Args:
            message: Error message
            status_code: HTTP status code
        """
        super().__init__(message)
        self.status_code = status_code
