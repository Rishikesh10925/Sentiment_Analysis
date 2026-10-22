"""Shared constants for the pipeline (ingestion, preprocessing, ML, Spark, backend)."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_COLUMNS = ["id", "platform", "post_id", "author", "text", "date", "topic", "hashtags"]

ALLOWED_PLATFORMS = {
    "Instagram", "Facebook", "YouTube", "Reddit", "X/Twitter", "WhatsApp Export",
}

SENTIMENT_LABELS = ["Positive", "Neutral", "Negative"]

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

DEFAULT_NEGATIVE_ALERT_THRESHOLD = 40  # percent

SAMPLE_DATA_PATH = PROJECT_ROOT / "data" / "sample" / "social_media_sample.csv"
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
