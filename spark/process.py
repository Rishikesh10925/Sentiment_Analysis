"""
Stage 5: PySpark processing.

This is the project's real Spark job. It genuinely uses Spark for:

    CSV ingestion, cleaning (regex + MLlib tokenizer/stopword removal),
    deduplication, sentiment/platform/topic/date aggregation, hashtag
    frequency, keyword frequency, and negative-content analysis.

Sentiment labels themselves come from the model trained in Stage 4
(ml/train.py + ml/predict.py) — training a scikit-learn model and running
it row-by-row would require a Python UDF, which this project's dev
environment cannot execute (see the Stage 5 section of README.md for why).
Instead, this job independently ingests and cleans the RAW dataset in
Spark (proving Spark does real work, not just reading pre-cleaned data),
then joins in the already-computed predictions by `post_id` — the same
"Spark does ETL/aggregation, an external model provides batch-scored
predictions" pattern real big-data systems use for non-Spark-native models.

Run:
    python -m ml.predict data/sample/social_media_sample.csv --output data/processed/predicted_social_media_sample.csv
    python -m spark.process
"""

import json

from pyspark.sql import functions as F

from ingestion.config import PROCESSED_DATA_DIR, SAMPLE_DATA_PATH
from spark.aggregate import (
    date_trend,
    hashtag_frequency,
    keyword_frequency,
    negative_topic_breakdown,
    overall_negative_percentage,
    platform_summary,
    sentiment_summary,
    top_negative_posts,
    topic_summary,
)
from spark.clean import spark_clean_pipeline
from spark.session import get_spark_session

PREDICTIONS_PATH = PROCESSED_DATA_DIR / "predicted_social_media_sample.csv"
OUTPUT_DIR = PROCESSED_DATA_DIR / "spark_aggregates"


def run_spark_pipeline(raw_path=None, predictions_path=None, write_output: bool = True) -> dict:
    raw_path = raw_path or SAMPLE_DATA_PATH
    predictions_path = predictions_path or PREDICTIONS_PATH

    spark = get_spark_session()
    try:
        raw_df = spark.read.csv(str(raw_path), header=True, inferSchema=True)
        rows_ingested = raw_df.count()

        cleaned = spark_clean_pipeline(raw_df, text_col="text")
        cleaned = cleaned.withColumn("original_text", F.col("text"))
        cleaned = cleaned.filter(
            F.col("text").isNotNull() & (F.trim(F.col("text")) != "")
        )
        rows_after_missing_text_drop = cleaned.count()

        deduped = cleaned.dropDuplicates(["post_id"])
        rows_after_dedup = deduped.count()

        predictions = spark.read.csv(str(predictions_path), header=True, inferSchema=True)
        predictions = predictions.select("post_id", "predicted_sentiment", "prediction_confidence")

        joined = deduped.join(predictions, on="post_id", how="left")
        rows_matched = joined.filter(F.col("predicted_sentiment").isNotNull()).count()
        joined = joined.filter(F.col("predicted_sentiment").isNotNull())

        joined.cache()

        results = {
            "sentiment_summary": sentiment_summary(joined),
            "platform_summary": platform_summary(joined),
            "topic_summary": topic_summary(joined),
            "daily_trend": date_trend(joined, "day"),
            "weekly_trend": date_trend(joined, "week"),
            "monthly_trend": date_trend(joined, "month"),
            "hashtag_frequency": hashtag_frequency(joined, top_n=30),
            "keyword_frequency": keyword_frequency(joined, top_n=30),
            "negative_topics": negative_topic_breakdown(joined),
            "negative_posts": top_negative_posts(joined, limit=20),
        }
        negative_pct = overall_negative_percentage(joined)

        report = {
            "rows_ingested_raw": rows_ingested,
            "rows_after_missing_text_drop": rows_after_missing_text_drop,
            "rows_after_dedup": rows_after_dedup,
            "rows_matched_with_predictions": rows_matched,
            "overall_negative_percentage": negative_pct,
        }

        print("Spark pipeline row counts:")
        for k, v in report.items():
            print(f"  {k}: {v}")
        print()
        for name, pdf in results.items():
            print(f"{name}: {len(pdf)} rows")

        if write_output:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            for name, pdf in results.items():
                out_path = OUTPUT_DIR / f"{name}.csv"
                pdf.to_csv(out_path, index=False, encoding="utf-8")
            with open(OUTPUT_DIR / "spark_processing_report.json", "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)
            print(f"\nAggregates written to {OUTPUT_DIR}")

        return {"report": report, "results": results}
    finally:
        spark.stop()


if __name__ == "__main__":
    run_spark_pipeline()
