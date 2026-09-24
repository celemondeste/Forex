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

There is no request-time training, browser-to-yfinance access, order execution, Redis, or WebSocket path in the MVP. SQL schema is created automatically in development. Production deployment should apply reviewed Alembic migrations before disabling development schema creation.

## Current scope

The implemented model evaluation is a chronological holdout likelihood. It does not yet establish trading performance or profitability; expand to walk-forward evaluation and regime stability analysis before operational use. Admin training currently runs synchronously and should move to a background job before longer training workloads.
