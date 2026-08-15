from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import DataQualityStatus, MarketRegimeRequest, Regime, RiskLevel, VolatilityEvidence
from app.service import _recommended_mode, _strategy_bias, analyze_market_regime


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["data"]["status"] == "healthy"
    assert payload["schema_version"] == "1.1"
    assert payload["correlation_id"]


def test_bull_market_regime():
    result = analyze_market_regime(
        MarketRegimeRequest(
            symbol="SPY",
            price=550,
            sma_50=530,
            sma_200=500,
            atr_pct=0.015,
            vix=15,
            market_breadth_pct=0.7,
        )
    )
    assert result.regime == Regime.BULL
    assert result.risk_level == RiskLevel.LOW
    assert result.profit_policy_context is not None
    assert result.profit_policy_context.regime == Regime.BULL
    assert result.profit_policy_context.atr_pct == 0.015
    assert result.profit_policy_context.trend_strength is not None
    assert result.recommended_mode == "normal"
    assert result.strategy_bias["news_momentum"] >= 0.20
    assert result.data_quality.status == DataQualityStatus.REVIEW
    assert result.data_quality.trade_allowed is True
    assert result.data_quality.timestamp_present is False


def test_bear_market_regime_is_cash_heavy():
    result = analyze_market_regime(
        MarketRegimeRequest(
            symbol="SPY",
            price=420,
            sma_50=450,
            sma_200=500,
            atr_pct=0.03,
            vix=25,
            market_breadth_pct=0.25,
        )
    )
    assert result.regime == Regime.BEAR
    assert result.risk_level == RiskLevel.MEDIUM
    assert result.recommended_mode == "cash_heavy"
    assert result.strategy_bias["core_dividend"] >= 0.70


def test_high_volatility_overrides_non_bear_to_volatile():
    result = analyze_market_regime(
        MarketRegimeRequest(
            symbol="QQQ",
            price=500,
            sma_50=490,
            sma_200=470,
            atr_pct=0.05,
            vix=32,
            market_breadth_pct=0.55,
        )
    )
    assert result.regime == Regime.VOLATILE
    assert result.risk_level == RiskLevel.HIGH
    assert result.recommended_mode == "cash_heavy"


@pytest.mark.parametrize("risk_level", RiskLevel)
def test_volatile_regime_is_explicitly_defensive_at_every_risk_level(risk_level):
    assert _recommended_mode(Regime.VOLATILE, risk_level) == "cash_heavy"
    assert _strategy_bias(Regime.VOLATILE, risk_level) == {
        "core_dividend": 0.70,
        "value_rebound": 0.25,
        "news_momentum": 0.05,
    }


def test_missing_volatility_is_unknown_and_blocks_trading():
    result = analyze_market_regime(
        MarketRegimeRequest(symbol="SPY", price=550, sma_50=530, sma_200=500)
    )

    assert result.regime == Regime.BULL
    assert result.risk_level == RiskLevel.UNKNOWN
    assert result.recommended_mode == "defensive"
    assert result.data_quality.status == DataQualityStatus.BLOCKED
    assert result.data_quality.trade_allowed is False
    assert result.data_quality.volatility_evidence == VolatilityEvidence.MISSING


def test_partial_volatility_is_review_but_not_blocked():
    result = analyze_market_regime(
        MarketRegimeRequest(symbol="SPY", price=550, sma_50=530, sma_200=500, atr_pct=0.015)
    )

    assert result.risk_level == RiskLevel.LOW
    assert result.data_quality.status == DataQualityStatus.REVIEW
    assert result.data_quality.trade_allowed is True
    assert result.data_quality.volatility_evidence == VolatilityEvidence.PARTIAL


def test_fresh_complete_market_data_is_good():
    result = analyze_market_regime(
        MarketRegimeRequest(
            symbol="SPY",
            price=550,
            sma_50=530,
            sma_200=500,
            atr_pct=0.015,
            vix=15,
            market_data_timestamp=datetime.now(timezone.utc),
        )
    )

    assert result.data_quality.status == DataQualityStatus.GOOD
    assert result.data_quality.trade_allowed is True
    assert result.data_quality.stale is False
    assert result.data_quality.data_age_seconds is not None


def test_stale_market_data_blocks_trading(monkeypatch):
    monkeypatch.setenv("MARKET_DATA_MAX_AGE_SECONDS", "300")
    result = analyze_market_regime(
        MarketRegimeRequest(
            symbol="SPY",
            price=550,
            sma_50=530,
            sma_200=500,
            atr_pct=0.015,
            vix=15,
            market_data_timestamp=datetime.now(timezone.utc) - timedelta(hours=1),
        )
    )

    assert result.data_quality.status == DataQualityStatus.BLOCKED
    assert result.data_quality.trade_allowed is False
    assert result.data_quality.stale is True


def test_future_market_data_timestamp_blocks_trading():
    result = analyze_market_regime(
        MarketRegimeRequest(
            symbol="SPY",
            price=550,
            sma_50=530,
            sma_200=500,
            atr_pct=0.015,
            vix=15,
            market_data_timestamp=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
    )

    assert result.data_quality.status == DataQualityStatus.BLOCKED
    assert result.data_quality.trade_allowed is False
    assert any("future" in reason for reason in result.data_quality.reasons)


def test_market_regime_endpoint():
    response = client.post(
        "/market/regime",
        headers={"X-Correlation-ID": "regime-test-123"},
        json={
            "symbol": "SPY",
            "price": 550,
            "sma_50": 530,
            "sma_200": 500,
            "atr_pct": 0.015,
            "vix": 15,
            "market_breadth_pct": 0.7,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["schema_version"] == "1.1"
    assert payload["correlation_id"] == "regime-test-123"
    assert payload["data"]["regime"] == "bull"
    assert payload["data"]["profit_policy_context"]["context_version"] == "profit-market-context.v1"
    assert payload["data"]["symbol"] == "SPY"
    assert payload["data"]["data_quality"]["status"] == "review"


def test_profit_policy_context_preserves_optional_volatility_and_timestamp():
    result = analyze_market_regime(
        MarketRegimeRequest(
            symbol="SPY",
            price=550,
            sma_50=530,
            sma_200=500,
            atr_pct=0.025,
            volatility_percentile=65,
            market_data_timestamp="2026-07-22T00:00:00Z",
        )
    )

    context = result.profit_policy_context
    assert context is not None
    assert context.volatility_percentile == 65
    assert context.observed_at.isoformat() == "2026-07-22T00:00:00+00:00"
    assert context.source == "market-regime-agent"


def test_profit_policy_context_does_not_fabricate_missing_trend_strength():
    result = analyze_market_regime(MarketRegimeRequest(symbol="SPY", atr_pct=0.04))

    assert result.profit_policy_context is not None
    assert result.profit_policy_context.trend_strength is None
    assert result.data_quality.trade_allowed is False
