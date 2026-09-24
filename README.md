# Forex Prediction

Daily foreign exchange analysis with a React dashboard, FastAPI, Microsoft SQL Server, yfinance ingestion, and an approved Gaussian HMM. This MVP is analytical only and does not place trades.

## Run locally without Docker

1. Create a Python virtual environment and install backend dependencies once:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

2. Copy `.env.example` to `.env` and set strong local values for both secrets.
3. Run the whole application with one command:

```powershell
npm.cmd run start
```

4. Open `http://127.0.0.1:8000`; the API documentation is at `http://127.0.0.1:8000/docs`.
5. Sync daily history, then train and explicitly approve a candidate model:

```powershell
$key = (Get-Content .env | Where-Object { $_ -like 'ADMIN_API_KEY=*' }) -replace '^ADMIN_API_KEY=', ''
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/admin/sync/EURUSD -Headers @{ 'X-Admin-Key' = $key }
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/admin/train/EURUSD -Headers @{ 'X-Admin-Key' = $key }
```

Take the returned `model_version` and approve it:

```powershell
$version = 'EURUSD-1d-YYYYMMDDTHHMMSSZ'
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/admin/models/$version/approve" -Headers @{ 'X-Admin-Key' = $key }
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/admin/predict/EURUSD -Headers @{ 'X-Admin-Key' = $key }
```

Refresh the dashboard after approval. Sync is an idempotent daily OHLC upsert. Admin routes require the API key. Do not commit `.env` or model artifacts.

## API contract

- `GET /api/health` checks the database connection.
- `GET /api/market/{pair}?timeframe=1d&limit=250` returns stored OHLC and stale-data metadata. Use a path value such as `EURUSD`; both `EURUSD` and the internal `EUR/USD` form are accepted.
- `GET /api/predictions/{pair}?timeframe=1d` returns current-state posterior and next-state transition probabilities separately, plus `as_of_timestamp`, `forecast_horizon`, and `forecast_for_timestamp`.
- `GET /api/models/{pair}?timeframe=1d` returns approved model lineage.
- `POST /api/admin/sync/{pair}` fetches and validates daily Yahoo Finance bars.
- `POST /api/admin/train/{pair}` trains a chronological 80/20 candidate and records validation log likelihood.
- `POST /api/admin/predict/{pair}` creates and stores a forecast from the approved model.
- `POST /api/admin/models/{model_version}/approve` activates a candidate, retiring the prior approved model for that pair/timeframe.

The MVP supports the daily timeframe. WebSockets, Redis, automated scheduling, user accounts, and order execution are out of scope. The current candidate evaluation is a chronological holdout likelihood; use a fuller walk-forward evaluation before relying on a model operationally.

Development startup creates SQL tables automatically. For a production API container, set `APP_ENV=production` and run `alembic upgrade head` as a deployment step before starting the API.
