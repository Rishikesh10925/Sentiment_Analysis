"""Aspect-term polarity classification on SemEval-2014 Task 4.

Input is the sentence plus the gold aspect term (the standard aspect-term
classification setting, not end-to-end term extraction). The model is a
word+character TF-IDF linear classifier; it is intentionally simple and
CPU-only so the result is reproducible without a GPU.

Run:
    python -m research.absa
"""

from __future__ import annotations

import time

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion

from research.config import LABELS, RESEARCH_MODELS_DIR, RESEARCH_RESULTS_DIR, SEED
from research.data import load_absa
from research.metrics import (
    bootstrap_ci,
    classification_report,
    expected_calibration_error,
    save_json,
)
from research.text import normalise

DOMAINS = ("restaurants", "laptops")
PREDICTIONS_DIR = RESEARCH_RESULTS_DIR / "predictions"
MODEL_PATH = RESEARCH_MODELS_DIR / "absa_tfidf_logreg.joblib"


def _input_text(text: str, aspect: str) -> str:
    # Repeating the aspect term gives the linear model a strong anchor while
    # keeping the sentence context that disambiguates polarity.
    return f"{normalise(text)} [ASPECT] {normalise(aspect)} [ASPECT] {normalise(aspect)}"


def _train_vectorizer() -> FeatureUnion:
    return FeatureUnion([
        ("word", TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True,
                                 max_features=80_000, strip_accents="unicode")),
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2,
                                 sublinear_tf=True, max_features=60_000)),
    ])


def _evaluate(y_true, preds, probs) -> dict:
    report = classification_report(y_true, preds, labels=LABELS)
    report["bootstrap_macro_f1"] = bootstrap_ci(y_true, preds, metric="macro_f1")
    if probs is not None:
        report["calibration"] = expected_calibration_error(y_true, probs, labels=LABELS)
    return report


def train_absa() -> dict:
    np.random.seed(SEED)
    splits = load_absa()
    train = pd.concat([splits[f"{domain}_train"].assign(domain=domain) for domain in DOMAINS],
                      ignore_index=True)
    test = pd.concat([splits[f"{domain}_test"].assign(domain=domain) for domain in DOMAINS],
                     ignore_index=True)
    train["model_text"] = [_input_text(t, a) for t, a in zip(train["text"], train["aspect"])]
    test["model_text"] = [_input_text(t, a) for t, a in zip(test["text"], test["aspect"])]

    vectorizer = _train_vectorizer()
    start = time.perf_counter()
    X_train = vectorizer.fit_transform(train["model_text"])
    model = LogisticRegression(
        max_iter=3000, C=4.0, class_weight="balanced", random_state=SEED, n_jobs=-1,
    )
    model.fit(X_train, train["polarity"])
    train_seconds = time.perf_counter() - start

    start = time.perf_counter()
    X_test = vectorizer.transform(test["model_text"])
    probs = model.predict_proba(X_test)
    preds = model.predict(X_test)
    inference_seconds = time.perf_counter() - start

    report = {
        "available": True,
        "task": "SemEval-2014 Task 4 aspect-term polarity classification",
        "input": "sentence + gold aspect term",
        "dataset": {
            "train_rows": int(len(train)),
            "test_rows": int(len(test)),
            "aspect_terms": int(train["aspect"].nunique()),
            "train_by_domain": train.groupby("domain").size().to_dict(),
            "test_by_domain": test.groupby("domain").size().to_dict(),
            "label_distribution": {
                split: frame["polarity"].value_counts().reindex(LABELS, fill_value=0).to_dict()
                for split, frame in (("train", train), ("test", test))
            },
        },
        "model": {
            "name": "tfidf_word_char_logreg",
            "features": "word 1-2 grams + char_wb 3-5 grams",
            "class_weight": "balanced",
        },
        "models": {},
        "train_seconds": round(train_seconds, 2),
        "inference_seconds": round(inference_seconds, 3),
        "latency_ms_per_1k": round(inference_seconds / max(len(test), 1) * 1000 * 1000, 2),
    }

    # Majority baseline, measured on the same test rows.
    majority = train["polarity"].value_counts().idxmax()
    majority_preds = [majority] * len(test)
    report["models"]["majority"] = _evaluate(test["polarity"].tolist(), majority_preds, None)
    report["models"]["tfidf_word_char_logreg"] = _evaluate(
        test["polarity"].tolist(), preds.tolist(), probs,
    )

    combined = report["models"]["tfidf_word_char_logreg"]
    report["macro_f1"] = combined["macro_f1"]
    report["accuracy"] = combined["accuracy"]

    for domain in DOMAINS:
        mask = (test["domain"] == domain).to_numpy()
        domain_metrics = _evaluate(
            test.loc[mask, "polarity"].tolist(),
            preds[mask].tolist(),
            probs[mask],
        )
        report[domain] = domain_metrics
        report.setdefault("by_domain", {})[domain] = domain_metrics

    # Cross-domain transfer: restaurants -> laptops and the reverse.
    report["cross_domain"] = {}
    for source, target in (("restaurants", "laptops"), ("laptops", "restaurants")):
        source_train = splits[f"{source}_train"]
        target_test = splits[f"{target}_test"]
        cross_vec = _train_vectorizer()
        X_source = cross_vec.fit_transform([
            _input_text(t, a) for t, a in zip(source_train["text"], source_train["aspect"])
        ])
        cross_model = LogisticRegression(
            max_iter=3000, C=4.0, class_weight="balanced", random_state=SEED,
        )
        cross_model.fit(X_source, source_train["polarity"])
        X_target = cross_vec.transform([
            _input_text(t, a) for t, a in zip(target_test["text"], target_test["aspect"])
        ])
        cross_preds = cross_model.predict(X_target)
        report["cross_domain"][f"{source}_to_{target}"] = classification_report(
            target_test["polarity"].tolist(), cross_preds.tolist(), labels=LABELS,
        )

    report["limitations"] = [
        "Aspect terms are provided at test time; this measures polarity classification, not extraction.",
        "SemEval-2014 is restaurant/laptop reviews, not social media; results do not transfer automatically.",
        "Neutral is a minority class and per-class recall is reported rather than hidden by macro-F1.",
        "A single train/test split is used; confidence intervals reflect test sampling, not training variance.",
    ]

    RESEARCH_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    RESEARCH_MODELS_DIR.mkdir(parents=True, exist_ok=True)
    PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"vectorizer": vectorizer, "model": model, "labels": LABELS}, MODEL_PATH)
    payload = pd.DataFrame({
        "text": test["text"].values,
        "aspect": test["aspect"].values,
        "domain": test["domain"].values,
        "gold": test["polarity"].values,
        "predicted": preds,
        "prob_negative": probs[:, list(model.classes_).index("Negative")],
        "prob_neutral": probs[:, list(model.classes_).index("Neutral")],
        "prob_positive": probs[:, list(model.classes_).index("Positive")],
    })
    payload.to_parquet(PREDICTIONS_DIR / "absa_test.parquet", index=False)
    save_json(RESEARCH_RESULTS_DIR / "absa.json", report)
    print(f"ABSA macro-F1: {report['macro_f1']} | accuracy: {report['accuracy']} | "
          f"test rows: {len(test):,}")
    return report


if __name__ == "__main__":
    train_absa()
