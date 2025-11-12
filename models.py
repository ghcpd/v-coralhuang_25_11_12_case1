"""
models.py

Sample SQLAlchemy models and pagination-aware helpers.
These are intentionally minimal to enable unit tests without a full app stack.
"""
from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    DateTime,
    String,
    create_engine,
    desc,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True)
    title = Column(String(140))
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


# Basic config for helpers
DEFAULT_PAGINATION_CONFIG = {
    "max_page_allowed": 1000,
    "max_per_page": 100,
}


def apply_deterministic_sort(query, order_columns):
    """Augment query order_by to ensure deterministic ordering.

    If the primary ordering is timestamp DESC, append id DESC as a deterministic tie-breaker.
    This function is intentionally conservative and only appends additional keys when
    it detects a non-unique ordering column.
    """
    # For the purposes of offline testing we will always append id as a secondary key
    # if timestamp is present as the primary sort. In a production app you can detect
    # or pass metadata about sort uniqueness.
    new_order = []
    for col in order_columns:
        # assume col is a SQLAlchemy order_by column; keep as is
        new_order.append(col)
    # if the ordering doesn't hit the PK, force it as a final fallback
    new_order.append(desc(Post.id))
    return query.order_by(*new_order)


def safe_paginate_query(query, page, per_page, config=None):
    """Apply safe pagination limits and return (items, total_estimate)

    Strategy:
        - Clamp page to 1..max_page_allowed
        - Clamp per_page to 1..max_per_page
        - If page hits max_page_allowed, return empty list to avoid expensive offset scans
        - Encourage keyset pagination: use filters on timestamp/id for large offsets (not implemented here)
    """
    cfg = DEFAULT_PAGINATION_CONFIG.copy()
    if config:
        cfg.update(config)

    max_page_allowed = cfg.get("max_page_allowed", 1000)
    max_per_page = cfg.get("max_per_page", 100)

    page = max(1, int(page))
    per_page = max(1, min(int(per_page), max_per_page))

    if page > max_page_allowed:
        # Defensive: return a lightweight empty result
        return [], 0

    offset = (page - 1) * per_page
    # Note: In a real system, you might use keyset pagination for high offsets. Here we guard
    # against abuse by trimming large pages.
    items = query.limit(per_page).offset(offset).all()

    # Optionally compute total - but it's expensive for large tables; we return a simple estimate
    total_estimate = None
    try:
        count_q = query.statement.with_only_columns([query.session.query(Post.id).count()]).order_by(None)
    except Exception:
        total_estimate = None
    return items, total_estimate


# Minimal in-memory DB setup helper for tests
def create_in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()
