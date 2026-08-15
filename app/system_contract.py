from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from app.models import StandardAgentResponse
from app.security import resolve_correlation_id

MARKET_REGIME_AGENT_TYPE = "market-regime-agent"
MARKET_REGIME_AGENT_VERSION = "0.2.0"
SCHEMA_VERSION = "1.1"

router = APIRouter()


def contract_response(
    *,
    status: str,
    correlation_id: str,
    data: Dict[str, Any] | None = None,
    metadata: Dict[str, Any] | None = None,
    error: Dict[str, Any] | None = None,
    confidence_score: float | None = None,
) -> Dict[str, Any]:
    response = StandardAgentResponse[Dict[str, Any]](
        status=status,
        correlation_id=correlation_id,
        data=data,
        metadata=metadata or {},
        error=error,
        confidence_score=confidence_score,
    )
    return response.model_dump(mode="json")


@router.get("/version")
def version(correlation_id: str = Depends(resolve_correlation_id)) -> Dict[str, Any]:
    return contract_response(
        status="success",
        correlation_id=correlation_id,
        data={
            "agent_type": MARKET_REGIME_AGENT_TYPE,
            "version": MARKET_REGIME_AGENT_VERSION,
            "schema_version": SCHEMA_VERSION,
            "api_contract": "multi-agent-trading-api-contract",
        },
        metadata={
            "required_operational_endpoints": ["/health", "/ready", "/version"],
        },
    )


@router.get("/ready")
def ready(correlation_id: str = Depends(resolve_correlation_id)) -> Dict[str, Any]:
    return contract_response(
        status="success",
        correlation_id=correlation_id,
        data={
            "ready": True,
            "regime_endpoint": "/market/regime",
            "risk_level_endpoint": "/market/risk-level",
            "strategy_bias_endpoint": "/market/strategy-bias",
            "strategy_endpoint": "/market/strategy",
            "supported_regimes": ["bull", "bear", "sideways", "volatile", "unknown"],
            "supported_risk_levels": ["low", "medium", "high", "unknown"],
        },
        metadata={
            "contract_source": "market-regime-agent-runtime-contract",
        },
        confidence_score=1.0,
    )
