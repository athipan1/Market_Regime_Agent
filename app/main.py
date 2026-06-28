from __future__ import annotations

from fastapi import FastAPI

from app.models import HealthData, MarketRegimeData, MarketRegimeRequest, StandardAgentResponse, StrategyRecommendation
from app.service import analyze_market_regime
from app.strategy_router import recommend_strategy


app = FastAPI(
    title="Market Regime Agent",
    description="Classifies market regime and risk mode for the multi-agent trading system.",
    version="0.1.0",
)


@app.get("/health", response_model=StandardAgentResponse[HealthData])
def health() -> StandardAgentResponse[HealthData]:
    return StandardAgentResponse(status="success", data=HealthData())


@app.post("/market/regime", response_model=StandardAgentResponse[MarketRegimeData])
def market_regime(request: MarketRegimeRequest) -> StandardAgentResponse[MarketRegimeData]:
    data = analyze_market_regime(request)
    return StandardAgentResponse(status="success", data=data)


@app.post("/market/risk-level", response_model=StandardAgentResponse[MarketRegimeData])
def market_risk_level(request: MarketRegimeRequest) -> StandardAgentResponse[MarketRegimeData]:
    data = analyze_market_regime(request)
    return StandardAgentResponse(status="success", data=data)


@app.post("/market/strategy-bias", response_model=StandardAgentResponse[MarketRegimeData])
def market_strategy_bias(request: MarketRegimeRequest) -> StandardAgentResponse[MarketRegimeData]:
    data = analyze_market_regime(request)
    return StandardAgentResponse(status="success", data=data)


@app.post("/market/strategy", response_model=StandardAgentResponse[StrategyRecommendation])
def market_strategy(request: MarketRegimeRequest) -> StandardAgentResponse[StrategyRecommendation]:
    regime_data = analyze_market_regime(request)
    recommendation = recommend_strategy(regime_data)
    return StandardAgentResponse(status="success", data=recommendation)


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {"message": "Market Regime Agent is running"}
