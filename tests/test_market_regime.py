import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import MarketRegimeRequest, Regime, RiskLevel
from app.service import _recommended_mode, _strategy_bias, analyze_market_regime


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["data"]["status"] == "healthy"


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


def test_market_regime_endpoint():
    response = client.post(
        "/market/regime",
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
    assert payload["data"]["regime"] == "bull"
    assert payload["data"]["profit_policy_context"]["context_version"] == (
        "profit-market-context.v1"
    )
    assert payload["data"]["symbol"] == "SPY"


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
    result = analyze_market_regime(
        MarketRegimeRequest(symbol="SPY", atr_pct=0.04)
    )

    assert result.profit_policy_context is not None
    assert result.profit_policy_context.trend_strength is None
