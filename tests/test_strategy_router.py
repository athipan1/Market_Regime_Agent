import itertools

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import (
    DataQualityStatus,
    MarketDataQuality,
    MarketRegimeData,
    MarketRegimeRequest,
    RecommendedAction,
    RecommendedStrategy,
    Regime,
    RiskLevel,
    VolatilityEvidence,
)
from app.service import _recommended_mode, analyze_market_regime
from app.strategy_router import MULTIPLIER_FIELDS, recommend_strategy


client = TestClient(app)


def _good_quality() -> MarketDataQuality:
    return MarketDataQuality(
        status=DataQualityStatus.GOOD,
        trade_allowed=True,
        trend_evidence_complete=True,
        volatility_evidence=VolatilityEvidence.COMPLETE,
        timestamp_present=True,
        stale=False,
        data_age_seconds=1.0,
        reasons=[],
    )


def _regime_data(regime: Regime, risk_level: RiskLevel) -> MarketRegimeData:
    return MarketRegimeData(
        symbol="SPY",
        regime=regime,
        risk_level=risk_level,
        recommended_mode=_recommended_mode(regime, risk_level),
        confidence_score=0.8,
        reason="test fixture",
        strategy_bias={},
        signals={},
        data_quality=_good_quality(),
    )


@pytest.mark.parametrize(
    ("regime", "risk_level"),
    itertools.product(Regime, RiskLevel),
    ids=lambda value: value.value,
)
def test_all_regime_and_risk_combinations_preserve_multiplier_contract(regime, risk_level):
    recommendation = recommend_strategy(_regime_data(regime, risk_level))

    if not recommendation.allowed_strategies:
        assert all(getattr(recommendation, field) == 0.0 for field in MULTIPLIER_FIELDS)
        assert recommendation.recommended_strategy == RecommendedStrategy.NO_TRADE
        assert recommendation.recommended_action != RecommendedAction.TRADE
    else:
        assert recommendation.recommended_action == RecommendedAction.TRADE
        assert recommendation.recommended_strategy in recommendation.allowed_strategies

    assert not (set(recommendation.allowed_strategies) & set(recommendation.blocked_strategies))
    assert RecommendedStrategy.NO_TRADE not in recommendation.blocked_strategies


def test_bear_high_blocks_all_strategies_and_zeroes_all_multipliers():
    recommendation = recommend_strategy(_regime_data(Regime.BEAR, RiskLevel.HIGH))

    assert recommendation.allowed_strategies == []
    assert recommendation.recommended_action == RecommendedAction.NO_TRADE
    assert recommendation.recommended_strategy == RecommendedStrategy.NO_TRADE
    assert all(getattr(recommendation, field) == 0.0 for field in MULTIPLIER_FIELDS)


def test_output_validation_rejects_empty_allowed_strategies_with_nonzero_multiplier(monkeypatch):
    monkeypatch.setattr(
        "app.strategy_router._recommendation_multipliers",
        lambda *args, **kwargs: {
            "position_size_multiplier": 0.25,
            "risk_multiplier": 0.0,
            "risk_budget_multiplier": 0.0,
            "exposure_cap": 0.0,
        },
    )

    with pytest.raises(RuntimeError, match="safety invariant violated"):
        recommend_strategy(_regime_data(Regime.BEAR, RiskLevel.HIGH))


def test_bull_regime_recommends_trend_following():
    regime = analyze_market_regime(
        MarketRegimeRequest(symbol="SPY", price=550, sma_50=530, sma_200=500, atr_pct=0.015, vix=15, market_breadth_pct=0.70)
    )

    recommendation = recommend_strategy(regime)

    assert recommendation.recommended_action == RecommendedAction.TRADE
    assert recommendation.recommended_strategy == RecommendedStrategy.TREND_FOLLOWING
    assert recommendation.position_size_multiplier == 1.0
    assert recommendation.risk_multiplier == 1.0
    assert recommendation.risk_budget_multiplier == 1.0
    assert recommendation.exposure_cap == 1.0
    assert recommendation.allowed_strategies[0] == RecommendedStrategy.TREND_FOLLOWING
    assert recommendation.alternatives["trend_following"] > recommendation.alternatives["mean_reversion"]


def test_sideways_regime_recommends_mean_reversion():
    regime = analyze_market_regime(
        MarketRegimeRequest(symbol="SPY", price=500, sma_50=502, sma_200=500, atr_pct=0.018, vix=18, market_breadth_pct=0.50)
    )

    recommendation = recommend_strategy(regime)

    assert recommendation.recommended_action == RecommendedAction.TRADE
    assert recommendation.recommended_strategy == RecommendedStrategy.MEAN_REVERSION
    assert recommendation.position_size_multiplier == 0.5
    assert recommendation.risk_multiplier == 0.5
    assert recommendation.risk_budget_multiplier == 0.6
    assert recommendation.exposure_cap == 0.5
    assert recommendation.allowed_strategies == [RecommendedStrategy.MEAN_REVERSION, RecommendedStrategy.SMA_CROSSOVER]


def test_bear_regime_recommends_best_allowed_strategy_not_no_trade_sentinel():
    regime = analyze_market_regime(
        MarketRegimeRequest(symbol="SPY", price=420, sma_50=450, sma_200=500, atr_pct=0.03, vix=25, market_breadth_pct=0.25)
    )

    recommendation = recommend_strategy(regime)

    assert recommendation.recommended_action == RecommendedAction.TRADE
    assert recommendation.recommended_strategy == RecommendedStrategy.MEAN_REVERSION
    assert recommendation.position_size_multiplier == 0.25
    assert recommendation.risk_multiplier == 0.25
    assert recommendation.risk_budget_multiplier == 0.35
    assert recommendation.exposure_cap == 0.25
    assert recommendation.allowed_strategies == [RecommendedStrategy.MEAN_REVERSION, RecommendedStrategy.SMA_CROSSOVER]
    assert recommendation.alternatives["no_trade"] > recommendation.alternatives["mean_reversion"]


def test_volatile_regime_recommends_no_trade_and_zero_size():
    regime = analyze_market_regime(
        MarketRegimeRequest(symbol="QQQ", price=500, sma_50=490, sma_200=470, atr_pct=0.05, vix=32, market_breadth_pct=0.55)
    )

    recommendation = recommend_strategy(regime)

    assert recommendation.recommended_action == RecommendedAction.NO_TRADE
    assert recommendation.recommended_strategy == RecommendedStrategy.NO_TRADE
    assert recommendation.position_size_multiplier == 0.0
    assert recommendation.risk_multiplier == 0.0
    assert recommendation.risk_budget_multiplier == 0.0
    assert recommendation.exposure_cap == 0.0
    assert recommendation.allowed_strategies == []
    assert RecommendedStrategy.NO_TRADE not in recommendation.blocked_strategies
    assert recommendation.decision_notes


def test_missing_volatility_returns_review_and_zero_multipliers():
    regime = analyze_market_regime(
        MarketRegimeRequest(symbol="SPY", price=550, sma_50=530, sma_200=500)
    )

    recommendation = recommend_strategy(regime)

    assert recommendation.risk_level == RiskLevel.UNKNOWN
    assert recommendation.recommended_action == RecommendedAction.REVIEW
    assert recommendation.recommended_strategy == RecommendedStrategy.NO_TRADE
    assert recommendation.allowed_strategies == []
    assert all(getattr(recommendation, field) == 0.0 for field in MULTIPLIER_FIELDS)


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
    assert payload["schema_version"] == "1.1"
    assert payload["correlation_id"]
    assert payload["data"]["recommended_action"] == "trade"
    assert payload["data"]["recommended_strategy"] == "trend_following"
    assert payload["data"]["regime"] == "bull"
    assert payload["data"]["symbol"] == "SPY"
    assert payload["data"]["risk_multiplier"] == 1.0
    assert payload["data"]["risk_budget_multiplier"] == 1.0
    assert payload["data"]["exposure_cap"] == 1.0
    assert payload["data"]["allowed_strategies"] == ["trend_following", "breakout", "sma_crossover"]
    assert "decision_notes" in payload["data"]
    assert payload["data"]["data_quality"]["status"] == "review"
