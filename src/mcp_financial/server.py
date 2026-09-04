"""MCP server entrypoint: wires the tools up to the MCP SDK's server runtime.

Each tool: validates its input with a Pydantic model (models.py), fetches
data through the cached/error-handled data layer (data.py), runs the
calculation through the pure metrics layer (metrics.py), and returns a
plain dict. Errors are caught and turned into a structured `{"error": ...}`
payload instead of an unhandled exception, so a bad ticker degrades
gracefully for the calling model instead of crashing the tool call.
"""

from __future__ import annotations

import logging

from mcp.server.mcpserver import MCPServer
from pydantic import ValidationError

from .data import fetch_close_prices, fetch_history, fetch_quote
from .errors import FinancialDataError
from .logging_config import configure_logging
from .metrics import (
    annualized_return,
    annualized_volatility,
    correlation_matrix,
    cumulative_return,
    daily_returns,
    max_drawdown,
    moving_averages,
    portfolio_daily_returns,
    sharpe_ratio,
)
from .models import (
    CompareAssetsInput,
    HistoricalSummaryInput,
    PortfolioMetricsInput,
    QuoteInput,
)

configure_logging()
logger = logging.getLogger(__name__)

mcp = MCPServer("financial-data-server")


def _error_payload(exc: Exception) -> dict:
    if isinstance(exc, ValidationError):
        return {"error": "invalid_input", "details": [e["msg"] for e in exc.errors()]}
    if isinstance(exc, FinancialDataError):
        return {"error": "data_unavailable", "details": str(exc)}
    logger.exception("unexpected_tool_error")
    return {"error": "internal_error", "details": str(exc)}


@mcp.tool()
def get_quote(ticker: str) -> dict:
    """Get the current price and day change for a stock ticker.

    Args:
        ticker: Ticker symbol, e.g. 'AAPL', 'MSFT', or 'PETR4.SA' for B3-listed stocks.

    Returns the latest price, previous close, absolute and percentage change,
    and currency. Returns an {"error": ...} payload if the ticker is invalid
    or the data provider is unreachable.
    """
    try:
        payload = QuoteInput(ticker=ticker)
        return fetch_quote(payload.ticker)
    except Exception as exc:
        return _error_payload(exc)


@mcp.tool()
def get_portfolio_metrics(
    tickers: list[str],
    weights: list[float],
    period: str = "1y",
    risk_free_rate: float = 0.0,
) -> dict:
    """Compute risk/return metrics for a weighted portfolio of stocks.

    Args:
        tickers: Ticker symbols in the portfolio, e.g. ['AAPL', 'MSFT'].
        weights: Portfolio weight per ticker, same order, must sum to 1.0.
        period: Lookback window: one of '1mo','3mo','6mo','1y','2y','5y','10y','ytd','max'.
        risk_free_rate: Annualized risk-free rate for the Sharpe ratio (e.g. 0.1075 for 10.75%).

    Returns cumulative return, annualized return, annualized volatility,
    Sharpe ratio, and max drawdown for the combined portfolio.
    """
    try:
        payload = PortfolioMetricsInput(
            tickers=tickers, weights=weights, period=period, risk_free_rate=risk_free_rate
        )
        prices = fetch_close_prices(payload.tickers, period=payload.period)
        port_returns = portfolio_daily_returns(prices, payload.weights)
        port_prices = (1.0 + port_returns).cumprod()

        return {
            "tickers": payload.tickers,
            "weights": payload.weights,
            "period": payload.period,
            "cumulative_return": round(float(port_prices.iloc[-1] - 1.0), 6),
            "annualized_return": round(annualized_return(port_returns), 6),
            "annualized_volatility": round(annualized_volatility(port_returns), 6),
            "sharpe_ratio": round(
                sharpe_ratio(port_returns, risk_free_rate=payload.risk_free_rate), 6
            ),
            "max_drawdown": round(max_drawdown(port_prices), 6),
        }
    except Exception as exc:
        return _error_payload(exc)


@mcp.tool()
def compare_assets(tickers: list[str], period: str = "1y") -> dict:
    """Compute the correlation matrix of daily returns between two or more assets.

    Args:
        tickers: Two or more ticker symbols to correlate, e.g. ['AAPL', 'MSFT', 'GOOGL'].
        period: Lookback window: one of '1mo','3mo','6mo','1y','2y','5y','10y','ytd','max'.

    Returns a ticker-by-ticker correlation matrix of daily returns (-1 to 1).
    """
    try:
        payload = CompareAssetsInput(tickers=tickers, period=period)
        prices = fetch_close_prices(payload.tickers, period=payload.period)
        corr = correlation_matrix(prices)
        return {
            "tickers": payload.tickers,
            "period": payload.period,
            "correlation_matrix": {
                row: {col: round(float(val), 4) for col, val in corr.loc[row].items()}
                for row in corr.index
            },
        }
    except Exception as exc:
        return _error_payload(exc)


@mcp.tool()
def get_historical_summary(ticker: str, period: str = "6mo") -> dict:
    """Get a summarized price history for one ticker: moving averages, high/low, and return.

    Args:
        ticker: Ticker symbol, e.g. 'AAPL' or 'VALE3.SA'.
        period: Lookback window: one of '1mo','3mo','6mo','1y','2y','5y','10y','ytd','max'.

    Returns the 20/50-day simple moving averages, period high/low close,
    and cumulative return over the window. Moving averages are null when
    there isn't enough history for that window.
    """
    try:
        payload = HistoricalSummaryInput(ticker=ticker, period=period)
        history = fetch_history(payload.ticker, period=payload.period)
        close = history["Close"]
        returns = daily_returns(close)

        return {
            "ticker": payload.ticker,
            "period": payload.period,
            "start_date": close.index[0].strftime("%Y-%m-%d"),
            "end_date": close.index[-1].strftime("%Y-%m-%d"),
            "last_close": round(float(close.iloc[-1]), 4),
            "period_high": round(float(close.max()), 4),
            "period_low": round(float(close.min()), 4),
            "cumulative_return": round(cumulative_return(close), 6),
            "annualized_volatility": round(annualized_volatility(returns), 6),
            **{
                k: (round(v, 4) if v is not None else None)
                for k, v in moving_averages(close).items()
            },
        }
    except Exception as exc:
        return _error_payload(exc)


def main() -> None:
    logger.info("server_starting", extra={"server": "financial-data-server"})
    mcp.run()


if __name__ == "__main__":
    main()
