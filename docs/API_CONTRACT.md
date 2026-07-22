# Market_Regime_Agent API Contract

This document defines the baseline API contract for `Market_Regime_Agent`.

`Market_Regime_Agent` classifies market conditions and provides strategy-routing context for other agents.

## Standard Headers

```http
Content-Type: application/json
X-Correlation-ID: <uuid>
X-API-KEY: <market-regime-agent-api-key>
```

## Standard Response Envelope

Operational contract endpoints return this envelope:

```json
{
  "status": "success",
  "agent_type": "market-regime-agent",
  "version": "0.1.0",
  "schema_version": "1.0",
  "timestamp": "2026-07-04T00:00:00Z",
  "correlation_id": null,
  "data": {},
  "metadata": {},
  "error": null,
  "confidence_score": null
}
```

## Operational Endpoints

```http
GET /health
GET /ready
GET /version
```

## Market Endpoints

```http
POST /market/regime
POST /market/risk-level
POST /market/strategy-bias
POST /market/strategy
```

## Profit policy context

Every market analysis response includes a non-binding
`data.profit_policy_context` projection for Manager_Agent:

```json
{
  "context_version": "profit-market-context.v1",
  "regime": "bull",
  "risk_level": "medium",
  "atr_pct": 0.025,
  "volatility_percentile": 65,
  "trend_strength": 0.48,
  "observed_at": "2026-07-22T00:00:00Z",
  "source": "market-regime-agent"
}
```

`volatility_percentile` and `observed_at` are preserved only when supplied by
the caller. `trend_strength` is a deterministic normalized separation of price,
SMA50, and SMA200; it is `null` when those inputs are incomplete. The agent
never fabricates missing context and this projection cannot override stop or
Risk_Agent safety rules.

## Strategy Recommendation Safety Contract

Callers such as `Manager_Agent`, `Portfolio_Agent`, and `Risk_Agent` **must check
`allowed_strategies` before every multiplier or strategy recommendation**.

### Contract guarantee

- An empty `allowed_strategies` list means that no strategy may open a new
  position.
- Whenever `allowed_strategies` is empty, `position_size_multiplier`,
  `risk_multiplier`, `risk_budget_multiplier`, and `exposure_cap` are all
  guaranteed to be `0.0`.
- Callers that already honor `allowed_strategies` require no behavior change;
  the zero multipliers are a redundant safety signal for callers that consume
  sizing fields.

## Notes

1. This service provides market-regime context for other agents.
2. Runtime readiness is reported through `/ready`.
3. Version and schema metadata are reported through `/version`.
4. Existing market endpoints keep their current response models.
