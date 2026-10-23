"""Read-only tests for the v2 analytics API and serving explanations."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def _db_available() -> bool:
    try:
        from sqlalchemy import text
        from backend.db.session import engine
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


db_required = pytest.mark.skipif(not _db_available(), reason="PostgreSQL unavailable")


@db_required
def test_meta_reports_real_corpus_and_model():
    response = client.get("/api/v2/meta")
    assert response.status_code == 200
    body = response.json()
    assert body["total_posts"] > 1_000_000
    assert "X/Twitter" in body["platforms"]
    assert body["model"]["available"] is True
    assert body["provenance"]["sources"]


@db_required
def test_summary_and_filters_are_consistent():
    everything = client.get("/api/v2/summary").json()
    reddit = client.get("/api/v2/summary", params={"platform": "Reddit"}).json()
    assert reddit["total_posts"] < everything["total_posts"]
    assert abs(sum(reddit["percentages"].values()) - 100) < 0.1
    assert everything["average_confidence"] is not None


@db_required
def test_trends_respect_granularity_and_date_bounds():
    response = client.get("/api/v2/trends", params={"granularity": "month"})
    assert response.status_code == 200
    points = response.json()["points"]
    assert points
    assert all(point["total"] > 0 for point in points)
    bad = client.get("/api/v2/trends", params={"granularity": "fortnight"})
    assert bad.status_code == 422


@db_required
def test_posts_and_detail_expose_evidence():
    listing = client.get("/api/v2/posts", params={"limit": 3}).json()
    assert listing["total"] > 0
    post = listing["items"][0]
    detail = client.get(f"/api/v2/posts/{post['post_id']}").json()
    assert detail["post_id"] == post["post_id"]
    assert "probabilities" in detail
    assert detail["explanation"]["tokens"]
    assert "gold_sentiment" not in detail


@db_required
def test_missing_post_returns_404():
    response = client.get("/api/v2/posts/not-a-real-post")
    assert response.status_code == 404


def test_predict_and_explain_are_exact_and_bounded():
    text = "I love this update, it fixed every crash."
    predicted = client.post("/api/v2/predict", json={"text": text})
    assert predicted.status_code == 200
    body = predicted.json()
    assert body["sentiment"] in {"Positive", "Neutral", "Negative"}
    assert abs(sum(body["probabilities"].values()) - 1) < 0.01
    assert body["explanation"]["tokens"]

    explanation = client.post("/api/v2/explain", json={"text": text})
    assert explanation.status_code == 200
    assert explanation.json()["method"].startswith("exact linear SHAP")

    too_long = client.post("/api/v2/predict", json={"text": "x" * 2001})
    assert too_long.status_code == 422


@db_required
def test_exports_have_attachment_headers():
    csv_response = client.get("/api/v2/export/posts.csv", params={"max_rows": 5})
    assert csv_response.status_code == 200
    assert "text/csv" in csv_response.headers["content-type"]
    assert "attachment" in csv_response.headers["content-disposition"]
    assert len(csv_response.text.splitlines()) <= 6

    pdf_response = client.get("/api/v2/export/report.pdf")
    assert pdf_response.status_code == 200
    assert pdf_response.content.startswith(b"%PDF")


@db_required
def test_research_payload_contains_measured_limitations():
    response = client.get("/api/v2/research")
    assert response.status_code == 200
    body = response.json()
    assert body["leaderboard"]
    assert body["limitations"]
    assert body["baselines"]["dataset"]["test_rows"] == 12284


def test_upload_api_key_is_enforced_when_configured(monkeypatch):
    from backend import main

    monkeypatch.setattr(main.settings, "api_key", "secret-key")
    payload = "id,platform,post_id,author,text,date,topic,hashtags\n1,Reddit,R1,u,x,2025-01-01,General,\n"
    files = {"file": ("x.csv", io.BytesIO(payload.encode()), "text/csv")}
    assert client.post("/api/upload", params={"analyze": "false"}, files=files).status_code == 401
    files = {"file": ("x.csv", io.BytesIO(payload.encode()), "text/csv")}
    allowed = client.post(
        "/api/upload",
        params={"analyze": "false"},
        files=files,
        headers={"X-API-Key": "secret-key"},
    )
    assert allowed.status_code == 200
