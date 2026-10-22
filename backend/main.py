"""
Stage 8: FastAPI backend.

Serves the processed/analyzed data (loaded into PostgreSQL by
backend/db/load_data.py) to the React dashboard (Stage 9).

Run:
    uvicorn backend.main:app --reload --port 8000
"""

import shutil
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend import crud
from backend.db.session import get_db
from ingestion.config import RAW_DATA_DIR, REQUIRED_COLUMNS
from ingestion.validate import ValidationError, load_csv, validate_data
from scripts.run_pipeline import run_full_pipeline

app = FastAPI(
    title="Social Media Sentiment & Trend Analysis API",
    description="Serves multi-platform sentiment analytics computed by the PySpark + ML pipeline.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo project; restrict this to the dashboard's origin in production
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/upload")
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
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted.")

    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    dest_path = RAW_DATA_DIR / file.filename
    with open(dest_path, "wb") as out:
        shutil.copyfileobj(file.file, out)

    try:
        df = load_csv(dest_path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read CSV: {exc}") from exc

    try:
        report = validate_data(df, source_label=file.filename)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    result = {
        "filename": file.filename,
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
        pipeline_result = run_full_pipeline(dest_path, load_db=True, log=pipeline_log.append)
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
