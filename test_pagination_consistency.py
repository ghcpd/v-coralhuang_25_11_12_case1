import pytest
from datetime import datetime

from request_normalizer import normalize_from_mapping, normalize_pagination_params
from models import create_in_memory_db, Post, apply_deterministic_sort, safe_paginate_query


def test_duplicate_page_params_normalized_first():
    result = normalize_from_mapping({"page": ["3", "2"], "sort": ["ts_desc"]})
    assert result["page"] == 3
    assert result["canonical_query"]["page"] == 3


def test_negative_page_clamped_to_one():
    result = normalize_from_mapping({"page": ["-1"]})
    assert result["page"] == 1


def test_excessive_page_truncated_at_max():
    result = normalize_from_mapping({"page": ["999999"]})
    assert result["page"] == 1000
    assert result["truncated"] is True


def test_duplicate_from_template_and_spa():
    result = normalize_from_mapping({"page": ["4", "5"]})
    assert result["page"] == 4


def test_missing_page_default_to_one():
    result = normalize_from_mapping({})
    assert result["page"] == 1


def test_array_encoded_page_first_element():
    result = normalize_from_mapping({"page[]": ["2", "3"], "per_page": ["20"]})
    assert result["page"] == 2
    assert result["per_page"] == 20


def test_hybrid_offset_limit_client():
    result = normalize_from_mapping({"offset": ["50"], "limit": ["25"]})
    assert result["page"] == 3
    assert result["per_page"] == 25
    assert result["from_offset"] is True


def test_empty_page_param_falls_back():
    result = normalize_from_mapping({"page": [""]})
    assert result["page"] == 1


def test_timestamp_tie_breaking_deterministic_order():
    session = create_in_memory_db()

    # Create 5 posts with identical timestamps
    now = datetime(2025, 11, 11, 12, 0, 0)
    for i in range(1, 6):
        p = Post(id=i, title=f"post {i}", timestamp=now)
        session.add(p)
    session.commit()

    # Base query ordered by timestamp desc
    from sqlalchemy import desc

    q = session.query(Post)
    q = q.order_by(desc(Post.timestamp))

    # Apply deterministic sorter to ensure id desc tiebreak
    q = apply_deterministic_sort(q, [desc(Post.timestamp)])
    items = q.all()

    # Because we enforced id DESC tiebreaker, highest id should be first
    assert items[0].id == 5
    assert items[-1].id == 1


def test_cache_isolation_hint_detected_for_user_sensitive():
    result = normalize_from_mapping({"page": ["2"], "user": ["alice"]})
    assert result["page"] == 2
    assert result["cache_isolation_required"] is True
    assert ("user", "alice") in result["cache_key_components"]


def test_per_page_alias_mapping_and_inconsistent_alias():
    # p=4 maps to page=4; size=10 maps to per_page
    result = normalize_from_mapping({"p": ["4"], "size": ["10"]})
    assert result["page"] == 4
    assert result["per_page"] == 10


def test_malformed_param_fallback():
    # page=abc -> fallback to page 1 but per_page preserved
    result = normalize_from_mapping({"page": ["abc"], "per_page": ["50"]})
    assert result["page"] == 1
    assert result["per_page"] == 50


def test_abusive_pagination_sanitized():
    result = normalize_from_mapping({"page": ["5000000"], "per_page": ["5000"]})
    # Should clamp per_page to max and page to max_page_allowed
    assert result["page"] == 1000
    assert result["per_page"] == 100


def test_safe_paginate_prevents_extreme_offset():
    session = create_in_memory_db()
    # add a few rows
    for i in range(10):
        session.add(Post(title=f"post {i+1}"))
    session.commit()
    q = session.query(Post)
    items, total = safe_paginate_query(q, page=1000000, per_page=10)
    assert items == []
