"""
Stage 8: query functions backing the API.

Keeps SQL/ORM query logic out of the route handlers in backend/main.py,
so each endpoint function stays a thin "parse params -> call crud ->
return" shell.
"""

from datetime import date as date_type

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.db.models import Alert, DailySentiment, Hashtag, Keyword, Post, SentimentResult, Topic

SENTIMENT_LABELS = ["Positive", "Neutral", "Negative"]


def get_summary(db: Session) -> dict:
    total = db.query(func.count(Post.id)).scalar() or 0
    sentiment_counts = dict(
        db.query(SentimentResult.sentiment, func.count(SentimentResult.id))
        .group_by(SentimentResult.sentiment)
        .all()
    )
    num_platforms = db.query(func.count(func.distinct(Post.platform))).scalar() or 0
    num_topics = db.query(func.count(func.distinct(Post.topic))).scalar() or 0

    def pct(n):
        return round(n / total * 100, 2) if total else 0.0

    positive = sentiment_counts.get("Positive", 0)
    neutral = sentiment_counts.get("Neutral", 0)
    negative = sentiment_counts.get("Negative", 0)

    return {
        "total_posts": total,
        "positive_count": positive,
        "neutral_count": neutral,
        "negative_count": negative,
        "positive_pct": pct(positive),
        "neutral_pct": pct(neutral),
        "negative_pct": pct(negative),
        "num_platforms": num_platforms,
        "num_topics": num_topics,
    }


def get_sentiment_breakdown(db: Session) -> list:
    total = db.query(func.count(SentimentResult.id)).scalar() or 0
    rows = (
        db.query(SentimentResult.sentiment, func.count(SentimentResult.id).label("count"))
        .group_by(SentimentResult.sentiment)
        .all()
    )
    return [
        {"sentiment": sentiment, "count": count, "percentage": round(count / total * 100, 2) if total else 0.0}
        for sentiment, count in rows
    ]


def get_platform_breakdown(db: Session) -> list:
    rows = (
        db.query(Post.platform, SentimentResult.sentiment, func.count(Post.id).label("count"))
        .join(SentimentResult, Post.post_id == SentimentResult.post_id)
        .group_by(Post.platform, SentimentResult.sentiment)
        .all()
    )
    by_platform = {}
    for platform, sentiment, count in rows:
        entry = by_platform.setdefault(platform, {"platform": platform, "Positive": 0, "Neutral": 0, "Negative": 0})
        entry[sentiment] = count

    result = []
    for entry in by_platform.values():
        total = entry["Positive"] + entry["Neutral"] + entry["Negative"]
        entry["total"] = total
        for s in SENTIMENT_LABELS:
            entry[f"{s.lower()}_pct"] = round(entry[s] / total * 100, 2) if total else 0.0
        result.append(entry)
    return sorted(result, key=lambda r: r["total"], reverse=True)


def get_topic_breakdown(db: Session) -> list:
    rows = db.query(Topic).order_by(Topic.total.desc()).all()
    result = []
    for t in rows:
        entry = {
            "topic": t.topic, "Positive": t.positive, "Neutral": t.neutral,
            "Negative": t.negative, "total": t.total,
        }
        for s in SENTIMENT_LABELS:
            entry[f"{s.lower()}_pct"] = round(entry[s] / t.total * 100, 2) if t.total else 0.0
        result.append(entry)
    return result


def get_trends(db: Session, granularity: str = "day") -> list:
    if granularity == "day":
        bucket = DailySentiment.period_date
    elif granularity == "week":
        bucket = func.date_trunc("week", DailySentiment.period_date)
    elif granularity == "month":
        bucket = func.date_trunc("month", DailySentiment.period_date)
    else:
        raise ValueError(f"Unknown granularity: {granularity}. Use day, week, or month.")

    rows = (
        db.query(
            bucket.label("period"),
            func.sum(DailySentiment.positive).label("positive"),
            func.sum(DailySentiment.neutral).label("neutral"),
            func.sum(DailySentiment.negative).label("negative"),
            func.sum(DailySentiment.total).label("total"),
        )
        .group_by(bucket)
        .order_by(bucket)
        .all()
    )
    result = []
    for period, positive, neutral, negative, total in rows:
        period_str = period.isoformat() if isinstance(period, date_type) else str(period)
        result.append({
            "period": period_str,
            "positive": positive,
            "neutral": neutral,
            "negative": negative,
            "total": total,
            "negative_pct": round(negative / total * 100, 2) if total else 0.0,
        })
    return result


def get_hashtags(db: Session, limit: int = 30) -> list:
    rows = db.query(Hashtag).order_by(Hashtag.count.desc()).limit(limit).all()
    return [{"hashtag": r.hashtag, "count": r.count} for r in rows]


def get_keywords(db: Session, limit: int = 30) -> list:
    rows = db.query(Keyword).order_by(Keyword.count.desc()).limit(limit).all()
    return [{"keyword": r.keyword, "count": r.count} for r in rows]


def get_negative_posts(db: Session, limit: int = 20) -> list:
    rows = (
        db.query(Post, SentimentResult)
        .join(SentimentResult, Post.post_id == SentimentResult.post_id)
        .filter(SentimentResult.sentiment == "Negative")
        .order_by(SentimentResult.confidence.desc().nullslast())
        .limit(limit)
        .all()
    )
    return [
        {
            "post_id": post.post_id,
            "platform": post.platform,
            "topic": post.topic,
            "original_text": post.original_text,
            "sentiment": sentiment.sentiment,
            "confidence": sentiment.confidence,
            "date": post.post_date.isoformat() if post.post_date else None,
        }
        for post, sentiment in rows
    ]


def get_alerts(db: Session) -> list:
    rows = db.query(Alert).order_by(Alert.created_at.desc()).all()
    return [
        {
            "type": a.alert_type,
            "triggered": a.triggered,
            "message": a.message,
            "threshold": a.threshold,
            "negative_percentage": a.negative_percentage,
            "major_topic": a.major_topic,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in rows
    ]


def get_posts(
    db: Session,
    platform: str = None,
    sentiment: str = None,
    topic: str = None,
    date: str = None,
    keyword: str = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    query = db.query(Post, SentimentResult).join(SentimentResult, Post.post_id == SentimentResult.post_id)

    if platform:
        query = query.filter(Post.platform == platform)
    if sentiment:
        query = query.filter(SentimentResult.sentiment == sentiment)
    if topic:
        query = query.filter(Post.topic == topic)
    if date:
        query = query.filter(func.date(Post.post_date) == date)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(Post.clean_text.ilike(like))

    total = query.count()
    rows = query.order_by(Post.post_date.desc()).offset(offset).limit(limit).all()

    items = [
        {
            "post_id": post.post_id,
            "platform": post.platform,
            "author": post.author,
            "date": post.post_date.isoformat() if post.post_date else None,
            "topic": post.topic,
            "hashtags": post.hashtags,
            "original_text": post.original_text,
            "clean_text": post.clean_text,
            "sentiment": sentiment_row.sentiment,
            "confidence": sentiment_row.confidence,
        }
        for post, sentiment_row in rows
    ]
    return {"total": total, "limit": limit, "offset": offset, "items": items}
