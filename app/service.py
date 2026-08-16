from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Dict, Tuple

from app.models import (
    DataQualityStatus,
    MarketDataQuality,
    MarketRegimeData,
    MarketRegimeRequest,
    ProfitPolicyMarketContext,
    RecommendedMode,
    Regime,
    RiskLevel,
    VolatilityEvidence,
)


BASE_STRATEGY_BIAS = {
    "core_dividend": 0.50,
    "value_rebound": 0.30,
    "news_momentum": 0.20,
}

DEFAULT_MAX_MARKET_DATA_AGE_SECONDS = 900.0
FUTURE_TIMESTAMP_TOLERANCE_SECONDS = 60.0


def _max_market_data_age_seconds() -> float:
    raw = os.getenv("MARKET_DATA_MAX_AGE_SECONDS", str(DEFAULT_MAX_MARKET_DATA_AGE_SECONDS))
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_MAX_MARKET_DATA_AGE_SECONDS
    return max(1.0, value)


def _risk_from_volatility(atr_pct: float | None, vix: float | None) -> RiskLevel:
    if atr_pct is None and vix is None:
        return RiskLevel.UNKNOWN

    atr_value = atr_pct if atr_pct is not None else 0.0
    vix_value = vix if vix is not None else 0.0
    if atr_value >= 0.04 or vix_value >= 30:
        return RiskLevel.HIGH
    if atr_value >= 0.025 or vix_value >= 22:
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
    if regime == Regime.VOLATILE:
        return {"core_dividend": 0.70, "value_rebound": 0.25, "news_momentum": 0.05}
    if risk_level in {RiskLevel.HIGH, RiskLevel.UNKNOWN}:
        return {"core_dividend": 0.70, "value_rebound": 0.25, "news_momentum": 0.05}
    if regime == Regime.BULL:
        return {"core_dividend": 0.45, "value_rebound": 0.30, "news_momentum": 0.25}
    if regime == Regime.BEAR:
        return {"core_dividend": 0.75, "value_rebound": 0.20, "news_momentum": 0.05}
    if regime == Regime.SIDEWAYS:
        return {"core_dividend": 0.60, "value_rebound": 0.35, "news_momentum": 0.05}
    return BASE_STRATEGY_BIAS.copy()


def _recommended_mode(regime: Regime, risk_level: RiskLevel) -> RecommendedMode:
    if regime == Regime.VOLATILE:
        return RecommendedMode.CASH_HEAVY
    if risk_level == RiskLevel.UNKNOWN:
        return RecommendedMode.DEFENSIVE
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
    if risk_level in {RiskLevel.MEDIUM, RiskLevel.HIGH}:
        score += 0.05
    return round(max(0.0, min(score, 0.85)), 4)


def _trend_strength(request: MarketRegimeRequest) -> float | None:
    """Normalize price/SMA separation without fabricating missing evidence."""
    if (
        request.price is None
        or request.sma_50 is None
        or request.sma_200 is None
        or request.price <= 0
        or request.sma_200 <= 0
    ):
        return None
    price_separation = abs(request.price - request.sma_50) / request.price
    average_separation = abs(request.sma_50 - request.sma_200) / request.sma_200
    return round(min(1.0, (price_separation + average_separation) / 0.20), 4)


def _market_data_quality(
    request: MarketRegimeRequest,
    *,
    now: datetime | None = None,
) -> MarketDataQuality:
    trend_values = (request.price, request.sma_50, request.sma_200)
    trend_complete = all(value is not None and value > 0 for value in trend_values)

    volatility_count = sum(value is not None for value in (request.atr_pct, request.vix))
    if volatility_count == 2:
        volatility_evidence = VolatilityEvidence.COMPLETE
    elif volatility_count == 1:
        volatility_evidence = VolatilityEvidence.PARTIAL
    else:
        volatility_evidence = VolatilityEvidence.MISSING

    reasons: list[str] = []
    trade_allowed = True
    stale = False
    data_age_seconds: float | None = None

    if not trend_complete:
        trade_allowed = False
        reasons.append("trend evidence is incomplete; price, SMA50, and SMA200 are required")

    if volatility_evidence == VolatilityEvidence.MISSING:
        trade_allowed = False
        reasons.append("volatility evidence is missing; provide ATR percent or VIX")
    elif volatility_evidence == VolatilityEvidence.PARTIAL:
        reasons.append("volatility evidence is partial; only one of ATR percent or VIX is present")

    observed_at = request.market_data_timestamp
    timestamp_present = observed_at is not None
    if observed_at is None:
        reasons.append("market data timestamp is missing; freshness cannot be verified")
    elif observed_at.tzinfo is None or observed_at.utcoffset() is None:
        trade_allowed = False
        reasons.append("market data timestamp must include a timezone offset")
    else:
        current = now or datetime.now(timezone.utc)
        age_seconds = (current - observed_at.astimezone(timezone.utc)).total_seconds()
        if age_seconds < -FUTURE_TIMESTAMP_TOLERANCE_SECONDS:
            trade_allowed = False
            reasons.append("market data timestamp is too far in the future")
        else:
            data_age_seconds = round(max(0.0, age_seconds), 3)
            if age_seconds > _max_market_data_age_seconds():
                stale = True
                trade_allowed = False
                reasons.append("market data is stale")

    if not trade_allowed:
        status = DataQualityStatus.BLOCKED
    elif reasons:
        status = DataQualityStatus.REVIEW
    else:
        status = DataQualityStatus.GOOD

    return MarketDataQuality(
        status=status,
        trade_allowed=trade_allowed,
        trend_evidence_complete=trend_complete,
        volatility_evidence=volatility_evidence,
        timestamp_present=timestamp_present,
        stale=stale,
        data_age_seconds=data_age_seconds,
        reasons=reasons,
    )


def analyze_market_regime(request: MarketRegimeRequest) -> MarketRegimeData:
    trend_regime, trend_reason = _classify_trend(request.price, request.sma_50, request.sma_200)
    risk_level = _risk_from_volatility(request.atr_pct, request.vix)
    data_quality = _market_data_quality(request)

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

    if risk_level == RiskLevel.UNKNOWN:
        risk_note = "Risk level is unknown because volatility evidence is missing."
    else:
        risk_note = f"Risk level is {risk_level.value}."

    quality_note = ""
    if data_quality.status != DataQualityStatus.GOOD:
        quality_note = f" Data quality is {data_quality.status.value}."

    reason = f"{trend_reason}. {risk_note}{breadth_note}{quality_note}"
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
            "market_data_timestamp": request.market_data_timestamp,
        },
        data_quality=data_quality,
        profit_policy_context=ProfitPolicyMarketContext(
            regime=regime,
            risk_level=risk_level,
            atr_pct=request.atr_pct,
            volatility_percentile=request.volatility_percentile,
            trend_strength=_trend_strength(request),
            observed_at=request.market_data_timestamp,
        ),
    )
