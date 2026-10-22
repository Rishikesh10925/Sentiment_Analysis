"""
Stage 4: ML prediction.

Loads the saved TF-IDF vectorizer + sentiment model (produced by
ml/train.py) and applies them to new data:

- unlabeled data (e.g. data/processed/cleaned_social_media_sample.csv)
  -> adds a `predicted_sentiment` column
- labeled data (has a ground-truth column, e.g. the sample labeled file)
  -> also evaluates predictions against that column

Run:
    python -m ml.predict data/processed/cleaned_social_media_sample.csv
    python -m ml.predict data/sample/social_media_sample_labeled.csv --label-column sentiment --text-column text
"""

import argparse

import joblib
import pandas as pd
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

from ml.train import MODEL_PATH, VECTORIZER_PATH
from preprocessing.clean import clean_text


class ModelNotTrainedError(Exception):
    """Raised when predict is called before a model has been trained/saved."""


def load_artifacts():
    if not MODEL_PATH.exists() or not VECTORIZER_PATH.exists():
        raise ModelNotTrainedError(
            f"No saved model found at {MODEL_PATH}. Run `python -m ml.train` first."
        )
    model = joblib.load(MODEL_PATH)
    vectorizer = joblib.load(VECTORIZER_PATH)
    return model, vectorizer


def predict_dataframe(df: pd.DataFrame, model, vectorizer, text_column: str = "clean_text") -> pd.DataFrame:
    if text_column not in df.columns:
        raise ValueError(f"Column '{text_column}' not found in input data")

    texts = df[text_column].fillna("")
    X = vectorizer.transform(texts)
    preds = model.predict(X)

    result = df.copy()
    result["predicted_sentiment"] = preds
    if hasattr(model, "predict_proba"):
        result["prediction_confidence"] = model.predict_proba(X).max(axis=1).round(4)
    return result


def run_predict(input_path, output_path=None, text_column="clean_text", label_column=None) -> pd.DataFrame:
    df = pd.read_csv(input_path)

    if text_column not in df.columns and "text" in df.columns:
        df[text_column] = df["text"].apply(clean_text)

    model, vectorizer = load_artifacts()
    result = predict_dataframe(df, model, vectorizer, text_column=text_column)

    print(f"Predicted sentiment for {len(result)} rows.")
    print(result["predicted_sentiment"].value_counts().to_string())

    if label_column and label_column in df.columns:
        accuracy = accuracy_score(df[label_column], result["predicted_sentiment"])
        precision, recall, f1, _ = precision_recall_fscore_support(
            df[label_column], result["predicted_sentiment"], average="weighted", zero_division=0
        )
        print(f"\nEvaluation against '{label_column}':")
        print(f"  accuracy:  {round(float(accuracy), 4)}")
        print(f"  precision: {round(float(precision), 4)}")
        print(f"  recall:    {round(float(recall), 4)}")
        print(f"  f1:        {round(float(f1), 4)}")

    if output_path:
        result.to_csv(output_path, index=False)
        print(f"\nPredictions written to {output_path}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Predict sentiment using the saved model.")
    parser.add_argument("path", help="Path to input CSV")
    parser.add_argument("--output", default=None, help="Path to write predictions CSV")
    parser.add_argument("--text-column", default="clean_text", help="Column containing text to classify")
    parser.add_argument("--label-column", default=None, help="If set and present, evaluate predictions against this column")
    args = parser.parse_args()
    run_predict(args.path, args.output, args.text_column, args.label_column)


if __name__ == "__main__":
    main()
