from fastapi.testclient import TestClient

from app.main import app
from app.models import MarketRegimeRequest, Regime, RiskLevel
from app.service import analyze_market_regime


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
    assert payload["data"]["symbol"] == "SPY"
