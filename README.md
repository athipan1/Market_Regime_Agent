# Market Regime Agent

Market Regime Agent classifies the current market environment for the multi-agent trading system.

It does **not** place orders. It returns advisory regime, risk, data-quality, and strategy-routing metadata for `Manager_Agent`, `Portfolio_Agent`, and `Risk_Agent`.

Market responses also expose a versioned `profit_policy_context` projection for Manager_Agent. It carries regime/risk, ATR, optional volatility percentile, deterministic trend strength, and the caller-supplied observation timestamp. Missing evidence remains `null`; this advisory context cannot override stop, Risk_Agent, or execution safety rules.

## Responsibilities

- Classify market regime: `bull`, `bear`, `sideways`, `volatile`, or `unknown`
- Estimate risk level: `low`, `medium`, `high`, or `unknown`
- Recommend operating mode: `normal`, `defensive`, or `cash_heavy`
- Publish explicit data-quality and freshness state
- Route strategies with fail-closed sizing invariants
- Propagate `X-Correlation-ID` through the standard response envelope

## Data-quality safety

`data.data_quality` is returned with every market analysis result.

- Missing price/SMA50/SMA200 blocks new entries.
- Missing both ATR and VIX returns `risk_level=unknown` and blocks new entries.
- Supplying only one of ATR or VIX is marked `review` but remains tradeable for backward compatibility.
- A missing market-data timestamp is marked `review`; freshness cannot be verified.
- A supplied stale, timezone-less, or materially future timestamp blocks new entries.
- `MARKET_DATA_MAX_AGE_SECONDS` controls the stale-data threshold and defaults to 900 seconds.

When data quality blocks trading, `/market/strategy` returns `recommended_action=review`, `recommended_strategy=no_trade`, an empty `allowed_strategies`, and all sizing/risk multipliers at `0.0`.

## Strategy contract

`recommended_action` is the top-level decision:

- `trade`: `recommended_strategy` is guaranteed to be inside `allowed_strategies`.
- `no_trade`: no tradeable strategies are allowed and all multipliers are zero.
- `review`: market data quality blocks new entries and all multipliers are zero.

`no_trade` is an action sentinel and is never included in `blocked_strategies`.

## API

Operational endpoints:

```text
GET /health
GET /ready
GET /version
```

Market endpoints:

```text
POST /market/regime
POST /market/risk-level
POST /market/strategy-bias
POST /market/strategy
```

Example:

```bash
curl -X POST http://localhost:8014/market/strategy \
  -H 'Content-Type: application/json' \
  -H 'X-Correlation-ID: demo-123' \
  -d '{
    "symbol": "SPY",
    "price": 550,
    "sma_50": 530,
    "sma_200": 500,
    "atr_pct": 0.015,
    "vix": 15,
    "market_breadth_pct": 0.70
  }'
```

## Authentication

Health/readiness/version endpoints remain open. Market endpoints require `X-API-KEY` when either:

- `APP_ENV=production` (or `prod`), or
- `MARKET_REGIME_AUTH_REQUIRED=true`.

Configure the shared secret with `MARKET_REGIME_API_KEY`. If authentication is required but the key is missing, the service fails closed with HTTP 503. Development remains backward compatible unless auth is explicitly enabled.

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8014
```

## Tests

```bash
ruff check app tests
pytest -q
```

## Docker

```bash
docker build -t market-regime-agent .
docker run --rm -p 8014:8014 market-regime-agent
```

## Integration rule

`Market_Regime_Agent` is advisory only. It must never call `Execution_Agent` directly.

```text
Market_Regime_Agent
  -> Manager_Agent
  -> Portfolio_Agent / Risk_Agent
  -> Execution_Agent
```
