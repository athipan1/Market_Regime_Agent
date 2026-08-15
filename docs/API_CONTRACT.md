# Market_Regime_Agent API Contract

This document defines API contract version `1.1` for `Market_Regime_Agent` version `0.2.0`.

`Market_Regime_Agent` classifies market conditions and provides strategy-routing context for other agents. It is advisory only and never places broker orders.

## Standard headers

```http
Content-Type: application/json
X-Correlation-ID: <caller correlation id>
X-API-KEY: <market-regime-agent-api-key>
```

`X-Correlation-ID` is optional. The service generates one when absent and rejects values longer than 128 characters.

`X-API-KEY` is required for market endpoints when `APP_ENV` is `production`/`prod` or `MARKET_REGIME_AUTH_REQUIRED=true`. The shared secret is read from `MARKET_REGIME_API_KEY`. Operational endpoints remain open.

## Standard response envelope

Success and handled error responses use the same envelope:

```json
{
  "status": "success",
  "agent_type": "market-regime-agent",
  "version": "0.2.0",
  "schema_version": "1.1",
  "timestamp": "2026-08-16T00:00:00Z",
  "correlation_id": "example-123",
  "data": {},
  "metadata": {},
  "error": null,
  "confidence_score": 0.85
}
```

Authentication, request validation, and correlation-header failures return `status=error` with the same contract fields and a structured `error` object.

## Operational endpoints

```http
GET /health
GET /ready
GET /version
```

## Market endpoints

```http
POST /market/regime
POST /market/risk-level
POST /market/strategy-bias
POST /market/strategy
```

## Risk semantics

Supported risk levels are:

```text
low
medium
high
unknown
```

`unknown` is returned when both ATR percent and VIX are absent. Unknown volatility risk is fail-closed for strategy routing.

## Data-quality contract

Every market analysis response includes `data.data_quality`:

```json
{
  "status": "review",
  "trade_allowed": true,
  "trend_evidence_complete": true,
  "volatility_evidence": "complete",
  "timestamp_present": false,
  "stale": false,
  "data_age_seconds": null,
  "reasons": [
    "market data timestamp is missing; freshness cannot be verified"
  ]
}
```

Statuses:

- `good`: all required evidence is present and supplied timestamp is fresh.
- `review`: evidence is usable but incomplete for full confidence, such as a missing timestamp or one missing volatility input.
- `blocked`: data is unsafe for new entries.

Blocking conditions include:

- missing or non-positive price/SMA50/SMA200 evidence,
- missing both ATR percent and VIX,
- timezone-less supplied timestamps,
- supplied timestamps older than `MARKET_DATA_MAX_AGE_SECONDS` (default 900 seconds),
- supplied timestamps more than 60 seconds in the future.

A blocked result forces strategy routing to `recommended_action=review`, empty `allowed_strategies`, and zero multipliers.

## Strategy recommendation safety contract

`recommended_action` is the top-level routing decision:

```text
trade | no_trade | review
```

Contract guarantees:

- `trade` requires a non-empty `allowed_strategies` list.
- For `trade`, `recommended_strategy` must be a member of `allowed_strategies`.
- `no_trade` and `review` require `recommended_strategy=no_trade` and `allowed_strategies=[]`.
- Whenever `allowed_strategies=[]`, `position_size_multiplier`, `risk_multiplier`, `risk_budget_multiplier`, and `exposure_cap` are all `0.0`.
- `allowed_strategies` and `blocked_strategies` never overlap.
- `no_trade` is an action sentinel and is never included in `blocked_strategies`.

For regimes such as `bear` where the overall alternative score may still favor staying out, `recommended_strategy` is selected only from strategies that are actually allowed. This removes the previous contradictory `recommended_strategy=no_trade` plus non-empty allow-list state.

## Profit policy context

Every market analysis response includes a non-binding `data.profit_policy_context` projection for Manager_Agent:

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

`volatility_percentile` and `observed_at` are preserved only when supplied by the caller. `trend_strength` is a deterministic normalized separation of price, SMA50, and SMA200 and remains `null` when those inputs are incomplete. This projection cannot override stop, Risk_Agent, or execution safety rules.
