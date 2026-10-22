import pandas as pd

from ingestion.config import SAMPLE_DATA_PATH
from ingestion.validate import load_csv
from preprocessing.clean import clean_text, extract_hashtags
from preprocessing.pipeline import preprocess_dataframe


def test_extract_hashtags_dedupes_and_lowercases():
    text = "Loving #Battery life and #TechReview today #battery"
    assert extract_hashtags(text) == ["battery", "techreview"]


def test_extract_hashtags_empty_input():
    assert extract_hashtags("") == []
    assert extract_hashtags(None) == []


def test_clean_text_strips_noise_and_stopwords():
    raw = "@user Check this out!!! http://example.com #Cool The BEST!!!"
    cleaned = clean_text(raw)
    assert cleaned == "check best"
    assert "http" not in cleaned
    assert "@" not in cleaned
    assert "#" not in cleaned


def test_clean_text_strips_emojis():
    raw = "Great camera quality \U0001F600 and ❤️ amazing ⚠️ warning"
    cleaned = clean_text(raw)
    assert "\U0001F600" not in cleaned
    assert "❤" not in cleaned
    assert cleaned == "great camera quality amazing warning"


def test_clean_text_empty_input():
    assert clean_text("") == ""
    assert clean_text(None) == ""
    assert clean_text("   ") == ""


def test_preprocess_dataframe_drops_missing_text_and_dedupes():
    df = pd.DataFrame({
        "id": [1, 2, 3, 4, 5],
        "platform": ["Reddit", "Instagram", "Reddit", "Facebook", "Reddit"],
        "post_id": ["A", "B", "B", "C", "A"],
        "author": ["u1", "u2", "u3", "u4", "u1"],
        "text": ["Great #battery life!", "", "duplicate of B", "Bad service http://x.com @support", "Great #battery life! (re-scraped)"],
        "date": ["2025-04-01 10:00:00"] * 5,
        "topic": ["Battery", "Camera", "Battery", None, "Battery"],
        "hashtags": ["", "", "", "", ""],
    })
    result = preprocess_dataframe(df)

    assert list(result.columns) == [
        "id", "platform", "post_id", "author", "date", "topic",
        "hashtags", "original_text", "clean_text",
    ]
    # id=2 (empty text, post_id "B") dropped for missing text;
    # id=5 (post_id "A", a duplicate of id=1) dropped for being a duplicate post_id.
    assert len(result) == 3
    assert set(result["post_id"]) == {"A", "B", "C"}
    assert result.loc[result["post_id"] == "A", "id"].iloc[0] == 1  # first occurrence kept
    assert result.loc[result["post_id"] == "A", "hashtags"].iloc[0] == "#battery"
    assert result.loc[result["post_id"] == "C", "topic"].iloc[0] == "Unknown"
    assert "http" not in result.loc[result["post_id"] == "C", "clean_text"].iloc[0]
    assert "@" not in result.loc[result["post_id"] == "C", "clean_text"].iloc[0]


def test_pipeline_on_sample_dataset():
    df = load_csv(SAMPLE_DATA_PATH)
    original_len = len(df)
    result = preprocess_dataframe(df)

    assert "original_text" in result.columns
    assert "clean_text" in result.columns
    assert "hashtags" in result.columns
    assert "text" not in result.columns
    assert len(result) < original_len
    assert result["post_id"].duplicated().sum() == 0
    assert (result["topic"] == "").sum() == 0
    assert result["clean_text"].isna().sum() == 0
    assert not result["clean_text"].str.contains("http", case=False).any()
    assert not result["clean_text"].str.contains("@").any()
    assert not result["clean_text"].str.contains("#").any()
