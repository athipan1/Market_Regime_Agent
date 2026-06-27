from __future__ import annotations

from typing import Dict, Tuple

from app.models import MarketRegimeData, MarketRegimeRequest, RecommendedMode, Regime, RiskLevel


BASE_STRATEGY_BIAS = {
    "core_dividend": 0.50,
    "value_rebound": 0.30,
    "news_momentum": 0.20,
}


def _risk_from_volatility(atr_pct: float | None, vix: float | None) -> RiskLevel:
    atr_pct = atr_pct or 0.0
    vix = vix or 0.0
    if atr_pct >= 0.04 or vix >= 30:
        return RiskLevel.HIGH
    if atr_pct >= 0.025 or vix >= 22:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _classify_trend(price: float | None, sma_50: float | None, sma_200: float | None) -> Tuple[Regime, str]:
    if price is None or sma_50 is None or sma_200 is None or sma_200 <= 0:
        return Regime.UNKNOWN, "insufficient moving-average data"

    bullish_stack = price > sma_50 > sma_200
    bearish_stack = price < sma_50 < sma_200
    near_flat = abs(sma_50 - sma_200) / sma_200 < 0.02

    if bullish_stack:
        return Regime.BULL, "price is above SMA50 and SMA50 is above SMA200"
    if bearish_stack:
        return Regime.BEAR, "price is below SMA50 and SMA50 is below SMA200"
    if near_flat:
        return Regime.SIDEWAYS, "SMA50 and SMA200 are close together"
    return Regime.SIDEWAYS, "trend structure is mixed"


def _strategy_bias(regime: Regime, risk_level: RiskLevel) -> Dict[str, float]:
    if risk_level == RiskLevel.HIGH:
        return {"core_dividend": 0.70, "value_rebound": 0.25, "news_momentum": 0.05}
    if regime == Regime.BULL:
        return {"core_dividend": 0.45, "value_rebound": 0.30, "news_momentum": 0.25}
    if regime == Regime.BEAR:
        return {"core_dividend": 0.75, "value_rebound": 0.20, "news_momentum": 0.05}
    if regime == Regime.SIDEWAYS:
        return {"core_dividend": 0.60, "value_rebound": 0.35, "news_momentum": 0.05}
    return BASE_STRATEGY_BIAS.copy()


def _recommended_mode(regime: Regime, risk_level: RiskLevel) -> RecommendedMode:
    if risk_level == RiskLevel.HIGH or regime == Regime.BEAR:
        return RecommendedMode.CASH_HEAVY
    if risk_level == RiskLevel.MEDIUM or regime in {Regime.SIDEWAYS, Regime.UNKNOWN}:
        return RecommendedMode.DEFENSIVE
    return RecommendedMode.NORMAL


def _confidence(request: MarketRegimeRequest, regime: Regime, risk_level: RiskLevel) -> float:
    available = sum(
        value is not None
        for value in [request.price, request.sma_50, request.sma_200, request.atr_pct, request.vix, request.market_breadth_pct]
    )
    score = 0.35 + (available * 0.08)
    if regime != Regime.UNKNOWN:
        score += 0.10
    if risk_level != RiskLevel.LOW:
        score += 0.05
    return round(max(0.0, min(score, 0.85)), 4)


def analyze_market_regime(request: MarketRegimeRequest) -> MarketRegimeData:
    trend_regime, trend_reason = _classify_trend(request.price, request.sma_50, request.sma_200)
    risk_level = _risk_from_volatility(request.atr_pct, request.vix)

    regime = trend_regime
    if risk_level == RiskLevel.HIGH and trend_regime != Regime.BEAR:
        regime = Regime.VOLATILE

    breadth_note = ""
    if request.market_breadth_pct is not None:
        if request.market_breadth_pct < 0.35 and regime == Regime.BULL:
            regime = Regime.SIDEWAYS
            breadth_note = " Market breadth is weak, so bullish signal is downgraded."
        elif request.market_breadth_pct > 0.65 and regime == Regime.SIDEWAYS:
            breadth_note = " Market breadth is supportive, but trend is not fully confirmed yet."

    reason = f"{trend_reason}. Risk level is {risk_level.value}.{breadth_note}"
    return MarketRegimeData(
        symbol=request.symbol.upper(),
        regime=regime,
        risk_level=risk_level,
        recommended_mode=_recommended_mode(regime, risk_level),
        confidence_score=_confidence(request, regime, risk_level),
        reason=reason,
        strategy_bias=_strategy_bias(regime, risk_level),
        signals={
            "price": request.price,
            "sma_50": request.sma_50,
            "sma_200": request.sma_200,
            "atr_pct": request.atr_pct,
            "vix": request.vix,
            "market_breadth_pct": request.market_breadth_pct,
        },
    )
