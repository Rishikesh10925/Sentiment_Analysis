"""Inference + explanation helpers shared by the API and scripts.

The default deployed model is the word 1-2 gram TF-IDF logistic regression
trained in ``research/baselines.py``. It is small (a few MB), CPU-fast and
exactly explainable: for a linear model the SHAP values of the TF-IDF
features are ``tfidf_value * coefficient`` (LinearExplainer's exact
attribution), so no sampling approximation is needed at request time.

A fine-tuned DistilBERT checkpoint is available in ``models/research`` and
is reported on the research page, but the serving path deliberately defaults
to the linear model so the API stays deployable on a 512 MB instance.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np

from research.config import LABELS, RESEARCH_MODELS_DIR, RESEARCH_RESULTS_DIR
from research.text import normalise

MODEL_PATH = RESEARCH_MODELS_DIR / "tfidf_logreg.joblib"
VECTORIZER_PATH = RESEARCH_MODELS_DIR / "tfidf_vectorizer.joblib"
BASELINES_PATH = RESEARCH_RESULTS_DIR / "baselines.json"
TRANSFORMER_DIR = RESEARCH_MODELS_DIR / "distilbert_tweet_eval"

MODEL_NAME = "tfidf_logreg_word12"
MODEL_DISPLAY_NAME = "TF-IDF (1-2 grams) + Logistic Regression"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()[:12]


class ModelNotAvailableError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _load():
    if not MODEL_PATH.exists() or not VECTORIZER_PATH.exists():
        raise ModelNotAvailableError(
            f"Trained linear model missing. Run `python -m research.baselines` first ({MODEL_PATH})."
        )
    model = joblib.load(MODEL_PATH)
    vectorizer = joblib.load(VECTORIZER_PATH)
    return model, vectorizer


def model_info() -> dict:
    info = {
        "name": MODEL_NAME,
        "display_name": MODEL_DISPLAY_NAME,
        "labels": LABELS,
        "available": MODEL_PATH.exists(),
        "explanation": "exact linear SHAP (tfidf_value x class coefficient)",
    }
    if MODEL_PATH.exists():
        info["artifact_sha256_12"] = _sha256(MODEL_PATH)
        info["size_kb"] = round(MODEL_PATH.stat().st_size / 1024, 1)
    if BASELINES_PATH.exists():
        metrics = json.loads(BASELINES_PATH.read_text(encoding="utf-8"))
        selected = metrics.get("tfidf_logreg", {})
        info["test_metrics"] = {
            key: selected.get(key) for key in
            ("accuracy", "macro_f1", "weighted_f1", "bootstrap_macro_f1", "calibration")
            if key in selected
        }
        info["training"] = metrics.get("dataset", {})
    info["transformer_checkpoint"] = {
        "path": str(TRANSFORMER_DIR),
        "available": (TRANSFORMER_DIR / "config.json").exists(),
        "fine_tuned": (TRANSFORMER_DIR / "config.json").exists(),
        "serving_default": False,
    }
    return info


def predict(texts, with_probabilities: bool = True) -> list[dict]:
    model, vectorizer = _load()
    if isinstance(texts, str):
        texts = [texts]
    normalised = [normalise(text) for text in texts]
    X = vectorizer.transform(normalised)
    preds = model.predict(X)
    probs = model.predict_proba(X) if with_probabilities and hasattr(model, "predict_proba") else None
    out = []
    for i, pred in enumerate(preds):
        row = {"sentiment": str(pred)}
        if probs is not None:
            row["confidence"] = round(float(probs[i].max()), 4)
            row["probabilities"] = {label: round(float(probs[i][j]), 4) for j, label in enumerate(model.classes_)}
        out.append(row)
    return out


def explain(text: str, top_k: int = 12) -> dict:
    """Exact per-token linear attribution for the predicted class.

    Multi-word n-grams are kept as features and also folded into their
    unigrams, so the UI can highlight words in the original sentence.
    """
    model, vectorizer = _load()
    text = normalise(text)
    X = vectorizer.transform([text])
    pred = str(model.predict(X)[0])
    class_idx = int(np.where(model.classes_ == pred)[0][0])
    coefficients = model.coef_[class_idx]
    feature_names = vectorizer.get_feature_names_out()

    row = X.tocoo()
    contributions: dict[str, float] = {}
    for col, value in zip(row.col, row.data):
        token = str(feature_names[col])
        contribution = float(value * coefficients[col])
        contributions[token] = contributions.get(token, 0.0) + contribution
        # Fold n-grams into their unigrams for a readable token view.
        if " " in token:
            share = contribution / len(token.split())
            for part in token.split():
                contributions[part] = contributions.get(part, 0.0) + share

    ranked = sorted(contributions.items(), key=lambda item: abs(item[1]), reverse=True)[:top_k]
    probabilities = None
    if hasattr(model, "predict_proba"):
        probs = model.predict_proba(X)[0]
        probabilities = {label: round(float(probs[j]), 4) for j, label in enumerate(model.classes_)}

    return {
        "text": text,
        "sentiment": pred,
        "probabilities": probabilities,
        "model": MODEL_NAME,
        "method": "exact linear SHAP (feature value x coefficient)",
        "tokens": [
            {"token": token, "weight": round(weight, 4),
             "direction": "supports" if weight >= 0 else "opposes"}
            for token, weight in ranked
        ],
        "base_value_note": "Contributions are relative to the model's linear decision function.",
    }


def transformer_available() -> bool:
    return (TRANSFORMER_DIR / "config.json").exists()
