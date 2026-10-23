"""Load the real curated corpus + predictions into PostgreSQL.

Bulk COPY is used instead of ORM inserts: 1.65M posts and 1.65M sentiment
rows are loaded in tens of seconds rather than minutes, and memory stays
bounded by the parquet batch size.

Run:
    python -m backend.db.load_real_data
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from datetime import datetime
from pathlib import Path

import pyarrow.parquet as pq
from sqlalchemy import text

from backend.db.migrate import run_migrations
from backend.db.models import Base
from backend.db.session import engine
from research.config import CURATED_POSTS_PATH, CURATED_PREDICTIONS_PATH, RESEARCH_RESULTS_DIR

BATCH_SIZE = 50_000


def _model_version(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()[:12]


def _copy_batch(cursor, table: str, columns: list[str], rows: list[tuple]) -> None:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerows(rows)
    buffer.seek(0)
    cursor.copy_expert(
        f"COPY {table} ({', '.join(columns)}) FROM STDIN WITH (FORMAT csv)",
        buffer,
    )


def _clean_text(value) -> str:
    return "" if value is None else str(value)


def load_posts_and_predictions() -> dict:
    if not CURATED_PREDICTIONS_PATH.exists():
        raise FileNotFoundError(
            f"{CURATED_PREDICTIONS_PATH} missing. Run `python -m scripts.predict_curated` first."
        )
    version = _model_version(Path("models/research/tfidf_logreg.joblib"))
    raw = engine.raw_connection()
    posts_total = 0
    sentiments_total = 0
    try:
        cursor = raw.cursor()
        cursor.execute(
            "TRUNCATE TABLE sentiment_results, posts, daily_sentiment, hashtags, keywords, topics, alerts "
            "RESTART IDENTITY CASCADE"
        )
        parquet_file = pq.ParquetFile(CURATED_PREDICTIONS_PATH)
        for batch in parquet_file.iter_batches(batch_size=BATCH_SIZE):
            df = batch.to_pandas()
            posts = []
            sentiments = []
            for row in df.itertuples(index=False):
                posts.append((
                    str(row.post_id), row.platform, _clean_text(row.author)[:100],
                    _clean_text(row.date) or None, _clean_text(row.topic)[:100] or "General",
                    _clean_text(row.original_text), _clean_text(row.clean_text),
                    _clean_text(row.hashtags),
                ))
                gold = row.gold_sentiment
                sentiments.append((
                    str(row.post_id), row.predicted_sentiment, float(row.confidence),
                    None if gold is None or (isinstance(gold, float) and gold != gold) else str(gold),
                    float(row.prob_negative), float(row.prob_neutral), float(row.prob_positive),
                    "tfidf_logreg_word12", version,
                ))
            _copy_batch(cursor, "posts",
                        ["post_id", "platform", "author", "post_date", "topic",
                         "original_text", "clean_text", "hashtags"], posts)
            _copy_batch(cursor, "sentiment_results",
                        ["post_id", "sentiment", "confidence", "gold_sentiment",
                         "prob_negative", "prob_neutral", "prob_positive",
                         "model_name", "model_version"], sentiments)
            posts_total += len(posts)
            sentiments_total += len(sentiments)
            print(f"  loaded {posts_total:,} posts", flush=True)
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()
    return {"posts": posts_total, "sentiment_results": sentiments_total, "model_version": version}


def build_aggregate_tables() -> dict:
    statements = {
        "daily_sentiment": """
            INSERT INTO daily_sentiment (period_date, positive, neutral, negative, total, negative_pct)
            SELECT p.post_date::date,
                   COUNT(*) FILTER (WHERE s.sentiment = 'Positive'),
                   COUNT(*) FILTER (WHERE s.sentiment = 'Neutral'),
                   COUNT(*) FILTER (WHERE s.sentiment = 'Negative'),
                   COUNT(*),
                   ROUND(100.0 * COUNT(*) FILTER (WHERE s.sentiment = 'Negative') / NULLIF(COUNT(*), 0), 2)
            FROM posts p JOIN sentiment_results s ON p.post_id = s.post_id
            WHERE p.post_date IS NOT NULL
            GROUP BY 1 ORDER BY 1
        """,
        "topics": """
            INSERT INTO topics (topic, positive, neutral, negative, total)
            SELECT p.topic,
                   COUNT(*) FILTER (WHERE s.sentiment = 'Positive'),
                   COUNT(*) FILTER (WHERE s.sentiment = 'Neutral'),
                   COUNT(*) FILTER (WHERE s.sentiment = 'Negative'),
                   COUNT(*)
            FROM posts p JOIN sentiment_results s ON p.post_id = s.post_id
            GROUP BY p.topic
        """,
        "hashtags": """
            INSERT INTO hashtags (hashtag, count)
            SELECT tag, COUNT(*) FROM (
                SELECT unnest(string_to_array(hashtags, ' ')) AS tag FROM posts
            ) exploded
            WHERE tag LIKE '#%' AND length(tag) > 1
            GROUP BY tag ORDER BY COUNT(*) DESC LIMIT 100
        """,
        "keywords": """
            INSERT INTO keywords (keyword, count)
            SELECT token, COUNT(*) FROM posts,
                 LATERAL regexp_split_to_table(clean_text, '\\s+') AS token
            WHERE char_length(token) > 2
            GROUP BY token ORDER BY COUNT(*) DESC LIMIT 100
        """,
    }
    counts = {}
    with engine.begin() as connection:
        for table, statement in statements.items():
            connection.execute(text(statement))
            counts[table] = connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
    return counts


def build_alerts() -> dict:
    with engine.begin() as connection:
        total, negative = connection.execute(text("""
            SELECT COUNT(*), COUNT(*) FILTER (WHERE sentiment = 'Negative')
            FROM sentiment_results
        """)).one()
        negative_pct = round(negative / total * 100, 2) if total else 0.0
        threshold = float(os.environ.get("NEGATIVE_SENTIMENT_ALERT_THRESHOLD", "40"))
        major_topic = connection.execute(text("""
            SELECT topic FROM topics
            WHERE total >= 500
            ORDER BY (negative::float / NULLIF(total, 0)) DESC, total DESC
            LIMIT 1
        """)).scalar() or "Unknown"
        max_date = connection.execute(text("SELECT MAX(post_date)::date FROM posts")).scalar()
        from datetime import timedelta
        start = max_date - timedelta(days=14)
        previous = start - timedelta(days=14)
        period = connection.execute(text("""
            SELECT
              COUNT(*) FILTER (WHERE sentiment = 'Negative' AND post_date::date > :start) AS neg,
              COUNT(*) FILTER (WHERE post_date::date > :start) AS total,
              COUNT(*) FILTER (WHERE sentiment = 'Negative' AND post_date::date <= :start
                               AND post_date::date > :prev) AS prev_neg,
              COUNT(*) FILTER (WHERE post_date::date <= :start AND post_date::date > :prev) AS prev_total
            FROM posts p JOIN sentiment_results s ON p.post_id = s.post_id
            WHERE post_date::date > :prev
        """), {"start": start, "prev": previous}).mappings().one()
        current_pct = round(period["neg"] / period["total"] * 100, 2) if period["total"] else 0.0
        prev_pct = round(period["prev_neg"] / period["prev_total"] * 100, 2) if period["prev_total"] else 0.0
        change = round(current_pct - prev_pct, 2) if period["prev_total"] else 0.0

        connection.execute(text("DELETE FROM alerts"))
        connection.execute(text("""
            INSERT INTO alerts (alert_type, triggered, message, threshold, negative_percentage, major_topic)
            VALUES (:type, :triggered, :message, :threshold, :negative_pct, :topic)
        """), {
            "type": "negative_threshold",
            "triggered": negative_pct > threshold,
            "message": (f"Negative sentiment is {negative_pct}% (threshold {threshold}%), "
                        f"driven by {major_topic}.") if negative_pct > threshold else
                       f"Negative sentiment is {negative_pct}% (threshold {threshold}%).",
            "threshold": threshold,
            "negative_pct": negative_pct,
            "topic": major_topic,
        })
        connection.execute(text("""
            INSERT INTO alerts (alert_type, triggered, message, threshold, negative_percentage, major_topic)
            VALUES (:type, :triggered, :message, :threshold, :negative_pct, :topic)
        """), {
            "type": "period_change",
            "triggered": bool(change > 5),
            "message": f"Negative share changed by {change:+.2f} pp over the latest 28 days.",
            "threshold": 5.0,
            "negative_pct": current_pct,
            "topic": None,
        })
    return {
        "overall_negative_pct": negative_pct,
        "major_topic": major_topic,
        "current_28d_negative_pct": current_pct,
        "previous_28d_negative_pct": prev_pct,
        "change_pp": change,
    }


def run_load_real() -> dict:
    print(f"Loading {CURATED_PREDICTIONS_PATH} into PostgreSQL...")
    Base.metadata.create_all(engine)
    run_migrations()
    counts = {}
    counts.update(load_posts_and_predictions())
    counts.update(build_aggregate_tables())
    alerts = build_alerts()
    counts["alerts"] = 2
    report = {"counts": counts, "alerts": alerts, "loaded_at": datetime.utcnow().isoformat()}
    RESEARCH_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESEARCH_RESULTS_DIR / "db_load.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    run_load_real()
