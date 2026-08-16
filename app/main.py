from __future__ import annotations

from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.models import (
    HealthData,
    MarketRegimeData,
    MarketRegimeRequest,
    StandardAgentResponse,
    StrategyRecommendation,
)
from app.security import require_api_key, resolve_correlation_id
from app.service import analyze_market_regime
from app.strategy_router import recommend_strategy
from app.system_contract import router as system_contract_router


app = FastAPI(
    title="Market Regime Agent",
    description="Classifies market regime and risk mode for the multi-agent trading system.",
    version="0.2.0",
)
app.include_router(system_contract_router)


def _error_correlation_id(request: Request) -> str:
    candidate = request.headers.get("X-Correlation-ID", "").strip()
    if candidate and len(candidate) <= 128:
        return candidate
    return str(uuid4())


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: object | None = None,
) -> JSONResponse:
    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = jsonable_encoder(details)
    response = StandardAgentResponse[dict](
        status="error",
        correlation_id=_error_correlation_id(request),
        error=error,
    )
    return JSONResponse(status_code=status_code, content=response.model_dump(mode="json"))


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return _error_response(
        request,
        status_code=exc.status_code,
        code=f"http_{exc.status_code}",
        message=str(exc.detail),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return _error_response(
        request,
        status_code=422,
        code="validation_error",
        message="request validation failed",
        details=exc.errors(),
    )


@app.get("/health", response_model=StandardAgentResponse[HealthData])
def health(
    correlation_id: str = Depends(resolve_correlation_id),
) -> StandardAgentResponse[HealthData]:
    return StandardAgentResponse(
        status="success",
        data=HealthData(),
        correlation_id=correlation_id,
        confidence_score=1.0,
    )


@app.post(
    "/market/regime",
    response_model=StandardAgentResponse[MarketRegimeData],
    dependencies=[Depends(require_api_key)],
)
def market_regime(
    request: MarketRegimeRequest,
    correlation_id: str = Depends(resolve_correlation_id),
) -> StandardAgentResponse[MarketRegimeData]:
    data = analyze_market_regime(request)
    return StandardAgentResponse(
        status="success",
        data=data,
        correlation_id=correlation_id,
        confidence_score=data.confidence_score,
    )


@app.post(
    "/market/risk-level",
    response_model=StandardAgentResponse[MarketRegimeData],
    dependencies=[Depends(require_api_key)],
)
def market_risk_level(
    request: MarketRegimeRequest,
    correlation_id: str = Depends(resolve_correlation_id),
) -> StandardAgentResponse[MarketRegimeData]:
    data = analyze_market_regime(request)
    return StandardAgentResponse(
        status="success",
        data=data,
        correlation_id=correlation_id,
        confidence_score=data.confidence_score,
    )


@app.post(
    "/market/strategy-bias",
    response_model=StandardAgentResponse[MarketRegimeData],
    dependencies=[Depends(require_api_key)],
)
def market_strategy_bias(
    request: MarketRegimeRequest,
    correlation_id: str = Depends(resolve_correlation_id),
) -> StandardAgentResponse[MarketRegimeData]:
    data = analyze_market_regime(request)
    return StandardAgentResponse(
        status="success",
        data=data,
        correlation_id=correlation_id,
        confidence_score=data.confidence_score,
    )


@app.post(
    "/market/strategy",
    response_model=StandardAgentResponse[StrategyRecommendation],
    dependencies=[Depends(require_api_key)],
)
def market_strategy(
    request: MarketRegimeRequest,
    correlation_id: str = Depends(resolve_correlation_id),
) -> StandardAgentResponse[StrategyRecommendation]:
    regime_data = analyze_market_regime(request)
    recommendation = recommend_strategy(regime_data)
    return StandardAgentResponse(
        status="success",
        data=recommendation,
        correlation_id=correlation_id,
        confidence_score=recommendation.confidence_score,
    )


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {"message": "Market Regime Agent is running"}
