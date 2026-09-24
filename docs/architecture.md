# Architecture

The browser dashboard is a React/Vite client of FastAPI. FastAPI owns ingestion, validation, persistence, feature engineering, model training, approval, and prediction. SQL Server is the system of record for OHLC bars, sync runs, models, and prediction records. Model artifacts are stored separately and referenced by a content hash.

## MVP data flow

1. An admin sync requests Yahoo Finance daily history and validates OHLC consistency.
2. Bars are upserted by pair, timeframe, and UTC timestamp; sync results are recorded.
3. Versioned causal features are computed from stored bars.
4. Training uses a chronological 80/20 split and stores a candidate artifact with validation log likelihood and lineage.
5. An admin explicitly approves a candidate. Approval retires the previous model for that pair/timeframe.
6. An admin prediction run stores a forecast using the approved artifact. Read endpoints return current and next-state probabilities separately without mutating data.
7. The React dashboard reads normalized REST endpoints and exposes missing model, loading, stale data, and API error states.

## Searching an arbitrary pair

The dashboard search box calls `GET /api/search/{pair}`. With `AUTO_PREPARE_PAIRS` enabled (the default for local use) that route performs steps 1-5 on demand for a pair nobody has prepared yet, marking the resulting model `auto_approved` so it stays distinguishable from an admin-approved lineage. Disabling the flag restores the strictly admin-driven pipeline. The forecast chart is a Monte Carlo expansion of the same approved artifact: regimes are resampled through the transition matrix and log returns are drawn from each regime's Gaussian emission, then compounded onto the last close.

One process serves both tiers: `npm start` builds the Vite bundle and starts uvicorn, which serves `dist/` for any non-`/api` path, so the dashboard and API share an origin.

There is no browser-to-yfinance access, order execution, Redis, or WebSocket path in the MVP. SQL schema is created automatically in development. Production deployment should apply reviewed Alembic migrations before disabling development schema creation.

## Current scope

The implemented model evaluation is a chronological holdout likelihood. It does not yet establish trading performance or profitability; expand to walk-forward evaluation and regime stability analysis before operational use. Admin training currently runs synchronously and should move to a background job before longer training workloads.
