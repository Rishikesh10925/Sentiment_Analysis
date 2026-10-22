import pandas as pd
import pytest

from ingestion.config import SAMPLE_DATA_PATH
from ingestion.validate import ValidationError, load_csv, validate_data, validate_schema


def test_validate_schema_ok():
    df = pd.DataFrame(columns=[
        "id", "platform", "post_id", "author", "text", "date", "topic", "hashtags",
    ])
    assert validate_schema(df) == []


def test_validate_schema_missing_columns():
    df = pd.DataFrame(columns=["id", "platform", "post_id", "author", "text", "date"])
    missing = validate_schema(df)
    assert "topic" in missing
    assert "hashtags" in missing


def test_validate_data_raises_on_missing_columns():
    df = pd.DataFrame({"id": [1], "platform": ["Reddit"]})
    with pytest.raises(ValidationError):
        validate_data(df)


def test_validate_data_counts_missing_and_duplicates():
    df = pd.DataFrame({
        "id": [1, 2, 3, 4],
        "platform": ["Reddit", "Instagram", "Reddit", "Unknown"],
        "post_id": ["A", "B", "B", "C"],
        "author": ["u1", "u2", "u3", "u4"],
        "text": ["hello world", "", None, "another post"],
        "date": ["2025-04-01 10:00:00", "2025-04-02 10:00:00", "not-a-date", "2025-04-03 10:00:00"],
        "topic": ["Battery", "Camera", "Battery", None],
        "hashtags": ["", "", "", ""],
    })
    report = validate_data(df, source_label="test-fixture")

    assert report["total_rows"] == 4
    assert report["missing_values"]["text"] == 2       # empty string + None
    assert report["missing_values"]["topic"] == 1
    assert report["missing_values"]["hashtags"] == 4
    assert report["duplicate_post_ids"] == 1            # "B" appears twice
    assert report["invalid_platform_count"] == 1
    assert report["invalid_platform_values"] == ["Unknown"]
    assert report["invalid_date_count"] == 1


def test_sample_dataset_loads_and_passes_schema():
    df = load_csv(SAMPLE_DATA_PATH)
    assert validate_schema(df) == []
    report = validate_data(df, source_label=str(SAMPLE_DATA_PATH))

    # Deterministic because the generator uses a fixed random seed.
    assert report["total_rows"] == 5150
    assert report["invalid_platform_count"] == 0
    assert set(report["platform_counts"].keys()) == {
        "Instagram", "Facebook", "YouTube", "Reddit", "X/Twitter", "WhatsApp Export",
    }
    assert report["duplicate_post_ids"] > 0  # duplicates were injected intentionally
    assert report["missing_values"]["text"] > 0  # missing text injected intentionally
