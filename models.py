"""
Database models with robust pagination support and deterministic ordering.

This module provides SQLAlchemy models with pagination utilities that ensure
deterministic ordering and efficient query execution.
"""

from datetime import datetime
from typing import Optional, Tuple, List, Any
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import desc, asc, or_
from sqlalchemy.orm import Query

from request_normalizer import NormalizedPaginationParams, PaginationConfig


db = SQLAlchemy()


class Post(db.Model):
    """Post model with timestamp and deterministic ordering support."""
    
    __tablename__ = 'posts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('posts', lazy=True))
    
    def __repr__(self):
        return f'<Post {self.id} by user {self.user_id}>'
    
    def to_dict(self):
        """Convert post to dictionary representation."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'content': self.content,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class User(db.Model):
    """User model."""
    
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f'<User {self.username}>'
    
    def to_dict(self):
        """Convert user to dictionary representation."""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Follow(db.Model):
    """Follow relationship model for user following."""
    
    __tablename__ = 'follows'
    
    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    followed_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (db.UniqueConstraint('follower_id', 'followed_id', name='unique_follow'),)
    
    follower = db.relationship('User', foreign_keys=[follower_id], backref='following')
    followed = db.relationship('User', foreign_keys=[followed_id], backref='followers')


class PaginatedResult:
    """Container for paginated query results with metadata."""
    
    def __init__(
        self,
        items: List[Any],
        page: int,
        per_page: int,
        total: int,
        pages: int
    ):
        self.items = items
        self.page = page
        self.per_page = per_page
        self.total = total
        self.pages = pages
    
    @property
    def has_prev(self) -> bool:
        """Check if there is a previous page."""
        return self.page > 1
    
    @property
    def has_next(self) -> bool:
        """Check if there is a next page."""
        return self.page < self.pages
    
    @property
    def prev_page(self) -> Optional[int]:
        """Get previous page number."""
        return self.page - 1 if self.has_prev else None
    
    @property
    def next_page(self) -> Optional[int]:
        """Get next page number."""
        return self.page + 1 if self.has_next else None
    
    def to_dict(self) -> dict:
        """Convert paginated result to dictionary."""
        return {
            'items': [item.to_dict() if hasattr(item, 'to_dict') else str(item) for item in self.items],
            'pagination': {
                'page': self.page,
                'per_page': self.per_page,
                'total': self.total,
                'pages': self.pages,
                'has_prev': self.has_prev,
                'has_next': self.has_next,
                'prev_page': self.prev_page,
                'next_page': self.next_page
            }
        }


class PaginationQueryBuilder:
    """Builder for paginated queries with deterministic ordering."""
    
    @staticmethod
    def paginate_query(
        query: Query,
        params: NormalizedPaginationParams,
        order_by: Optional[List[Tuple[str, str]]] = None,
        deterministic_key: str = 'id'
    ) -> PaginatedResult:
        """
        Paginate a SQLAlchemy query with deterministic ordering.
        
        Args:
            query: SQLAlchemy query object
            params: Normalized pagination parameters
            order_by: List of (column_name, direction) tuples for ordering.
                     Direction should be 'asc' or 'desc'.
                     Defaults to timestamp DESC if not provided.
            deterministic_key: Column name to use as secondary sort key for stability.
                             Defaults to 'id'.
        
        Returns:
            PaginatedResult with items and pagination metadata
        """
        # Apply deterministic ordering
        query = PaginationQueryBuilder._apply_deterministic_ordering(
            query, order_by, deterministic_key
        )
        
        # Get total count (before pagination)
        total = query.count()
        
        # Calculate total pages
        pages = (total + params.per_page - 1) // params.per_page if total > 0 else 0
        
        # Apply pagination
        if params.offset is not None:
            items = query.offset(params.offset).limit(params.per_page).all()
        else:
            # Fallback calculation
            offset = (params.page - 1) * params.per_page
            items = query.offset(offset).limit(params.per_page).all()
        
        return PaginatedResult(
            items=items,
            page=params.page,
            per_page=params.per_page,
            total=total,
            pages=pages
        )
    
    @staticmethod
    def _apply_deterministic_ordering(
        query: Query,
        order_by: Optional[List[Tuple[str, str]]],
        deterministic_key: str = 'id'
    ) -> Query:
        """
        Apply ordering with deterministic tie-breaking.
        
        Ensures that queries with identical primary sort values (e.g., same timestamp)
        are ordered consistently by adding a secondary sort key.
        """
        if order_by is None:
            # Default ordering: timestamp DESC
            order_by = [('timestamp', 'desc')]
        
        # Get the entity class from the query
        entity_class = None
        try:
            # Try to get entity class from query mapper
            if hasattr(query, 'column_descriptions') and query.column_descriptions:
                entity_class = query.column_descriptions[0]['entity']
            elif hasattr(query, '_entities') and query._entities:
                entity_class = query._entities[0].entity.class_
            elif hasattr(query, 'entity') and query.entity:
                entity_class = query.entity.class_
        except (AttributeError, IndexError, TypeError):
            pass
        
        if entity_class is None:
            # If we can't determine the entity, return query as-is
            return query
        
        # Apply primary ordering
        for column_name, direction in order_by:
            try:
                column = getattr(entity_class, column_name, None)
                if column is None:
                    continue
                
                if direction.lower() == 'desc':
                    query = query.order_by(desc(column))
                else:
                    query = query.order_by(asc(column))
            except (AttributeError, TypeError):
                continue
        
        # Add deterministic secondary sort key
        try:
            deterministic_column = getattr(entity_class, deterministic_key, None)
            if deterministic_column is not None:
                # Use DESC for deterministic ordering to ensure stability
                query = query.order_by(desc(deterministic_column))
        except (AttributeError, TypeError):
            # If deterministic key doesn't exist, skip it
            pass
        
        return query
    
    @staticmethod
    def get_user_posts(
        user_id: int,
        params: NormalizedPaginationParams,
        order_by: Optional[List[Tuple[str, str]]] = None
    ) -> PaginatedResult:
        """Get paginated posts for a specific user."""
        query = Post.query.filter_by(user_id=user_id)
        return PaginationQueryBuilder.paginate_query(query, params, order_by)
    
    @staticmethod
    def get_followed_posts(
        user_id: int,
        params: NormalizedPaginationParams,
        order_by: Optional[List[Tuple[str, str]]] = None
    ) -> PaginatedResult:
        """Get paginated posts from users that the current user follows."""
        # Get list of followed user IDs
        followed_ids = db.session.query(Follow.followed_id).filter_by(
            follower_id=user_id
        ).subquery()
        
        query = Post.query.filter(Post.user_id.in_(db.session.query(followed_ids)))
        return PaginationQueryBuilder.paginate_query(query, params, order_by)
    
    @staticmethod
    def get_all_posts(
        params: NormalizedPaginationParams,
        order_by: Optional[List[Tuple[str, str]]] = None
    ) -> PaginatedResult:
        """Get all paginated posts."""
        query = Post.query
        return PaginationQueryBuilder.paginate_query(query, params, order_by)


def init_db(app: Flask):
    """Initialize database with app context."""
    db.init_app(app)
    with app.app_context():
        db.create_all()

