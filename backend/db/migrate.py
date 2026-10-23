"""Idempotent, additive schema migrations.

The original project created tables with ``Base.metadata.create_all`` and
never altered them. Existing databases therefore need explicit ALTERs for
the research columns and query indexes. PostgreSQL supports
``IF NOT EXISTS`` for both, so running this repeatedly is safe.
"""

from __future__ import annotations

from sqlalchemy import text

from backend.db.session import engine

STATEMENTS = [
    "ALTER TABLE sentiment_results ADD COLUMN IF NOT EXISTS gold_sentiment VARCHAR(20)",
    "ALTER TABLE sentiment_results ADD COLUMN IF NOT EXISTS prob_negative DOUBLE PRECISION",
    "ALTER TABLE sentiment_results ADD COLUMN IF NOT EXISTS prob_neutral DOUBLE PRECISION",
    "ALTER TABLE sentiment_results ADD COLUMN IF NOT EXISTS prob_positive DOUBLE PRECISION",
    "ALTER TABLE sentiment_results ADD COLUMN IF NOT EXISTS model_name VARCHAR(100)",
    "ALTER TABLE sentiment_results ADD COLUMN IF NOT EXISTS model_version VARCHAR(50)",
    "CREATE INDEX IF NOT EXISTS ix_posts_date_platform ON posts (post_date, platform)",
    "CREATE INDEX IF NOT EXISTS ix_posts_platform_date ON posts (platform, post_date)",
    "CREATE INDEX IF NOT EXISTS ix_posts_topic_date ON posts (topic, post_date)",
    "CREATE INDEX IF NOT EXISTS ix_sentiment_post_sentiment ON sentiment_results (post_id, sentiment)",
    "CREATE INDEX IF NOT EXISTS ix_sentiment_sentiment_post ON sentiment_results (sentiment, post_id)",
]


def run_migrations() -> None:
    with engine.begin() as connection:
        for statement in STATEMENTS:
            connection.execute(text(statement))
    print(f"Applied {len(STATEMENTS)} idempotent schema statements.")


if __name__ == "__main__":
    run_migrations()
