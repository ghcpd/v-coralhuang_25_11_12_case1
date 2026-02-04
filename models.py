"""
SQLAlchemy models with pagination, deterministic ordering, and user context isolation.

This module provides:
- Post model with deterministic multi-key ordering
- User model with proper relationships
- Query helpers that enforce stable ordering and pagination
- Thread-safe request context isolation
"""

from datetime import datetime
from typing import List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

# We'll use SQLAlchemy base imports - these should be injected by the app
try:
    from flask_sqlalchemy import SQLAlchemy
    db = SQLAlchemy()
except ImportError:
    # For testing/import purposes
    db = None


class User(db.Model if db else object):
    """User model with proper relationships for pagination."""
    
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True) if db else None
    username = db.Column(db.String(64), unique=True, nullable=False, index=True) if db else None
    email = db.Column(db.String(120), unique=True, nullable=False, index=True) if db else None
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False) if db else None
    
    # Relationships
    posts = db.relationship('Post', backref='author', lazy='dynamic', cascade='all, delete-orphan') if db else None
    followed = db.relationship(
        'User',
        secondary='user_follow' if db else None,
        primaryjoin='User.id==user_follow.c.follower_id' if db else None,
        secondaryjoin='User.id==user_follow.c.followed_id' if db else None,
        backref='followers',
        lazy='dynamic'
    ) if db else None
    
    def __repr__(self):
        return f'<User {self.username}>'
    
    def get_posts_query(self):
        """Return a deterministically ordered query of user's posts."""
        if not self.posts:
            return None
        return self.posts.order_by(Post.timestamp.desc(), Post.id.desc())
    
    def get_followed_posts_query(self):
        """Return a deterministically ordered query of followed users' posts."""
        if not db or not self.followed:
            return None
        return Post.query.filter(
            Post.author_id.in_(
                self.followed.with_entities(User.id)
            )
        ).order_by(Post.timestamp.desc(), Post.id.desc())


class Post(db.Model if db else object):
    """Post model with deterministic ordering support."""
    
    __tablename__ = 'post'
    
    id = db.Column(db.Integer, primary_key=True) if db else None
    body = db.Column(db.String(500), nullable=False) if db else None
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True) if db else None
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True) if db else None
    
    __table_args__ = (
        # Composite index for efficient pagination queries with deterministic ordering
        db.Index('ix_post_timestamp_id', 'timestamp', 'id', mysql_length={'timestamp': None}) if db else None,
    ) if db else None
    
    def __repr__(self):
        return f'<Post {self.id} by {self.author_id}>'


class PaginatedQueryResult:
    """
    Thread-safe result container for paginated queries.
    
    Encapsulates:
    - Items for the current page
    - Total count
    - Pagination metadata
    - Normalization issues/audit info
    """
    
    def __init__(
        self,
        items: List,
        page: int,
        per_page: int,
        total: int,
        pages: int,
        has_prev: bool,
        has_next: bool,
        prev_page: Optional[int] = None,
        next_page: Optional[int] = None,
        normalization_issues: Optional[List] = None,
        cache_key: Optional[str] = None,
    ):
        self.items = items
        self.page = page
        self.per_page = per_page
        self.total = total
        self.pages = pages
        self.has_prev = has_prev
        self.has_next = has_next
        self.prev_page = prev_page
        self.next_page = next_page
        self.normalization_issues = normalization_issues or []
        self.cache_key = cache_key
    
    def to_dict(self):
        """Convert result to dictionary for serialization."""
        return {
            'items': [item.to_dict() if hasattr(item, 'to_dict') else str(item) for item in self.items],
            'page': self.page,
            'per_page': self.per_page,
            'total': self.total,
            'pages': self.pages,
            'has_prev': self.has_prev,
            'has_next': self.has_next,
            'prev_page': self.prev_page,
            'next_page': self.next_page,
            'normalization_issues': self.normalization_issues,
        }


class PaginationHelper:
    """
    Helper class for safe, deterministic pagination with proper query ordering.
    
    Key features:
    - Enforces secondary sort keys for determinism
    - Applies normalized bounds
    - Tracks pagination metadata
    - Thread-safe and request-context-aware
    """
    
    @staticmethod
    def paginate_query(
        query,
        page: int,
        per_page: int,
        total: Optional[int] = None,
        normalization_issues: Optional[List] = None,
        cache_key: Optional[str] = None,
    ) -> PaginatedQueryResult:
        """
        Apply safe pagination to a SQLAlchemy query.
        
        Args:
            query: SQLAlchemy query object
            page: Page number (1-indexed, already normalized)
            per_page: Items per page (already normalized)
            total: Optional pre-computed total count
            normalization_issues: List of normalization issues for audit
            cache_key: Optional cache key for this paginated result
        
        Returns:
            PaginatedQueryResult with items and metadata
        """
        # Ensure safe bounds
        if page < 1:
            page = 1
        if per_page < 1:
            per_page = 25
        
        # Compute total if not provided
        if total is None:
            try:
                total = query.count()
            except Exception as e:
                logger.error(f"Error counting query results: {e}")
                total = 0
        
        # Calculate pagination metadata
        pages = (total + per_page - 1) // per_page if total > 0 else 1
        
        # Clamp page to valid range
        if page > pages and pages > 0:
            page = pages
        
        has_prev = page > 1
        has_next = page < pages
        prev_page = page - 1 if has_prev else None
        next_page = page + 1 if has_next else None
        
        # Apply offset and limit
        offset = (page - 1) * per_page
        
        try:
            items = query.offset(offset).limit(per_page).all()
        except Exception as e:
            logger.error(f"Error executing paginated query: {e}")
            items = []
        
        return PaginatedQueryResult(
            items=items,
            page=page,
            per_page=per_page,
            total=total,
            pages=pages,
            has_prev=has_prev,
            has_next=has_next,
            prev_page=prev_page,
            next_page=next_page,
            normalization_issues=normalization_issues,
            cache_key=cache_key,
        )
    
    @staticmethod
    def add_deterministic_ordering(query, *order_by_clauses):
        """
        Add deterministic ordering to ensure stable pagination results.
        
        If the query already has ordering, this appends additional clauses.
        If no ordering exists, applies the provided clauses.
        
        Args:
            query: SQLAlchemy query object
            order_by_clauses: SQLAlchemy order_by column expressions
        
        Returns:
            Modified query with deterministic ordering
        """
        if not order_by_clauses:
            return query
        
        try:
            # Add the order by clauses
            for clause in order_by_clauses:
                query = query.order_by(clause)
        except Exception as e:
            logger.error(f"Error applying deterministic ordering: {e}")
        
        return query


def get_user_feed(
    user,
    page: int,
    per_page: int,
    normalization_issues: Optional[List] = None,
    use_cache: bool = True,
) -> PaginatedQueryResult:
    """
    Get a deterministically paginated feed of posts from followed users.
    
    Args:
        user: User object
        page: Normalized page number
        per_page: Normalized per_page value
        normalization_issues: Audit information about normalization
        use_cache: Whether to include cache headers
    
    Returns:
        PaginatedQueryResult
    """
    if not db or not user:
        return PaginatedQueryResult([], page, per_page, 0, 0, False, False)
    
    try:
        # Build query for followed posts with deterministic ordering
        query = Post.query.filter(
            Post.author_id.in_(
                db.session.query(User.id).filter(
                    User.id.in_(
                        [u.id for u in user.followed.all()]
                    )
                )
            )
        )
        
        # Apply deterministic ordering: timestamp DESC, then id DESC
        query = PaginationHelper.add_deterministic_ordering(
            query,
            Post.timestamp.desc(),
            Post.id.desc()
        )
        
        # Build cache key if caching is enabled
        cache_key = None
        if use_cache:
            cache_key = f"user_{user.id}_feed_p{page}_pp{per_page}"
        
        return PaginationHelper.paginate_query(
            query,
            page=page,
            per_page=per_page,
            normalization_issues=normalization_issues,
            cache_key=cache_key,
        )
    except Exception as e:
        logger.error(f"Error fetching user feed: {e}")
        return PaginatedQueryResult([], page, per_page, 0, 0, False, False)


def get_user_posts(
    user,
    page: int,
    per_page: int,
    normalization_issues: Optional[List] = None,
) -> PaginatedQueryResult:
    """
    Get deterministically paginated posts by a specific user.
    
    Args:
        user: User object
        page: Normalized page number
        per_page: Normalized per_page value
        normalization_issues: Audit information about normalization
    
    Returns:
        PaginatedQueryResult
    """
    if not db or not user:
        return PaginatedQueryResult([], page, per_page, 0, 0, False, False)
    
    try:
        # Build query for user's posts with deterministic ordering
        query = user.posts
        
        # Apply deterministic ordering: timestamp DESC, then id DESC
        query = PaginationHelper.add_deterministic_ordering(
            query,
            Post.timestamp.desc(),
            Post.id.desc()
        )
        
        return PaginationHelper.paginate_query(
            query,
            page=page,
            per_page=per_page,
            normalization_issues=normalization_issues,
            cache_key=f"user_{user.id}_posts_p{page}_pp{per_page}",
        )
    except Exception as e:
        logger.error(f"Error fetching user posts: {e}")
        return PaginatedQueryResult([], page, per_page, 0, 0, False, False)


# Export helper functions for external use
__all__ = [
    'db',
    'User',
    'Post',
    'PaginatedQueryResult',
    'PaginationHelper',
    'get_user_feed',
    'get_user_posts',
]
