"""Thin wrapper around yfinance: caching, error handling, and normalization.

Every function here either returns a well-formed result or raises one of
our own `errors.FinancialDataError` subclasses — callers never have to
guess whether an empty DataFrame means "bad ticker" or "network blip".
"""

from __future__ import annotations

import logging

import pandas as pd
import yfinance as yf

from .cache import ttl_cache
from .errors import DataProviderError, TickerNotFoundError

logger = logging.getLogger(__name__)

QUOTE_CACHE_TTL_SECONDS = 15.0
HISTORY_CACHE_TTL_SECONDS = 300.0


@ttl_cache(ttl_seconds=QUOTE_CACHE_TTL_SECONDS)
def fetch_quote(ticker: str) -> dict:
    """Fetch the latest price and day change for `ticker`.

    Raises TickerNotFoundError if the symbol doesn't exist, DataProviderError
    if yfinance itself fails (network, upstream outage, etc).
    """
    try:
        info = yf.Ticker(ticker).fast_info
        # yfinance's FastInfo is dict-like with camelCase keys but also
        # exposes the same data as snake_case attributes; using attributes
        # here is what stays valid across yfinance's still-shifting key names.
        price = info.last_price
        previous_close = info.previous_close
        currency = info.currency
    except (KeyError, AttributeError):
        raise TickerNotFoundError(ticker) from None
    except Exception as exc:  # yfinance raises assorted exception types
        logger.warning("data_provider_error", extra={"ticker": ticker, "error": str(exc)})
        raise DataProviderError(ticker, cause=exc) from exc

    if price is None or previous_close is None:
        raise TickerNotFoundError(ticker)

    change = price - previous_close
    change_pct = (change / previous_close * 100) if previous_close else 0.0

    logger.info("quote_fetched", extra={"ticker": ticker, "price": price})
    return {
        "ticker": ticker,
        "price": round(float(price), 4),
        "previous_close": round(float(previous_close), 4),
        "change": round(float(change), 4),
        "change_pct": round(float(change_pct), 4),
        "currency": currency,
    }


@ttl_cache(ttl_seconds=HISTORY_CACHE_TTL_SECONDS)
def fetch_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    """Fetch OHLCV history for `ticker` over `period`.

    Returns a DataFrame indexed by date with at least a 'Close' column.
    Raises TickerNotFoundError if no rows come back, DataProviderError on
    upstream/network failure.
    """
    try:
        history = yf.Ticker(ticker).history(period=period, auto_adjust=True)
    except Exception as exc:
        logger.warning("data_provider_error", extra={"ticker": ticker, "error": str(exc)})
        raise DataProviderError(ticker, cause=exc) from exc

    if history is None or history.empty:
        raise TickerNotFoundError(ticker)

    logger.info("history_fetched", extra={"ticker": ticker, "period": period, "rows": len(history)})
    return history


def fetch_close_prices(tickers: list[str], period: str = "1y") -> pd.DataFrame:
    """Fetch aligned daily close prices for multiple tickers as one DataFrame."""
    series = {}
    for ticker in tickers:
        history = fetch_history(ticker, period=period)
        series[ticker] = history["Close"]
    prices = pd.DataFrame(series)
    return prices.dropna(how="all")
