# Flask Pagination Normalization System

## Overview

This project provides a robust, production-ready pagination normalization and validation system for Flask + SQLAlchemy applications. It addresses critical data consistency, input normalization, and pagination stability issues that arise in heterogeneous production environments with load balancers, API gateways, single-page app routers, and reverse proxies.

## Problem Statement

Production Flask applications often experience pagination inconsistencies due to:

1. **Duplicate Query Parameters** - Frontend and upstream layers inject multiple `page` parameters (e.g., `/explore?page=3&page=2`), causing unpredictable results
2. **Malformed Inputs** - Invalid values like `page=-1`, `page=`, or `page=abc` break pagination logic
3. **Extreme Offsets** - Large page values (e.g., `page=999999`) trigger expensive database OFFSET scans
4. **Array Encoding** - Some proxies encode parameters as arrays (`page[]=2&page[]=3`), which Flask's parser may ignore
5. **Parameter Aliases** - Clients use inconsistent parameter names (`p`, `limit`, `size`, `offset`) causing API contract divergence
6. **Timestamp Instability** - Queries ordered by timestamp without deterministic tiebreakers produce non-repeatable results
7. **Cache Inconsistencies** - Different cache layers cache inconsistent query-string variants
8. **Session Drift** - User-dependent paginated views cached without user context lead to data leakage

## Solution Architecture

### Core Components

#### 1. `request_normalizer.py`
Centralized pagination parameter normalization module that:
- Detects and handles duplicate parameters (uses first valid value)
- Normalizes parameter aliases (`p` → `page`, `limit` → `per_page`)
- Converts `offset/limit` to `page/per_page`
- Handles array-encoded parameters (`page[]=2`)
- Enforces configurable bounds (`max_page_allowed`, `max_per_page`)
- Generates canonical URLs with exactly one pagination parameter

#### 2. `models.py`
Database models with deterministic ordering support:
- `PaginationQueryBuilder` - Ensures stable pagination with secondary sort keys
- `PaginatedResult` - Standardized pagination result container
- Automatic tie-breaking using `id DESC` when primary sort values are identical

#### 3. `test_pagination_consistency.py`
Comprehensive test suite covering:
- All input.json test cases
- Edge cases (empty params, negative values, extreme offsets)
- Deterministic ordering validation
- Cache safety mechanisms

## Usage

### Basic Usage

```python
from flask import Flask, request
from request_normalizer import normalize_pagination_params, PaginationConfig
from models import PaginationQueryBuilder, Post

app = Flask(__name__)

@app.route('/explore')
def explore():
    # Normalize pagination parameters
    config = PaginationConfig(
        default_per_page=25,
        max_page_allowed=1000,
        max_per_page=100
    )
    params, metadata = normalize_pagination_params(request, config)
    
    # Use normalized parameters in query
    result = PaginationQueryBuilder.paginate_query(
        Post.query.order_by(Post.timestamp.desc()),
        params,
        order_by=[('timestamp', 'desc')]
    )
    
    return {
        'posts': [post.to_dict() for post in result.items],
        'pagination': {
            'page': result.page,
            'per_page': result.per_page,
            'total': result.total,
            'pages': result.pages,
            'has_next': result.has_next,
            'has_prev': result.has_prev
        }
    }
```

### Handling User-Dependent Feeds

```python
from flask_login import current_user
from models import PaginationQueryBuilder

@app.route('/feed')
@login_required
def feed():
    params, metadata = normalize_pagination_params(request)
    
    # Get posts from followed users
    result = PaginationQueryBuilder.get_followed_posts(
        current_user.id,
        params,
        order_by=[('timestamp', 'desc')]
    )
    
    # Mark as non-cacheable for user-specific content
    response = jsonify(result.to_dict())
    response.headers['Cache-Control'] = 'private, no-cache, no-store, must-revalidate'
    response.headers['Vary'] = 'Authorization'
    
    return response
```

### Generating Canonical URLs

```python
from request_normalizer import PaginationNormalizer

normalizer = PaginationNormalizer()

# Generate canonical pagination links
canonical_url = normalizer.build_canonical_url(
    request.url,
    page=result.next_page,
    per_page=params.per_page,
    preserve_other_params=True
)
```

## Normalization Rules

### Page Parameter
- **Duplicates**: First valid integer value is used, rest are discarded
- **Negative/Zero**: Clamped to `1`
- **Empty/Invalid**: Defaults to `1`
- **Exceeds Max**: Clamped to `max_page_allowed` (default: 1000)
- **Array Encoding**: First valid integer from array is extracted

### Per-Page Parameter
- **Duplicates**: First valid integer value is used
- **Below Minimum**: Clamped to `min_per_page` (default: 1)
- **Exceeds Max**: Clamped to `max_per_page` (default: 100)
- **Missing**: Uses `default_per_page` (default: 25)

### Offset/Limit Conversion
- **offset + limit**: Converts to `page = (offset / limit) + 1`, `per_page = limit`
- **offset only**: Converts using default `per_page`
- **limit only**: Uses as `per_page`

### Parameter Aliases
- **Page**: `page`, `p`
- **Per-Page**: `per_page`, `limit`, `size`
- **Offset**: `offset`, `start`

## Deterministic Ordering

To ensure stable pagination when primary sort values are identical (e.g., posts with same timestamp), the system automatically adds a secondary sort key:

```python
# Without normalization (unstable):
Post.query.order_by(Post.timestamp.desc())

# With normalization (stable):
PaginationQueryBuilder.paginate_query(
    Post.query,
    params,
    order_by=[('timestamp', 'desc')]  # Automatically adds id DESC as tiebreaker
)
```

## Cache Safety

### User-Dependent Content
For routes that depend on `current_user` or session context:

```python
response.headers['Cache-Control'] = 'private, no-cache, no-store, must-revalidate'
response.headers['Vary'] = 'Authorization'
```

### Public Content
For public paginated content, ensure canonical URLs are used consistently:

```python
# Generate canonical URL for pagination links
canonical_url = normalizer.build_canonical_url(
    request.url,
    page=next_page,
    per_page=params.per_page
)
```

## Testing

### Run All Tests

**Linux/macOS:**
```bash
chmod +x run_test.sh
./run_test.sh
```

**Windows:**
```cmd
run_test.bat
```

### Run Specific Test Suite
```bash
python -m pytest test_pagination_consistency.py -v
```

### Test Coverage
The test suite covers:
- ✅ Duplicate parameter handling
- ✅ Negative and zero values
- ✅ Extreme offset protection
- ✅ Array-encoded parameters
- ✅ Offset/limit conversion
- ✅ Parameter aliases
- ✅ Deterministic ordering
- ✅ Cache safety
- ✅ All input.json test cases

## Deployment Recommendations

### 1. Input Validation Layer
Deploy `request_normalizer.py` as middleware or decorator to normalize all pagination requests before they reach view handlers.

### 2. Database Indexing
Ensure indexes exist on:
- Primary sort columns (e.g., `timestamp`)
- Secondary sort columns (e.g., `id`)
- Foreign keys used in filters (e.g., `user_id`)

### 3. Rate Limiting
Implement rate limiting on pagination endpoints to prevent abuse:
```python
from flask_limiter import Limiter

limiter = Limiter(app, key_func=get_remote_address)

@app.route('/explore')
@limiter.limit("100 per minute")
def explore():
    # ...
```

### 4. Monitoring
Monitor for:
- Requests exceeding `max_page_allowed`
- High-offset queries (page > 100)
- Duplicate parameter occurrences
- Cache hit rates for paginated endpoints

### 5. CDN Configuration
For user-dependent content:
- Set `Cache-Control: private`
- Use `Vary: Authorization` header
- Consider edge-side includes (ESI) for personalized content

## Configuration

### Environment Variables
```bash
PAGINATION_DEFAULT_PER_PAGE=25
PAGINATION_MAX_PAGE_ALLOWED=1000
PAGINATION_MAX_PER_PAGE=100
```

### Application Config
```python
app.config['PAGINATION_CONFIG'] = {
    'default_per_page': 25,
    'max_page_allowed': 1000,
    'max_per_page': 100,
    'min_per_page': 1
}
```

## Performance Considerations

### Database Optimization
- **Cursor-Based Pagination**: For very large datasets, consider cursor-based pagination instead of offset-based
- **Indexed Columns**: Ensure all sort columns are indexed
- **Query Optimization**: Use `EXPLAIN` to verify query plans

### Caching Strategy
- **Public Content**: Cache canonical URLs with appropriate TTL
- **User Content**: Use user-specific cache keys or disable caching
- **Cache Invalidation**: Implement cache invalidation on data updates

## Troubleshooting

### Issue: Duplicate items across pages
**Solution**: Ensure deterministic ordering is applied (secondary sort key)

### Issue: Missing items between pages
**Solution**: Check for concurrent data modifications; consider cursor-based pagination

### Issue: High database load
**Solution**: Reduce `max_page_allowed`, implement rate limiting, consider cursor-based pagination

### Issue: Cache serving wrong user's data
**Solution**: Ensure `Cache-Control: private` and `Vary: Authorization` headers are set

## License

This project is provided as-is for production use in Flask applications.

## Contributing

When contributing, ensure:
1. All tests pass
2. New test cases are added for edge cases
3. Documentation is updated
4. Code follows PEP 8 style guidelines

