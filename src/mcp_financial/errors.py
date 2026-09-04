"""Custom exceptions for the financial data layer.

Kept distinct from Pydantic's ValidationError so tool handlers can tell
"bad input shape" (client error, fix the call) apart from
"valid input, but the market data couldn't be fetched" (upstream error,
retry or pick another ticker).
"""


class FinancialDataError(Exception):
    """Base class for all domain errors raised by this server."""


class TickerNotFoundError(FinancialDataError):
    """Raised when yfinance returns no data for a ticker (invalid or delisted)."""

    def __init__(self, ticker: str):
        self.ticker = ticker
        super().__init__(f"No market data found for ticker '{ticker}'.")


class DataProviderError(FinancialDataError):
    """Raised when the upstream data provider fails or is unreachable."""

    def __init__(self, ticker: str, cause: Exception | None = None):
        self.ticker = ticker
        self.cause = cause
        message = f"Failed to fetch data for '{ticker}' from the data provider."
        if cause is not None:
            message += f" Cause: {cause}"
        super().__init__(message)


class InsufficientDataError(FinancialDataError):
    """Raised when there isn't enough history to compute a metric reliably."""
