"""
Stage 8: FastAPI backend.

Serves the processed/analyzed data (loaded into PostgreSQL by
backend/db/load_data.py) to the React dashboard (Stage 9).

Run:
    uvicorn backend.main:app --reload --port 8000
"""

import importlib.util
import re
import secrets
import time
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend import crud, v2
from backend.db.session import get_db
from backend.observability import (
    ObservabilityMiddleware,
    RateLimitMiddleware,
    configure_logging,
)
from backend.settings import get_settings
from ingestion.config import RAW_DATA_DIR, REQUIRED_COLUMNS
from ingestion.validate import ValidationError, load_csv, validate_data
from scripts.run_pipeline import run_full_pipeline

settings = get_settings()
configure_logging()

app = FastAPI(
    title="Signal - Social Sentiment Intelligence API",
    description=(
        "Analytics over 1.65M real public social posts, with filtered aggregates, "
        "per-post explanations, research artifacts and reproducible exports."
    ),
    version="2.0.0",
    docs_url="/api/docs" if settings.enable_docs else None,
    redoc_url="/api/redoc" if settings.enable_docs else None,
    openapi_url="/api/openapi.json" if settings.enable_docs else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "X-Request-ID"],
    expose_headers=["X-Request-ID", "X-Response-Time-Ms", "Content-Disposition"],
    max_age=600,
)
app.add_middleware(ObservabilityMiddleware)
app.add_middleware(RateLimitMiddleware, per_minute=settings.rate_limit_per_minute)
app.include_router(v2.router)


def _require_upload_key(x_api_key: str | None = Header(default=None)) -> None:
    """Upload is the only destructive endpoint, so it is key-protected.

    An empty ``API_KEY`` keeps local/demo development open. Any public
    deployment must set it (see docs/DEPLOYMENT.md).
    """
    if settings.api_key and not secrets.compare_digest(x_api_key or "", settings.api_key):
        raise HTTPException(status_code=401, detail="A valid X-API-Key header is required.")


def _safe_filename(filename: str) -> str:
    name = Path(filename).name
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._") or "upload.csv"
    return f"{datetime.utcnow():%Y%m%d_%H%M%S}_{stem}"


def _full_pipeline_available() -> bool:
    """The upload re-analysis path runs the PySpark pipeline.

    The production API image (`requirements-api.txt`) deliberately omits
    Spark, so this lets the endpoint return an honest 503 instead of a
    stack trace, while the research/dev image keeps the full behaviour.
    """
    return importlib.util.find_spec("pyspark") is not None


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/ready")
def ready(db: Session = Depends(get_db)):
    """Readiness probe: verifies the database and serving model artifact."""
    from sqlalchemy import text

    db.execute(text("SELECT 1"))
    model_artifact = Path("models/research/tfidf_logreg.joblib").exists()
    return {"status": "ready" if model_artifact else "degraded", "database": True,
            "model_artifact": model_artifact,
            "full_reanalysis": _full_pipeline_available()}


@app.post("/api/upload", dependencies=[Depends(_require_upload_key)])
def upload_csv(file: UploadFile, analyze: bool = True, db: Session = Depends(get_db)):
    """Validates the uploaded CSV, then (by default) runs the full pipeline
    on it: cleaning -> ML prediction -> Spark aggregation -> analytics ->
    PostgreSQL reload. This REPLACES the data the dashboard shows with this
    file's analysis (the DB loader clears tables before reloading), which
    is exactly the point of uploading a file — pass ?analyze=false to only
    validate without touching the dashboard's data.

    This is a plain (non-async) endpoint on purpose: it runs real,
    CPU-bound work (Spark) that would otherwise block the whole server's
    event loop. FastAPI runs sync path operations in a worker thread pool
    instead, so other requests keep working while this one is processing.
    """
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted.")

    limit_bytes = settings.max_upload_mb * 1024 * 1024
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_filename(file.filename or "upload.csv")
    dest_path = RAW_DATA_DIR / safe_name
    written = 0
    try:
        with open(dest_path, "wb") as out:
            while chunk := file.file.read(1024 * 1024):
                written += len(chunk)
                if written > limit_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds the {settings.max_upload_mb} MB upload limit.",
                    )
                out.write(chunk)
    except HTTPException:
        dest_path.unlink(missing_ok=True)
        raise

    try:
        df = load_csv(dest_path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read CSV: {exc}") from exc

    try:
        report = validate_data(df, source_label=file.filename or safe_name)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    result = {
        "filename": file.filename or safe_name,
        "stored_filename": safe_name,
        "saved_to": str(dest_path),
        "required_columns": REQUIRED_COLUMNS,
        "validation_report": report,
        "analyzed": False,
    }

    if not analyze:
        result["next_steps"] = (
            "File saved and validated only (analyze=false). Run "
            "`python scripts/run_pipeline.py` to analyze it and update the dashboard."
        )
        return result

    try:
        pipeline_log = []
        if not _full_pipeline_available():
            raise HTTPException(
                status_code=503,
                detail=(
                    "This deployment validates uploads only (PySpark is not installed). "
                    "Re-upload with analyze=false, or run the full pipeline in the "
                    "research environment: python scripts/run_pipeline.py <file.csv>"
                ),
            )
        pipeline_result = run_full_pipeline(dest_path, load_db=True, log=pipeline_log.append)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"File was validated but full analysis failed: {exc}",
        ) from exc

    result["analyzed"] = True
    result["db_loaded"] = "db" in pipeline_result
    if "db_error" in pipeline_result:
        result["db_error"] = pipeline_result["db_error"]
    # pipeline_result["spark"] also carries the actual Spark result DataFrames
    # (results, not just counts) - only the small "report" dict of row counts
    # is JSON-serializable/worth sending back.
    spark_result = pipeline_result.get("spark") or {}
    result["spark_report"] = spark_result.get("report")
    result["db_counts"] = pipeline_result.get("db")
    if result["db_loaded"]:
        result["summary"] = crud.get_summary(db)
        result["alerts"] = crud.get_alerts(db)
    result["next_steps"] = (
        "Full analysis complete. The dashboard now reflects this file's data."
        if result["db_loaded"]
        else "Analysis complete but PostgreSQL wasn't reachable, so the dashboard "
             "still shows the previous data. Start it (`docker compose up -d`) and "
             "re-upload, or run `python -m backend.db.load_data`."
    )
    return result


@app.get("/api/dashboard/summary")
def dashboard_summary(db: Session = Depends(get_db)):
    return crud.get_summary(db)


@app.get("/api/dashboard/sentiment")
def dashboard_sentiment(db: Session = Depends(get_db)):
    return crud.get_sentiment_breakdown(db)


@app.get("/api/dashboard/platforms")
def dashboard_platforms(db: Session = Depends(get_db)):
    return crud.get_platform_breakdown(db)


@app.get("/api/dashboard/topics")
def dashboard_topics(db: Session = Depends(get_db)):
    return crud.get_topic_breakdown(db)


@app.get("/api/dashboard/trends")
def dashboard_trends(
    granularity: str = Query("day", pattern="^(day|week|month)$"),
    db: Session = Depends(get_db),
):
    return crud.get_trends(db, granularity=granularity)


@app.get("/api/dashboard/hashtags")
def dashboard_hashtags(limit: int = Query(30, ge=1, le=100), db: Session = Depends(get_db)):
    return crud.get_hashtags(db, limit=limit)


@app.get("/api/dashboard/keywords")
def dashboard_keywords(limit: int = Query(30, ge=1, le=100), db: Session = Depends(get_db)):
    return crud.get_keywords(db, limit=limit)


@app.get("/api/dashboard/negative-posts")
def dashboard_negative_posts(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    return crud.get_negative_posts(db, limit=limit)


@app.get("/api/dashboard/alerts")
def dashboard_alerts(db: Session = Depends(get_db)):
    return crud.get_alerts(db)


@app.get("/api/posts")
def posts(
    platform: str = None,
    sentiment: str = None,
    topic: str = None,
    date: str = None,
    keyword: str = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    return crud.get_posts(
        db, platform=platform, sentiment=sentiment, topic=topic,
        date=date, keyword=keyword, limit=limit, offset=offset,
    )
