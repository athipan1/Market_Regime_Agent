from fastapi.testclient import TestClient

from app.main import app


REQUIRED_CONTRACT_FIELDS = {
    "status",
    "agent_type",
    "version",
    "schema_version",
    "timestamp",
    "correlation_id",
    "data",
    "metadata",
    "error",
    "confidence_score",
}


client = TestClient(app)


def assert_contract_response(payload):
    assert REQUIRED_CONTRACT_FIELDS.issubset(payload.keys())
    assert payload["agent_type"] == "market-regime-agent"
    assert payload["version"] == "0.2.0"
    assert payload["schema_version"] == "1.1"
    assert payload["correlation_id"]


def test_version_endpoint_uses_contract_response():
    response = client.get("/version", headers={"X-Correlation-ID": "version-123"})

    assert response.status_code == 200
    payload = response.json()
    assert_contract_response(payload)
    assert payload["correlation_id"] == "version-123"
    assert payload["data"]["api_contract"] == "multi-agent-trading-api-contract"
    assert payload["data"]["schema_version"] == "1.1"


def test_ready_endpoint_uses_contract_response():
    response = client.get("/ready")

    assert response.status_code == 200
    payload = response.json()
    assert_contract_response(payload)
    assert payload["data"]["ready"] is True
    assert payload["metadata"]["contract_source"] == "market-regime-agent-runtime-contract"
    assert "unknown" in payload["data"]["supported_risk_levels"]


def test_health_endpoint_uses_full_contract_response():
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert_contract_response(payload)
    assert payload["data"]["status"] == "healthy"
    assert payload["confidence_score"] == 1.0


def test_market_endpoint_uses_full_contract_response():
    response = client.post(
        "/market/regime",
        headers={"X-Correlation-ID": "market-123"},
        json={"symbol": "SPY", "price": 550, "sma_50": 530, "sma_200": 500, "atr_pct": 0.015, "vix": 15},
    )

    assert response.status_code == 200
    payload = response.json()
    assert_contract_response(payload)
    assert payload["correlation_id"] == "market-123"
    assert payload["confidence_score"] == payload["data"]["confidence_score"]


def test_market_endpoint_requires_api_key_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("MARKET_REGIME_API_KEY", "test-secret")
    monkeypatch.delenv("MARKET_REGIME_AUTH_REQUIRED", raising=False)

    payload = {"symbol": "SPY", "price": 550, "sma_50": 530, "sma_200": 500, "atr_pct": 0.015, "vix": 15}

    missing = client.post("/market/regime", json=payload)
    wrong = client.post("/market/regime", headers={"X-API-KEY": "wrong"}, json=payload)
    valid = client.post("/market/regime", headers={"X-API-KEY": "test-secret"}, json=payload)

    assert missing.status_code == 401
    assert missing.json()["status"] == "error"
    assert missing.json()["schema_version"] == "1.1"
    assert missing.json()["error"]["code"] == "http_401"
    assert wrong.status_code == 401
    assert valid.status_code == 200


def test_production_auth_misconfiguration_fails_closed(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("MARKET_REGIME_API_KEY", raising=False)
    monkeypatch.delenv("MARKET_REGIME_AUTH_REQUIRED", raising=False)

    response = client.post(
        "/market/regime",
        json={"symbol": "SPY", "price": 550, "sma_50": 530, "sma_200": 500, "atr_pct": 0.015, "vix": 15},
    )

    assert response.status_code == 503
    assert response.json()["status"] == "error"
    assert response.json()["error"]["code"] == "http_503"


def test_health_remains_open_when_production_auth_is_enabled(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("MARKET_REGIME_API_KEY", "test-secret")

    response = client.get("/health")
    assert response.status_code == 200


def test_correlation_id_has_size_limit():
    response = client.get("/health", headers={"X-Correlation-ID": "x" * 129})
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["schema_version"] == "1.1"
    assert payload["error"]["code"] == "http_400"


def test_validation_errors_use_contract_envelope():
    response = client.post(
        "/market/regime",
        headers={"X-Correlation-ID": "validation-123"},
        json={"symbol": "SPY", "price": -1},
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["correlation_id"] == "validation-123"
    assert payload["error"]["code"] == "validation_error"
