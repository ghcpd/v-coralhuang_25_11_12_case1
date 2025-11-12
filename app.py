from flask import Flask, request, jsonify
from models import get_session, seed_posts, Post
from request_normalizer import normalize_pagination_params, canonicalize_query_string, generate_cache_key

app = Flask(__name__)

# simple in-memory DB for demo/testing
session = get_session()
user = seed_posts(session, n=120)


@app.route("/explore")
def explore():
    # simulate current_user via query string if present for testing
    user_id = request.args.get("_uid")
    normalized = normalize_pagination_params({k: request.args.getlist(k) for k in request.args}, per_page_default=25, max_page_allowed=1000, max_per_page=100)
    page = normalized["page"]
    per_page = normalized["per_page"]
    q, offset, limit, exhausted, clamped = None, None, None, False, False

    from models import get_paginated_query
    q, offset, limit, exhausted, clamped = get_paginated_query(session, Post, page, per_page)

    posts = [p.content for p in q.all()]

    canonical_url = canonicalize_query_string(request.path, normalized["canonical_query"])
    cache_key = generate_cache_key(request.path, normalized["canonical_query"], user_id)

    resp = {
        "normalized": normalized,
        "canonical_url": canonical_url,
        "cache_key": cache_key,
        "offset": offset,
        "limit": limit,
        "clamped": clamped,
        "exhausted": exhausted,
        "posts": posts
    }
    return jsonify(resp)


if __name__ == "__main__":
    app.run(debug=True)
