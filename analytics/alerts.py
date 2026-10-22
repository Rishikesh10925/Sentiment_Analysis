"""
Stage 6: Alerts.

Two independent alert checks:

1. A configurable negative-sentiment threshold alert (spec default: 40%).
2. Period-over-period negative sentiment change detection, when enough
   date history exists (at least 2 periods).
"""

import os

DEFAULT_NEGATIVE_THRESHOLD = 40.0
DEFAULT_PERIOD_CHANGE_THRESHOLD = 10.0  # percentage points


def get_negative_threshold() -> float:
    """Reads NEGATIVE_SENTIMENT_ALERT_THRESHOLD from the environment (see .env.example), default 40%."""
    return float(os.environ.get("NEGATIVE_SENTIMENT_ALERT_THRESHOLD", DEFAULT_NEGATIVE_THRESHOLD))


def check_negative_threshold_alert(negative_pct: float, major_topic: str = None, threshold: float = None) -> dict:
    threshold = get_negative_threshold() if threshold is None else threshold
    triggered = negative_pct > threshold

    message = None
    if triggered:
        message = f"⚠ Negative Sentiment Alert\nNegative sentiment: {round(negative_pct, 2)}%\nThreshold: {threshold}%"
        if major_topic:
            message += f"\nMajor topic: {major_topic}"

    return {
        "type": "negative_threshold",
        "triggered": triggered,
        "negative_percentage": round(negative_pct, 2),
        "threshold": threshold,
        "major_topic": major_topic,
        "message": message,
    }


def detect_period_change(
    trend_df,
    pct_col: str = "negative_pct",
    period_col: str = "period",
    change_threshold: float = DEFAULT_PERIOD_CHANGE_THRESHOLD,
) -> dict:
    """Compares the most recent two periods' negative_pct in trend_df.

    Returns triggered=False (with a reason) if there isn't at least 2
    periods of date history to compare — this is expected, not an error,
    for small/short-lived datasets.
    """
    if trend_df is None or len(trend_df) < 2:
        return {
            "type": "period_change",
            "triggered": False,
            "message": None,
            "reason": "not enough date history (need at least 2 periods)",
        }

    sorted_df = trend_df.sort_values(period_col)
    last = sorted_df.iloc[-1]
    prev = sorted_df.iloc[-2]
    current_pct = round(float(last[pct_col]), 2)
    previous_pct = round(float(prev[pct_col]), 2)
    change = round(current_pct - previous_pct, 2)
    triggered = abs(change) >= change_threshold

    message = None
    if triggered:
        direction = "increased" if change > 0 else "decreased"
        message = (
            f"Negative sentiment {direction} by {abs(change)} points "
            f"({previous_pct}% -> {current_pct}%) between {prev[period_col]} and {last[period_col]}"
        )

    return {
        "type": "period_change",
        "triggered": triggered,
        "current_period": str(last[period_col]),
        "previous_period": str(prev[period_col]),
        "current_negative_pct": current_pct,
        "previous_negative_pct": previous_pct,
        "change": change,
        "change_threshold": change_threshold,
        "message": message,
    }
