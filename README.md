# Forex Prediction

Daily foreign exchange analysis with a React dashboard, FastAPI, SQL persistence, Twelve Data ingestion, and an approved Gaussian HMM. This MVP is analytical only and does not place trades.

## Run locally without Docker

1. Create a Python virtual environment and install backend dependencies once:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
npm.cmd install
```

On macOS or Linux use `python3 -m venv .venv` and `.venv/bin/pip install -r backend/requirements.txt`.

2. Copy `.env.example` to `.env`. Set `TWELVE_DATA_API_KEY` to your own Twelve Data key for historical and live prices, and replace the example admin key. The default local database is SQLite; the SQL Server password is only needed when using Docker Compose. Virtual environments contain machine-specific Python paths, so recreate `.venv` after moving the project to another computer or Python installation.
3. Run the whole application with one command:

```powershell
npm.cmd run start
```

`npm run start` builds the React bundle and starts the API, which serves that bundle from the same origin: one command, one URL, one process. It finds `.venv` automatically on Windows, macOS, and Linux; set `PYTHON` to override the interpreter, or `HOST`/`PORT` to move the server.

On first search, the API requests daily OHLC history from Twelve Data. `AUTO_PREPARE_OUTPUTSIZE` controls the number of bars requested (260–5000, default 1500). A missing or invalid API key prevents fresh market data from being ingested.

The offline HMM regression test uses synthetic OHLC data and needs no market-data key:

```powershell
$env:PYTHONPATH = (Resolve-Path backend).Path
.\.venv\Scripts\python.exe -m unittest discover -s backend\tests -v
```

4. Open `http://127.0.0.1:8000`; the API documentation is at `http://127.0.0.1:8000/docs`.
5. Type any currency in the dashboard search box (`EURUSD`, `USDVND`, or just `vnd`). The first search for a pair ingests its daily history, fits a Hidden Markov Model, and renders two charts: the OHLC price history and a simulated forecast path with a 10-90% band. Set `AUTO_PREPARE_PAIRS=false` in `.env` to keep ingestion and model approval admin-only.

### Automatic chart refresh

While the dashboard tab is visible, the latest price is checked every minute and the daily history plus HMM forecast are refreshed every five minutes. The charts keep showing their last successful data if a refresh fails. Returning to a tab that has been hidden triggers a refresh when its interval has elapsed. Set `VITE_CHART_REFRESH_SECONDS` in the root `.env` to change the full-chart interval (minimum 60 seconds); restart `npm run start` because Vite reads this setting at build time. The daily historical feed contains completed bars, so it normally changes only once per trading day. The backend's daily scheduler updates stored pairs, and on-demand stale-data sync attempts are limited to once per hour per pair with 30 recent bars after the initial history load.

### Admin pipeline (explicit approval)

Sync daily history, then train and explicitly approve a candidate model:

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
- `GET /api/currencies?q=vnd` returns ranked pair suggestions for the search box.
- `GET /api/forecast/{pair}?timeframe=1d&horizon=30` returns a Monte Carlo price path (`expected`, `lower`, `upper` per future session) simulated from the approved HMM.
- `GET /api/search/{pair}?timeframe=1d&horizon=30` is the single call behind the search box: it prepares the pair when allowed, then returns history, prediction, forecast, and model lineage together.
- `POST /api/admin/sync/{pair}` fetches and validates daily Twelve Data bars.
- `POST /api/admin/train/{pair}` trains a chronological 80/20 candidate and records validation log likelihood.
- `POST /api/admin/predict/{pair}` creates and stores a forecast from the approved model.
- `POST /api/admin/models/{model_version}/approve` activates a candidate, retiring the prior approved model for that pair/timeframe.

The MVP supports the daily timeframe. WebSockets, Redis, user accounts, and order execution are out of scope. The current candidate evaluation is a chronological holdout likelihood; use a fuller walk-forward evaluation before relying on a model operationally.

Development startup creates SQL tables automatically. For a production API container, set `APP_ENV=production` and run `alembic upgrade head` as a deployment step before starting the API.
