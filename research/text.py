"""Text normalisation shared by baselines and transformer experiments.

Two views are deliberately kept:

``normalise``   minimal social-media normalisation (URLs/most mentions
                replaced, whitespace collapsed, repeated characters
                shortened). Punctuation, negation and emoji are preserved.
``clean_text``  the original aggressive bag-of-words cleaner (stopwords,
                punctuation and hashtags removed), kept for ablation.
"""

from __future__ import annotations

import ftfy
import pandas as pd

from preprocessing.clean import clean_text

URL = r"https?://\S+|www\.\S+"
MENTION = r"@\w+"
REPEATED = r"(.)\1{2,}"


def normalise(text: str) -> str:
    if not isinstance(text, str):
        return ""
    import re
    text = ftfy.fix_text(text)
    text = re.sub(URL, " <url> ", text)
    text = re.sub(MENTION, " <user> ", text)
    text = re.sub(REPEATED, r"\1\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def apply_view(series: pd.Series, view: str) -> pd.Series:
    if view == "clean":
        return series.map(clean_text)
    if view == "raw":
        return series.map(normalise)
    raise ValueError(f"Unknown text view: {view}")
