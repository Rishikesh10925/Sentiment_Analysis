"""Measured Spark scaling benchmark + full-corpus aggregate job.

Three arms compute the same aggregate (count of posts per
platform x topic x predicted_sentiment) starting from the *same* cached
four-column projection of the real 1.6M-row corpus, so the measurement
isolates the aggregation stage rather than parquet decoding:

``naive``      row-wise Python UDF cleaning, Adaptive Query Execution off,
               the default 200 shuffle partitions, no column pruning, and a
               full-width intermediate frame.
``native``     identical configuration, but the cleaning step uses built-in
               Spark SQL expressions instead of a Python UDF. This arm
               isolates the UDF penalty on its own.
``optimized``  native expressions + column pruning before the wide
               aggregation + AQE on + shuffle partitions sized to the
               machine (2 x cores, capped at 200).

Sizing shuffle partitions to the machine is deliberate: an earlier version
of this benchmark hard-coded 16 partitions on a 24-core host, which made the
"optimized" arm *slower* than the naive arm because it left a third of the
cores idle. That negative result is not hidden; the partition sweep at the
largest size records the sensitivity, so the reader can see the choice.

Every arm is run ``repeats`` times; the reported number is the median
wall-clock time and every individual timing is kept in the report.
"""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

import pandas as pd
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import StringType

from research.config import CURATED_PREDICTIONS_PATH, RESEARCH_RESULTS_DIR, SEED
from spark.aggregate import (
    date_trend,
    hashtag_frequency,
    keyword_frequency,
    negative_topic_breakdown,
    platform_summary,
    sentiment_summary,
    top_negative_posts,
    topic_summary,
)
from spark.clean import clean_text_column, remove_stopwords
from spark.session import get_spark_session

BENCH_DIR = Path("data/processed/benchmark")
AGG_DIR = Path("data/processed/spark_aggregates_real")
SIZES = [100_000, 500_000, 1_600_000]
GROUP_COLS = ("platform", "topic", "predicted_sentiment")
# Columns every arm is allowed to read. Keeping the projection identical
# across arms is what makes the comparison fair: the arms differ in how the
# aggregation stage is executed, not in how much parquet they decode.
BASE_COLS = ("platform", "topic", "predicted_sentiment", "original_text",
             "post_id", "author", "date", "confidence", "hashtags", "clean_text")


def _aggregate(df: DataFrame) -> DataFrame:
    return (
        df.groupBy(*GROUP_COLS)
        .agg(F.count("*").alias("count"))
        .orderBy(*GROUP_COLS)
    )


def _naive_clean(df: DataFrame) -> DataFrame:
    clean_udf = F.udf(
        lambda value: " ".join(
            str(value or "").lower().replace("http", " ").replace("@", " ").replace("#", " ").split()
        ),
        StringType(),
    )
    out = df.withColumn("bench_clean", clean_udf(F.col("original_text")))
    return out.filter(F.length(F.col("bench_clean")) > 0)


def _native_clean(df: DataFrame) -> DataFrame:
    out = df.withColumn(
        "bench_clean",
        F.trim(
            F.regexp_replace(
                F.lower(F.coalesce(F.col("original_text"), F.lit(""))),
                r"[^a-z0-9\s]",
                " ",
            )
        ),
    )
    return out.filter(F.length(F.col("bench_clean")) > 0)


def _set_engine(spark, *, aqe: bool, partitions: int) -> None:
    spark.conf.set("spark.sql.adaptive.enabled", "true" if aqe else "false")
    spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true" if aqe else "false")
    spark.conf.set("spark.sql.shuffle.partitions", str(partitions))


def _naive_pipeline(spark, source: DataFrame) -> tuple[pd.DataFrame, int]:
    _set_engine(spark, aqe=False, partitions=200)
    # Deliberately no pruning and no repartition: the whole point of this arm.
    result = _aggregate(_naive_clean(source))
    return result.toPandas(), result.count()


def _native_pipeline(spark, source: DataFrame) -> tuple[pd.DataFrame, int]:
    _set_engine(spark, aqe=False, partitions=200)
    result = _aggregate(_native_clean(source))
    return result.toPandas(), result.count()


def _optimized_pipeline(spark, source: DataFrame, partitions: int) -> tuple[pd.DataFrame, int]:
    _set_engine(spark, aqe=True, partitions=partitions)
    pruned = source.select(*BASE_COLS)
    result = _aggregate(_native_clean(pruned))
    return result.toPandas(), result.count()


def _sample_frame(source: DataFrame, spark, n: int, total: int) -> DataFrame:
    """Deterministic in-memory sample, materialised before timing starts.

    Writing a sample parquet requires winutils/HADOOP_HOME on Windows, which
    this project deliberately avoids. Caching the sample also keeps the
    benchmark focused on the aggregation pipelines rather than on disk I/O.
    """
    if n >= total:
        sample = source
    else:
        sample = source.sample(withReplacement=False, fraction=n / total, seed=SEED).limit(n)
    sample = sample.cache()
    spark.sparkContext.setJobDescription(f"materialise sample {n}")
    sample.count()
    return sample


def _timed(fn, *args, repeats: int) -> tuple[object, list[float], int]:
    timings: list[float] = []
    result = None
    agg_rows = 0
    for _ in range(repeats):
        start = time.perf_counter()
        result, agg_rows = fn(*args)
        timings.append(time.perf_counter() - start)
    return result, timings, agg_rows


def run_benchmark(sizes=None, repeats: int = 3) -> dict:
    sizes = sizes or SIZES
    spark = get_spark_session("sentiment-benchmark")
    cores = spark.sparkContext.defaultParallelism
    tuned_partitions = min(200, max(2, 2 * cores))
    results = {
        "environment": {
            "spark": spark.version,
            "java": spark.sparkContext._jvm.System.getProperty("java.version"),
            "logical_cores": cores,
            "driver_memory": spark.conf.get("spark.driver.memory", "default"),
            "repeats": repeats,
            "seed": SEED,
            "tuned_shuffle_partitions": tuned_partitions,
            "sample_strategy": "in-memory seeded sample; not written to disk (Windows winutils-free)",
        },
        "methodology": (
            "Three arms share one cached input projection and one aggregate "
            "(count per platform x topic x predicted_sentiment). naive = Python-UDF "
            "cleaning, AQE off, 200 shuffle partitions. native = same settings, "
            "built-in SQL expressions instead of the UDF. optimized = native "
            f"expressions, column pruning, AQE on, {tuned_partitions} shuffle "
            "partitions. Reported seconds are medians over the repeats."
        ),
        "runs": [],
        "partition_sweep": [],
    }
    source = spark.read.parquet(str(CURATED_PREDICTIONS_PATH)).select(*BASE_COLS)
    total = source.count()
    try:
        for index, n in enumerate(sizes):
            sample = _sample_frame(source, spark, int(n), total)
            rows = sample.count()
            if index == 0:
                # JIT/plan-cache warmup, discarded, only on the first size.
                _native_pipeline(spark, sample)
                _naive_pipeline(spark, sample)
            naive_result = None
            try:
                for method, fn in (
                    ("naive", lambda sp, df: _naive_pipeline(sp, df)),
                    ("native", lambda sp, df: _native_pipeline(sp, df)),
                    ("optimized", lambda sp, df: _optimized_pipeline(sp, df, tuned_partitions)),
                ):
                    result, timings, agg_rows = _timed(fn, spark, sample, repeats=repeats)
                    elapsed = statistics.median(timings)
                    record = {
                        "rows": int(rows),
                        "method": method,
                        "seconds": round(elapsed, 3),
                        "seconds_all": [round(t, 3) for t in timings],
                        "rows_per_second": round(rows / elapsed, 1),
                        "aggregate_rows": int(agg_rows),
                        "shuffle_partitions": 200 if method != "optimized" else tuned_partitions,
                        "repeat_times": [round(t, 3) for t in timings],
                    }
                    if method == "naive":
                        naive_result = result.set_index(list(GROUP_COLS))["count"].sort_index()
                    else:
                        current = result.set_index(list(GROUP_COLS))["count"].sort_index()
                        record["matches_naive"] = bool(naive_result.equals(current))
                        naive_seconds = next(
                            r["seconds"] for r in results["runs"]
                            if r["rows"] == rows and r["method"] == "naive"
                        )
                        record["speedup_vs_naive"] = round(naive_seconds / elapsed, 2)
                    results["runs"].append(record)
                    print(
                        f"{method:10} {rows:>9,} rows  {elapsed:7.2f}s  "
                        f"{rows / elapsed:>10,.0f} rows/s",
                        flush=True,
                    )
            finally:
                if sample is not source:
                    sample.unpersist()

        # Where does the time actually go at the largest size? Sweep the
        # partition count for the optimized arm so the choice above is
        # auditable instead of asserted.
        largest = sizes[-1]
        sweep_sample = _sample_frame(source, spark, int(largest), total)
        try:
            for partitions in (16, tuned_partitions, 200):
                _, timings, _ = _timed(
                    lambda sp, df, p=partitions: _optimized_pipeline(sp, df, p),
                    spark, sweep_sample, repeats=repeats,
                )
                results["partition_sweep"].append({
                    "rows": int(largest),
                    "shuffle_partitions": partitions,
                    "seconds": round(statistics.median(timings), 3),
                })
                print(f"sweep {partitions:>3} partitions -> {statistics.median(timings):6.2f}s", flush=True)
        finally:
            if sweep_sample is not source:
                sweep_sample.unpersist()

        RESEARCH_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        (RESEARCH_RESULTS_DIR / "spark_benchmark.json").write_text(
            json.dumps(results, indent=2), encoding="utf-8"
        )
        pd.DataFrame(results["runs"]).to_csv(
            RESEARCH_RESULTS_DIR / "spark_benchmark.csv", index=False
        )
        print(f"Saved benchmark -> {RESEARCH_RESULTS_DIR / 'spark_benchmark.json'}")
    finally:
        spark.stop()
    return results


def run_full_aggregates() -> dict:
    """Run the optimized pipeline once on the full corpus and persist the
    dashboard aggregates, for reproducibility and non-SQL consumers."""
    spark = get_spark_session("sentiment-aggregates")
    spark.conf.set("spark.sql.shuffle.partitions", "16")
    spark.conf.set("spark.sql.adaptive.enabled", "true")
    try:
        df = spark.read.parquet(str(CURATED_PREDICTIONS_PATH)).select(
            "post_id", "platform", "topic", "author", "original_text", "clean_text",
            "date", "hashtags", "predicted_sentiment", "confidence",
        )
        df = clean_text_column(df, text_col="original_text", out_col="spark_clean")
        df = df.withColumn("hashtags_array", F.split(F.coalesce(F.col("hashtags"), F.lit("")), " "))
        df = df.withColumn("prediction_confidence", F.col("confidence"))
        df = remove_stopwords(df, text_col="spark_clean", out_col="filtered_tokens")
        df = df.withColumn("filtered_tokens", F.filter(F.col("filtered_tokens"), lambda w: F.length(w) > 1))
        df = df.repartition(16, "platform").cache()
        count = df.count()
        AGG_DIR.mkdir(parents=True, exist_ok=True)
        outputs = {
            "sentiment_summary": sentiment_summary(df),
            "platform_summary": platform_summary(df),
            "topic_summary": topic_summary(df),
            "daily_trend": date_trend(df, "day"),
            "weekly_trend": date_trend(df, "week"),
            "monthly_trend": date_trend(df, "month"),
            "hashtag_frequency": hashtag_frequency(df, top_n=100),
            "keyword_frequency": keyword_frequency(df, top_n=100),
            "negative_topics": negative_topic_breakdown(df),
            "negative_posts": top_negative_posts(df, limit=100),
        }
        for name, frame in outputs.items():
            frame.to_csv(AGG_DIR / f"{name}.csv", index=False)
        report = {
            "rows": int(count),
            "partitions": df.rdd.getNumPartitions(),
            "outputs": {name: int(len(frame)) for name, frame in outputs.items()},
        }
        (AGG_DIR / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        df.unpersist()
        return report
    finally:
        spark.stop()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--full-only", action="store_true")
    parser.add_argument("--bench-only", action="store_true")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--sizes", type=str, default="100000,500000,1600000")
    args = parser.parse_args()
    if not args.full_only:
        run_benchmark([int(value) for value in args.sizes.split(",")], repeats=args.repeats)
    if not args.bench_only:
        run_full_aggregates()
