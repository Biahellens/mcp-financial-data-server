"""Pure financial calculations: no I/O, no yfinance, no caching.

Kept isolated from `data.py` on purpose — these are the numbers a wrong
answer would quietly destroy trust in (a broken Sharpe or drawdown is worse
than no Sharpe at all), so they need to be testable against hand-computed
values without touching the network.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .errors import InsufficientDataError

TRADING_DAYS_PER_YEAR = 252


def daily_returns(prices: pd.Series) -> pd.Series:
    if len(prices) < 2:
        raise InsufficientDataError("Need at least 2 price points to compute returns.")
    return prices.pct_change().dropna()


def cumulative_return(prices: pd.Series) -> float:
    """Total return over the whole window, e.g. 0.12 == +12%."""
    if len(prices) < 2:
        raise InsufficientDataError("Need at least 2 price points to compute cumulative return.")
    return float(prices.iloc[-1] / prices.iloc[0] - 1.0)


def annualized_return(returns: pd.Series, periods_per_year: int = TRADING_DAYS_PER_YEAR) -> float:
    """CAGR implied by a series of periodic returns."""
    if len(returns) == 0:
        raise InsufficientDataError("Need at least 1 return to annualize.")
    growth = float((1.0 + returns).prod())
    n_periods = len(returns)
    if growth <= 0:
        return -1.0
    return growth ** (periods_per_year / n_periods) - 1.0


def annualized_volatility(
    returns: pd.Series, periods_per_year: int = TRADING_DAYS_PER_YEAR
) -> float:
    if len(returns) < 2:
        raise InsufficientDataError("Need at least 2 returns to compute volatility.")
    return float(returns.std(ddof=1) * np.sqrt(periods_per_year))


def sharpe_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> float:
    """Annualized Sharpe ratio. `risk_free_rate` is annualized (e.g. 0.1075)."""
    vol = annualized_volatility(returns, periods_per_year=periods_per_year)
    if vol == 0:
        return 0.0
    ann_return = annualized_return(returns, periods_per_year=periods_per_year)
    return float((ann_return - risk_free_rate) / vol)


def max_drawdown(prices: pd.Series) -> float:
    """Largest peak-to-trough decline over the window, expressed as a negative fraction."""
    if len(prices) < 2:
        raise InsufficientDataError("Need at least 2 price points to compute drawdown.")
    running_max = prices.cummax()
    drawdown = prices / running_max - 1.0
    return float(drawdown.min())


def portfolio_daily_returns(prices: pd.DataFrame, weights: list[float]) -> pd.Series:
    """Weighted daily returns of a portfolio from aligned close-price columns."""
    if list(prices.columns) == []:
        raise InsufficientDataError("No price columns to build a portfolio from.")
    asset_returns = prices.pct_change().dropna(how="all")
    weights_arr = np.array(weights)
    return (asset_returns.fillna(0.0) * weights_arr).sum(axis=1)


def correlation_matrix(prices: pd.DataFrame) -> pd.DataFrame:
    if prices.shape[0] < 2:
        raise InsufficientDataError("Need at least 2 price points to compute correlation.")
    return prices.pct_change().dropna(how="all").corr()


def moving_averages(
    prices: pd.Series, windows: tuple[int, ...] = (20, 50)
) -> dict[str, float | None]:
    """Latest simple moving average for each window; None if not enough history."""
    result: dict[str, float | None] = {}
    for window in windows:
        if len(prices) >= window:
            result[f"sma_{window}"] = float(prices.rolling(window).mean().iloc[-1])
        else:
            result[f"sma_{window}"] = None
    return result
