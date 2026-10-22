"""
Stage 4: ML training + evaluation.

Trains and compares two sentiment classifiers on the synthetic labeled
training file (data/sample/social_media_sample_labeled.csv):

    TF-IDF + Logistic Regression
    TF-IDF + Multinomial Naive Bayes

Evaluates both with accuracy, precision, recall, F1 (weighted average
across the 3 classes) and a confusion matrix — all actually computed from
the held-out test split, never invented — then saves the
better-performing model and its TF-IDF vectorizer to models/, along with
a JSON report of both models' measured metrics.

Run:
    python -m ml.train
    python -m ml.train path/to/other_labeled.csv
"""

import argparse
import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB

from ingestion.config import PROJECT_ROOT, SENTIMENT_LABELS
from preprocessing.clean import clean_text

LABELED_DATA_PATH = PROJECT_ROOT / "data" / "sample" / "social_media_sample_labeled.csv"
MODELS_DIR = PROJECT_ROOT / "models"
MODEL_PATH = MODELS_DIR / "sentiment_model.joblib"
VECTORIZER_PATH = MODELS_DIR / "tfidf_vectorizer.joblib"
METRICS_REPORT_PATH = MODELS_DIR / "metrics_report.json"

RANDOM_STATE = 42


def load_labeled_data(path=None) -> pd.DataFrame:
    path = Path(path) if path else LABELED_DATA_PATH
    df = pd.read_csv(path)
    df["clean_text"] = df["text"].apply(clean_text)
    df = df[df["clean_text"].str.strip() != ""].reset_index(drop=True)
    return df


def evaluate_model(model, X_test, y_test) -> dict:
    preds = model.predict(X_test)
    accuracy = accuracy_score(y_test, preds)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_test, preds, average="weighted", zero_division=0
    )
    cm = confusion_matrix(y_test, preds, labels=SENTIMENT_LABELS)
    return {
        "accuracy": round(float(accuracy), 4),
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1": round(float(f1), 4),
        "confusion_matrix": cm.tolist(),
        "confusion_matrix_labels": SENTIMENT_LABELS,
    }


def run_training(path=None, save: bool = True) -> dict:
    df = load_labeled_data(path)

    X_train_text, X_test_text, y_train, y_test = train_test_split(
        df["clean_text"], df["sentiment"],
        test_size=0.2, random_state=RANDOM_STATE, stratify=df["sentiment"],
    )

    vectorizer = TfidfVectorizer(max_features=5000, ngram_range=(1, 2), min_df=2)
    X_train = vectorizer.fit_transform(X_train_text)
    X_test = vectorizer.transform(X_test_text)

    candidates = {
        "logistic_regression": LogisticRegression(max_iter=1000, random_state=RANDOM_STATE),
        "multinomial_naive_bayes": MultinomialNB(),
    }

    trained_models = {}
    metrics = {}
    for name, model in candidates.items():
        model.fit(X_train, y_train)
        trained_models[name] = model
        metrics[name] = evaluate_model(model, X_test, y_test)

    selected_name = max(metrics, key=lambda n: (metrics[n]["f1"], metrics[n]["accuracy"]))
    selected_model = trained_models[selected_name]

    print(f"Training rows: {len(X_train_text)}  |  Test rows: {len(X_test_text)}")
    print()
    for name, m in metrics.items():
        print(f"{name}:")
        print(f"  accuracy:  {m['accuracy']}")
        print(f"  precision: {m['precision']}")
        print(f"  recall:    {m['recall']}")
        print(f"  f1:        {m['f1']}")
        print(f"  confusion matrix (rows=true, cols=predicted, labels={SENTIMENT_LABELS}):")
        for row in m["confusion_matrix"]:
            print(f"    {row}")
        print()
    print(f"Selected model: {selected_name} (highest weighted F1)")

    report = {
        "training_rows": len(X_train_text),
        "test_rows": len(X_test_text),
        "selected_model": selected_name,
        "models": metrics,
    }

    if save:
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(selected_model, MODEL_PATH)
        joblib.dump(vectorizer, VECTORIZER_PATH)
        with open(METRICS_REPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\nSaved model -> {MODEL_PATH}")
        print(f"Saved vectorizer -> {VECTORIZER_PATH}")
        print(f"Saved metrics report -> {METRICS_REPORT_PATH}")

    return report


def main():
    parser = argparse.ArgumentParser(description="Train and compare sentiment classifiers.")
    parser.add_argument("path", nargs="?", default=None, help="Path to labeled CSV (default: sample labeled dataset)")
    args = parser.parse_args()
    run_training(args.path)


if __name__ == "__main__":
    main()
