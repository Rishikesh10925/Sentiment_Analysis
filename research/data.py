"""Loaders for the real, public datasets used by this project.

Datasets
--------
TweetEval sentiment (Cardiff NLP)  - 45k human-labelled tweets, 3 classes.
Sentiment140 (Go et al., 2009)     - 1.6M tweets, binary distant labels,
                                     with timestamps and usernames.
GoEmotions (Demszky et al., 2020)  - 58k Reddit comments, 27 emotions.
SemEval-2014 Task 4                - restaurant/laptop aspect-term polarity.

The loaders are pure functions over files in ``data/real`` so that every
experiment is reproducible from the downloader alone.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from research.config import (
    ABSA_DIR,
    GO_EMOTIONS_PATH,
    LABELS,
    NEGATIVE_EMOTIONS,
    NEUTRAL_EMOTIONS,
    POSITIVE_EMOTIONS,
    SENTIMENT140_PATH,
    TWEET_EVAL_DIR,
    TWEET_EVAL_ID_TO_LABEL,
)

# --- Topic taxonomy -------------------------------------------------------
# Heuristic, documented in docs/RESEARCH.md. It is intentionally simple and
# auditable; it is not presented as a trained topic model.

_TOPIC_RULES = [
    ("Pricing", r"\b(price|pricing|cost|costly|expensive|cheap|refund|billing|charged|charge|subscription|fee|fees|discount|coupon)\b"),
    ("Support", r"\b(support|customer service|help desk|agent|ticket|complaint|representative|response|reply|contact)\b"),
    ("Delivery", r"\b(delivery|delivery|shipping|shipment|shipped|order|arrived|arrive|late|package|courier|tracking)\b"),
    ("Performance", r"\b(battery|speed|fast|slow|lag|laggy|crash|crashes|bug|bugs|glitch|performance|update|firmware)\b"),
    ("UX", r"\b(design|interface|ui|ux|usability|feature|features|easy to use|difficult|confusing|screen|layout)\b"),
    ("Product", r"\b(product|quality|purchase|bought|buy|brand|item|device|phone|laptop|headphones|camera)\b"),
    ("Politics", r"\b(election|president|government|policy|politics|political|vote|voting|congress|senate|parliament)\b"),
    ("Sports", r"\b(football|basketball|baseball|soccer|cricket|tennis|hockey|nba|nfl|match|team|coach|player|tournament)\b"),
    ("Entertainment", r"\b(movie|film|music|song|album|concert|show|series|actor|actress|celebrity|netflix|tv)\b"),
    ("Gaming", r"\b(gaming|gamer|xbox|playstation|nintendo|steam|console|video game|videogame)\b"),
    ("Technology", r"\b(technology|tech|software|apple|google|microsoft|android|iphone|computer|internet|app|ai)\b"),
    ("Health", r"\b(health|doctor|hospital|medicine|medical|sick|pain|covid|vaccine|mental health)\b"),
    ("Education", r"\b(school|college|university|exam|student|class|teacher|homework|degree)\b"),
    ("Finance", r"\b(stocks|stock market|invest|investing|finance|financial|economy|inflation|bank|money)\b"),
    ("Relationships", r"\b(relationship|dating|girlfriend|boyfriend|wife|husband|marriage|family|friend|friends)\b"),
    ("Science", r"\b(science|research|study|space|physics|chemistry|biology|climate|nasa)\b"),
]
_TOPIC_PATTERNS = [(name, re.compile(pattern, re.IGNORECASE)) for name, pattern in _TOPIC_RULES]

_SUBREDDIT_TOPICS = {
    "gaming": "Gaming", "games": "Gaming", "pcgaming": "Gaming",
    "nrl": "Sports", "nba": "Sports", "soccer": "Sports", "hockey": "Sports",
    "football": "Sports", "baseball": "Sports", "formula1": "Sports",
    "cricket": "Sports", "tennis": "Sports", "cfb": "Sports",
    "technology": "Technology", "programming": "Technology", "linux": "Technology",
    "python": "Technology", "android": "Technology", "apple": "Technology",
    "buildapc": "Technology", "pcmasterrace": "Technology",
    "politics": "Politics", "worldnews": "Politics", "news": "Politics",
    "conservative": "Politics", "liberal": "Politics", "unpopularopinion": "Politics",
    "movies": "Entertainment", "television": "Entertainment", "music": "Entertainment",
    "books": "Entertainment", "anime": "Entertainment", "gifs": "Entertainment",
    "relationships": "Relationships", "relationship_advice": "Relationships",
    "dating_advice": "Relationships", "amitheasshole": "Relationships",
    "science": "Science", "space": "Science", "physics": "Science",
    "personalfinance": "Finance", "finance": "Finance", "investing": "Finance",
    "askscience": "Science", "todayilearned": "General",
}


def infer_topic(text: str, subreddit: str | None = None) -> str:
    """Rule-based topic tag. Transparent, deterministic, no leakage."""
    if isinstance(subreddit, str) and subreddit.lower() in _SUBREDDIT_TOPICS:
        return _SUBREDDIT_TOPICS[subreddit.lower()]
    if not isinstance(text, str):
        return "General"
    for name, pattern in _TOPIC_PATTERNS:
        if pattern.search(text):
            return name
    return "General"


def load_tweet_eval() -> dict[str, pd.DataFrame]:
    """TweetEval sentiment splits with string labels."""
    splits = {}
    for split in ("train", "validation", "test"):
        df = pd.read_parquet(TWEET_EVAL_DIR / f"{split}.parquet")
        # The HuggingFace parquet uses 'label'; some exports use 'sentiment'.
        label_col = "label" if "label" in df.columns else "sentiment"
        df = df.rename(columns={label_col: "label_id"})
        df["label"] = df["label_id"].map(TWEET_EVAL_ID_TO_LABEL)
        splits[split] = df[["text", "label", "label_id"]].dropna().reset_index(drop=True)
    return splits


def _parse_twitter_dates(values: pd.Series) -> pd.Series:
    # Example: "Mon Apr 06 22:19:45 PDT 2009". pandas' %Z does not know PDT,
    # so parse the unambiguous parts and ignore the timezone abbreviation
    # (Sentiment140 timestamps are US/Pacific; we keep them as naive UTC-ish
    # wall time and document that no cross-source timezone normalization is
    # claimed).
    parsed = pd.to_datetime(
        values.str.slice(0, 20) + " " + values.str.slice(-4),
        format="%a %b %d %H:%M:%S %Y",
        errors="coerce",
    )
    return parsed


def load_sentiment140(use_cache: bool = True) -> pd.DataFrame:
    """Load the full Sentiment140 CSV (1.6M rows) with normalised columns."""
    cache = SENTIMENT140_PATH.with_suffix(".parquet")
    if use_cache and cache.exists():
        return pd.read_parquet(cache)
    df = pd.read_csv(SENTIMENT140_PATH)
    df = df.rename(columns={
        "Label": "label_id", "ID": "post_id", "Date": "date",
        "Flag": "query", "User": "author", "Text": "text",
    })
    df["label"] = df["label_id"].map({0: "Negative", 4: "Positive"})
    df["date"] = _parse_twitter_dates(df["date"])
    df["post_id"] = df["post_id"].astype(str)
    df = df.dropna(subset=["text", "date", "label"])
    if use_cache:
        df.to_parquet(cache, index=False)
    return df


def load_go_emotions() -> pd.DataFrame:
    """Aggregate GoEmotions' per-rater rows into one row per comment."""
    raw = pd.read_parquet(GO_EMOTIONS_PATH)
    emotion_cols = [c for c in raw.columns if c in POSITIVE_EMOTIONS | NEGATIVE_EMOTIONS | NEUTRAL_EMOTIONS]
    grouped = raw.groupby("id", as_index=False).agg(
        {**{c: "sum" for c in emotion_cols},
         "text": "first", "author": "first", "subreddit": "first",
         "created_utc": "first", "example_very_unclear": "max"}
    )
    grouped = grouped[~grouped["example_very_unclear"].astype(bool)].copy()
    grouped = grouped[grouped["text"].astype(str).str.strip() != ""]
    grouped = grouped[~grouped["text"].astype(str).str.lower().isin({"[deleted]", "[removed]"})]

    counts = grouped[emotion_cols].to_numpy()
    top_idx = counts.argmax(axis=1)
    top_count = counts.max(axis=1)
    # Drop comments with no positive signal or a tie between top emotions.
    tied = (counts == top_count[:, None]).sum(axis=1) > 1
    grouped = grouped[(top_count > 0) & (~tied)].copy()
    counts = grouped[emotion_cols].to_numpy()
    top_idx = counts.argmax(axis=1)
    top_emotion = [emotion_cols[i] for i in top_idx]
    grouped["emotion"] = top_emotion

    def polarity(emotion: str) -> str:
        if emotion in POSITIVE_EMOTIONS:
            return "Positive"
        if emotion in NEGATIVE_EMOTIONS:
            return "Negative"
        return "Neutral"

    grouped["label"] = grouped["emotion"].map(polarity)
    grouped["date"] = pd.to_datetime(grouped["created_utc"], unit="s", utc=True).dt.tz_localize(None)
    grouped = grouped.rename(columns={"id": "post_id"})
    return grouped[["post_id", "text", "author", "subreddit", "date", "emotion", "label"]].reset_index(drop=True)


def load_absa() -> dict[str, pd.DataFrame]:
    """Parse the official SemEval-2014 Task 4 XML files.

    Returns one row per (sentence, aspect term) pair, which is the standard
    aspect-term polarity classification setup.
    """
    import xml.etree.ElementTree as ET

    files = {
        ("restaurants", "train"): "Restaurants_Train.xml",
        ("restaurants", "test"): "Restaurants_Test_Gold.xml",
        ("laptops", "train"): "Laptops_Train.xml",
        ("laptops", "test"): "Laptops_Test_Gold.xml",
    }
    polarity_map = {"negative": (-1, "Negative"), "neutral": (0, "Neutral"), "positive": (1, "Positive")}
    out = {}
    for (domain, split), filename in files.items():
        path = ABSA_DIR / filename
        root = ET.parse(path).getroot()
        rows = []
        for sentence in root.findall("sentence"):
            text = (sentence.findtext("text") or "").strip()
            if not text:
                continue
            for term in sentence.findall("./aspectTerms/aspectTerm"):
                aspect = (term.get("term") or "").strip()
                polarity = (term.get("polarity") or "").lower()
                if not aspect or polarity not in polarity_map:
                    continue
                polarity_id, polarity_label = polarity_map[polarity]
                rows.append({
                    "text": text,
                    "aspect": aspect,
                    "polarity": polarity_label,
                    "polarity_id": polarity_id,
                    "domain": domain,
                    "split": split,
                })
        out[f"{domain}_{split}"] = pd.DataFrame(rows)
    return out


def sentiment_distribution(df: pd.DataFrame, label_col: str = "label") -> dict:
    counts = df[label_col].value_counts().to_dict()
    total = int(len(df))
    return {
        label: {"count": int(counts.get(label, 0)),
                "percentage": round(counts.get(label, 0) / total * 100, 2) if total else 0.0}
        for label in LABELS
    }
