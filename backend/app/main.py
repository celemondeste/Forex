from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.api import router
from app.db.models import Base
from app.db.session import engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    if os.environ.get("APP_ENV", "development") == "development":
        if engine.dialect.name == "mssql":
            master_url = make_url(engine.url).set(database="master")
            admin_engine = create_engine(master_url, isolation_level="AUTOCOMMIT")
            with admin_engine.connect() as connection:
                connection.execute(text("IF DB_ID(N'ForexPrediction') IS NULL CREATE DATABASE ForexPrediction"))
            admin_engine.dispose()
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Forex Prediction API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000",
                   "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True, allow_methods=["GET", "POST"], allow_headers=["*"])
app.include_router(router)

frontend_dist = Path(__file__).resolve().parents[2] / "dist"


@app.get("/{path:path}", include_in_schema=False)
async def frontend(path: str):
    """Serve the built React app from the same origin as the API."""
    index = frontend_dist / "index.html"
    if not index.is_file():
        return PlainTextResponse("Frontend bundle is missing. Run `npm start` or `npm run build` first.",
                                 status_code=503)
    requested_file = (frontend_dist / path).resolve()
    if path and requested_file.is_file() and frontend_dist.resolve() in requested_file.parents:
        return FileResponse(requested_file)
    return FileResponse(index)
