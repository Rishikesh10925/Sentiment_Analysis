"""
Stage 6: Analytics summary.

Consolidates the Stage 5 Spark aggregation outputs
(data/processed/spark_aggregates/*.csv) into the final dashboard-ready
structures — overview, platforms, topics, trends, hashtags, keywords,
negative content — and evaluates both alerts. This is the data Stage 7
loads into PostgreSQL and Stage 8's API serves.

Run:
    python -m analytics.build_summary
"""

import json

import pandas as pd

from analytics.alerts import check_negative_threshold_alert, detect_period_change, get_negative_threshold
from ingestion.config import PROCESSED_DATA_DIR

SPARK_AGG_DIR = PROCESSED_DATA_DIR / "spark_aggregates"
OUTPUT_PATH = PROCESSED_DATA_DIR / "analytics_summary.json"


def _read(name: str) -> pd.DataFrame:
    path = SPARK_AGG_DIR / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}. Run `python -m spark.process` first.")
    return pd.read_csv(path)


def build_overview(sentiment_df: pd.DataFrame, platform_df: pd.DataFrame, topic_df: pd.DataFrame) -> dict:
    total = int(sentiment_df["count"].sum())
    counts = {row["predicted_sentiment"]: int(row["count"]) for _, row in sentiment_df.iterrows()}
    return {
        "total_posts": total,
        "positive_count": counts.get("Positive", 0),
        "neutral_count": counts.get("Neutral", 0),
        "negative_count": counts.get("Negative", 0),
        "positive_pct": round(counts.get("Positive", 0) / total * 100, 2) if total else 0.0,
        "neutral_pct": round(counts.get("Neutral", 0) / total * 100, 2) if total else 0.0,
        "negative_pct": round(counts.get("Negative", 0) / total * 100, 2) if total else 0.0,
        "num_platforms": int(platform_df["platform"].nunique()),
        "num_topics": int(topic_df["topic"].nunique()),
    }


def build_summary(write_output: bool = True) -> dict:
    sentiment_df = _read("sentiment_summary")
    platform_df = _read("platform_summary")
    topic_df = _read("topic_summary")
    daily_df = _read("daily_trend")
    weekly_df = _read("weekly_trend")
    monthly_df = _read("monthly_trend")
    hashtag_df = _read("hashtag_frequency")
    keyword_df = _read("keyword_frequency")
    negative_topics_df = _read("negative_topics")
    negative_posts_df = _read("negative_posts")

    overview = build_overview(sentiment_df, platform_df, topic_df)

    major_negative_topic = None
    if len(negative_topics_df) > 0:
        major_negative_topic = str(
            negative_topics_df.sort_values("count", ascending=False).iloc[0]["topic"]
        )

    threshold_alert = check_negative_threshold_alert(overview["negative_pct"], major_topic=major_negative_topic)
    # Weekly (not daily) periods for change detection: more stable/meaningful
    # than day-to-day noise on a dataset this size.
    period_alert = detect_period_change(weekly_df, pct_col="negative_pct", period_col="period")

    summary = {
        "overview": overview,
        "platforms": platform_df.to_dict(orient="records"),
        "topics": topic_df.to_dict(orient="records"),
        "trends": {
            "daily": daily_df.to_dict(orient="records"),
            "weekly": weekly_df.to_dict(orient="records"),
            "monthly": monthly_df.to_dict(orient="records"),
        },
        "hashtags": hashtag_df.to_dict(orient="records"),
        "keywords": keyword_df.to_dict(orient="records"),
        "negative_topics": negative_topics_df.to_dict(orient="records"),
        "negative_posts": negative_posts_df.to_dict(orient="records"),
        "alerts": {
            "negative_threshold": threshold_alert,
            "period_change": period_alert,
            "configured_threshold": get_negative_threshold(),
        },
    }

    print(f"Total posts: {overview['total_posts']}")
    print(
        f"Positive: {overview['positive_pct']}%  "
        f"Neutral: {overview['neutral_pct']}%  "
        f"Negative: {overview['negative_pct']}%"
    )
    print(f"Platforms: {overview['num_platforms']}  Topics: {overview['num_topics']}")
    if threshold_alert["triggered"]:
        print("\n" + threshold_alert["message"])
    else:
        print(
            f"\nNo negative-threshold alert "
            f"(negative {overview['negative_pct']}% <= threshold {get_negative_threshold()}%)"
        )
    if period_alert["triggered"]:
        print(period_alert["message"])

    if write_output:
        PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, default=str)
        print(f"\nAnalytics summary written to {OUTPUT_PATH}")

    return summary


def main():
    build_summary()


if __name__ == "__main__":
    main()
