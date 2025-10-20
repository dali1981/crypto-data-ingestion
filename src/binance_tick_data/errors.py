"""
Custom error hierarchy for Binance tick data pipeline.

Provides specific, actionable error messages to help users debug issues quickly.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime


class BinanceDataError(Exception):
    """Base exception for all Binance data pipeline errors."""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None
    ):
        self.message = message
        self.details = details or {}
        self.suggestions = suggestions or []
        super().__init__(self.format_message())

    def format_message(self) -> str:
        """Format a comprehensive error message."""
        lines = [f"❌ {self.message}"]

        if self.details:
            lines.append("\n📋 Details:")
            for key, value in self.details.items():
                lines.append(f"   • {key}: {value}")

        if self.suggestions:
            lines.append("\n💡 Suggestions:")
            for suggestion in self.suggestions:
                lines.append(f"   → {suggestion}")

        return "\n".join(lines)


# =============================================================================
# Database Errors
# =============================================================================

class DatabaseError(BinanceDataError):
    """Base class for database-related errors."""
    pass


class DatabaseNotFoundError(DatabaseError):
    """Raised when the database file doesn't exist."""

    def __init__(self, db_path: str):
        super().__init__(
            message=f"Database file not found: {db_path}",
            details={
                "db_path": db_path,
                "file_exists": False,
            },
            suggestions=[
                "Run the data ingestion pipeline first to create the database",
                "Check if the database path in config.yaml is correct",
                "Verify BINANCE_DATABASE__DB_PATH environment variable",
            ]
        )


class DatabaseConnectionError(DatabaseError):
    """Raised when unable to connect to the database."""

    def __init__(self, db_path: str, original_error: Optional[Exception] = None):
        super().__init__(
            message=f"Failed to connect to database: {db_path}",
            details={
                "db_path": db_path,
                "original_error": str(original_error) if original_error else None,
            },
            suggestions=[
                "Check if the database file is corrupted",
                "Verify file permissions",
                "Try closing other connections to the database",
            ]
        )


class SchemaNotFoundError(DatabaseError):
    """Raised when the required schema doesn't exist in the database."""

    def __init__(self, schema_name: str, db_path: str, available_schemas: Optional[List[str]] = None):
        details = {
            "schema_name": schema_name,
            "db_path": db_path,
        }
        if available_schemas:
            details["available_schemas"] = ", ".join(available_schemas)

        super().__init__(
            message=f"Schema '{schema_name}' not found in database",
            details=details,
            suggestions=[
                "Run the data ingestion pipeline to create the schema",
                "Check the schema_name in config.yaml",
                "Verify BINANCE_DATABASE__SCHEMA_NAME environment variable",
            ]
        )


class TableNotFoundError(DatabaseError):
    """Raised when a required table doesn't exist."""

    def __init__(
        self,
        table_name: str,
        schema_name: str,
        db_path: str,
        available_tables: Optional[List[str]] = None
    ):
        details = {
            "table_name": table_name,
            "schema_name": schema_name,
            "db_path": db_path,
        }
        if available_tables:
            details["available_tables"] = ", ".join(available_tables)

        super().__init__(
            message=f"Table '{table_name}' not found in schema '{schema_name}'",
            details=details,
            suggestions=[
                "Run the data ingestion pipeline to create the table",
                "Check if you're using the correct table name",
                "Verify the database has been initialized",
                f"Available tables: {', '.join(available_tables)}" if available_tables else "No tables found",
            ]
        )


# =============================================================================
# Data Errors
# =============================================================================

class DataError(BinanceDataError):
    """Base class for data-related errors."""
    pass


class NoDataFoundError(DataError):
    """Raised when a query returns no data."""

    def __init__(
        self,
        symbol: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        table_name: Optional[str] = None,
    ):
        details = {}
        if symbol:
            details["symbol"] = symbol
        if start_time:
            details["start_time"] = start_time.isoformat()
        if end_time:
            details["end_time"] = end_time.isoformat()
        if table_name:
            details["table"] = table_name

        super().__init__(
            message="No data found for the specified criteria",
            details=details,
            suggestions=[
                "Check if data exists for this symbol and time range",
                "Try a broader date range",
                "Run data ingestion to fetch historical data",
                "Verify the symbol name is correct (e.g., 'BTCUSDT')",
            ]
        )


class InvalidSymbolError(DataError):
    """Raised when an invalid trading symbol is provided."""

    def __init__(self, symbol: str, valid_symbols: Optional[List[str]] = None):
        details = {"symbol": symbol}
        if valid_symbols:
            details["valid_symbols"] = ", ".join(valid_symbols[:10])  # Show first 10

        super().__init__(
            message=f"Invalid trading symbol: {symbol}",
            details=details,
            suggestions=[
                "Use format like 'BTCUSDT', 'ETHUSDT', etc.",
                "Check Binance for valid trading pairs",
                f"Available symbols: {', '.join(valid_symbols[:10])}" if valid_symbols else "No symbols available",
            ]
        )


class DataQualityError(DataError):
    """Raised when data quality issues are detected."""

    def __init__(
        self,
        message: str,
        issues: List[str],
        affected_records: Optional[int] = None
    ):
        details = {"issues_found": len(issues)}
        if affected_records:
            details["affected_records"] = affected_records

        super().__init__(
            message=message,
            details=details,
            suggestions=[
                f"Data quality issues: {', '.join(issues[:5])}",
                "Consider re-fetching the data",
                "Check data validation rules",
            ]
        )


class InsufficientDataError(DataError):
    """Raised when there's not enough data for an operation."""

    def __init__(
        self,
        operation: str,
        required_records: int,
        available_records: int
    ):
        super().__init__(
            message=f"Insufficient data for operation: {operation}",
            details={
                "required_records": required_records,
                "available_records": available_records,
                "shortage": required_records - available_records,
            },
            suggestions=[
                f"Need at least {required_records} records, but only {available_records} available",
                "Fetch more historical data",
                "Adjust the operation parameters",
            ]
        )


# =============================================================================
# Configuration Errors
# =============================================================================

class ConfigurationError(BinanceDataError):
    """Base class for configuration-related errors."""
    pass


class InvalidConfigurationError(ConfigurationError):
    """Raised when configuration is invalid."""

    def __init__(self, config_field: str, reason: str, example: Optional[str] = None):
        details = {
            "field": config_field,
            "reason": reason,
        }
        if example:
            details["example"] = example

        super().__init__(
            message=f"Invalid configuration for '{config_field}'",
            details=details,
            suggestions=[
                "Check config.yaml for errors",
                "Verify environment variables",
                f"Example: {example}" if example else "Check documentation for valid values",
            ]
        )


class ConfigurationFileNotFoundError(ConfigurationError):
    """Raised when configuration file doesn't exist."""

    def __init__(self, config_path: str):
        super().__init__(
            message=f"Configuration file not found: {config_path}",
            details={"config_path": config_path},
            suggestions=[
                "Create config.yaml in the project root",
                "Use the default configuration template",
                "Set configuration via environment variables",
            ]
        )


# =============================================================================
# API Errors
# =============================================================================

class APIError(BinanceDataError):
    """Base class for API-related errors."""
    pass


class RateLimitError(APIError):
    """Raised when API rate limit is exceeded."""

    def __init__(self, retry_after: Optional[int] = None):
        details = {}
        if retry_after:
            details["retry_after_seconds"] = retry_after

        super().__init__(
            message="Binance API rate limit exceeded",
            details=details,
            suggestions=[
                "Wait before making more requests",
                f"Retry after {retry_after} seconds" if retry_after else "Retry in a few minutes",
                "Consider using API keys for higher rate limits",
                "Reduce batch sizes or request frequency",
            ]
        )


class APIConnectionError(APIError):
    """Raised when unable to connect to Binance API."""

    def __init__(self, original_error: Optional[Exception] = None):
        super().__init__(
            message="Failed to connect to Binance API",
            details={
                "original_error": str(original_error) if original_error else None,
            },
            suggestions=[
                "Check your internet connection",
                "Verify Binance API is accessible",
                "Check if you're behind a firewall",
                "Try again in a few moments",
            ]
        )


# =============================================================================
# Query Errors
# =============================================================================

class QueryError(BinanceDataError):
    """Base class for query-related errors."""
    pass


class InvalidDateRangeError(QueryError):
    """Raised when date range is invalid."""

    def __init__(self, start_time: datetime, end_time: datetime):
        super().__init__(
            message="Invalid date range: start_time is after end_time",
            details={
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
            },
            suggestions=[
                "Ensure start_time is before end_time",
                "Check datetime objects are created correctly",
            ]
        )


class InvalidParameterError(QueryError):
    """Raised when invalid parameters are provided to a query."""

    def __init__(self, parameter: str, value: Any, reason: str):
        super().__init__(
            message=f"Invalid parameter '{parameter}': {reason}",
            details={
                "parameter": parameter,
                "value": str(value),
                "reason": reason,
            },
            suggestions=[
                "Check the parameter documentation",
                "Verify the parameter type and value range",
            ]
        )


# =============================================================================
# Helper Functions
# =============================================================================

def format_error_context(
    operation: str,
    **context
) -> str:
    """Format error context for logging."""
    lines = [f"Operation: {operation}"]
    for key, value in context.items():
        lines.append(f"  {key}: {value}")
    return "\n".join(lines)


def create_data_not_found_error(
    table_name: str,
    symbol: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> NoDataFoundError:
    """
    Convenience function to create a descriptive NoDataFoundError.

    Usage:
        raise create_data_not_found_error("agg_trades", symbol="BTCUSDT")
    """
    return NoDataFoundError(
        symbol=symbol,
        start_time=start_time,
        end_time=end_time,
        table_name=table_name,
    )