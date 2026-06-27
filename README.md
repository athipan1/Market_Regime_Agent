# Market Regime Agent

Market Regime Agent classifies the current market environment for the multi-agent trading system.

It does **not** place orders. It returns advisory regime, risk level, and strategy-bias metadata for `Manager_Agent`, `Portfolio_Agent`, and `Risk_Agent`.

## Responsibilities

- Classify market regime: `bull`, `bear`, `sideways`, `volatile`, or `unknown`
- Estimate risk level: `low`, `medium`, or `high`
- Recommend operating mode: `normal`, `defensive`, or `cash_heavy`
- Suggest strategy bucket bias for the core-satellite policy

## API

### Health

```bash
curl http://localhost:8014/health
```

### Market Regime

```bash
curl -X POST http://localhost:8014/market/regime \
  -H 'Content-Type: application/json' \
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

Example response:

```json
{
  "status": "success",
  "agent_type": "market-regime-agent",
  "version": "0.1.0",
  "data": {
    "symbol": "SPY",
    "regime": "bull",
    "risk_level": "low",
    "recommended_mode": "normal",
    "confidence_score": 0.85,
    "strategy_bias": {
      "core_dividend": 0.45,
      "value_rebound": 0.30,
      "news_momentum": 0.25
    }
  }
}
```

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

`Market_Regime_Agent` is advisory only. It should never call `Execution_Agent` directly.

Recommended flow:

```text
Market_Regime_Agent
  -> Manager_Agent
  -> Portfolio_Agent / Risk_Agent
  -> Execution_Agent
```
