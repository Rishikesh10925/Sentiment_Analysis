"""Measured faithfulness of the serving model's explanations.

Two questions are tested on held-out TweetEval rows:

1. **Deletion faithfulness** - does removing the tokens with the largest
   positive attributions reduce the predicted-class probability more than
   removing the same number of random tokens?
2. **LIME agreement** - how often does an independent local surrogate
   (LIME) surface the same words as the exact linear attribution?

The exact attribution is the linear SHAP value of a TF-IDF feature:
``tfidf_value * coefficient``. It is exact for this model, not sampled.

Run:
    python -m research.explainability
"""

from __future__ import annotations

import json
import random
import re
import time

import joblib
import numpy as np
import pandas as pd

from research.config import (
    LABELS,
    RESEARCH_MODELS_DIR,
    RESEARCH_RESULTS_DIR,
    SEED,
)
from research.data import load_tweet_eval
from research.metrics import save_json
from research.text import normalise

MODEL_PATH = RESEARCH_MODELS_DIR / "tfidf_logreg.joblib"
VECTORIZER_PATH = RESEARCH_MODELS_DIR / "tfidf_vectorizer.joblib"
SAMPLE_SIZE = 150
LIME_SAMPLE_SIZE = 60
TOP_K = 3


def _load():
    model = joblib.load(MODEL_PATH)
    vectorizer = joblib.load(VECTORIZER_PATH)
    return model, vectorizer


def _contributions(model, vectorizer, text: str, predicted: str) -> dict[str, float]:
    X = vectorizer.transform([normalise(text)])
    class_idx = int(np.where(model.classes_ == predicted)[0][0])
    coefficients = model.coef_[class_idx]
    features = vectorizer.get_feature_names_out()
    row = X.tocoo()
    contributions: dict[str, float] = {}
    for col, value in zip(row.col, row.data):
        token = str(features[col])
        weight = float(value * coefficients[col])
        contributions[token] = contributions.get(token, 0.0) + weight
        if " " in token:
            for part in token.split():
                contributions[part] = contributions.get(part, 0.0) + weight / len(token.split())
    return contributions


def _remove_tokens(text: str, tokens: list[str]) -> str:
    result = text
    for token in tokens:
        if not token:
            continue
        result = re.sub(rf"(?<!\w){re.escape(token)}(?!\w)", " ", result, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", result).strip()


def _probability(model, vectorizer, text: str, label: str) -> float:
    X = vectorizer.transform([normalise(text)])
    classes = list(model.classes_)
    return float(model.predict_proba(X)[0, classes.index(label)])


def _lime_overlap(model, vectorizer, text: str, predicted: str, explainer) -> float:
    classes = list(model.classes_)
    class_idx = classes.index(predicted)

    def predict_proba(texts):
        return model.predict_proba(vectorizer.transform([normalise(t) for t in texts]))

    explanation = explainer.explain_instance(
        normalise(text), predict_proba, num_features=8, labels=[class_idx],
    )
    lime_tokens = {word for word, weight in explanation.as_list(label=class_idx) if weight > 0}
    shap_tokens = {
        token for token, weight in sorted(
            _contributions(model, vectorizer, text, predicted).items(),
            key=lambda item: item[1], reverse=True,
        )[:5] if weight > 0
    }
    if not lime_tokens or not shap_tokens:
        return 0.0
    return len(lime_tokens & shap_tokens) / len(lime_tokens | shap_tokens)


def run_explainability() -> dict:
    from lime.lime_text import LimeTextExplainer

    random.seed(SEED)
    np.random.seed(SEED)
    model, vectorizer = _load()
    test = load_tweet_eval()["test"]
    sample = test.sample(min(SAMPLE_SIZE, len(test)), random_state=SEED).reset_index(drop=True)
    start = time.perf_counter()

    top_drops, random_drops, examples = [], [], []
    for row in sample.itertuples(index=False):
        text = normalise(row.text)
        predicted = str(model.predict(vectorizer.transform([text]))[0])
        base = _probability(model, vectorizer, text, predicted)
        contributions = _contributions(model, vectorizer, text, predicted)
        top_tokens = [
            token for token, weight in sorted(contributions.items(), key=lambda item: item[1], reverse=True)
            if weight > 0 and " " not in token
        ][:TOP_K]
        if not top_tokens:
            continue
        top_text = _remove_tokens(text, top_tokens)
        top_prob = _probability(model, vectorizer, top_text, predicted) if top_text else 0.0

        words = [token for token in re.findall(r"[A-Za-z']+", text) if token.lower() not in {t.lower() for t in top_tokens}]
        random_tokens = random.sample(words, min(TOP_K, len(words))) if words else []
        random_text = _remove_tokens(text, random_tokens)
        random_prob = _probability(model, vectorizer, random_text, predicted) if random_text else 0.0

        top_drops.append(base - top_prob)
        random_drops.append(base - random_prob)
        if len(examples) < 8:
            examples.append({
                "text": row.text,
                "predicted": predicted,
                "probability": round(base, 4),
                "top_tokens": top_tokens,
                "probability_after_top_deletion": round(top_prob, 4),
                "probability_after_random_deletion": round(random_prob, 4),
            })

    explainer = LimeTextExplainer(class_names=LABELS)
    lime_sample = sample.head(min(LIME_SAMPLE_SIZE, len(sample)))
    overlaps = []
    for row in lime_sample.itertuples(index=False):
        predicted = str(model.predict(vectorizer.transform([normalise(row.text)]))[0])
        overlaps.append(_lime_overlap(model, vectorizer, row.text, predicted, explainer))

    report = {
        "available": True,
        "method": "exact linear SHAP (TF-IDF value x class coefficient)",
        "n_examples": len(top_drops),
        "top_k": TOP_K,
        "deletion_faithfulness": {
            "mean_probability_drop_top_tokens": round(float(np.mean(top_drops)), 4),
            "mean_probability_drop_random_tokens": round(float(np.mean(random_drops)), 4),
            "faithfulness_gap": round(float(np.mean(top_drops) - np.mean(random_drops)), 4),
            "share_top_beats_random": round(float(np.mean(np.array(top_drops) > np.array(random_drops))), 4),
        },
        "lime_agreement": {
            "n_examples": len(overlaps),
            "mean_top5_jaccard": round(float(np.mean(overlaps)), 4),
            "share_with_any_overlap": round(float(np.mean(np.array(overlaps) > 0)), 4),
        },
        "examples": examples,
        "runtime_seconds": round(time.perf_counter() - start, 2),
        "limitations": [
            "Deletion changes the TF-IDF normalisation as well as the token, so the measured drop is not a pure causal effect.",
            "LIME is itself an approximation and uses random perturbations; agreement is descriptive.",
            "The sample is 150 held-out rows, so the intervals around these means are not negligible.",
            "Attributions are model behaviour, not evidence about the author's intent or real-world impact.",
        ],
    }
    save_json(RESEARCH_RESULTS_DIR / "explainability.json", report)
    print(json.dumps({k: report[k] for k in ("n_examples", "deletion_faithfulness", "lime_agreement")}, indent=2))
    return report


if __name__ == "__main__":
    run_explainability()
