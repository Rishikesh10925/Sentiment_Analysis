"""
Tests for the Stage 7 database layer. These reload the dashboard tables from
the sample CSV, so they only run against a throwaway database configured via
TEST_DATABASE_URL (see conftest.py). Without it they skip: running them
against the demo database would replace the 1.65M-row corpus with sample data.
"""

import os

import pytest
from sqlalchemy import text


def _db_available():
    try:
        from backend.db.session import engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL") or not _db_available(),
    reason=(
        "Destructive loader tests require TEST_DATABASE_URL pointing at a "
        "throwaway PostgreSQL database"
    ),
)


def test_load_data_populates_all_tables():
    from backend.db.load_data import run_load

    counts = run_load()

    assert counts["posts"] > 0
    assert counts["sentiment_results"] == counts["posts"]
    assert counts["daily_sentiment"] > 0
    assert counts["hashtags"] > 0
    assert counts["topics"] > 0
    assert counts["alerts"] == 2


def test_load_data_is_idempotent():
    from backend.db.load_data import run_load

    first = run_load()
    second = run_load()
    assert first == second


def test_posts_and_sentiment_join_matches_spark_platform_summary():
    from backend.db.session import SessionLocal
    from backend.db.models import Post, SentimentResult
    from sqlalchemy import func

    session = SessionLocal()
    try:
        rows = (
            session.query(Post.platform, func.count(SentimentResult.id))
            .join(SentimentResult, Post.post_id == SentimentResult.post_id)
            .group_by(Post.platform)
            .all()
        )
        counts = dict(rows)
        assert set(counts.keys()) == {
            "Instagram", "Facebook", "YouTube", "Reddit", "X/Twitter", "WhatsApp Export",
        }
        assert sum(counts.values()) == session.query(Post).count()
    finally:
        session.close()


def test_alerts_table_has_both_alert_types():
    from backend.db.session import SessionLocal
    from backend.db.models import Alert

    session = SessionLocal()
    try:
        types = {row.alert_type for row in session.query(Alert).all()}
        assert types == {"negative_threshold", "period_change"}
    finally:
        session.close()
