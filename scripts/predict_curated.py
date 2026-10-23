"""Batch-score the curated corpus with the deployed linear model.

Uses PyArrow batch iteration so 1.6M rows never have to fit in memory at
once. Output is a parquet file with predictions + class probabilities and
a small inference report (throughput, distribution, artifact hashes).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import joblib
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from research.config import CURATED_POSTS_PATH, CURATED_PREDICTIONS_PATH, RESEARCH_MODELS_DIR, RESEARCH_RESULTS_DIR
from research.text import normalise

BATCH_SIZE = 100_000


def predict_curated(input_path: Path = CURATED_POSTS_PATH,
                    output_path: Path = CURATED_PREDICTIONS_PATH,
                    batch_size: int = BATCH_SIZE) -> dict:
    model = joblib.load(RESEARCH_MODELS_DIR / "tfidf_logreg.joblib")
    vectorizer = joblib.load(RESEARCH_MODELS_DIR / "tfidf_vectorizer.joblib")
    classes = list(model.classes_)

    parquet_file = pq.ParquetFile(input_path)
    writer = None
    rows = 0
    distribution = {label: 0 for label in classes}
    start = time.perf_counter()

    for batch in parquet_file.iter_batches(batch_size=batch_size):
        df = batch.to_pandas()
        texts = df["text"].map(normalise)
        X = vectorizer.transform(texts)
        probs = model.predict_proba(X)
        pred_idx = probs.argmax(axis=1)
        out = pd.DataFrame({
            "post_id": df["post_id"],
            "platform": df["platform"],
            "author": df["author"],
            "date": df["date"],
            "topic": df["topic"],
            "hashtags": df["hashtags"],
            "original_text": df["text"],
            "clean_text": df["clean_text"],
            "gold_sentiment": df["gold_sentiment"],
            "predicted_sentiment": [classes[i] for i in pred_idx],
            "confidence": probs.max(axis=1).round(4),
        })
        for i, label in enumerate(classes):
            out[f"prob_{label.lower()}"] = probs[:, i].round(4)
            distribution[label] += int((pred_idx == i).sum())
        table = pa.Table.from_pandas(out, preserve_index=False)
        if writer is None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            writer = pq.ParquetWriter(output_path, table.schema)
        writer.write_table(table)
        rows += len(out)
        print(f"  scored {rows:,} rows ({rows / (time.perf_counter() - start):,.0f} rows/s)", flush=True)

    if writer:
        writer.close()
    elapsed = time.perf_counter() - start
    report = {
        "rows": int(rows),
        "seconds": round(elapsed, 2),
        "rows_per_second": round(rows / elapsed, 1),
        "distribution": distribution,
        "model": "tfidf_logreg_word12",
        "batch_size": batch_size,
        "output": str(output_path),
    }
    report_path = RESEARCH_RESULTS_DIR / "bulk_inference.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    predict_curated()
