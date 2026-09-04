"""Unit tests for Pydantic input validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from mcp_financial.models import (
    CompareAssetsInput,
    HistoricalSummaryInput,
    PortfolioMetricsInput,
    QuoteInput,
)


def test_quote_input_normalizes_ticker_case_and_whitespace():
    assert QuoteInput(ticker=" aapl ").ticker == "AAPL"


def test_quote_input_rejects_empty_ticker():
    with pytest.raises(ValidationError):
        QuoteInput(ticker="   ")


def test_historical_summary_rejects_invalid_period():
    with pytest.raises(ValidationError):
        HistoricalSummaryInput(ticker="AAPL", period="3days")


def test_historical_summary_accepts_valid_period():
    payload = HistoricalSummaryInput(ticker="aapl", period="1y")
    assert payload.ticker == "AAPL"
    assert payload.period == "1y"


def test_compare_assets_requires_at_least_two_tickers():
    with pytest.raises(ValidationError):
        CompareAssetsInput(tickers=["AAPL"], period="1y")


def test_compare_assets_rejects_duplicate_tickers():
    with pytest.raises(ValidationError):
        CompareAssetsInput(tickers=["AAPL", "aapl"], period="1y")


def test_portfolio_metrics_valid_input():
    payload = PortfolioMetricsInput(
        tickers=["AAPL", "MSFT"], weights=[0.6, 0.4], period="1y", risk_free_rate=0.05
    )
    assert payload.tickers == ["AAPL", "MSFT"]
    assert payload.weights == [0.6, 0.4]


def test_portfolio_metrics_rejects_weights_not_summing_to_one():
    with pytest.raises(ValidationError):
        PortfolioMetricsInput(tickers=["AAPL", "MSFT"], weights=[0.5, 0.6])


def test_portfolio_metrics_rejects_mismatched_lengths():
    with pytest.raises(ValidationError):
        PortfolioMetricsInput(tickers=["AAPL", "MSFT", "GOOGL"], weights=[0.5, 0.5])


def test_portfolio_metrics_rejects_negative_weights():
    with pytest.raises(ValidationError):
        PortfolioMetricsInput(tickers=["AAPL", "MSFT"], weights=[1.2, -0.2])


def test_portfolio_metrics_rejects_duplicate_tickers():
    with pytest.raises(ValidationError):
        PortfolioMetricsInput(tickers=["AAPL", "AAPL"], weights=[0.5, 0.5])
