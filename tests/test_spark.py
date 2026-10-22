"""
Tests for the Stage 5 PySpark pipeline.

Spins up a real local SparkSession (via spark.session.get_spark_session,
which falls back to the portable bundled JDK automatically). Skipped
gracefully if pyspark or a JVM isn't available in the environment running
the tests, since that's an environment concern, not a code-correctness one.
"""

import pytest

pyspark = pytest.importorskip("pyspark")

import csv
from pathlib import Path

from ingestion.config import PROCESSED_DATA_DIR, PROJECT_ROOT
from spark.clean import spark_clean_pipeline
from spark.session import get_spark_session


def _spark_available():
    try:
        spark = get_spark_session("pytest-availability-check")
        spark.createDataFrame  # noqa: B018 - just confirm session object is usable
        spark.range(1).count()
        spark.stop()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _spark_available(), reason="No working local Spark/JVM available in this environment"
)


@pytest.fixture(scope="module")
def spark():
    session = get_spark_session("pytest-social-sentiment")
    yield session
    session.stop()


@pytest.fixture()
def tiny_csv(tmp_path):
    path = tmp_path / "tiny.csv"
    rows = [
        {"id": 1, "platform": "Reddit", "post_id": "A", "author": "u1",
         "text": "@user Check this out!!! http://example.com #Cool The BEST!!!",
         "date": "2025-04-01 10:00:00", "topic": "Battery", "hashtags": ""},
        {"id": 2, "platform": "Instagram", "post_id": "B", "author": "u2",
         "text": "", "date": "2025-04-01 10:00:00", "topic": "Camera", "hashtags": ""},
        {"id": 3, "platform": "Reddit", "post_id": "A", "author": "u3",
         "text": "@user Check this out!!! http://example.com #Cool The BEST!!! (dup)",
         "date": "2025-04-01 10:00:00", "topic": "Battery", "hashtags": ""},
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_spark_clean_pipeline_strips_noise_and_extracts_hashtags(spark, tiny_csv):
    df = spark.read.csv(str(tiny_csv), header=True, inferSchema=True)
    cleaned = spark_clean_pipeline(df, text_col="text")
    pdf = cleaned.filter(cleaned.id == 1).toPandas()

    clean_text = pdf.iloc[0]["spark_clean_text_final"]
    assert "http" not in clean_text
    assert "@" not in clean_text
    assert "#" not in clean_text
    assert "check" in clean_text
    assert "best" in clean_text

    hashtags = pdf.iloc[0]["hashtags_array"]
    assert list(hashtags) == ["cool"]


def test_spark_dedup_by_post_id(spark, tiny_csv):
    df = spark.read.csv(str(tiny_csv), header=True, inferSchema=True)
    deduped = df.dropDuplicates(["post_id"])
    assert deduped.count() == 2  # post_id "A" appears twice, "B" once


def test_full_spark_pipeline_matches_upstream_stage_counts():
    from spark.process import run_spark_pipeline

    predictions_path = PROCESSED_DATA_DIR / "predicted_social_media_sample.csv"
    if not predictions_path.exists():
        pytest.skip("Run `python -m ml.predict` first to produce predictions for the Spark job")

    output = run_spark_pipeline(write_output=True)
    report = output["report"]
    results = output["results"]

    assert report["rows_ingested_raw"] > 0
    assert report["rows_after_dedup"] <= report["rows_after_missing_text_drop"]
    assert report["rows_after_missing_text_drop"] <= report["rows_ingested_raw"]
    assert report["rows_matched_with_predictions"] == report["rows_after_dedup"]
    assert 0 <= report["overall_negative_percentage"] <= 100

    assert set(results["sentiment_summary"]["predicted_sentiment"]) <= {"Positive", "Neutral", "Negative"}
    assert len(results["platform_summary"]) == 6
    assert len(results["hashtag_frequency"]) <= 30
    assert len(results["keyword_frequency"]) <= 30
    assert len(results["negative_posts"]) <= 20

    out_dir = PROCESSED_DATA_DIR / "spark_aggregates"
    assert (out_dir / "sentiment_summary.csv").exists()
    assert (out_dir / "spark_processing_report.json").exists()
