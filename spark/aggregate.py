"""
Spark aggregations for the analytics dashboard.

Every function here operates on a Spark DataFrame using groupBy/agg/
pivot/orderBy — genuine distributed computation, not Pandas underneath.
Results are collected to the driver via .toPandas() only at the very end
of each function, once the data has already been reduced from thousands
of rows down to a small summary table (a handful to a few hundred rows)
— exactly the point in a real big-data pipeline where it's correct to
bring data back to a single process for reporting/storage.
"""

import pandas as pd
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

SENTIMENT_COL = "predicted_sentiment"


def sentiment_summary(df: DataFrame) -> pd.DataFrame:
    total = df.count()
    counts = df.groupBy(SENTIMENT_COL).count().toPandas()
    counts["percentage"] = (counts["count"] / total * 100).round(2)
    return counts.sort_values("count", ascending=False).reset_index(drop=True)


def platform_summary(df: DataFrame) -> pd.DataFrame:
    pivot = (
        df.groupBy("platform")
        .pivot(SENTIMENT_COL, ["Positive", "Neutral", "Negative"])
        .count()
        .fillna(0)
    )
    result = pivot.withColumn(
        "total", F.col("Positive") + F.col("Neutral") + F.col("Negative")
    )
    for sentiment in ("Positive", "Neutral", "Negative"):
        result = result.withColumn(
            f"{sentiment.lower()}_pct",
            F.round(F.col(sentiment) / F.col("total") * 100, 2),
        )
    return result.orderBy(F.col("total").desc()).toPandas()


def topic_summary(df: DataFrame) -> pd.DataFrame:
    pivot = (
        df.groupBy("topic")
        .pivot(SENTIMENT_COL, ["Positive", "Neutral", "Negative"])
        .count()
        .fillna(0)
    )
    result = pivot.withColumn(
        "total", F.col("Positive") + F.col("Neutral") + F.col("Negative")
    )
    for sentiment in ("Positive", "Neutral", "Negative"):
        result = result.withColumn(
            f"{sentiment.lower()}_pct",
            F.round(F.col(sentiment) / F.col("total") * 100, 2),
        )
    return result.orderBy(F.col("total").desc()).toPandas()


def date_trend(df: DataFrame, granularity: str = "day") -> pd.DataFrame:
    """granularity: 'day', 'week', or 'month'."""
    parsed = df.withColumn("_ts", F.to_timestamp("date", "yyyy-MM-dd HH:mm:ss"))

    if granularity == "day":
        bucket = F.to_date("_ts")
    elif granularity == "week":
        bucket = F.date_trunc("week", F.col("_ts")).cast("date")
    elif granularity == "month":
        bucket = F.trunc(F.col("_ts"), "month")
    else:
        raise ValueError(f"Unknown granularity: {granularity}")

    bucketed = parsed.withColumn("period", bucket)
    agg = bucketed.groupBy("period").agg(
        F.count("*").alias("total"),
        F.sum(F.when(F.col(SENTIMENT_COL) == "Positive", 1).otherwise(0)).alias("positive"),
        F.sum(F.when(F.col(SENTIMENT_COL) == "Neutral", 1).otherwise(0)).alias("neutral"),
        F.sum(F.when(F.col(SENTIMENT_COL) == "Negative", 1).otherwise(0)).alias("negative"),
    )
    agg = agg.withColumn(
        "negative_pct", F.round(F.col("negative") / F.col("total") * 100, 2)
    )
    return agg.orderBy("period").toPandas()


def hashtag_frequency(df: DataFrame, hashtags_col: str = "hashtags_array", top_n: int = 30) -> pd.DataFrame:
    exploded = df.select(F.explode(F.col(hashtags_col)).alias("hashtag"))
    exploded = exploded.filter(F.length(F.col("hashtag")) > 0)
    result = exploded.groupBy("hashtag").count().orderBy(F.col("count").desc()).limit(top_n)
    return result.toPandas()


def keyword_frequency(df: DataFrame, tokens_col: str = "filtered_tokens", top_n: int = 30) -> pd.DataFrame:
    exploded = df.select(F.explode(F.col(tokens_col)).alias("keyword"))
    result = exploded.groupBy("keyword").count().orderBy(F.col("count").desc()).limit(top_n)
    return result.toPandas()


def negative_topic_breakdown(df: DataFrame) -> pd.DataFrame:
    negative = df.filter(F.col(SENTIMENT_COL) == "Negative")
    result = negative.groupBy("topic").count().orderBy(F.col("count").desc())
    return result.toPandas()


def top_negative_posts(df: DataFrame, limit: int = 20) -> pd.DataFrame:
    negative = df.filter(F.col(SENTIMENT_COL) == "Negative")
    order_col = "prediction_confidence" if "prediction_confidence" in negative.columns else "post_id"
    result = (
        negative.select("post_id", "platform", "topic", "original_text", SENTIMENT_COL, order_col)
        .orderBy(F.col(order_col).desc())
        .limit(limit)
    )
    return result.toPandas()


def overall_negative_percentage(df: DataFrame) -> float:
    total = df.count()
    if total == 0:
        return 0.0
    negative = df.filter(F.col(SENTIMENT_COL) == "Negative").count()
    return round(negative / total * 100, 2)
