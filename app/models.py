from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Generic, Optional, TypeVar

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


class MarketRegimeRequest(BaseModel):
    symbol: str = Field(default="SPY", description="Market proxy symbol, usually SPY/QQQ/VTI.")
    price: Optional[float] = Field(default=None, ge=0)
    sma_50: Optional[float] = Field(default=None, ge=0)
    sma_200: Optional[float] = Field(default=None, ge=0)
    atr_pct: Optional[float] = Field(default=None, ge=0, description="ATR as percentage/ratio, e.g. 0.025 = 2.5%")
    vix: Optional[float] = Field(default=None, ge=0)
    market_breadth_pct: Optional[float] = Field(default=None, ge=0, le=1, description="Percent of stocks above key moving average.")


class MarketRegimeData(BaseModel):
    symbol: str
    regime: Regime
    risk_level: RiskLevel
    recommended_mode: RecommendedMode
    confidence_score: float = Field(ge=0, le=1)
    reason: str
    strategy_bias: Dict[str, float]
    signals: Dict[str, Any]


class StrategyRecommendation(BaseModel):
    symbol: str
    regime: Regime
    risk_level: RiskLevel
    recommended_mode: RecommendedMode
    recommended_strategy: RecommendedStrategy
    position_size_multiplier: float = Field(ge=0, le=1)
    confidence_score: float = Field(ge=0, le=1)
    reason: str
    alternatives: Dict[str, float]
    signals: Dict[str, Any]


class HealthData(BaseModel):
    status: str = "healthy"
    service: str = "market-regime-agent"


class StandardAgentResponse(BaseModel, Generic[T]):
    status: str
    agent_type: str = "market-regime-agent"
    version: str = "0.1.0"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data: Optional[T] = None
    error: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
