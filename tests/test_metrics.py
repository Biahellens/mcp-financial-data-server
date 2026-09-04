"""Unit tests for the pure financial calculations in metrics.py.

Expected values are hand-derived (see comments) rather than recomputed
with the same formulas the code under test uses — a Sharpe or drawdown
bug here would otherwise slip straight past the tests.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from mcp_financial.errors import InsufficientDataError
from mcp_financial.metrics import (
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


def test_daily_returns_basic():
    prices = pd.Series([100.0, 110.0, 104.5])
    returns = daily_returns(prices)
    assert returns.tolist() == pytest.approx([0.10, -0.05])


def test_daily_returns_requires_two_points():
    with pytest.raises(InsufficientDataError):
        daily_returns(pd.Series([100.0]))


def test_cumulative_return_compounds_returns():
    # 100 -> 110 (+10%) -> 104.5 (-5%) -> 106.59 (+2%) == 1.10 * 0.95 * 1.02 - 1
    prices = pd.Series([100.0, 110.0, 104.5, 106.59])
    assert cumulative_return(prices) == pytest.approx(0.0659, abs=1e-4)


def test_cumulative_return_requires_two_points():
    with pytest.raises(InsufficientDataError):
        cumulative_return(pd.Series([100.0]))


def test_annualized_return_matches_cumulative_when_periods_equal_span():
    # When periods_per_year == number of return observations, the "annualized"
    # return is mathematically just the total compounded return.
    returns = pd.Series([0.10, -0.05, 0.02])
    total_growth = 1.10 * 0.95 * 1.02
    assert annualized_return(returns, periods_per_year=3) == pytest.approx(total_growth - 1)


def test_annualized_return_scales_a_flat_rate_correctly():
    # A constant 1% daily return for 252 days compounds to 1.01**252 annualized.
    returns = pd.Series([0.01] * 252)
    expected = 1.01**252 - 1
    assert annualized_return(returns, periods_per_year=252) == pytest.approx(expected, rel=1e-9)


def test_annualized_volatility_hand_computed():
    returns = pd.Series([0.02, -0.02])
    # sample std (ddof=1) of [0.02, -0.02]: mean=0, deviations=+/-0.02,
    # variance = (0.02^2 + 0.02^2) / (2-1) = 0.0008, std = sqrt(0.0008)
    daily_std = math.sqrt(0.0008)
    expected = daily_std * math.sqrt(252)
    assert annualized_volatility(returns) == pytest.approx(expected)


def test_annualized_volatility_requires_two_points():
    with pytest.raises(InsufficientDataError):
        annualized_volatility(pd.Series([0.01]))


def test_sharpe_ratio_zero_volatility_returns_zero_not_inf():
    returns = pd.Series([0.01, 0.01, 0.01, 0.01])
    assert sharpe_ratio(returns) == 0.0


def test_sharpe_ratio_hand_computed():
    returns = pd.Series([0.02, -0.02])
    vol = annualized_volatility(returns)
    ann_ret = annualized_return(returns, periods_per_year=252)
    risk_free = 0.05
    expected = (ann_ret - risk_free) / vol
    assert sharpe_ratio(returns, risk_free_rate=risk_free) == pytest.approx(expected)


def test_max_drawdown_hand_computed():
    # peak 120 at t=1, trough 90 at t=2 -> drawdown = 90/120 - 1 = -0.25
    prices = pd.Series([100.0, 120.0, 90.0, 95.0, 130.0])
    assert max_drawdown(prices) == pytest.approx(-0.25)


def test_max_drawdown_no_decline_is_zero():
    prices = pd.Series([100.0, 105.0, 110.0, 120.0])
    assert max_drawdown(prices) == pytest.approx(0.0)


def test_max_drawdown_requires_two_points():
    with pytest.raises(InsufficientDataError):
        max_drawdown(pd.Series([100.0]))


def test_portfolio_daily_returns_weighted_average():
    prices = pd.DataFrame(
        {
            "A": [100.0, 110.0, 121.0],  # +10%, +10%
            "B": [50.0, 45.0, 45.0],  # -10%, 0%
        }
    )
    port_returns = portfolio_daily_returns(prices, weights=[0.5, 0.5])
    # day1: 0.5*0.10 + 0.5*(-0.10) = 0.0 ; day2: 0.5*0.10 + 0.5*0.0 = 0.05
    assert port_returns.tolist() == pytest.approx([0.0, 0.05])


def _prices_from_returns(start_price: float, returns: list[float]) -> pd.Series:
    growth = pd.Series([1.0] + [1.0 + r for r in returns]).cumprod()
    return start_price * growth


def test_correlation_matrix_perfectly_correlated_assets():
    # B's returns are an exact positive multiple of A's -> correlation must be 1.0,
    # regardless of price scale (Pearson correlation is scale-invariant).
    a_returns = [0.05, -0.02, 0.03, 0.01]
    b_returns = [2 * r for r in a_returns]
    prices = pd.DataFrame(
        {
            "A": _prices_from_returns(100.0, a_returns),
            "B": _prices_from_returns(50.0, b_returns),
        }
    )
    corr = correlation_matrix(prices)
    assert corr.loc["A", "B"] == pytest.approx(1.0)
    assert corr.loc["A", "A"] == pytest.approx(1.0)


def test_correlation_matrix_perfectly_anticorrelated_assets():
    # B's returns are the exact negative of A's -> correlation must be -1.0.
    a_returns = [0.05, -0.02, 0.03, 0.01]
    b_returns = [-r for r in a_returns]
    prices = pd.DataFrame(
        {
            "A": _prices_from_returns(100.0, a_returns),
            "B": _prices_from_returns(100.0, b_returns),
        }
    )
    corr = correlation_matrix(prices)
    assert corr.loc["A", "B"] == pytest.approx(-1.0)


def test_moving_averages_computes_available_windows_and_nulls_the_rest():
    prices = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    result = moving_averages(prices, windows=(3, 10))
    assert result["sma_3"] == pytest.approx((3.0 + 4.0 + 5.0) / 3)
    assert result["sma_10"] is None
