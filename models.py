"""
SQLAlchemy models and safe pagination helpers.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func, desc
from sqlalchemy.orm import declarative_base, relationship, Session
from sqlalchemy import create_engine, select
from datetime import datetime, timedelta

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)


class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(String)
    timestamp = Column(DateTime, default=func.now(), nullable=False)

    owner = relationship("User")


DEFAULT_MAX_PAGE_ALLOWED = 1000
DEFAULT_MAX_PER_PAGE = 100


def get_session(uri: str = "sqlite:///:memory:") -> Session:
    engine = create_engine(uri, echo=False, future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def seed_posts(session: Session, n: int = 200, start_ts: datetime = None):
    if start_ts is None:
        start_ts = datetime.utcnow()
    # create a single user for simplicity
    user = User(username="alice")
    session.add(user)
    session.flush()

    posts = []
    # create posts with timestamps and occasional duplicate timestamps to test tie-breaking
    for i in range(1, n+1):
        ts = start_ts - timedelta(seconds=(i // 3))  # causes ties every 3 posts
        posts.append(Post(owner_id=user.id, content=f"post {i}", timestamp=ts))
    session.add_all(posts)
    session.commit()
    return user


def ensure_deterministic_order(query, model, primary_order_cols=None):
    """
    Ensure the query is ordered by primary_order_cols and then by id as a tie-breaker.
    primary_order_cols should be a list of SQLAlchemy columns or expressions.
    """
    from sqlalchemy import desc

    if primary_order_cols is None:
        primary_order_cols = [desc(model.timestamp), desc(model.id)]
    else:
        # ensure id is appended to break ties
        # if last element is not model.id, add it
        last = primary_order_cols[-1]
        # we assume last may be a desc(column) or asc; we just append id desc
        primary_order_cols = primary_order_cols + [desc(model.id)]

    return query.order_by(*primary_order_cols)


def get_paginated_query(session: Session, model, page: int, per_page: int, *, max_page_allowed=DEFAULT_MAX_PAGE_ALLOWED, max_per_page=DEFAULT_MAX_PER_PAGE, primary_order_cols=None):
    """
    Return a tuple (query, offset, limit, exhausted) where query has deterministic ordering and offset/limit applied safely.
    If page > max_page_allowed, we clamp it and set exhausted True.
    If page * per_page is large (>= max_page_allowed * max_per_page), we also clamp.
    """
    clamped = False
    if page <= 0:
        page = 1
        clamped = True
    if per_page <= 0:
        per_page = 25
        clamped = True
    if per_page > max_per_page:
        per_page = max_per_page
        clamped = True
    if page > max_page_allowed:
        page = max_page_allowed
        clamped = True

    # calculate offset simple safe check: if page is too large, return empty query
    offset = (page - 1) * per_page
    worst_offset_threshold = max_page_allowed * max_per_page
    if offset >= worst_offset_threshold:
        # return empty result set to avoid huge offset
        q = session.query(model).filter(False)  # always false
        return q, offset, per_page, True, clamped

    q = session.query(model)
    q = ensure_deterministic_order(q, model, primary_order_cols)
    q = q.offset(offset).limit(per_page)
    return q, offset, per_page, False, clamped
