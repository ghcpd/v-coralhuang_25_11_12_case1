"""
Example Flask application demonstrating pagination normalization usage.

This file shows how to integrate the pagination normalization system
into a Flask application.
"""

from flask import Flask, request, jsonify
from flask_login import LoginManager, login_required, current_user
from request_normalizer import normalize_pagination_params, PaginationConfig
from models import (
    db,
    Post,
    User,
    PaginationQueryBuilder
)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///example.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-here'

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)

# Configure pagination
PAGINATION_CONFIG = PaginationConfig(
    default_per_page=25,
    max_page_allowed=1000,
    max_per_page=100
)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/')
def index():
    """Public feed with pagination."""
    # Normalize pagination parameters
    params, metadata = normalize_pagination_params(request, PAGINATION_CONFIG)
    
    # Get paginated posts
    result = PaginationQueryBuilder.paginate_query(
        Post.query,
        params,
        order_by=[('timestamp', 'desc')]
    )
    
    # Generate canonical URLs for pagination links
    from request_normalizer import PaginationNormalizer
    normalizer = PaginationNormalizer(PAGINATION_CONFIG)
    
    pagination_links = {
        'current': normalizer.build_canonical_url(request.url, params.page, params.per_page),
        'next': normalizer.build_canonical_url(request.url, result.next_page, params.per_page) if result.has_next else None,
        'prev': normalizer.build_canonical_url(request.url, result.prev_page, params.per_page) if result.has_prev else None,
    }
    
    return jsonify({
        'posts': [post.to_dict() for post in result.items],
        'pagination': result.to_dict()['pagination'],
        'links': pagination_links,
        'normalization_metadata': metadata
    })


@app.route('/explore')
def explore():
    """Explore feed with pagination."""
    params, metadata = normalize_pagination_params(request, PAGINATION_CONFIG)
    
    result = PaginationQueryBuilder.paginate_query(
        Post.query,
        params,
        order_by=[('timestamp', 'desc')]
    )
    
    response = jsonify({
        'posts': [post.to_dict() for post in result.items],
        'pagination': result.to_dict()['pagination']
    })
    
    # Mark as cacheable for public content
    response.headers['Cache-Control'] = 'public, max-age=300'
    
    return response


@app.route('/user/<username>')
def user_profile(username):
    """User profile with paginated posts."""
    user = User.query.filter_by(username=username).first_or_404()
    
    params, metadata = normalize_pagination_params(request, PAGINATION_CONFIG)
    
    result = PaginationQueryBuilder.get_user_posts(
        user.id,
        params,
        order_by=[('timestamp', 'desc')]
    )
    
    return jsonify({
        'user': user.to_dict(),
        'posts': [post.to_dict() for post in result.items],
        'pagination': result.to_dict()['pagination']
    })


@app.route('/api/feed')
@login_required
def feed():
    """User's personalized feed (requires authentication)."""
    params, metadata = normalize_pagination_params(request, PAGINATION_CONFIG)
    
    # Get posts from users that current_user follows
    result = PaginationQueryBuilder.get_followed_posts(
        current_user.id,
        params,
        order_by=[('timestamp', 'desc')]
    )
    
    response = jsonify({
        'posts': [post.to_dict() for post in result.items],
        'pagination': result.to_dict()['pagination']
    })
    
    # CRITICAL: Mark as non-cacheable for user-specific content
    # This prevents cross-user data leakage
    response.headers['Cache-Control'] = 'private, no-cache, no-store, must-revalidate'
    response.headers['Vary'] = 'Authorization'
    
    return response


@app.route('/api/users/<username>/posts')
def user_posts_api(username):
    """API endpoint for user posts with pagination."""
    user = User.query.filter_by(username=username).first_or_404()
    
    params, metadata = normalize_pagination_params(request, PAGINATION_CONFIG)
    
    result = PaginationQueryBuilder.get_user_posts(
        user.id,
        params,
        order_by=[('timestamp', 'desc')]
    )
    
    return jsonify(result.to_dict())


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    app.run(debug=True)

