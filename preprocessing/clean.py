"""
Pure text-cleaning functions used across the project (Pandas here in
Stage 3, and again as PySpark UDFs in Stage 5). Kept dependency-light and
framework-agnostic on purpose: every function takes/returns plain
strings/lists so it can run identically inside a pandas `.apply` or a
Spark UDF.
"""

import re

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

STOPWORDS = frozenset(ENGLISH_STOP_WORDS)

URL_PATTERN = re.compile(r"http\S+|www\.\S+")
MENTION_PATTERN = re.compile(r"@\w+")
HASHTAG_TOKEN_PATTERN = re.compile(r"#(\w+)")
NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9\s]")
WHITESPACE_PATTERN = re.compile(r"\s+")
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001FAFF"  # symbols & pictographs, supplemental symbols
    "\U00002600-\U000027BF"  # misc symbols, dingbats (incl. hearts, warning sign)
    "\U0001F1E6-\U0001F1FF"  # regional indicators (flag emoji)
    "\U0001F900-\U0001F9FF"  # supplemental symbols & pictographs
    "\U0000FE00-\U0000FE0F"  # variation selectors (emoji presentation)
    "]+",
    flags=re.UNICODE,
)


def extract_hashtags(text: str) -> list:
    """Extracts hashtag words (without '#') from raw text, lowercased, in order of first appearance."""
    if not isinstance(text, str) or not text:
        return []
    found = [tag.lower() for tag in HASHTAG_TOKEN_PATTERN.findall(text)]
    seen = []
    for tag in found:
        if tag not in seen:
            seen.append(tag)
    return seen


def clean_text(text: str) -> str:
    """Lowercases and strips URLs, mentions, hashtags, emojis, punctuation,
    stopwords, and extra whitespace. Returns "" for empty/non-string input."""
    if not isinstance(text, str) or not text.strip():
        return ""

    t = text.lower()
    t = URL_PATTERN.sub(" ", t)
    t = MENTION_PATTERN.sub(" ", t)
    t = HASHTAG_TOKEN_PATTERN.sub(" ", t)  # hashtags are extracted separately, not part of clean_text
    t = EMOJI_PATTERN.sub(" ", t)
    t = NON_ALNUM_PATTERN.sub(" ", t)
    t = WHITESPACE_PATTERN.sub(" ", t).strip()

    tokens = [w for w in t.split() if w not in STOPWORDS and len(w) > 1]
    return " ".join(tokens)
