"""Paths, labels and constants shared by the research code."""

from pathlib import Path

from ingestion.config import PROJECT_ROOT

SEED = 42

REAL_DATA_DIR = PROJECT_ROOT / "data" / "real"
CURATED_DATA_DIR = PROJECT_ROOT / "data" / "curated"
RESEARCH_RESULTS_DIR = PROJECT_ROOT / "results" / "research"
RESEARCH_MODELS_DIR = PROJECT_ROOT / "models" / "research"

CURATED_POSTS_PATH = CURATED_DATA_DIR / "social_posts.parquet"
CURATED_PREDICTIONS_PATH = CURATED_DATA_DIR / "social_posts_predictions.parquet"

TWEET_EVAL_DIR = REAL_DATA_DIR / "tweet_eval"
SENTIMENT140_PATH = REAL_DATA_DIR / "sentiment140" / "Sentiment140.csv"
GO_EMOTIONS_PATH = REAL_DATA_DIR / "go_emotions" / "raw_train.parquet"
ABSA_DIR = REAL_DATA_DIR / "absa"

LABELS = ["Negative", "Neutral", "Positive"]
LABEL_TO_ID = {label: idx for idx, label in enumerate(LABELS)}

TWEET_EVAL_ID_TO_LABEL = {0: "Negative", 1: "Neutral", 2: "Positive"}

# Sentiment140 is binary: 0 = negative, 4 = positive.
SENTIMENT140_LABEL = {0: "Negative", 4: "Positive"}

# GoEmotions' 27 fine-grained emotions collapsed into a 3-way polarity.
POSITIVE_EMOTIONS = {
    "admiration", "amusement", "approval", "caring", "desire", "excitement",
    "gratitude", "joy", "love", "optimism", "pride", "relief",
}
NEGATIVE_EMOTIONS = {
    "anger", "annoyance", "disappointment", "disapproval", "disgust",
    "embarrassment", "fear", "grief", "nervousness", "remorse", "sadness",
}
NEUTRAL_EMOTIONS = {"neutral", "confusion", "curiosity", "realization", "surprise"}


def ensure_research_dirs() -> None:
    for path in (CURATED_DATA_DIR, RESEARCH_RESULTS_DIR, RESEARCH_MODELS_DIR):
        path.mkdir(parents=True, exist_ok=True)
