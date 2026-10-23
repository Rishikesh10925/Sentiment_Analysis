"""Traditional baselines and ablation studies on TweetEval sentiment.

Design choices
--------------
* Train on the official TweetEval train split, report the official test split.
* The validation split is used only for choosing the deployed linear model.
* The main view keeps social-media surface form (URLs/users as tokens,
  punctuation, negation). Aggressive stopword cleaning is an ablation.
* Every number is computed from the data; no hard-coded scores.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.naive_bayes import ComplementNB, MultinomialNB
from sklearn.pipeline import FeatureUnion
from sklearn.svm import LinearSVC

from research.config import (
    CURATED_POSTS_PATH,
    LABELS,
    RESEARCH_MODELS_DIR,
    RESEARCH_RESULTS_DIR,
    SEED,
)
from research.metrics import (
    bootstrap_ci,
    classification_report,
    error_examples,
    expected_calibration_error,
    mcnemar_test,
    save_json,
)
from research.text import apply_view

PREDICTIONS_DIR = RESEARCH_RESULTS_DIR / "predictions"


@dataclass
class FittedModel:
    name: str
    vectorizer: object
    model: object
    train_seconds: float
    config: dict = field(default_factory=dict)

    def predict(self, texts):
        return self.model.predict(self.vectorizer.transform(texts))

    def predict_proba(self, texts):
        X = self.vectorizer.transform(texts)
        if hasattr(self.model, "predict_proba"):
            return self.model.predict_proba(X)
        return None


def _word_vectorizer(ngram=(1, 2), max_features=100_000) -> TfidfVectorizer:
    return TfidfVectorizer(
        ngram_range=ngram,
        max_features=max_features,
        min_df=2,
        sublinear_tf=True,
        strip_accents="unicode",
    )


def _char_vectorizer() -> TfidfVectorizer:
    return TfidfVectorizer(
        analyzer="char_wb", ngram_range=(3, 5), max_features=50_000, min_df=3,
        sublinear_tf=True,
    )


def _build(name: str, view: str, union: bool = False):
    if name == "majority":
        return None, DummyClassifier(strategy="most_frequent")
    if name == "tfidf_logreg":
        return _word_vectorizer(), LogisticRegression(max_iter=2000, C=4.0, class_weight="balanced", random_state=SEED)
    if name == "tfidf_logreg_unigram":
        return _word_vectorizer(ngram=(1, 1)), LogisticRegression(max_iter=2000, C=4.0, class_weight="balanced", random_state=SEED)
    if name == "tfidf_logreg_nocw":
        return _word_vectorizer(), LogisticRegression(max_iter=2000, C=4.0, random_state=SEED)
    if name in {"tfidf_multinomial_nb", "tfidf_complement_nb"}:
        cls = MultinomialNB(alpha=0.3) if name.endswith("multinomial_nb") else ComplementNB(alpha=0.3)
        return _word_vectorizer(), cls
    if name == "tfidf_linear_svc":
        return _word_vectorizer(), LinearSVC(C=0.5, class_weight="balanced", random_state=SEED)
    if name == "tfidf_word_char_logreg":
        vectorizer = FeatureUnion([("word", _word_vectorizer()), ("char", _char_vectorizer())])
        return vectorizer, LogisticRegression(max_iter=2000, C=4.0, class_weight="balanced", random_state=SEED)
    if name == "tfidf_logreg_clean":
        return _word_vectorizer(), LogisticRegression(max_iter=2000, C=4.0, class_weight="balanced", random_state=SEED)
    raise ValueError(name)


def fit_model(name: str, train_texts, y_train, view: str = "raw", union: bool = False) -> FittedModel:
    vectorizer, model = _build(name, view, union=union)
    start = time.perf_counter()
    if vectorizer is None:
        model.fit(np.zeros((len(train_texts), 1)), y_train)
        vectorizer = TfidfVectorizer().fit(["noop"])
    else:
        X = vectorizer.fit_transform(train_texts)
        model.fit(X, y_train)
    elapsed = time.perf_counter() - start
    return FittedModel(name=name, vectorizer=vectorizer, model=model, train_seconds=elapsed,
                       config={"view": view, "vectorizer": type(vectorizer).__name__})


def evaluate(fitted: FittedModel, texts, y_true, store_predictions: bool = False) -> dict:
    start = time.perf_counter()
    preds = fitted.predict(texts)
    inference_seconds = time.perf_counter() - start
    probs = fitted.predict_proba(texts)
    report = classification_report(y_true, preds)
    report["bootstrap_macro_f1"] = bootstrap_ci(y_true, preds, metric="macro_f1")
    if probs is not None:
        report["calibration"] = expected_calibration_error(y_true, probs)
    report["latency_ms_per_1k"] = round(inference_seconds / max(len(texts), 1) * 1000 * 1000, 2)
    report["train_seconds"] = round(fitted.train_seconds, 2)
    if store_predictions:
        PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)
        payload = pd.DataFrame({
            "text": list(texts),
            "gold": list(y_true),
            "predicted": list(preds),
        })
        if probs is not None:
            for i, label in enumerate(LABELS):
                payload[f"prob_{label.lower()}"] = probs[:, i]
        payload.to_parquet(PREDICTIONS_DIR / f"{fitted.name}_test.parquet", index=False)
    return report


def top_coefficients(fitted: FittedModel, top_n: int = 20) -> dict:
    model = fitted.model
    if not hasattr(model, "coef_"):
        return {}
    feature_names = np.asarray(fitted.vectorizer.get_feature_names_out())
    out = {}
    for i, label in enumerate(model.classes_):
        weights = model.coef_[i]
        order = np.argsort(weights)
        out[str(label)] = {
            "positive": [{"token": str(feature_names[j]), "weight": round(float(weights[j]), 4)}
                         for j in order[::-1][:top_n]],
            "negative": [{"token": str(feature_names[j]), "weight": round(float(weights[j]), 4)}
                         for j in order[:top_n]],
        }
    return out


def domain_shift_eval(fitted: FittedModel, sample_size: int = 20_000) -> dict:
    """Evaluate the TweetEval model on real Sentiment140 + Reddit data.

    Sentiment140 has no neutral class. We report coverage (share of
    predictions that are Positive/Negative), accuracy on covered rows, and
    the neutral prediction rate, rather than hiding abstentions.
    """
    if not CURATED_POSTS_PATH.exists():
        return {}
    df = pd.read_parquet(CURATED_POSTS_PATH)
    results = {}
    for platform in ("X/Twitter", "Reddit"):
        subset = df[df["platform"] == platform]
        if subset.empty:
            continue
        subset = subset.sample(min(sample_size, len(subset)), random_state=SEED)
        texts = apply_view(subset["text"], "raw")
        gold = subset["gold_sentiment"].values
        preds = fitted.predict(texts)
        # Sentiment140/GoEmotions gold labels include no neutral for the
        # Twitter corpus, so binary metrics are computed on rows where the
        # model committed to a polarity and the gold label is polar.
        covered = np.isin(preds, ["Positive", "Negative"]) & np.isin(gold, ["Positive", "Negative"])
        results[platform] = {
            "n": int(len(subset)),
            "neutral_prediction_rate": round(float((preds == "Neutral").mean()), 4),
            "coverage_binary": round(float(covered.mean()), 4),
            "binary_accuracy_on_covered": round(float((preds[covered] == gold[covered]).mean()), 4) if covered.any() else None,
            "binary_macro_f1_on_covered": round(float(f1_score(
                gold[covered], preds[covered], average="macro", labels=["Negative", "Positive"]
            )), 4) if covered.any() else None,
            "binary_gold_n": int(covered.sum()),
            "gold_distribution": {str(k): int(v) for k, v in subset["gold_sentiment"].value_counts().items()},
        }
    return results


def run_baselines(save: bool = True) -> dict:
    from research.data import load_tweet_eval

    splits = load_tweet_eval()
    train = splits["train"]
    test = splits["test"]
    X_train = apply_view(train["text"], "raw")
    X_test = apply_view(test["text"], "raw")
    y_train, y_test = train["label"].values, test["label"].values

    model_names = [
        "majority", "tfidf_logreg", "tfidf_multinomial_nb",
        "tfidf_complement_nb", "tfidf_linear_svc", "tfidf_word_char_logreg",
    ]
    results = {}
    fitted_models = {}
    for name in model_names:
        print(f"Training {name}...")
        fitted = fit_model(name, X_train, y_train, view="raw")
        fitted_models[name] = fitted
        results[name] = evaluate(fitted, X_test, y_test, store_predictions=name in {"tfidf_logreg", "tfidf_linear_svc"})
        print(f"  macro-F1={results[name]['macro_f1']}  acc={results[name]['accuracy']}")

    # Ablations around the main linear model.
    ablations = []
    ablation_specs = [
        ("aggressive_cleaning", "tfidf_logreg_clean", "clean", "raw (minimal normalisation)", "aggressive stopword/punctuation cleaning"),
        ("unigram_only", "tfidf_logreg_unigram", "raw", "word 1-2 grams", "word 1 grams"),
        ("no_class_weighting", "tfidf_logreg_nocw", "raw", "class_weight=balanced", "class_weight=none"),
    ]
    X_train_clean = apply_view(train["text"], "clean")
    X_test_clean = apply_view(test["text"], "clean")
    for key, name, view, baseline_label, variant_label in ablation_specs:
        print(f"Ablation {key}...")
        train_texts = X_train_clean if view == "clean" else X_train
        test_texts = X_test_clean if view == "clean" else X_test
        fitted = fit_model(name, train_texts, y_train, view=view)
        metrics = classification_report(y_test, fitted.predict(test_texts))
        ablations.append({
            "name": key,
            "baseline": baseline_label,
            "variant": variant_label,
            "baseline_macro_f1": results["tfidf_logreg"]["macro_f1"],
            "variant_macro_f1": metrics["macro_f1"],
            "delta_macro_f1": round(metrics["macro_f1"] - results["tfidf_logreg"]["macro_f1"], 4),
            "accuracy": metrics["accuracy"],
        })

    # Learning curve (fraction of training data, same test set).
    results["ablations"] = ablations
    if save:
        learning_curve = []
        for frac in (0.1, 0.25, 0.5, 1.0):
            n = max(100, int(len(X_train) * frac))
            sampled = train.sample(n=min(n, len(train)), random_state=SEED)
            fitted = fit_model("tfidf_logreg", apply_view(sampled["text"], "raw"), sampled["label"].values)
            preds = fitted.predict(X_test)
            learning_curve.append({
                "train_rows": int(len(sampled)),
                "fraction": frac,
                "macro_f1": round(float(f1_score(y_test, preds, labels=LABELS, average="macro", zero_division=0)), 4),
                "accuracy": round(float((preds == y_test).mean()), 4),
            })
        results["learning_curve"] = learning_curve
    else:
        results["learning_curve"] = []

    main = fitted_models["tfidf_logreg"]
    results["deployed_linear_model"] = "tfidf_logreg"
    results["top_coefficients"] = top_coefficients(main)
    results["error_examples"] = error_examples(
        X_test.values, y_test, main.predict(X_test),
        confidences=main.predict_proba(X_test).max(axis=1),
    )
    results["domain_shift"] = domain_shift_eval(main)
    results["dataset"] = {
        "name": "TweetEval sentiment",
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "labels": LABELS,
        "train_distribution": {str(k): int(v) for k, v in train["label"].value_counts().items()},
        "test_distribution": {str(k): int(v) for k, v in test["label"].value_counts().items()},
    }
    results["environment"] = {
        "seed": SEED,
        "python": __import__("sys").version.split()[0],
        "sklearn": __import__("sklearn").__version__,
        "pandas": pd.__version__,
        "numpy": np.__version__,
    }

    if save:
        RESEARCH_MODELS_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(main.model, RESEARCH_MODELS_DIR / "tfidf_logreg.joblib")
        joblib.dump(main.vectorizer, RESEARCH_MODELS_DIR / "tfidf_vectorizer.joblib")
        save_json(RESEARCH_RESULTS_DIR / "baselines.json", results)
        # Paired predictions support McNemar tests against the transformer.
        save_json(RESEARCH_RESULTS_DIR / "baselines_summary.json", {
            name: {k: v for k, v in metrics.items() if k in {"accuracy", "macro_f1", "weighted_f1", "n", "train_seconds"}}
            for name, metrics in results.items() if isinstance(metrics, dict) and "macro_f1" in metrics
        })
        with open(RESEARCH_MODELS_DIR / "labels.json", "w", encoding="utf-8") as handle:
            json.dump(LABELS, handle)
        print(f"Saved research artifacts to {RESEARCH_RESULTS_DIR} and {RESEARCH_MODELS_DIR}")
    return results


if __name__ == "__main__":
    run_baselines()
