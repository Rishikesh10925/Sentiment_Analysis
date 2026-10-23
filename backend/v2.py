"""Versioned analytics API used by the redesigned dashboard.

Design notes
------------
* Every aggregate is recomputed from the filtered post/sentiment tables, so
  platform/topic/date filters are real filters rather than decoration.
* Expensive global aggregates are cached in-process for a short TTL. The
  cache key includes every filter, and is documented as single-instance.
* All endpoints are read-only except /predict and /explain, which are
  stateless. Uploads stay on the legacy, API-key-protected endpoint.
"""

from __future__ import annotations

import csv
import io
import json
import threading
import time
from datetime import date, datetime, time as dt_time, timedelta
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session

from backend.db.models import Alert, Hashtag, Keyword, Post, SentimentResult, Topic
from backend.db.session import get_db
from backend.settings import get_settings
from ml import serving
from research.config import CURATED_DATA_DIR, LABELS, RESEARCH_RESULTS_DIR

router = APIRouter(prefix="/api/v2", tags=["analytics-v2"])

_CACHE: dict[str, tuple[float, object]] = {}
_CACHE_LOCK = threading.Lock()


def _cached(key: str, ttl: float, loader):
    now = time.time()
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1]
    value = loader()
    with _CACHE_LOCK:
        _CACHE[key] = (now, value)
    return value


def _key(prefix: str, **kwargs) -> str:
    serialised = json.dumps(kwargs, sort_keys=True, default=str)
    return f"{prefix}:{serialised}"


def _apply_filters(query, start: date | None, end: date | None, platform: str | None,
                   topic: str | None, sentiment: str | None):
    if start:
        query = query.filter(Post.post_date >= datetime.combine(start, dt_time.min))
    if end:
        query = query.filter(Post.post_date < datetime.combine(end + timedelta(days=1), dt_time.min))
    if platform:
        query = query.filter(Post.platform == platform)
    if topic:
        query = query.filter(Post.topic == topic)
    if sentiment:
        query = query.filter(SentimentResult.sentiment == sentiment)
    return query


def _joined(db: Session):
    return db.query(Post, SentimentResult).join(SentimentResult, Post.post_id == SentimentResult.post_id)


def _sentiment_counts(db: Session, start, end, platform, topic, sentiment) -> dict:
    query = db.query(SentimentResult.sentiment, func.count(SentimentResult.id))
    query = _apply_filters(query.join(Post, Post.post_id == SentimentResult.post_id),
                           start, end, platform, topic, sentiment)
    counts = {label: 0 for label in LABELS}
    for label, count in query.group_by(SentimentResult.sentiment).all():
        counts[label] = int(count)
    total = sum(counts.values())
    return {
        "total": total,
        "counts": counts,
        "percentages": {label: round(counts[label] / total * 100, 2) if total else 0.0 for label in LABELS},
    }


def _period_summary(db, start, end, platform, topic, sentiment) -> dict:
    stats = _sentiment_counts(db, start, end, platform, topic, sentiment)
    return {
        "start": start.isoformat() if start else None,
        "end": end.isoformat() if end else None,
        **stats,
    }


def _dataset_bounds(db: Session) -> tuple[date | None, date | None]:
    row = db.query(func.min(Post.post_date), func.max(Post.post_date)).one()
    return (row[0].date() if row[0] else None, row[1].date() if row[1] else None)


@router.get("/meta")
def meta(db: Session = Depends(get_db)):
    def load():
        min_date, max_date = _dataset_bounds(db)
        total = db.query(func.count(Post.id)).scalar() or 0
        platforms = [row[0] for row in db.query(Post.platform).distinct().order_by(Post.platform).all()]
        topics = [
            {"topic": row[0], "count": int(row[1])}
            for row in db.query(Post.topic, func.count(Post.id)).group_by(Post.topic).order_by(func.count(Post.id).desc()).all()
        ]
        manifest = {}
        manifest_path = CURATED_DATA_DIR / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return {
            "app": get_settings().app_name,
            "environment": get_settings().environment,
            "total_posts": int(total),
            "date_range": {
                "min": min_date.isoformat() if min_date else None,
                "max": max_date.isoformat() if max_date else None,
            },
            "platforms": platforms,
            "topics": topics,
            "labels": LABELS,
            "model": serving.model_info(),
            "provenance": {
                "sources": manifest.get("sources", []),
                "generated_at": manifest.get("generated_at"),
                "rows_by_platform": manifest.get("rows_by_platform"),
                "notes": manifest.get("notes", []),
            },
            "research": {
                "available": (RESEARCH_RESULTS_DIR / "baselines.json").exists(),
                "transformer_available": (RESEARCH_RESULTS_DIR / "transformer.json").exists(),
                "absa_available": (RESEARCH_RESULTS_DIR / "absa.json").exists(),
                "spark_available": (RESEARCH_RESULTS_DIR / "spark_benchmark.json").exists(),
            },
        }
    return _cached(_key("meta"), get_settings().cache_ttl_seconds, load)


@router.get("/summary")
def summary(
    start: date | None = None,
    end: date | None = None,
    platform: str | None = None,
    topic: str | None = None,
    sentiment: str | None = Query(None, pattern="^(Positive|Neutral|Negative)$"),
    compare: bool = True,
    db: Session = Depends(get_db),
):
    def load():
        stats = _sentiment_counts(db, start, end, platform, topic, sentiment)
        total = stats["total"]
        platforms = db.query(func.count(func.distinct(Post.platform)))
        topics = db.query(func.count(func.distinct(Post.topic)))
        if platform:
            platforms = platforms.filter(Post.platform == platform)
        if topic:
            topics = topics.filter(Post.topic == topic)
        avg_conf = db.query(func.avg(SentimentResult.confidence))
        avg_conf = _apply_filters(avg_conf.join(Post, Post.post_id == SentimentResult.post_id),
                                  start, end, platform, topic, sentiment).scalar()

        previous = None
        if compare and start and end:
            span = (end - start).days + 1
            prev_end = start - timedelta(days=1)
            prev_start = prev_end - timedelta(days=span - 1)
            previous = _period_summary(db, prev_start, prev_end, platform, topic, sentiment)
            previous["deltas"] = {
                label: round(stats["percentages"][label] - previous["percentages"][label], 2)
                for label in LABELS
            }
            previous["total_delta"] = total - previous["total"]

        return {
            "period": {"start": start.isoformat() if start else None, "end": end.isoformat() if end else None},
            "total_posts": total,
            "counts": stats["counts"],
            "percentages": stats["percentages"],
            "average_confidence": round(float(avg_conf), 4) if avg_conf is not None else None,
            "num_platforms": int(platforms.scalar() or 0),
            "num_topics": int(topics.scalar() or 0),
            "previous": previous,
        }
    return _cached(_key("summary", start=start, end=end, platform=platform, topic=topic,
                        sentiment=sentiment, compare=compare),
                   get_settings().cache_ttl_seconds, load)


@router.get("/trends")
def trends(
    granularity: Literal["day", "week", "month"] = "day",
    start: date | None = None,
    end: date | None = None,
    platform: str | None = None,
    topic: str | None = None,
    sentiment: str | None = Query(None, pattern="^(Positive|Neutral|Negative)$"),
    db: Session = Depends(get_db),
):
    def load():
        bucket = func.date_trunc(granularity, Post.post_date)
        query = db.query(
            bucket.label("period"),
            func.count(Post.id).label("total"),
            func.count(Post.id).filter(SentimentResult.sentiment == "Positive").label("positive"),
            func.count(Post.id).filter(SentimentResult.sentiment == "Neutral").label("neutral"),
            func.count(Post.id).filter(SentimentResult.sentiment == "Negative").label("negative"),
        ).join(SentimentResult, Post.post_id == SentimentResult.post_id)
        query = _apply_filters(query, start, end, platform, topic, sentiment)
        rows = query.group_by(bucket).order_by(bucket).all()
        result = []
        for period, total, positive, neutral, negative in rows:
            result.append({
                "period": period.date().isoformat() if granularity == "day" else period.date().isoformat(),
                "total": int(total),
                "positive": int(positive),
                "neutral": int(neutral),
                "negative": int(negative),
                "negative_pct": round(negative / total * 100, 2) if total else 0.0,
            })
        return {"granularity": granularity, "points": result}
    return _cached(_key("trends", granularity=granularity, start=start, end=end,
                        platform=platform, topic=topic, sentiment=sentiment),
                   get_settings().cache_ttl_seconds, load)


@router.get("/platforms")
def platforms(
    start: date | None = None, end: date | None = None,
    topic: str | None = None, sentiment: str | None = Query(None, pattern="^(Positive|Neutral|Negative)$"),
    db: Session = Depends(get_db),
):
    def load():
        query = db.query(Post.platform, SentimentResult.sentiment, func.count(Post.id))
        query = _apply_filters(query.join(SentimentResult, Post.post_id == SentimentResult.post_id),
                               start, end, None, topic, sentiment)
        rows = query.group_by(Post.platform, SentimentResult.sentiment).all()
        by_platform: dict[str, dict] = {}
        for platform, label, count in rows:
            entry = by_platform.setdefault(platform, {"platform": platform,
                                                       **{label_name: 0 for label_name in LABELS}})
            entry[label] = int(count)
        result = []
        for entry in by_platform.values():
            total = sum(entry[label] for label in LABELS)
            entry["total"] = total
            for label in LABELS:
                entry[f"{label.lower()}_pct"] = round(entry[label] / total * 100, 2) if total else 0.0
            result.append(entry)
        return {"platforms": sorted(result, key=lambda row: row["total"], reverse=True)}
    return _cached(_key("platforms", start=start, end=end, topic=topic, sentiment=sentiment),
                   get_settings().cache_ttl_seconds, load)


@router.get("/topics")
def topics(
    start: date | None = None, end: date | None = None,
    platform: str | None = None, sentiment: str | None = Query(None, pattern="^(Positive|Neutral|Negative)$"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    def load():
        query = db.query(Post.topic, SentimentResult.sentiment, func.count(Post.id))
        query = _apply_filters(query.join(SentimentResult, Post.post_id == SentimentResult.post_id),
                               start, end, platform, None, sentiment)
        rows = query.group_by(Post.topic, SentimentResult.sentiment).all()
        by_topic: dict[str, dict] = {}
        for topic, label, count in rows:
            entry = by_topic.setdefault(topic, {"topic": topic, **{l: 0 for l in LABELS}})
            entry[label] = int(count)
        result = []
        for entry in by_topic.values():
            total = sum(entry[label] for label in LABELS)
            entry["total"] = total
            for label in LABELS:
                entry[f"{label.lower()}_pct"] = round(entry[label] / total * 100, 2) if total else 0.0
            entry["negative_rate"] = entry["negative_pct"]
            result.append(entry)
        result.sort(key=lambda row: row["total"], reverse=True)
        return {"topics": result[:limit], "total_topics": len(result)}
    return _cached(_key("topics", start=start, end=end, platform=platform,
                        sentiment=sentiment, limit=limit),
                   get_settings().cache_ttl_seconds, load)


@router.get("/hashtags")
def hashtags(
    start: date | None = None, end: date | None = None,
    platform: str | None = None, limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
):
    def load():
        if not any((start, end, platform)):
            rows = db.query(Hashtag).order_by(Hashtag.count.desc()).limit(limit).all()
            return {"hashtags": [{"hashtag": row.hashtag, "count": row.count} for row in rows]}

        clauses, params = [], {"limit": limit}
        if start:
            clauses.append("p.post_date >= :start")
            params["start"] = datetime.combine(start, dt_time.min)
        if end:
            clauses.append("p.post_date < :end")
            params["end"] = datetime.combine(end + timedelta(days=1), dt_time.min)
        if platform:
            clauses.append("p.platform = :platform")
            params["platform"] = platform
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = text(f"""
            SELECT tag, count(*) AS count
            FROM posts p, LATERAL unnest(string_to_array(p.hashtags, ' ')) AS tag
            {where}
            {'AND' if where else 'WHERE'} tag LIKE '#%' AND length(tag) > 1
            GROUP BY tag ORDER BY count DESC LIMIT :limit
        """)
        rows = db.execute(sql, params).all()
        return {"hashtags": [{"hashtag": row[0], "count": int(row[1])} for row in rows]}
    return _cached(_key("hashtags", start=start, end=end, platform=platform, limit=limit),
                   get_settings().cache_ttl_seconds, load)


@router.get("/keywords")
def keywords(
    start: date | None = None, end: date | None = None,
    platform: str | None = None, limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
):
    def load():
        if not any((start, end, platform)):
            rows = db.query(Keyword).order_by(Keyword.count.desc()).limit(limit).all()
            return {"keywords": [{"keyword": row.keyword, "count": row.count} for row in rows]}
        clauses, params = [], {"limit": limit}
        if start:
            clauses.append("p.post_date >= :start")
            params["start"] = datetime.combine(start, dt_time.min)
        if end:
            clauses.append("p.post_date < :end")
            params["end"] = datetime.combine(end + timedelta(days=1), dt_time.min)
        if platform:
            clauses.append("p.platform = :platform")
            params["platform"] = platform
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = text(f"""
            SELECT token, count(*) AS count
            FROM posts p, LATERAL regexp_split_to_table(p.clean_text, '\\s+') AS token
            {where}
            {'AND' if where else 'WHERE'} char_length(token) > 2
            GROUP BY token ORDER BY count DESC LIMIT :limit
        """)
        rows = db.execute(sql, params).all()
        return {"keywords": [{"keyword": row[0], "count": int(row[1])} for row in rows]}
    return _cached(_key("keywords", start=start, end=end, platform=platform, limit=limit),
                   get_settings().cache_ttl_seconds, load)


@router.get("/posts")
def posts(
    start: date | None = None, end: date | None = None,
    platform: str | None = None, topic: str | None = None,
    sentiment: str | None = Query(None, pattern="^(Positive|Neutral|Negative)$"),
    keyword: str | None = Query(None, max_length=100),
    sort: Literal["date_desc", "date_asc", "confidence_desc"] = "date_desc",
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0, le=100_000),
    db: Session = Depends(get_db),
):
    """Paged explorer rows.

    ``offset`` is capped at 100k because PostgreSQL still walks the skipped
    rows; deep pagination over 1.6M rows is what the streaming CSV export is
    for. The total count is cached per filter combination so flipping through
    pages does not repeat a 1.6M-row COUNT.
    """
    query = _joined(db)
    query = _apply_filters(query, start, end, platform, topic, sentiment)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(or_(Post.original_text.ilike(like), Post.clean_text.ilike(like)))
    total = _cached(
        _key("posts_total", start=start, end=end, platform=platform, topic=topic,
             sentiment=sentiment, keyword=keyword),
        get_settings().cache_ttl_seconds,
        query.count,
    )
    order = {
        "date_desc": Post.post_date.desc(),
        "date_asc": Post.post_date.asc(),
        "confidence_desc": SentimentResult.confidence.desc().nullslast(),
    }[sort]
    rows = query.order_by(order, Post.post_id).offset(offset).limit(limit).all()
    items = []
    for post, result in rows:
        items.append({
            "post_id": post.post_id,
            "platform": post.platform,
            "author": post.author,
            "date": post.post_date.isoformat() if post.post_date else None,
            "topic": post.topic,
            "hashtags": [tag for tag in (post.hashtags or "").split() if tag],
            "text": post.original_text,
            "sentiment": result.sentiment,
            "confidence": result.confidence,
            "probabilities": {
                "Negative": result.prob_negative,
                "Neutral": result.prob_neutral,
                "Positive": result.prob_positive,
            },
        })
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@router.get("/posts/{post_id}")
def post_detail(post_id: str, include_gold: bool = False, db: Session = Depends(get_db)):
    row = _joined(db).filter(Post.post_id == post_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Post not found")
    post, result = row
    payload = {
        "post_id": post.post_id,
        "platform": post.platform,
        "author": post.author,
        "date": post.post_date.isoformat() if post.post_date else None,
        "topic": post.topic,
        "hashtags": [tag for tag in (post.hashtags or "").split() if tag],
        "text": post.original_text,
        "clean_text": post.clean_text,
        "sentiment": result.sentiment,
        "confidence": result.confidence,
        "probabilities": {
            "Negative": result.prob_negative,
            "Neutral": result.prob_neutral,
            "Positive": result.prob_positive,
        },
        "model": result.model_name,
        "model_version": result.model_version,
    }
    if include_gold:
        payload["gold_sentiment"] = result.gold_sentiment
    try:
        payload["explanation"] = serving.explain(post.original_text or "")
    except Exception as exc:  # model artifact unavailable
        payload["explanation_error"] = str(exc)
    return payload


@router.get("/alerts")
def alerts(db: Session = Depends(get_db)):
    rows = db.query(Alert).order_by(Alert.created_at.desc()).all()
    thresholds = get_settings().negative_sentiment_alert_threshold
    return {
        "configured_threshold": thresholds,
        "alerts": [
            {
                "type": row.alert_type,
                "triggered": row.triggered,
                "message": row.message,
                "threshold": row.threshold,
                "negative_percentage": row.negative_percentage,
                "major_topic": row.major_topic,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ],
    }


@router.get("/model")
def model():
    return serving.model_info()


_RESEARCH_FILES = {
    "baselines": "baselines.json",
    "transformer": "transformer.json",
    "external_roberta": "external_twitter_roberta.json",
    "absa": "absa.json",
    "explainability": "explainability.json",
    "spark_benchmark": "spark_benchmark.json",
    "bulk_inference": "bulk_inference.json",
    "db_load": "db_load.json",
}

LIMITATIONS = [
    "Sentiment140 labels are distant supervision from emoticons, not human annotations; they are noisier than TweetEval.",
    "The dashboard's 1.65M posts and the TweetEval benchmark are different distributions. Domain-shift numbers are reported rather than hidden.",
    "The X/Twitter corpus (2009) and Reddit corpus (2019) do not overlap in time, so cross-platform temporal comparisons are descriptive only.",
    "Topics are rule-based tags, not a trained topic model; 'General' is the intentional fallback.",
    "The deployed linear model is chosen for CPU latency and exact explainability; the fine-tuned transformer is stronger but heavier.",
    "Explanations are model attributions, not causal claims.",
]


@router.get("/research")
def research():
    def load():
        payload = {"available": {}, "limitations": LIMITATIONS}
        for key, filename in _RESEARCH_FILES.items():
            path = RESEARCH_RESULTS_DIR / filename
            payload["available"][key] = path.exists()
            if path.exists():
                payload[key] = json.loads(path.read_text(encoding="utf-8"))
        manifest = CURATED_DATA_DIR / "manifest.json"
        payload["provenance"] = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}
        if "baselines" in payload:
            baselines = payload["baselines"]
            payload["leaderboard"] = []
            for name, metrics in baselines.items():
                if isinstance(metrics, dict) and "macro_f1" in metrics:
                    payload["leaderboard"].append({
                        "model": name,
                        "macro_f1": metrics["macro_f1"],
                        "accuracy": metrics["accuracy"],
                        "macro_f1_ci": metrics.get("bootstrap_macro_f1"),
                        "ece": (metrics.get("calibration") or {}).get("ece"),
                        "train_seconds": metrics.get("train_seconds"),
                    })
            payload["leaderboard"].sort(key=lambda row: row["macro_f1"], reverse=True)
        return payload
    return _cached(_key("research"), get_settings().research_cache_ttl_seconds, load)


class PredictRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


@router.post("/predict")
def predict(request: PredictRequest):
    try:
        result = serving.predict([request.text])[0]
        result["explanation"] = serving.explain(request.text)
        result["model"] = serving.model_info()
        return result
    except serving.ModelNotAvailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/explain")
def explain(request: PredictRequest):
    try:
        return serving.explain(request.text)
    except serving.ModelNotAvailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _filtered_posts(db, start, end, platform, topic, sentiment, keyword):
    query = _joined(db)
    query = _apply_filters(query, start, end, platform, topic, sentiment)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(or_(Post.original_text.ilike(like), Post.clean_text.ilike(like)))
    return query


@router.get("/export/posts.csv")
def export_posts_csv(
    start: date | None = None, end: date | None = None,
    platform: str | None = None, topic: str | None = None,
    sentiment: str | None = Query(None, pattern="^(Positive|Neutral|Negative)$"),
    keyword: str | None = None, max_rows: int = Query(20_000, ge=1, le=50_000),
    db: Session = Depends(get_db),
):
    rows = _filtered_posts(db, start, end, platform, topic, sentiment, keyword).order_by(
        Post.post_date.desc()).limit(max_rows).all()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["post_id", "platform", "author", "date", "topic", "sentiment",
                     "confidence", "hashtags", "text"])
    for post, result in rows:
        writer.writerow([post.post_id, post.platform, post.author,
                         post.post_date.isoformat() if post.post_date else "",
                         post.topic, result.sentiment, result.confidence,
                         post.hashtags or "", post.original_text])
    data = buffer.getvalue()
    filename = f"signal_posts_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv"
    return Response(content=data, media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/export/report.pdf")
def export_report_pdf(
    start: date | None = None, end: date | None = None,
    platform: str | None = None, topic: str | None = None,
    sentiment: str | None = Query(None, pattern="^(Positive|Neutral|Negative)$"),
    db: Session = Depends(get_db),
):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    summary_data = _sentiment_counts(db, start, end, platform, topic, sentiment)
    topic_rows = db.query(Post.topic, SentimentResult.sentiment, func.count(Post.id))
    topic_rows = _apply_filters(topic_rows.join(SentimentResult, Post.post_id == SentimentResult.post_id),
                                start, end, platform, topic, sentiment)
    topic_rows = topic_rows.group_by(Post.topic, SentimentResult.sentiment).all()
    by_topic: dict[str, dict] = {}
    for name, label, count in topic_rows:
        entry = by_topic.setdefault(name, {l: 0 for l in LABELS})
        entry[label] = int(count)
    top_topics = sorted(by_topic.items(), key=lambda kv: sum(kv[1].values()), reverse=True)[:8]

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title="Signal sentiment report")
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Signal · Social Sentiment Report", styles["Title"]),
        Paragraph(
            f"Period: {start or 'all time'} → {end or 'latest'} · "
            f"Platform: {platform or 'all'} · Topic: {topic or 'all'}",
            styles["Normal"]),
        Spacer(1, 8),
        Paragraph(
            f"<b>{summary_data['total']:,}</b> classified posts. "
            f"Positive {summary_data['percentages']['Positive']}% · "
            f"Neutral {summary_data['percentages']['Neutral']}% · "
            f"Negative {summary_data['percentages']['Negative']}%.",
            styles["BodyText"]),
        Spacer(1, 10),
    ]

    sentiment_table = Table([
        ["Sentiment", "Posts", "Share"],
        *[[label, f"{summary_data['counts'][label]:,}", f"{summary_data['percentages'][label]}%"] for label in LABELS],
    ], colWidths=[50 * mm, 40 * mm, 40 * mm])
    sentiment_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story += [sentiment_table, Spacer(1, 14), Paragraph("Top topics", styles["Heading2"])]

    topic_table = Table([
        ["Topic", "Posts", "Negative share"],
        *[[name, f"{sum(counts.values()):,}",
           f"{round(counts['Negative'] / sum(counts.values()) * 100, 1)}%"]
          for name, counts in top_topics],
    ], colWidths=[62 * mm, 34 * mm, 34 * mm])
    topic_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0fdfa")]),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
    ]))
    story += [topic_table, Spacer(1, 14)]
    story.append(Paragraph(
        "Method: TF-IDF (1–2 grams) + class-weighted logistic regression trained on "
        "TweetEval sentiment; reported macro-F1 0.58 on the official test split. "
        "Labels on the 1.65M-post corpus are model predictions. See docs/RESEARCH.md "
        "for baselines, transformer results, ablations and limitations.",
        styles["Italic"]))
    doc.build(story)
    filename = f"signal_report_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.pdf"
    return Response(content=buffer.getvalue(), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})
