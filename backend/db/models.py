"""
Stage 7: database schema.

Kept intentionally simple (per the project spec): one table per concern,
no premature normalization beyond what the dashboard actually queries.

    posts              one row per deduplicated, cleaned post
    sentiment_results  the ML prediction for each post (1:1 with posts,
                        kept separate so "how was this classified" is its
                        own concern from "what is this post")
    daily_sentiment    Spark's daily trend aggregate
    hashtags           Spark's hashtag frequency aggregate
    topics             Spark's topic x sentiment breakdown
    alerts             a log of alert evaluations (from analytics/alerts.py)
"""

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True)
    post_id = Column(String(50), unique=True, nullable=False, index=True)
    platform = Column(String(50), nullable=False, index=True)
    author = Column(String(100))
    post_date = Column(DateTime, index=True)
    topic = Column(String(100), index=True)
    original_text = Column(Text)
    clean_text = Column(Text)
    hashtags = Column(Text)  # space-separated, e.g. "#battery #tech"


class SentimentResult(Base):
    __tablename__ = "sentiment_results"

    id = Column(Integer, primary_key=True)
    post_id = Column(String(50), ForeignKey("posts.post_id"), nullable=False, index=True)
    sentiment = Column(String(20), nullable=False, index=True)
    confidence = Column(Float)


class DailySentiment(Base):
    __tablename__ = "daily_sentiment"

    id = Column(Integer, primary_key=True)
    period_date = Column(Date, nullable=False, index=True)
    positive = Column(Integer, default=0)
    neutral = Column(Integer, default=0)
    negative = Column(Integer, default=0)
    total = Column(Integer, default=0)
    negative_pct = Column(Float)


class Hashtag(Base):
    __tablename__ = "hashtags"

    id = Column(Integer, primary_key=True)
    hashtag = Column(String(100), nullable=False, index=True)
    count = Column(Integer, nullable=False)


class Keyword(Base):
    __tablename__ = "keywords"

    id = Column(Integer, primary_key=True)
    keyword = Column(String(100), nullable=False, index=True)
    count = Column(Integer, nullable=False)


class Topic(Base):
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True)
    topic = Column(String(100), nullable=False, index=True)
    positive = Column(Integer, default=0)
    neutral = Column(Integer, default=0)
    negative = Column(Integer, default=0)
    total = Column(Integer, default=0)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True)
    alert_type = Column(String(50), nullable=False)
    triggered = Column(Boolean, nullable=False)
    message = Column(Text)
    threshold = Column(Float)
    negative_percentage = Column(Float)
    major_topic = Column(String(100))
    created_at = Column(DateTime, server_default=func.now())
