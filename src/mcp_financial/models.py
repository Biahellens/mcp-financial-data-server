"""Pydantic input schemas for every tool.

Validating explicitly here (instead of trusting the MCP client) means a
malformed call from any client fails fast with a clear message instead of
blowing up deep inside a pandas calculation.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator

_VALID_PERIODS = {"1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"}


def _normalize_ticker(value: str) -> str:
    ticker = value.strip().upper()
    if not ticker:
        raise ValueError("Ticker must not be empty.")
    if len(ticker) > 15:
        raise ValueError(f"'{value}' does not look like a valid ticker symbol.")
    return ticker


class QuoteInput(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol, e.g. 'AAPL' or 'PETR4.SA'.")

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        return _normalize_ticker(v)


class HistoricalSummaryInput(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol, e.g. 'MSFT' or 'VALE3.SA'.")
    period: str = Field(
        "6mo",
        description=f"Lookback window. One of {sorted(_VALID_PERIODS)}.",
    )

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        return _normalize_ticker(v)

    @field_validator("period")
    @classmethod
    def validate_period(cls, v: str) -> str:
        if v not in _VALID_PERIODS:
            raise ValueError(f"period must be one of {sorted(_VALID_PERIODS)}, got '{v}'.")
        return v


class CompareAssetsInput(BaseModel):
    tickers: list[str] = Field(..., description="Two or more ticker symbols to correlate.")
    period: str = Field("1y", description=f"Lookback window. One of {sorted(_VALID_PERIODS)}.")

    @field_validator("tickers")
    @classmethod
    def validate_tickers(cls, v: list[str]) -> list[str]:
        if len(v) < 2:
            raise ValueError("compare_assets needs at least 2 tickers.")
        normalized = [_normalize_ticker(t) for t in v]
        if len(set(normalized)) != len(normalized):
            raise ValueError("Duplicate tickers are not allowed.")
        return normalized

    @field_validator("period")
    @classmethod
    def validate_period(cls, v: str) -> str:
        if v not in _VALID_PERIODS:
            raise ValueError(f"period must be one of {sorted(_VALID_PERIODS)}, got '{v}'.")
        return v


class PortfolioMetricsInput(BaseModel):
    tickers: list[str] = Field(..., description="Ticker symbols in the portfolio.")
    weights: list[float] = Field(
        ..., description="Portfolio weight per ticker, same order, summing to 1.0."
    )
    period: str = Field("1y", description=f"Lookback window. One of {sorted(_VALID_PERIODS)}.")
    risk_free_rate: float = Field(
        0.0,
        description="Annualized risk-free rate used in the Sharpe ratio, e.g. 0.1075 for 10.75%.",
    )

    @field_validator("tickers")
    @classmethod
    def validate_tickers(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("tickers must not be empty.")
        normalized = [_normalize_ticker(t) for t in v]
        if len(set(normalized)) != len(normalized):
            raise ValueError("Duplicate tickers are not allowed.")
        return normalized

    @field_validator("period")
    @classmethod
    def validate_period(cls, v: str) -> str:
        if v not in _VALID_PERIODS:
            raise ValueError(f"period must be one of {sorted(_VALID_PERIODS)}, got '{v}'.")
        return v

    @model_validator(mode="after")
    def validate_weights(self) -> PortfolioMetricsInput:
        if len(self.weights) != len(self.tickers):
            raise ValueError(
                f"weights must have the same length as tickers ({len(self.tickers)}), "
                f"got {len(self.weights)}."
            )
        if any(w < 0 for w in self.weights):
            raise ValueError("weights must not be negative.")
        total = sum(self.weights)
        if abs(total - 1.0) > 1e-4:
            raise ValueError(f"weights must sum to 1.0, got {total:.4f}.")
        return self
