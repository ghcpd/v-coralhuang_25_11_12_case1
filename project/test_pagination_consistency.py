import pytest
from flask import Flask, request
from project.request_normalizer import normalize_pagination_params, MAX_PAGE_ALLOWED, MAX_PER_PAGE


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config['TESTING'] = True
    return app


def _norm_for_url(app, url):
    with app.test_request_context(url):
        norm = normalize_pagination_params(request)
        return norm


def test_duplicate_page_params_first_takes_precedence(app):
    url = "/explore?page=3&sort=ts_desc&filter=followed&page=2"
    norm = _norm_for_url(app, url)
    assert norm.page == 3
    assert "page=3" in norm.canonical_url
    assert "page=2" not in norm.canonical_url


def test_negative_page_number_clamped(app):
    url = "/index?page=-1"
    norm = _norm_for_url(app, url)
    assert norm.page == 1


def test_excessive_page_offset_truncated(app):
    url = "/explore?page=999999"
    norm = _norm_for_url(app, url)
    assert norm.page <= MAX_PAGE_ALLOWED


def test_array_encoded_page_maps_first(app):
    url = "/explore?page[]=2&page[]=3&per_page=20"
    norm = _norm_for_url(app, url)
    assert norm.page == 2
    assert norm.per_page == 20


def test_offset_limit_converted_to_page(app):
    url = "/api/feed?offset=50&limit=25"
    norm = _norm_for_url(app, url)
    assert norm.per_page == 25
    assert norm.page == 3  # (offset 50 / 25) + 1


def test_empty_page_param_fallback(app):
    url = "/explore?page=&per_page=25"
    norm = _norm_for_url(app, url)
    assert norm.page == 1


def test_missing_page_param_returns_default(app):
    url = "/user/jack"
    norm = _norm_for_url(app, url)
    assert norm.page == 1


def test_malformed_page_param_fallback(app):
    url = "/explore?page=abc&per_page=50"
    norm = _norm_for_url(app, url)
    assert norm.page == 1
    assert norm.per_page == 50


def test_permalink_canonicalization(app):
    url = "/explore?page=4&page=5"
    norm = _norm_for_url(app, url)
    assert norm.page == 4
    assert norm.canonical_url.count('page=') == 1


def test_abusive_pagination_truncation(app):
    url = f"/explore?page=5000000&per_page=5000"
    norm = _norm_for_url(app, url)
    assert norm.page <= MAX_PAGE_ALLOWED
    assert norm.per_page <= MAX_PER_PAGE


def test_deterministic_ordering(app, tmp_path):
    # Create an in-memory DB and model to test ordering
    from project.models import db, enforce_deterministic_order
    from flask_sqlalchemy import SQLAlchemy
    from datetime import datetime
    
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    class Post(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        timestamp = db.Column(db.Integer, nullable=False)

    with app.app_context():
        db.create_all()
        # Insert posts with identical timestamps
        for i in range(1, 6):
            p = Post(id=i, timestamp=1000)
            db.session.add(p)
        db.session.commit()

        # Order by timestamp desc without secondary sort
        q = Post.query.order_by(db.desc(Post.timestamp))
        ids_no_secondary = [p.id for p in q.all()]

        # With deterministic enforcement
        q2 = enforce_deterministic_order(Post.query, db.desc(Post.timestamp), Post, descending=True)
        ids_with_secondary = [p.id for p in q2.all()]

        # ids_with_secondary should be ordered by id DESC (5..1)
        assert ids_with_secondary == [5,4,3,2,1]

        # ids_no_secondary should be a permutation of the same IDs but not guaranteed order
        assert set(ids_no_secondary) == set(ids_with_secondary)


def test_cache_key_suggestion(app):
    # Ensure canonical URL includes only one page param — for cache-keying, include user key
    import json
    from project.request_normalizer import build_canonical_url, is_user_dependent_request
    raw = '/explore?page=2&page=3&user=alice'
    canonical = build_canonical_url(raw, {'page':2, 'per_page':25})
    assert canonical.count('page=') == 1
    assert 'user=alice' in canonical

    # is_user_dependent_request should detect user query keys and indicate cache isolation
    with app.test_request_context(raw):
        assert is_user_dependent_request(request) is True
