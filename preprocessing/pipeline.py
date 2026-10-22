"""
Stage 3: Text preprocessing.

Takes a validated CSV (see ingestion/validate.py) and produces a cleaned
DataFrame ready for ML (Stage 4) and PySpark aggregation (Stage 5):

- drops rows with missing/empty text (can't classify sentiment with no text)
- fills missing topic with "Unknown"
- de-duplicates by post_id (keeps first occurrence)
- extracts hashtags from raw text AND merges with any pre-existing
  `hashtags` column, before the text is cleaned
- cleans text (URLs, mentions, hashtags, emojis, punctuation, stopwords,
  whitespace — see preprocessing/clean.py)
- keeps `original_text`, `clean_text`, and `hashtags` side by side

Run:
    python -m preprocessing.pipeline                       # processes the sample dataset
    python -m preprocessing.pipeline path/to/other.csv      # process a custom CSV
"""

import argparse
import json
from pathlib import Path

import pandas as pd

from ingestion.config import PROCESSED_DATA_DIR, SAMPLE_DATA_PATH
from ingestion.validate import load_csv
from preprocessing.clean import clean_text, extract_hashtags

OUTPUT_FILENAME = "cleaned_social_media_sample.csv"
REPORT_FILENAME = "preprocessing_report.json"


def _merge_hashtags(raw_text: str, existing_hashtags) -> str:
    extracted = extract_hashtags(raw_text)
    existing = []
    if isinstance(existing_hashtags, str) and existing_hashtags.strip():
        existing = [tag.lstrip("#").lower() for tag in existing_hashtags.split()]
    merged = []
    for tag in extracted + existing:
        if tag not in merged:
            merged.append(tag)
    return " ".join(f"#{tag}" for tag in merged)


def preprocess_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    is_missing_text = df["text"].isna() | (df["text"].astype(str).str.strip() == "")
    df = df[~is_missing_text].copy()

    df["topic"] = df["topic"].fillna("Unknown")
    df.loc[df["topic"].astype(str).str.strip() == "", "topic"] = "Unknown"

    df = df.drop_duplicates(subset=["post_id"], keep="first")

    df["hashtags"] = [
        _merge_hashtags(text, tags) for text, tags in zip(df["text"], df["hashtags"])
    ]
    df["original_text"] = df["text"]
    df["clean_text"] = df["text"].apply(clean_text)

    df = df.drop(columns=["text"])
    column_order = [
        "id", "platform", "post_id", "author", "date", "topic",
        "hashtags", "original_text", "clean_text",
    ]
    return df[column_order].reset_index(drop=True)


def run_pipeline(path=None, write_output: bool = True) -> pd.DataFrame:
    path = Path(path) if path else SAMPLE_DATA_PATH
    df = load_csv(path)
    rows_before = len(df)

    cleaned = preprocess_dataframe(df)
    rows_after = len(cleaned)
    empty_clean_text = int((cleaned["clean_text"].str.strip() == "").sum())

    report = {
        "source": str(path),
        "rows_before": rows_before,
        "rows_after": rows_after,
        "rows_dropped_missing_text": int(
            (df["text"].isna() | (df["text"].astype(str).str.strip() == "")).sum()
        ),
        "rows_dropped_duplicates": rows_before - rows_after - int(
            (df["text"].isna() | (df["text"].astype(str).str.strip() == "")).sum()
        ),
        "rows_with_empty_clean_text_after_cleaning": empty_clean_text,
    }

    print(f"Source: {report['source']}")
    print(f"Rows before: {report['rows_before']}")
    print(f"Rows after: {report['rows_after']}")
    print(f"  dropped (missing text): {report['rows_dropped_missing_text']}")
    print(f"  dropped (duplicate post_id): {report['rows_dropped_duplicates']}")
    print(f"Rows where clean_text became empty after cleaning (e.g. only stopwords/emojis): {empty_clean_text}")

    if write_output:
        PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
        out_path = PROCESSED_DATA_DIR / OUTPUT_FILENAME
        cleaned.to_csv(out_path, index=False, encoding="utf-8")
        print(f"\nCleaned dataset written to {out_path}")

        report_path = PROCESSED_DATA_DIR / REPORT_FILENAME
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"Preprocessing report written to {report_path}")

    return cleaned


def main():
    parser = argparse.ArgumentParser(description="Clean a social-media CSV dataset.")
    parser.add_argument("path", nargs="?", default=None, help="Path to CSV (default: sample dataset)")
    args = parser.parse_args()
    run_pipeline(args.path)


if __name__ == "__main__":
    main()
