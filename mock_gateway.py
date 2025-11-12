"""
Mock gateway/proxy layer for testing pagination parameter duplication and anomalies.

This module simulates common production scenarios where proxies, load balancers,
or API gateways introduce duplicate parameters, reorder query strings, or
modify request semantics.
"""

from flask import Flask, request, jsonify
from werkzeug.datastructures import ImmutableMultiDict
from urllib.parse import urlencode, parse_qs, urlparse, urlunparse
import random


class MockGateway:
    """Mock gateway that introduces pagination anomalies for testing."""
    
    def __init__(self, app: Flask):
        self.app = app
        self.setup_routes()
    
    def setup_routes(self):
        """Setup mock gateway routes."""
        
        @self.app.before_request
        def inject_gateway_anomalies():
            """Inject gateway anomalies before request processing."""
            # Simulate proxy adding duplicate page parameter
            if random.random() < 0.3:  # 30% chance
                self._inject_duplicate_page()
            
            # Simulate query string reordering
            if random.random() < 0.2:  # 20% chance
                self._reorder_query_string()
            
            # Simulate array-encoded parameters
            if random.random() < 0.1:  # 10% chance
                self._convert_to_array_encoding()
    
    def _inject_duplicate_page(self):
        """Simulate proxy injecting duplicate page parameter."""
        if 'page' in request.args:
            # Create new args with duplicate
            new_args = request.args.to_dict(flat=False)
            new_args['page'].append(str(random.randint(1, 10)))
            request.args = ImmutableMultiDict([
                (k, v) for k, values in new_args.items() for v in values
            ])
    
    def _reorder_query_string(self):
        """Simulate query string reordering by proxy."""
        parsed = urlparse(request.url)
        if parsed.query:
            params = parse_qs(parsed.query, keep_blank_values=True)
            # Shuffle parameter order
            items = list(params.items())
            random.shuffle(items)
            new_query = urlencode(items, doseq=True)
            new_parsed = parsed._replace(query=new_query)
            # Note: This doesn't actually change request.url in Flask,
            # but simulates what would happen in a real proxy
            pass
    
    def _convert_to_array_encoding(self):
        """Simulate array-encoded parameters."""
        if 'page' in request.args:
            # Convert page to page[]
            new_args = request.args.to_dict(flat=False)
            if 'page' in new_args:
                new_args['page[]'] = new_args.pop('page')
                request.args = ImmutableMultiDict([
                    (k, v) for k, values in new_args.items() for v in values
                ])


def create_mock_app():
    """Create Flask app with mock gateway for testing."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize mock gateway
    MockGateway(app)
    
    return app


# Example usage endpoint
def create_test_endpoint(app):
    """Create a test endpoint that demonstrates normalization."""
    from request_normalizer import normalize_pagination_params, PaginationConfig
    from models import db, Post, PaginationQueryBuilder
    
    db.init_app(app)
    
    @app.route('/test/paginate')
    def test_paginate():
        """Test endpoint that shows normalization in action."""
        config = PaginationConfig(
            default_per_page=25,
            max_page_allowed=1000,
            max_per_page=100
        )
        
        params, metadata = normalize_pagination_params(request, config)
        
        # Simulate query
        with app.app_context():
            db.create_all()
            result = PaginationQueryBuilder.paginate_query(
                Post.query,
                params,
                order_by=[('timestamp', 'desc')]
            )
        
        return jsonify({
            'normalized_params': params.to_dict(),
            'metadata': metadata,
            'pagination': {
                'page': result.page,
                'per_page': result.per_page,
                'total': result.total,
                'pages': result.pages
            }
        })


if __name__ == '__main__':
    app = create_mock_app()
    create_test_endpoint(app)
    
    print("Mock Gateway running on http://127.0.0.1:5000")
    print("Test endpoint: http://127.0.0.1:5000/test/paginate?page=2&page=3")
    app.run(debug=True)

