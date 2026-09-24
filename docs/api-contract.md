# API contract

Pair identifiers are stored as `AAA/BBB`. Path parameters accept compact symbols such as `EURUSD`; the MVP timeframe is `1d`. Times are UTC. Market data is read from the backend database; the browser never calls yfinance.

## Market history

`GET /api/market/{pair}?timeframe=1d&limit=250`

Returns `pair`, `timeframe`, chronological `bars` (`timestamp`, `open`, `high`, `low`, `close`, optional `volume`), `as_of_timestamp`, and `stale`.

## Prediction

`GET /api/predictions/{pair}?timeframe=1d`

Returns `current_state`, `current_regime`, `current_probabilities`, `next_state_probabilities`, `signal`, `as_of_timestamp`, `forecast_horizon`, `forecast_for_timestamp`, and `model_version`. The two probability maps are separate: posterior probability describes the inferred state at the last observed bar; transition probability describes the state expected one step after it.

## Approved model

`GET /api/models/{pair}?timeframe=1d`

Returns model version, status, feature version, artifact hash, training time, and evaluation metrics for the model currently approved for serving.

## Admin operations

The following endpoints require `X-Admin-Key`, configured with `ADMIN_API_KEY`:

- `POST /api/admin/sync/{pair}`
- `POST /api/admin/train/{pair}`
- `POST /api/admin/predict/{pair}`
- `POST /api/admin/models/{model_version}/approve`

Training creates a candidate. Only explicit approval makes a model available for forecasts. The admin prediction route stores a prediction record; the public GET prediction route is read-only and computes the latest view without writing history.
