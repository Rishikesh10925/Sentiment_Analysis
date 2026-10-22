"""
Tests for the Stage 8 FastAPI backend. Uses FastAPI's TestClient, which
calls the app in-process (no server needed) but still exercises real
routing, dependency injection, and (for most tests) the real database.
DB-backed tests are skipped gracefully if no PostgreSQL is reachable.
"""

import io

import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def _db_available():
    try:
        from sqlalchemy import text
        from backend.db.session import engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


db_required = pytest.mark.skipif(not _db_available(), reason="No reachable PostgreSQL for this environment")


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_upload_valid_csv_validate_only():
    # analyze=false: validation only, doesn't touch the shared DB other
    # tests in this file depend on (see test_upload_with_analyze below
    # for the full-pipeline path, run against its own dedicated file).
    csv_content = "id,platform,post_id,author,text,date,topic,hashtags\n1,Reddit,RD-1,u1,great stuff,2025-04-01 10:00:00,Battery,\n"
    files = {"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    resp = client.post("/api/upload", params={"analyze": "false"}, files=files)
    assert resp.status_code == 200
    body = resp.json()
    assert body["analyzed"] is False
    assert body["validation_report"]["total_rows"] == 1
    assert body["required_columns"][0] == "id"


def test_upload_rejects_non_csv():
    files = {"file": ("test.txt", io.BytesIO(b"not a csv"), "text/plain")}
    resp = client.post("/api/upload", params={"analyze": "false"}, files=files)
    assert resp.status_code == 400


def test_upload_rejects_missing_columns():
    csv_content = "id,platform\n1,Reddit\n"
    files = {"file": ("bad.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    resp = client.post("/api/upload", params={"analyze": "false"}, files=files)
    assert resp.status_code == 422
    assert "Missing required columns" in resp.json()["detail"]


@db_required
def test_upload_with_analyze_runs_full_pipeline_and_replaces_dashboard_data():
    """The default (analyze=true) path: validates, then runs the real
    pipeline (preprocessing -> ml.predict -> spark.process -> analytics ->
    DB reload) and replaces the dashboard's data with this file's
    analysis. Uses a small dataset (30 rows) so Spark's real per-run cost
    is bounded; skipped if the environment has no working Spark, same as
    tests/test_spark.py checks for.

    This test intentionally overwrites the shared DB's data (that's the
    feature being tested), so it restores the original demo dataset in a
    `finally` block - other tests in this file depend on that data and
    must not see this test's 30-row upload instead, regardless of test
    order.
    """
    import pytest as _pytest

    try:
        from spark.session import get_spark_session
        s = get_spark_session("pytest-upload-check")
        s.range(1).count()
        s.stop()
    except Exception:
        _pytest.skip("No working local Spark/JVM available in this environment")

    rows = ["id,platform,post_id,author,text,date,topic,hashtags"]
    for i in range(1, 31):
        sentiment_word = "amazing love great" if i % 3 == 0 else ("terrible worst awful" if i % 3 == 1 else "okay fine average")
        rows.append(f"{i},Reddit,RD-up-{i},user{i},{sentiment_word} battery life,2025-06-0{(i % 9) + 1} 10:00:00,Battery,")
    csv_content = "\n".join(rows) + "\n"
    files = {"file": ("upload_pipeline_test.csv", io.BytesIO(csv_content.encode()), "text/csv")}

    try:
        resp = client.post("/api/upload", files=files)
        assert resp.status_code == 200
        body = resp.json()

        assert body["analyzed"] is True
        assert body["db_loaded"] is True
        assert body["spark_report"]["rows_ingested_raw"] == 30
        assert body["summary"]["total_posts"] > 0
        assert "alerts" in body

        # The dashboard now reflects this small file, not the original demo data.
        dashboard_resp = client.get("/api/dashboard/summary")
        assert dashboard_resp.json()["total_posts"] == body["summary"]["total_posts"]
    finally:
        from scripts.run_pipeline import run_full_pipeline
        run_full_pipeline(load_db=True, log=lambda *_: None)


@db_required
def test_dashboard_summary_percentages_sum_to_100():
    resp = client.get("/api/dashboard/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_posts"] > 0
    total_pct = body["positive_pct"] + body["neutral_pct"] + body["negative_pct"]
    assert round(total_pct, 0) == 100


@db_required
def test_dashboard_sentiment_has_three_classes():
    resp = client.get("/api/dashboard/sentiment")
    assert resp.status_code == 200
    sentiments = {row["sentiment"] for row in resp.json()}
    assert sentiments == {"Positive", "Neutral", "Negative"}


@db_required
def test_dashboard_platforms_has_six_rows():
    resp = client.get("/api/dashboard/platforms")
    assert resp.status_code == 200
    assert len(resp.json()) == 6


@db_required
def test_dashboard_trends_granularity_validation():
    resp = client.get("/api/dashboard/trends", params={"granularity": "day"})
    assert resp.status_code == 200
    assert len(resp.json()) > 0

    resp_bad = client.get("/api/dashboard/trends", params={"granularity": "bogus"})
    assert resp_bad.status_code == 422


@db_required
def test_dashboard_hashtags_respects_limit():
    resp = client.get("/api/dashboard/hashtags", params={"limit": 5})
    assert resp.status_code == 200
    assert len(resp.json()) <= 5


@db_required
def test_dashboard_negative_posts_all_negative():
    resp = client.get("/api/dashboard/negative-posts", params={"limit": 10})
    assert resp.status_code == 200
    posts = resp.json()
    assert len(posts) > 0
    assert all(p["sentiment"] == "Negative" for p in posts)


@db_required
def test_dashboard_alerts_returns_both_types():
    resp = client.get("/api/dashboard/alerts")
    assert resp.status_code == 200
    types = {a["type"] for a in resp.json()}
    assert types == {"negative_threshold", "period_change"}


@db_required
def test_posts_filter_by_platform_and_sentiment_matches_platform_breakdown():
    platforms_resp = client.get("/api/dashboard/platforms").json()
    reddit = next(p for p in platforms_resp if p["platform"] == "Reddit")

    posts_resp = client.get("/api/posts", params={"platform": "Reddit", "sentiment": "Negative", "limit": 1})
    assert posts_resp.status_code == 200
    body = posts_resp.json()
    assert body["total"] == reddit["Negative"]
    assert len(body["items"]) == 1
    assert body["items"][0]["platform"] == "Reddit"
    assert body["items"][0]["sentiment"] == "Negative"


@db_required
def test_posts_filter_by_keyword():
    resp = client.get("/api/posts", params={"keyword": "battery", "limit": 5})
    assert resp.status_code == 200
    body = resp.json()
    for item in body["items"]:
        assert "battery" in item["clean_text"]


@db_required
def test_posts_pagination():
    page1 = client.get("/api/posts", params={"limit": 5, "offset": 0}).json()
    page2 = client.get("/api/posts", params={"limit": 5, "offset": 5}).json()
    assert page1["items"][0]["post_id"] != page2["items"][0]["post_id"]
    assert page1["total"] == page2["total"]
