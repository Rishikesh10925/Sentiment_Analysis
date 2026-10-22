"""
Stage 7: load processed data into PostgreSQL.

Reads the outputs of earlier stages:
    data/processed/predicted_social_media_sample.csv  (Stage 4 ML predictions)
    data/processed/spark_aggregates/*.csv               (Stage 5 Spark aggregates)
    data/processed/analytics_summary.json                (Stage 6 alerts)

and loads them into the tables defined in backend/db/models.py. Safe to
re-run: it clears each table before reloading (idempotent), rather than
appending duplicates.

Run:
    python -m backend.db.load_data
"""

import json

import pandas as pd

from backend.db.models import Alert, Base, DailySentiment, Hashtag, Keyword, Post, SentimentResult, Topic
from backend.db.session import DB_HOST, DB_NAME, DB_PORT, engine, SessionLocal
from ingestion.config import PROCESSED_DATA_DIR

PREDICTIONS_PATH = PROCESSED_DATA_DIR / "predicted_social_media_sample.csv"
SPARK_AGG_DIR = PROCESSED_DATA_DIR / "spark_aggregates"
ANALYTICS_SUMMARY_PATH = PROCESSED_DATA_DIR / "analytics_summary.json"


def load_posts_and_sentiment(session, df: pd.DataFrame) -> tuple:
    session.query(SentimentResult).delete()
    session.query(Post).delete()

    posts = [
        {
            "post_id": str(row["post_id"]),
            "platform": row["platform"],
            "author": row["author"],
            "post_date": pd.to_datetime(row["date"], errors="coerce"),
            "topic": row["topic"] if pd.notna(row["topic"]) else "Unknown",
            "original_text": row["original_text"],
            "clean_text": row["clean_text"],
            "hashtags": row["hashtags"] if pd.notna(row["hashtags"]) else "",
        }
        for _, row in df.iterrows()
    ]
    session.bulk_insert_mappings(Post, posts)

    sentiments = [
        {
            "post_id": str(row["post_id"]),
            "sentiment": row["predicted_sentiment"],
            "confidence": float(row["prediction_confidence"]) if pd.notna(row.get("prediction_confidence")) else None,
        }
        for _, row in df.iterrows()
    ]
    session.bulk_insert_mappings(SentimentResult, sentiments)
    return len(posts), len(sentiments)


def load_daily_sentiment(session, df: pd.DataFrame) -> int:
    session.query(DailySentiment).delete()
    rows = [
        {
            "period_date": pd.to_datetime(row["period"]).date(),
            "positive": int(row["positive"]),
            "neutral": int(row["neutral"]),
            "negative": int(row["negative"]),
            "total": int(row["total"]),
            "negative_pct": float(row["negative_pct"]),
        }
        for _, row in df.iterrows()
    ]
    session.bulk_insert_mappings(DailySentiment, rows)
    return len(rows)


def load_hashtags(session, df: pd.DataFrame) -> int:
    session.query(Hashtag).delete()
    rows = [{"hashtag": row["hashtag"], "count": int(row["count"])} for _, row in df.iterrows()]
    session.bulk_insert_mappings(Hashtag, rows)
    return len(rows)


def load_keywords(session, df: pd.DataFrame) -> int:
    session.query(Keyword).delete()
    rows = [{"keyword": row["keyword"], "count": int(row["count"])} for _, row in df.iterrows()]
    session.bulk_insert_mappings(Keyword, rows)
    return len(rows)


def load_topics(session, df: pd.DataFrame) -> int:
    session.query(Topic).delete()
    rows = [
        {
            "topic": row["topic"] if pd.notna(row["topic"]) else "Unknown",
            "positive": int(row["Positive"]),
            "neutral": int(row["Neutral"]),
            "negative": int(row["Negative"]),
            "total": int(row["total"]),
        }
        for _, row in df.iterrows()
    ]
    session.bulk_insert_mappings(Topic, rows)
    return len(rows)


def load_alerts(session, summary: dict) -> int:
    session.query(Alert).delete()
    rows = []
    threshold_alert = summary["alerts"]["negative_threshold"]
    rows.append({
        "alert_type": threshold_alert["type"],
        "triggered": threshold_alert["triggered"],
        "message": threshold_alert["message"],
        "threshold": threshold_alert["threshold"],
        "negative_percentage": threshold_alert["negative_percentage"],
        "major_topic": threshold_alert["major_topic"],
    })
    period_alert = summary["alerts"]["period_change"]
    rows.append({
        "alert_type": period_alert["type"],
        "triggered": period_alert["triggered"],
        "message": period_alert.get("message"),
        "threshold": period_alert.get("change_threshold"),
        "negative_percentage": period_alert.get("current_negative_pct"),
        "major_topic": None,
    })
    session.bulk_insert_mappings(Alert, rows)
    return len(rows)


def run_load() -> dict:
    for path in (PREDICTIONS_PATH, SPARK_AGG_DIR / "daily_trend.csv",
                 SPARK_AGG_DIR / "hashtag_frequency.csv", SPARK_AGG_DIR / "keyword_frequency.csv",
                 SPARK_AGG_DIR / "topic_summary.csv", ANALYTICS_SUMMARY_PATH):
        if not path.exists():
            raise FileNotFoundError(
                f"Missing {path}. Run the earlier stages first "
                f"(ml.predict, spark.process, analytics.build_summary)."
            )

    print(f"Connecting to {DB_HOST}:{DB_PORT}/{DB_NAME}")
    Base.metadata.create_all(engine)

    predictions_df = pd.read_csv(PREDICTIONS_PATH)
    daily_df = pd.read_csv(SPARK_AGG_DIR / "daily_trend.csv")
    hashtag_df = pd.read_csv(SPARK_AGG_DIR / "hashtag_frequency.csv")
    keyword_df = pd.read_csv(SPARK_AGG_DIR / "keyword_frequency.csv")
    topic_df = pd.read_csv(SPARK_AGG_DIR / "topic_summary.csv")
    with open(ANALYTICS_SUMMARY_PATH, encoding="utf-8") as f:
        summary = json.load(f)

    session = SessionLocal()
    counts = {}
    try:
        counts["posts"], counts["sentiment_results"] = load_posts_and_sentiment(session, predictions_df)
        counts["daily_sentiment"] = load_daily_sentiment(session, daily_df)
        counts["hashtags"] = load_hashtags(session, hashtag_df)
        counts["keywords"] = load_keywords(session, keyword_df)
        counts["topics"] = load_topics(session, topic_df)
        counts["alerts"] = load_alerts(session, summary)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    print("Loaded rows:")
    for table, n in counts.items():
        print(f"  {table}: {n}")

    return counts


if __name__ == "__main__":
    run_load()
