"""Build the canonical, dashboard-ready dataset from real public corpora.

Output: ``data/curated/social_posts.parquet`` with the same 8 columns the
rest of the app already understands, plus ``gold_sentiment`` for research.

Provenance, row counts and checksums are written to
``data/curated/manifest.json``. The build is deterministic for a given
input: no random sampling by default, and the seed is recorded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform as _platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import ftfy
import pandas as pd

from ingestion.config import PROJECT_ROOT
from preprocessing.clean import clean_text, extract_hashtags
from research.config import (
    CURATED_DATA_DIR,
    CURATED_POSTS_PATH,
    GO_EMOTIONS_PATH,
    SEED,
    SENTIMENT140_PATH,
    TWEET_EVAL_DIR,
)
from research.data import (
    infer_topic,
    load_go_emotions,
    load_sentiment140,
    load_tweet_eval,
)


def _sha256(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _normalise(text: str) -> str:
    text = ftfy.fix_text(str(text))
    # Keep emoji and punctuation: the transformer consumes raw social text.
    return " ".join(text.replace("\x00", " ").split())


def _hashtags(text: str) -> str:
    tags = extract_hashtags(text)
    return " ".join(f"#{tag}" for tag in tags)


def _rows_from_frame(df: pd.DataFrame, platform: str, subreddit_col: str | None = None,
                     limit: int | None = None) -> pd.DataFrame:
    if limit is not None:
        df = df.head(limit)
    texts = df["text"].map(_normalise)
    subreddits = df[subreddit_col] if subreddit_col and subreddit_col in df else pd.Series([None] * len(df), index=df.index)
    out = pd.DataFrame({
        "platform": platform,
        "post_id": df["post_id"].astype(str),
        "author": df["author"].fillna("unknown").astype(str).str.slice(0, 100),
        "text": texts,
        "date": pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S"),
        "topic": [infer_topic(t, s) for t, s in zip(texts, subreddits)],
        "hashtags": texts.map(_hashtags),
        "gold_sentiment": df["label"].values,
    })
    out["clean_text"] = texts.map(clean_text)
    return out


def build_curated(max_tweets: int | None = None, include_reddit: bool = True) -> pd.DataFrame:
    print("Loading Sentiment140 (1.6M tweets)...")
    tweets = load_sentiment140()
    print(f"  {len(tweets):,} labelled tweets, {tweets['date'].min()} -> {tweets['date'].max()}")
    tweet_rows = _rows_from_frame(tweets, "X/Twitter", limit=max_tweets)

    frames = [tweet_rows]
    if include_reddit:
        print("Loading GoEmotions (Reddit)...")
        reddit = load_go_emotions()
        print(f"  {len(reddit):,} unique comments, {reddit['date'].min()} -> {reddit['date'].max()}")
        frames.append(_rows_from_frame(reddit, "Reddit", subreddit_col="subreddit"))

    df = pd.concat(frames, ignore_index=True)
    df = df[df["text"].astype(str).str.strip() != ""]
    df = df.drop_duplicates(subset=["platform", "post_id"], keep="first")
    df = df.sort_values(["date", "platform", "post_id"]).reset_index(drop=True)
    df.insert(0, "id", range(1, len(df) + 1))
    df = df[["id", "platform", "post_id", "author", "text", "date", "topic", "hashtags",
             "clean_text", "gold_sentiment"]]
    return df


def write_manifest(df: pd.DataFrame, out_path: Path, args) -> dict:
    try:
        output_label = str(Path(out_path).resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        output_label = str(out_path)
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": SEED,
        "python": sys.version.split()[0],
        "platform": _platform.platform(),
        "output": output_label,
        "rows": int(len(df)),
        "rows_by_platform": {str(k): int(v) for k, v in df["platform"].value_counts().items()},
        "rows_by_gold_sentiment": {str(k): int(v) for k, v in df["gold_sentiment"].value_counts(dropna=False).items()},
        "rows_by_topic": {str(k): int(v) for k, v in df["topic"].value_counts().items()},
        "date_range": {"min": str(df["date"].min()), "max": str(df["date"].max())},
        "columns": df.columns.tolist(),
        "sources": [
            {
                "name": "Sentiment140",
                "citation": "Go, Bhayani & Huang (2009), Twitter Sentiment Classification using Distant Supervision",
                "url": "https://huggingface.co/datasets/BrianLeung/sentiment140-csv",
                "local_file": str(SENTIMENT140_PATH.relative_to(PROJECT_ROOT)),
                "sha256": _sha256(SENTIMENT140_PATH),
                "usage": "Large-scale X/Twitter corpus; distant labels (binary).",
            },
            {
                "name": "GoEmotions (raw)",
                "citation": "Demszky et al. (2020), GoEmotions: A Dataset of Fine-Grained Emotions",
                "url": "https://huggingface.co/datasets/google-research-datasets/go_emotions",
                "local_file": str(GO_EMOTIONS_PATH.relative_to(PROJECT_ROOT)),
                "sha256": _sha256(GO_EMOTIONS_PATH),
                "usage": "Reddit comments; 27 emotions collapsed to 3-way polarity by majority rater label.",
            },
            {
                "name": "TweetEval sentiment",
                "citation": "Barbieri et al. (2020), TweetEval: Unified Benchmark and Comparative Evaluation for Tweet Classification",
                "url": "https://huggingface.co/datasets/cardiffnlp/tweet_eval",
                "local_dir": str(TWEET_EVAL_DIR.relative_to(PROJECT_ROOT)),
                "usage": "Held-out 3-class benchmark for model comparison (not loaded into the dashboard).",
            },
        ],
        "notes": [
            "Dates come from the source records; Sentiment140 is 2009-2010 and GoEmotions is 2019.",
            "Topic tags are rule-based (research/data.py) and documented in docs/RESEARCH.md.",
            "Gold labels are retained for evaluation only; the dashboard shows model predictions.",
            "No tweets are redistributed; the downloader fetches public research datasets.",
        ],
        "args": {key: (str(value) if isinstance(value, Path) else value) for key, value in vars(args).items()},
    }
    manifest_path = out_path.parent / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
    print(f"Manifest -> {manifest_path}")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the canonical real dataset.")
    parser.add_argument("--max-tweets", type=int, default=None, help="Limit X/Twitter rows (dev/testing).")
    parser.add_argument("--no-reddit", action="store_true", help="Exclude GoEmotions.")
    parser.add_argument("--output", type=Path, default=CURATED_POSTS_PATH)
    args = parser.parse_args()

    df = build_curated(max_tweets=args.max_tweets, include_reddit=not args.no_reddit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.output, index=False)
    print(f"Wrote {len(df):,} rows -> {args.output}")
    print(df["platform"].value_counts().to_string())
    print(df["gold_sentiment"].value_counts(dropna=False).to_string())
    write_manifest(df, args.output, args)


if __name__ == "__main__":
    main()
