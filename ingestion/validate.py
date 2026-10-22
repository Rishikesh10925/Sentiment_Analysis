"""
Stage 2: Data ingestion + validation.

Loads a raw social-media CSV and checks it against the expected schema,
producing a validation report describing data-quality issues (missing
columns, missing values, duplicates, invalid platforms/dates). This stage
only inspects and reports — cleaning/fixing text happens in Stage 3.

Run:
    python -m ingestion.validate                       # validates the sample dataset
    python -m ingestion.validate path/to/other.csv      # validates a custom CSV
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from ingestion.config import (
    ALLOWED_PLATFORMS,
    DATE_FORMAT,
    PROCESSED_DATA_DIR,
    REQUIRED_COLUMNS,
    SAMPLE_DATA_PATH,
)


class ValidationError(Exception):
    """Raised when a CSV fails structural validation (missing/renamed columns)."""


def load_csv(path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    return pd.read_csv(path, encoding="utf-8")


def validate_schema(df: pd.DataFrame) -> list:
    """Returns a list of missing required columns (empty list = schema OK)."""
    return [col for col in REQUIRED_COLUMNS if col not in df.columns]


def _missing_count(series: pd.Series) -> int:
    """A value counts as missing if it's NaN or an empty/whitespace-only string."""
    is_na = series.isna()
    is_blank = series.fillna("").astype(str).str.strip() == ""
    return int((is_na | is_blank).sum())


def _is_valid_date(value) -> bool:
    if pd.isna(value):
        return False
    try:
        datetime.strptime(str(value), DATE_FORMAT)
        return True
    except ValueError:
        return False


def validate_data(df: pd.DataFrame, source_label: str = "in-memory") -> dict:
    """Runs data-quality checks and returns a JSON-serializable report.

    Raises ValidationError if required columns are missing — everything
    else (missing values, duplicates, invalid rows) is reported as counts,
    not treated as fatal, since the sample dataset intentionally contains
    this kind of messiness for later preprocessing stages to handle.
    """
    missing_cols = validate_schema(df)
    if missing_cols:
        raise ValidationError(f"Missing required columns: {missing_cols}")

    missing_values = {col: _missing_count(df[col]) for col in REQUIRED_COLUMNS}

    invalid_platform_mask = ~df["platform"].isin(ALLOWED_PLATFORMS)
    invalid_platform_values = sorted(
        df.loc[invalid_platform_mask, "platform"].dropna().unique().tolist()
    )

    invalid_date_count = int((~df["date"].apply(_is_valid_date)).sum())

    report = {
        "source": source_label,
        "total_rows": int(len(df)),
        "missing_values": missing_values,
        "duplicate_post_ids": int(df["post_id"].duplicated().sum()),
        "duplicate_full_rows": int(df.drop(columns=["id"]).duplicated().sum()),
        "invalid_platform_count": int(invalid_platform_mask.sum()),
        "invalid_platform_values": invalid_platform_values,
        "invalid_date_count": invalid_date_count,
        "platform_counts": {
            str(k): int(v) for k, v in df["platform"].value_counts(dropna=False).items()
        },
    }
    return report


def print_report(report: dict) -> None:
    print(f"Source: {report['source']}")
    print(f"Total rows: {report['total_rows']}")
    print("Missing values per column:")
    for col, count in report["missing_values"].items():
        print(f"  - {col}: {count}")
    print(f"Duplicate post_id rows: {report['duplicate_post_ids']}")
    print(f"Duplicate full rows: {report['duplicate_full_rows']}")
    print(f"Invalid platform rows: {report['invalid_platform_count']} {report['invalid_platform_values']}")
    print(f"Invalid/unparseable dates: {report['invalid_date_count']}")
    print("Rows per platform:")
    for platform, count in report["platform_counts"].items():
        print(f"  - {platform}: {count}")


def run_validation(path=None, write_report: bool = True) -> dict:
    path = Path(path) if path else SAMPLE_DATA_PATH
    df = load_csv(path)
    report = validate_data(df, source_label=str(path))
    print_report(report)

    if write_report:
        PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
        out_path = PROCESSED_DATA_DIR / "validation_report.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\nValidation report written to {out_path}")

    return report


def main():
    parser = argparse.ArgumentParser(description="Validate a social-media CSV dataset.")
    parser.add_argument("path", nargs="?", default=None, help="Path to CSV (default: sample dataset)")
    args = parser.parse_args()
    run_validation(args.path)


if __name__ == "__main__":
    main()
