from fastapi.testclient import TestClient

from app.main import app
from app.models import MarketRegimeRequest, RecommendedStrategy
from app.service import analyze_market_regime
from app.strategy_router import recommend_strategy


client = TestClient(app)


def test_bull_regime_recommends_trend_following():
    regime = analyze_market_regime(
        MarketRegimeRequest(symbol="SPY", price=550, sma_50=530, sma_200=500, atr_pct=0.015, vix=15, market_breadth_pct=0.70)
    )

    recommendation = recommend_strategy(regime)

    assert recommendation.recommended_strategy == RecommendedStrategy.TREND_FOLLOWING
    assert recommendation.position_size_multiplier == 1.0
    assert recommendation.alternatives["trend_following"] > recommendation.alternatives["mean_reversion"]


def test_sideways_regime_recommends_mean_reversion():
    regime = analyze_market_regime(
        MarketRegimeRequest(symbol="SPY", price=500, sma_50=502, sma_200=500, atr_pct=0.018, vix=18, market_breadth_pct=0.50)
    )

    recommendation = recommend_strategy(regime)

    assert recommendation.recommended_strategy == RecommendedStrategy.MEAN_REVERSION
    assert recommendation.position_size_multiplier == 0.5


def test_bear_regime_recommends_no_trade():
    regime = analyze_market_regime(
        MarketRegimeRequest(symbol="SPY", price=420, sma_50=450, sma_200=500, atr_pct=0.03, vix=25, market_breadth_pct=0.25)
    )

    recommendation = recommend_strategy(regime)

    assert recommendation.recommended_strategy == RecommendedStrategy.NO_TRADE
    assert recommendation.position_size_multiplier == 0.25


def test_volatile_regime_recommends_no_trade_and_zero_size():
    regime = analyze_market_regime(
        MarketRegimeRequest(symbol="QQQ", price=500, sma_50=490, sma_200=470, atr_pct=0.05, vix=32, market_breadth_pct=0.55)
    )

    recommendation = recommend_strategy(regime)

    assert recommendation.recommended_strategy == RecommendedStrategy.NO_TRADE
    assert recommendation.position_size_multiplier == 0.0


def test_market_strategy_endpoint():
    response = client.post(
        "/market/strategy",
        json={
            "symbol": "SPY",
            "price": 550,
            "sma_50": 530,
            "sma_200": 500,
            "atr_pct": 0.015,
            "vix": 15,
            "market_breadth_pct": 0.70,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["data"]["recommended_strategy"] == "trend_following"
    assert payload["data"]["regime"] == "bull"
    assert payload["data"]["symbol"] == "SPY"
