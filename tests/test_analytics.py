import os

import pandas as pd
import pytest

from analytics.alerts import check_negative_threshold_alert, detect_period_change, get_negative_threshold
from analytics.build_summary import build_overview, build_summary


def test_get_negative_threshold_default():
    os.environ.pop("NEGATIVE_SENTIMENT_ALERT_THRESHOLD", None)
    assert get_negative_threshold() == 40.0


def test_get_negative_threshold_from_env(monkeypatch):
    monkeypatch.setenv("NEGATIVE_SENTIMENT_ALERT_THRESHOLD", "25")
    assert get_negative_threshold() == 25.0


def test_negative_threshold_alert_not_triggered_below_threshold():
    alert = check_negative_threshold_alert(28.85, major_topic="Battery", threshold=40.0)
    assert alert["triggered"] is False
    assert alert["message"] is None


def test_negative_threshold_alert_triggered_matches_spec_format():
    alert = check_negative_threshold_alert(43.0, major_topic="Battery", threshold=40.0)
    assert alert["triggered"] is True
    assert alert["message"] == (
        "⚠ Negative Sentiment Alert\n"
        "Negative sentiment: 43.0%\n"
        "Threshold: 40.0%\n"
        "Major topic: Battery"
    )


def test_detect_period_change_insufficient_history():
    df = pd.DataFrame({"period": ["2025-01"], "negative_pct": [30.0]})
    result = detect_period_change(df)
    assert result["triggered"] is False
    assert "not enough date history" in result["reason"]


def test_detect_period_change_triggers_on_large_swing():
    df = pd.DataFrame({
        "period": ["2025-01", "2025-02", "2025-03"],
        "negative_pct": [20.0, 22.0, 40.0],
    })
    result = detect_period_change(df, change_threshold=10.0)
    assert result["triggered"] is True
    assert result["current_period"] == "2025-03"
    assert result["previous_period"] == "2025-02"
    assert result["change"] == 18.0


def test_detect_period_change_no_trigger_on_small_swing():
    df = pd.DataFrame({
        "period": ["2025-01", "2025-02"],
        "negative_pct": [20.0, 22.0],
    })
    result = detect_period_change(df, change_threshold=10.0)
    assert result["triggered"] is False


def test_build_overview_percentages_sum_to_100():
    sentiment_df = pd.DataFrame({
        "predicted_sentiment": ["Positive", "Neutral", "Negative"],
        "count": [40, 32, 28],
    })
    platform_df = pd.DataFrame({"platform": ["Instagram", "Reddit"]})
    topic_df = pd.DataFrame({"topic": ["Battery", "Camera", "Pricing"]})

    overview = build_overview(sentiment_df, platform_df, topic_df)
    assert overview["total_posts"] == 100
    assert overview["num_platforms"] == 2
    assert overview["num_topics"] == 3
    total_pct = overview["positive_pct"] + overview["neutral_pct"] + overview["negative_pct"]
    assert round(total_pct, 1) == 100.0


def test_build_summary_on_real_spark_output():
    from ingestion.config import PROCESSED_DATA_DIR

    agg_dir = PROCESSED_DATA_DIR / "spark_aggregates"
    if not (agg_dir / "sentiment_summary.csv").exists():
        pytest.skip("Run `python -m spark.process` first to produce Spark aggregates")

    summary = build_summary(write_output=True)

    assert summary["overview"]["total_posts"] > 0
    assert 0 <= summary["overview"]["negative_pct"] <= 100
    assert "negative_threshold" in summary["alerts"]
    assert "period_change" in summary["alerts"]
    assert len(summary["platforms"]) == 6
    assert (PROCESSED_DATA_DIR / "analytics_summary.json").exists()
