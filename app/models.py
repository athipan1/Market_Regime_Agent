from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")


class Regime(str, Enum):
    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    VOLATILE = "volatile"
    UNKNOWN = "unknown"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class RecommendedMode(str, Enum):
    NORMAL = "normal"
    DEFENSIVE = "defensive"
    CASH_HEAVY = "cash_heavy"


class RecommendedStrategy(str, Enum):
    SMA_CROSSOVER = "sma_crossover"
    TREND_FOLLOWING = "trend_following"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"
    NO_TRADE = "no_trade"


class RecommendedAction(str, Enum):
    TRADE = "trade"
    NO_TRADE = "no_trade"
    REVIEW = "review"


class DataQualityStatus(str, Enum):
    GOOD = "good"
    REVIEW = "review"
    BLOCKED = "blocked"


class VolatilityEvidence(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"


class MarketRegimeRequest(BaseModel):
    symbol: str = Field(default="SPY", description="Market proxy symbol, usually SPY/QQQ/VTI.")
    price: Optional[float] = Field(default=None, ge=0)
    sma_50: Optional[float] = Field(default=None, ge=0)
    sma_200: Optional[float] = Field(default=None, ge=0)
    atr_pct: Optional[float] = Field(default=None, ge=0, description="ATR as percentage/ratio, e.g. 0.025 = 2.5%")
    volatility_percentile: Optional[float] = Field(default=None, ge=0, le=100)
    market_data_timestamp: Optional[datetime] = None
    vix: Optional[float] = Field(default=None, ge=0)
    market_breadth_pct: Optional[float] = Field(default=None, ge=0, le=1, description="Percent of stocks above key moving average.")


class MarketDataQuality(BaseModel):
    status: DataQualityStatus
    trade_allowed: bool
    trend_evidence_complete: bool
    volatility_evidence: VolatilityEvidence
    timestamp_present: bool
    stale: bool = False
    data_age_seconds: Optional[float] = Field(default=None, ge=0)
    reasons: List[str] = Field(default_factory=list)


class ProfitPolicyMarketContext(BaseModel):
    """Non-binding normalized context for deterministic profit policy."""

    context_version: str = "profit-market-context.v1"
    regime: Regime
    risk_level: RiskLevel
    atr_pct: Optional[float] = Field(default=None, ge=0)
    volatility_percentile: Optional[float] = Field(default=None, ge=0, le=100)
    trend_strength: Optional[float] = Field(default=None, ge=0, le=1)
    observed_at: Optional[datetime] = None
    source: str = "market-regime-agent"


class MarketRegimeData(BaseModel):
    symbol: str
    regime: Regime
    risk_level: RiskLevel
    recommended_mode: RecommendedMode
    confidence_score: float = Field(ge=0, le=1)
    reason: str
    strategy_bias: Dict[str, float]
    signals: Dict[str, Any]
    data_quality: MarketDataQuality
    profit_policy_context: Optional[ProfitPolicyMarketContext] = None


class StrategyRecommendation(BaseModel):
    symbol: str
    regime: Regime
    risk_level: RiskLevel
    recommended_mode: RecommendedMode
    recommended_action: RecommendedAction
    recommended_strategy: RecommendedStrategy
    position_size_multiplier: float = Field(ge=0, le=1)
    risk_multiplier: float = Field(default=1.0, ge=0, le=1)
    risk_budget_multiplier: float = Field(default=1.0, ge=0, le=1)
    exposure_cap: float = Field(default=1.0, ge=0, le=1)
    confidence_score: float = Field(ge=0, le=1)
    reason: str
    alternatives: Dict[str, float]
    allowed_strategies: List[RecommendedStrategy] = Field(default_factory=list)
    blocked_strategies: List[RecommendedStrategy] = Field(default_factory=list)
    decision_notes: List[str] = Field(default_factory=list)
    signals: Dict[str, Any]
    data_quality: MarketDataQuality


class HealthData(BaseModel):
    status: str = "healthy"
    service: str = "market-regime-agent"


class StandardAgentResponse(BaseModel, Generic[T]):
    status: str
    agent_type: str = "market-regime-agent"
    version: str = "0.2.0"
    schema_version: str = "1.1"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: Optional[str] = None
    data: Optional[T] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[Dict[str, Any]] = None
    confidence_score: Optional[float] = Field(default=None, ge=0, le=1)
