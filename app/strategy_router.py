from __future__ import annotations

from app.models import (
    MarketRegimeData,
    RecommendedMode,
    RecommendedStrategy,
    Regime,
    RiskLevel,
    StrategyRecommendation,
)


def _alternatives_for_regime(regime: Regime, risk_level: RiskLevel) -> dict[str, float]:
    if risk_level == RiskLevel.HIGH:
        return {
            RecommendedStrategy.NO_TRADE.value: 0.70,
            RecommendedStrategy.MEAN_REVERSION.value: 0.15,
            RecommendedStrategy.TREND_FOLLOWING.value: 0.10,
            RecommendedStrategy.BREAKOUT.value: 0.05,
        }
    if regime == Regime.BULL:
        return {
            RecommendedStrategy.TREND_FOLLOWING.value: 0.55,
            RecommendedStrategy.BREAKOUT.value: 0.25,
            RecommendedStrategy.SMA_CROSSOVER.value: 0.15,
            RecommendedStrategy.MEAN_REVERSION.value: 0.05,
        }
    if regime == Regime.SIDEWAYS:
        return {
            RecommendedStrategy.MEAN_REVERSION.value: 0.55,
            RecommendedStrategy.SMA_CROSSOVER.value: 0.20,
            RecommendedStrategy.BREAKOUT.value: 0.15,
            RecommendedStrategy.TREND_FOLLOWING.value: 0.10,
        }
    if regime == Regime.BEAR:
        return {
            RecommendedStrategy.NO_TRADE.value: 0.65,
            RecommendedStrategy.MEAN_REVERSION.value: 0.20,
            RecommendedStrategy.SMA_CROSSOVER.value: 0.10,
            RecommendedStrategy.TREND_FOLLOWING.value: 0.05,
        }
    return {
        RecommendedStrategy.SMA_CROSSOVER.value: 0.35,
        RecommendedStrategy.MEAN_REVERSION.value: 0.25,
        RecommendedStrategy.TREND_FOLLOWING.value: 0.25,
        RecommendedStrategy.BREAKOUT.value: 0.15,
    }


def _position_size_multiplier(regime: Regime, risk_level: RiskLevel, recommended_mode: RecommendedMode) -> float:
    if risk_level == RiskLevel.HIGH:
        return 0.0 if regime == Regime.VOLATILE else 0.25
    if recommended_mode == RecommendedMode.CASH_HEAVY:
        return 0.25
    if recommended_mode == RecommendedMode.DEFENSIVE:
        return 0.50
    if regime == Regime.SIDEWAYS:
        return 0.75
    return 1.0


def _reason(regime: Regime, strategy: RecommendedStrategy, risk_level: RiskLevel) -> str:
    if strategy == RecommendedStrategy.TREND_FOLLOWING:
        return f"{regime.value} regime favors trend-following setups while risk is {risk_level.value}."
    if strategy == RecommendedStrategy.MEAN_REVERSION:
        return f"{regime.value} regime favors mean-reversion setups while risk is {risk_level.value}."
    if strategy == RecommendedStrategy.BREAKOUT:
        return f"{regime.value} regime favors breakout setups while risk is {risk_level.value}."
    if strategy == RecommendedStrategy.NO_TRADE:
        return f"{regime.value} regime with {risk_level.value} risk favors capital protection over new entries."
    return f"{regime.value} regime uses sma_crossover as the neutral fallback strategy."


def recommend_strategy(regime_data: MarketRegimeData) -> StrategyRecommendation:
    alternatives = _alternatives_for_regime(regime_data.regime, regime_data.risk_level)
    recommended = RecommendedStrategy(max(alternatives, key=alternatives.get))
    multiplier = _position_size_multiplier(regime_data.regime, regime_data.risk_level, regime_data.recommended_mode)

    return StrategyRecommendation(
        symbol=regime_data.symbol,
        regime=regime_data.regime,
        risk_level=regime_data.risk_level,
        recommended_mode=regime_data.recommended_mode,
        recommended_strategy=recommended,
        position_size_multiplier=multiplier,
        confidence_score=regime_data.confidence_score,
        reason=_reason(regime_data.regime, recommended, regime_data.risk_level),
        alternatives=alternatives,
        signals=regime_data.signals,
    )
