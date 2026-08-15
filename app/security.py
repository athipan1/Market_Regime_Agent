from __future__ import annotations

import os
import secrets
from uuid import uuid4

from fastapi import Header, HTTPException, status


PRODUCTION_ENVIRONMENTS = {"prod", "production"}


def _env_flag(name: str) -> bool | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _auth_required() -> bool:
    explicit = _env_flag("MARKET_REGIME_AUTH_REQUIRED")
    if explicit is not None:
        return explicit
    return os.getenv("APP_ENV", "development").strip().lower() in PRODUCTION_ENVIRONMENTS


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-KEY")) -> None:
    if not _auth_required():
        return

    configured_key = os.getenv("MARKET_REGIME_API_KEY")
    if not configured_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="market regime API authentication is required but not configured",
        )
    if x_api_key is None or not secrets.compare_digest(x_api_key, configured_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid API key")


def resolve_correlation_id(
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-ID"),
) -> str:
    if x_correlation_id is None or not x_correlation_id.strip():
        return str(uuid4())
    correlation_id = x_correlation_id.strip()
    if len(correlation_id) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Correlation-ID must be 128 characters or fewer",
        )
    return correlation_id
