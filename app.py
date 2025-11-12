"""
Flask application with integrated pagination normalization.

Demonstrates proper usage of pagination parameter normalization across
multiple endpoints with proper error handling and cache control headers.
"""

from flask import Flask, render_template_string, request, jsonify, make_response
from functools import wraps
import logging
from datetime import datetime, timedelta

from request_normalizer import normalize_pagination_params, PaginationConfig, build_canonical_url

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Configure pagination
PAGINATION_CONFIG = PaginationConfig(
    default_page=1,
    default_per_page=25,
    max_page_allowed=1000,
    max_per_page=100,
)

# Mock data for demonstration
MOCK_POSTS = [
    {"id": i, "author": f"user_{i % 10}", "body": f"Post {i}", "timestamp": datetime.utcnow() - timedelta(seconds=i*10)}
    for i in range(1, 501)
]


def require_normalized_pagination(f):
    """
    Decorator to normalize pagination parameters for a route.
    
    - Validates and normalizes request parameters
    - Sets cache control headers appropriately
    - Includes normalization audit info in response
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get request parameters as dict (supports both single and multi-value)
        request_args = request.args.to_dict(flat=False)
        
        # Normalize pagination parameters
        normalized = normalize_pagination_params(request_args, PAGINATION_CONFIG)
        
        # Pass normalized values and audit info to view
        kwargs['normalized_pagination'] = normalized
        
        return f(*args, **kwargs)
    
    return decorated_function


def set_cache_headers(response, is_user_dependent=False):
    """
    Set appropriate cache control headers based on content type.
    
    User-dependent paginated content should not be publicly cached.
    """
    if is_user_dependent:
        response.headers['Cache-Control'] = 'private, no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    else:
        # Public content can be cached but should validate pagination consistency
        response.headers['Cache-Control'] = 'public, max-age=300, s-maxage=300'
        response.headers['Vary'] = 'page,per_page'  # Cache varies by these params
    
    return response


@app.route('/')
@require_normalized_pagination
def index(normalized_pagination=None):
    """Public feed with pagination normalization."""
    page = normalized_pagination.page
    per_page = normalized_pagination.per_page
    
    # Calculate pagination metadata
    total = len(MOCK_POSTS)
    pages = (total + per_page - 1) // per_page
    
    # Fetch items for this page
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    items = MOCK_POSTS[start_idx:end_idx]
    
    # Build response
    response_data = {
        'page': page,
        'per_page': per_page,
        'total': total,
        'pages': pages,
        'items': items,
        'normalization_issues': normalized_pagination.issues if normalized_pagination.is_modified else [],
        'pagination_links': {
            'self': build_canonical_url('/api/posts', page, per_page),
            'first': build_canonical_url('/api/posts', 1, per_page),
            'last': build_canonical_url('/api/posts', pages, per_page) if pages > 0 else None,
            'prev': build_canonical_url('/api/posts', page - 1, per_page) if page > 1 else None,
            'next': build_canonical_url('/api/posts', page + 1, per_page) if page < pages else None,
        }
    }
    
    resp = make_response(jsonify(response_data))
    return set_cache_headers(resp, is_user_dependent=False)


@app.route('/explore')
@require_normalized_pagination
def explore(normalized_pagination=None):
    """Explore endpoint with pagination normalization."""
    page = normalized_pagination.page
    per_page = normalized_pagination.per_page
    
    # Get optional filter parameters
    sort = request.args.get('sort', 'ts_desc')
    filter_by = request.args.get('filter', 'all')
    
    # Calculate pagination
    total = len(MOCK_POSTS)
    pages = (total + per_page - 1) // per_page
    
    # Fetch items
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    items = MOCK_POSTS[start_idx:end_idx]
    
    response_data = {
        'page': page,
        'per_page': per_page,
        'total': total,
        'pages': pages,
        'sort': sort,
        'filter': filter_by,
        'items': items,
        'normalization_issues': normalized_pagination.issues if normalized_pagination.is_modified else [],
        'canonical_url': build_canonical_url('/explore', page, per_page, sort=sort, filter=filter_by),
    }
    
    resp = make_response(jsonify(response_data))
    return set_cache_headers(resp, is_user_dependent=False)


@app.route('/api/feed')
@require_normalized_pagination
def api_feed(normalized_pagination=None):
    """
    API endpoint demonstrating offset/limit to page conversion.
    
    Handles both:
    - Traditional: /api/feed?page=2&per_page=25
    - Mobile: /api/feed?offset=25&limit=25
    """
    page = normalized_pagination.page
    per_page = normalized_pagination.per_page
    
    total = len(MOCK_POSTS)
    pages = (total + per_page - 1) // per_page
    
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    items = MOCK_POSTS[start_idx:end_idx]
    
    response_data = {
        'page': page,
        'per_page': per_page,
        'offset': (page - 1) * per_page,
        'total': total,
        'items': items,
        'normalization_notes': [
            "This endpoint accepts both page/per_page and offset/limit parameters.",
            "The normalization layer automatically converts offset/limit to page/per_page.",
        ] if normalized_pagination.issues else [],
        'normalization_issues': normalized_pagination.issues,
    }
    
    resp = make_response(jsonify(response_data))
    return set_cache_headers(resp, is_user_dependent=False)


@app.route('/user/<username>')
@require_normalized_pagination
def user_profile(username, normalized_pagination=None):
    """
    User profile with user-context-dependent pagination.
    
    This endpoint serves user-specific data and should NOT be cached
    across different users.
    """
    page = normalized_pagination.page
    per_page = normalized_pagination.per_page
    
    # In a real app, filter posts by user
    total = len(MOCK_POSTS)
    pages = (total + per_page - 1) // per_page
    
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    items = MOCK_POSTS[start_idx:end_idx]
    
    response_data = {
        'username': username,
        'page': page,
        'per_page': per_page,
        'total': total,
        'pages': pages,
        'items': items,
        'normalization_issues': normalized_pagination.issues,
        'cache_note': 'This endpoint is user-context-dependent and marked non-cacheable.',
    }
    
    resp = make_response(jsonify(response_data))
    return set_cache_headers(resp, is_user_dependent=True)


@app.route('/api/posts')
@require_normalized_pagination
def api_posts(normalized_pagination=None):
    """API endpoint for posts with full normalization audit."""
    page = normalized_pagination.page
    per_page = normalized_pagination.per_page
    
    total = len(MOCK_POSTS)
    pages = (total + per_page - 1) // per_page
    
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    items = MOCK_POSTS[start_idx:end_idx]
    
    response_data = {
        'data': {
            'items': items,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': pages,
                'has_prev': page > 1,
                'has_next': page < pages,
            }
        },
        'normalization': {
            'applied': normalized_pagination.is_modified,
            'issues_detected': len(normalized_pagination.issues),
            'issues': normalized_pagination.issues,
            'original_params': normalized_pagination.original_params,
        }
    }
    
    resp = make_response(jsonify(response_data))
    return set_cache_headers(resp, is_user_dependent=False)


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({'status': 'ok'}), 200


@app.errorhandler(400)
def bad_request(error):
    """Handle bad requests."""
    return jsonify({'error': str(error)}), 400


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle internal errors."""
    logger.error(f"Internal error: {error}")
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("Starting Flask app with pagination normalization...")
    print("Available endpoints:")
    print("  GET /                    - Public feed")
    print("  GET /explore             - Explore endpoint")
    print("  GET /api/feed            - API feed (offset/limit support)")
    print("  GET /user/<username>     - User profile (user-context-dependent)")
    print("  GET /api/posts           - API posts with full audit")
    print("  GET /health              - Health check")
    print("\nTest with various pagination parameters to see normalization in action.")
    
    app.run(debug=True, host='127.0.0.1', port=5000)
