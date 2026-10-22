"""
Stage 10: full pipeline orchestration.

Runs every stage in order, so the whole system can be reproduced with
one command instead of remembering the right sequence of module
invocations. Each step is the same function the individual stage's own
CLI calls — this script doesn't reimplement any logic, it just sequences
what's already tested independently.

    1. Data validation      (ingestion.validate)
    2. Text preprocessing   (preprocessing.pipeline)
    3. ML prediction        (ml.predict, using the model saved by ml.train)
    4. Spark processing     (spark.process)
    5. Analytics + alerts   (analytics.build_summary)
    6. Load into PostgreSQL (backend.db.load_data)

`run_full_pipeline(csv_path)` is also called directly by
`backend.main`'s upload endpoint, so uploading a CSV through the
dashboard runs this exact same sequence, not a separate reimplementation.

Run:
    python scripts/run_pipeline.py                  # processes the sample dataset
    python scripts/run_pipeline.py path/to/file.csv  # processes a specific CSV
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion.config import SAMPLE_DATA_PATH


def step(name, fn, log):
    log(f"\n{'=' * 60}\n{name}\n{'=' * 60}")
    start = time.time()
    result = fn()
    log(f"-- {name} done in {time.time() - start:.1f}s")
    return result


def run_full_pipeline(csv_path=None, load_db: bool = True, log=print) -> dict:
    """Runs every stage against csv_path (default: the sample dataset).

    Returns a dict with each stage's result/report. Raises if validation,
    preprocessing, ML prediction, or Spark processing fail (those are
    fatal - there's nothing useful to show without them). PostgreSQL
    loading failures are caught and reported instead of raised, since the
    rest of the pipeline's output is still valid/useful without a DB.
    """
    csv_path = Path(csv_path) if csv_path else SAMPLE_DATA_PATH
    results = {}

    from ingestion.validate import run_validation
    results["validation"] = step(
        "Stage 2: Data validation", lambda: run_validation(csv_path), log
    )

    from preprocessing.pipeline import run_pipeline as run_preprocessing
    step("Stage 3: Text preprocessing", lambda: run_preprocessing(csv_path), log)

    from ml.train import MODEL_PATH, VECTORIZER_PATH
    if not MODEL_PATH.exists() or not VECTORIZER_PATH.exists():
        from ml.train import run_training
        results["training"] = step(
            "Stage 4: ML training (no saved model found)", run_training, log
        )
    else:
        log("\nStage 4: ML training skipped (models/sentiment_model.joblib already exists)")

    from ml.predict import run_predict
    from ingestion.config import PROCESSED_DATA_DIR
    cleaned_path = PROCESSED_DATA_DIR / "cleaned_social_media_sample.csv"
    predictions_path = PROCESSED_DATA_DIR / "predicted_social_media_sample.csv"
    # Predict on Stage 3's cleaned+deduped output (has original_text/clean_text),
    # not the raw CSV - the raw file still has duplicates/missing text/no
    # original_text column, which Stage 7's loader depends on.
    step(
        "Stage 4: ML prediction",
        lambda: run_predict(cleaned_path, output_path=predictions_path),
        log,
    )

    from spark.process import run_spark_pipeline
    results["spark"] = step(
        "Stage 5: PySpark processing",
        lambda: run_spark_pipeline(raw_path=csv_path, predictions_path=predictions_path),
        log,
    )

    from analytics.build_summary import build_summary
    results["analytics"] = step("Stage 6: Analytics + alerts", build_summary, log)

    if load_db:
        from backend.db.load_data import run_load
        try:
            results["db"] = step("Stage 7: Load into PostgreSQL", run_load, log)
        except Exception as exc:
            log(f"\nStage 7 skipped/failed (no reachable PostgreSQL?): {exc}")
            results["db_error"] = str(exc)

    return results


def main():
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    run_full_pipeline(csv_path)
    print("\nPipeline complete. Start the API with:")
    print("  uvicorn backend.main:app --reload --port 8000")


if __name__ == "__main__":
    sys.exit(main())
