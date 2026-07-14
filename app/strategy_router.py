from __future__ import annotations

from app.models import (
    MarketRegimeData,
    RecommendedMode,
    RecommendedStrategy,
    Regime,
    RiskLevel,
    StrategyRecommendation,
)


TRADEABLE_STRATEGIES = [
    RecommendedStrategy.SMA_CROSSOVER,
    RecommendedStrategy.TREND_FOLLOWING,
    RecommendedStrategy.MEAN_REVERSION,
    RecommendedStrategy.BREAKOUT,
]

MULTIPLIER_FIELDS = (
    "position_size_multiplier",
    "risk_multiplier",
    "risk_budget_multiplier",
    "exposure_cap",
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


def _risk_multiplier(regime: Regime, risk_level: RiskLevel) -> float:
    if regime == Regime.VOLATILE or risk_level == RiskLevel.HIGH:
        return 0.0 if regime == Regime.VOLATILE else 0.25
    if regime == Regime.BEAR:
        return 0.25
    if risk_level == RiskLevel.MEDIUM or regime in {Regime.SIDEWAYS, Regime.UNKNOWN}:
        return 0.50
    return 1.0


def _risk_budget_multiplier(regime: Regime, risk_level: RiskLevel) -> float:
    if risk_level == RiskLevel.HIGH:
        return 0.0 if regime == Regime.VOLATILE else 0.25
    if regime == Regime.BEAR:
        return 0.35
    if regime in {Regime.SIDEWAYS, Regime.UNKNOWN} or risk_level == RiskLevel.MEDIUM:
        return 0.60
    return 1.0


def _exposure_cap(regime: Regime, risk_level: RiskLevel) -> float:
    if regime == Regime.VOLATILE:
        return 0.0
    if regime == Regime.BEAR or risk_level == RiskLevel.HIGH:
        return 0.25
    if regime == Regime.SIDEWAYS or risk_level == RiskLevel.MEDIUM:
        return 0.50
    if regime == Regime.UNKNOWN:
        return 0.40
    return 1.0


def _recommendation_multipliers(
    regime: Regime,
    risk_level: RiskLevel,
    recommended_mode: RecommendedMode,
    allowed_strategies: list[RecommendedStrategy],
) -> dict[str, float]:
    if not allowed_strategies:
        return {field: 0.0 for field in MULTIPLIER_FIELDS}

    return {
        "position_size_multiplier": _position_size_multiplier(regime, risk_level, recommended_mode),
        "risk_multiplier": _risk_multiplier(regime, risk_level),
        "risk_budget_multiplier": _risk_budget_multiplier(regime, risk_level),
        "exposure_cap": _exposure_cap(regime, risk_level),
    }


def _allowed_strategies(regime: Regime, risk_level: RiskLevel) -> list[RecommendedStrategy]:
    if regime == Regime.VOLATILE or risk_level == RiskLevel.HIGH:
        return []
    if regime == Regime.BEAR:
        return [RecommendedStrategy.MEAN_REVERSION, RecommendedStrategy.SMA_CROSSOVER]
    if regime == Regime.SIDEWAYS:
        return [RecommendedStrategy.MEAN_REVERSION, RecommendedStrategy.SMA_CROSSOVER]
    if regime == Regime.BULL:
        return [RecommendedStrategy.TREND_FOLLOWING, RecommendedStrategy.BREAKOUT, RecommendedStrategy.SMA_CROSSOVER]
    return [RecommendedStrategy.SMA_CROSSOVER, RecommendedStrategy.MEAN_REVERSION]


def _blocked_strategies(regime: Regime, risk_level: RiskLevel) -> list[RecommendedStrategy]:
    allowed = set(_allowed_strategies(regime, risk_level))
    blocked = [strategy for strategy in TRADEABLE_STRATEGIES if strategy not in allowed]
    if not allowed:
        blocked.append(RecommendedStrategy.NO_TRADE)
    return blocked


def _decision_notes(regime: Regime, risk_level: RiskLevel, allowed: list[RecommendedStrategy]) -> list[str]:
    notes: list[str] = []
    if regime == Regime.VOLATILE:
        notes.append("Volatile regime blocks new strategy entries and sets exposure cap to zero.")
    elif regime == Regime.BEAR:
        notes.append("Bear regime prioritizes capital protection and limits exposure.")
    elif regime == Regime.SIDEWAYS:
        notes.append("Sideways regime favors mean-reversion and reduced sizing.")
    elif regime == Regime.BULL:
        notes.append("Bull regime allows directional strategies with normal sizing.")
    else:
        notes.append("Unknown regime uses conservative fallback strategy routing.")

    if risk_level != RiskLevel.LOW:
        notes.append(f"{risk_level.value} risk level reduces risk budget and exposure.")
    if not allowed:
        notes.append("No tradeable strategies are allowed until risk conditions improve.")
    return notes


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


def _validate_strategy_recommendation(recommendation: StrategyRecommendation) -> None:
    if recommendation.allowed_strategies:
        return

    nonzero_multipliers = {
        field: getattr(recommendation, field)
        for field in MULTIPLIER_FIELDS
        if getattr(recommendation, field) != 0.0
    }
    if nonzero_multipliers:
        raise RuntimeError(
            "StrategyRecommendation safety invariant violated: allowed_strategies is empty "
            f"but multipliers are non-zero: {nonzero_multipliers}"
        )


def recommend_strategy(regime_data: MarketRegimeData) -> StrategyRecommendation:
    alternatives = _alternatives_for_regime(regime_data.regime, regime_data.risk_level)
    recommended = RecommendedStrategy(max(alternatives, key=alternatives.get))
    allowed = _allowed_strategies(regime_data.regime, regime_data.risk_level)
    multipliers = _recommendation_multipliers(
        regime_data.regime,
        regime_data.risk_level,
        regime_data.recommended_mode,
        allowed,
    )

    recommendation = StrategyRecommendation(
        symbol=regime_data.symbol,
        regime=regime_data.regime,
        risk_level=regime_data.risk_level,
        recommended_mode=regime_data.recommended_mode,
        recommended_strategy=recommended,
        position_size_multiplier=multipliers["position_size_multiplier"],
        risk_multiplier=multipliers["risk_multiplier"],
        risk_budget_multiplier=multipliers["risk_budget_multiplier"],
        exposure_cap=multipliers["exposure_cap"],
        confidence_score=regime_data.confidence_score,
        reason=_reason(regime_data.regime, recommended, regime_data.risk_level),
        alternatives=alternatives,
        allowed_strategies=allowed,
        blocked_strategies=_blocked_strategies(regime_data.regime, regime_data.risk_level),
        decision_notes=_decision_notes(regime_data.regime, regime_data.risk_level, allowed),
        signals=regime_data.signals,
    )
    _validate_strategy_recommendation(recommendation)
    return recommendation
