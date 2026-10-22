"""
Spark-native text cleaning.

Deliberately re-implemented using only built-in Spark SQL Column
expressions and MLlib feature transformers (Tokenizer, StopWordsRemover)
— NOT Python UDFs. A Python UDF would force Spark to serialize every row
back into a Python worker subprocess, which is slow (breaks Catalyst's
whole-stage codegen) and, in this project's Windows dev environment,
hits a broken Java<->Python socket IPC path that could not be fixed (see
README's Stage 5 section for the full story). Built-in functions and the
`transform`/`filter` higher-order Column functions below compile into
JVM bytecode and never spawn a Python worker, so this genuinely runs
distributed across Spark executors.

Mirrors preprocessing/clean.py's logic (extract hashtags, strip URLs,
mentions, hashtags, emojis, punctuation, stopwords, whitespace) as a
parallel, Spark-native implementation.
"""

from pyspark.ml.feature import StopWordsRemover, Tokenizer
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

URL_REGEX = r"http\S+|www\.\S+"
MENTION_REGEX = r"@\w+"
HASHTAG_REGEX = r"#\w+"
HASHTAG_CAPTURE_REGEX = r"#(\w+)"
EMOJI_REGEX = (
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
    "\U0001F900-\U0001F9FF\U0000FE00-\U0000FE0F]"
)
NON_ALNUM_REGEX = r"[^a-z0-9\s]"


def extract_hashtags_column(
    df: DataFrame, text_col: str = "text", out_col: str = "hashtags_array"
) -> DataFrame:
    """Extracts #tag words (lowercased, deduped) from text_col into an array column.

    Uses regexp_extract_all + the `transform`/`array_distinct` higher-order
    functions — these build a SQL expression tree at DataFrame-definition
    time; the lambda is not a per-row Python callback.
    """
    raw_text = F.coalesce(F.col(text_col), F.lit(""))
    extracted = F.regexp_extract_all(raw_text, F.lit(HASHTAG_CAPTURE_REGEX), F.lit(1))
    lowered = F.transform(extracted, lambda tag: F.lower(tag))
    return df.withColumn(out_col, F.array_distinct(lowered))


def clean_text_column(
    df: DataFrame, text_col: str = "text", out_col: str = "spark_clean_text"
) -> DataFrame:
    """Lowercases and strips URLs, mentions, hashtags, emojis, and punctuation."""
    raw_text = F.coalesce(F.col(text_col), F.lit(""))
    step = F.lower(raw_text)
    step = F.regexp_replace(step, URL_REGEX, " ")
    step = F.regexp_replace(step, MENTION_REGEX, " ")
    step = F.regexp_replace(step, HASHTAG_REGEX, " ")  # extracted separately above
    step = F.regexp_replace(step, EMOJI_REGEX, " ")
    step = F.regexp_replace(step, NON_ALNUM_REGEX, " ")
    step = F.trim(F.regexp_replace(step, r"\s+", " "))
    return df.withColumn(out_col, step)


def remove_stopwords(
    df: DataFrame,
    text_col: str = "spark_clean_text",
    out_col: str = "filtered_tokens",
) -> DataFrame:
    """Tokenizes and removes English stopwords via MLlib transformers (JVM-native, no UDF)."""
    tokenized = Tokenizer(inputCol=text_col, outputCol="_tokens").transform(df)
    filtered = StopWordsRemover(inputCol="_tokens", outputCol=out_col).transform(tokenized)
    return filtered.drop("_tokens")


def spark_clean_pipeline(df: DataFrame, text_col: str = "text") -> DataFrame:
    """Full Spark-native cleaning pipeline: extract hashtags, clean text, remove stopwords.

    Adds columns: hashtags_array, spark_clean_text, filtered_tokens,
    spark_clean_text_final (filtered_tokens rejoined into a string).
    """
    df = extract_hashtags_column(df, text_col=text_col, out_col="hashtags_array")
    df = clean_text_column(df, text_col=text_col, out_col="spark_clean_text")
    df = remove_stopwords(df, text_col="spark_clean_text", out_col="filtered_tokens")
    df = df.withColumn(
        "filtered_tokens", F.filter(F.col("filtered_tokens"), lambda w: F.length(w) > 1)
    )
    df = df.withColumn("spark_clean_text_final", F.array_join(F.col("filtered_tokens"), " "))
    return df
