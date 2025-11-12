import json
import os
import pytest
from request_normalizer import normalize_pagination_params, canonicalize_query_string, generate_cache_key
from models import get_session, seed_posts, get_paginated_query, Post

HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, '..'))
INPUT_JSON = os.path.join(ROOT, 'input.json')


@pytest.fixture(scope='session')
def input_data():
    with open(INPUT_JSON, 'r') as fh:
        return json.load(fh)


@pytest.fixture()
def session_db():
    session = get_session()
    user = seed_posts(session, n=120)
    yield session
    session.close()


def to_args_dict(query_str: str):
    # Very simple parser that builds a dict of values similar to Flask request.args.getlist
    from urllib.parse import parse_qs
    parsed = parse_qs(query_str.lstrip('/').split('?', 1)[-1]) if '?' in query_str else {}
    # return values as lists
    return {k: v for k, v in parsed.items()}


# ---------- Scenario tests from input.json ----------

def test_duplicate_page_params(input_data):
    t = [x for x in input_data['tests'] if x['id'] == 'duplicate_page_params'][0]
    args = to_args_dict(t['request_url'])
    normalized = normalize_pagination_params(args, per_page_default=input_data['config']['per_page'], max_page_allowed=input_data['config']['max_page_allowed'], max_per_page=input_data['config']['max_per_page'])
    assert normalized['page'] == 3
    assert normalized['canonical_query']['page'] == 3


def test_negative_page_number(input_data):
    t = [x for x in input_data['tests'] if x['id'] == 'negative_page_number'][0]
    args = to_args_dict(t['request_url'])
    normalized = normalize_pagination_params(args, per_page_default=input_data['config']['per_page'], max_page_allowed=input_data['config']['max_page_allowed'], max_per_page=input_data['config']['max_per_page'])
    assert normalized['page'] == 1


def test_excessive_page_offset(input_data):
    t = [x for x in input_data['tests'] if x['id'] == 'excessive_page_offset'][0]
    args = to_args_dict(t['request_url'])
    normalized = normalize_pagination_params(args, per_page_default=input_data['config']['per_page'], max_page_allowed=input_data['config']['max_page_allowed'], max_per_page=input_data['config']['max_per_page'])
    assert normalized['page'] == input_data['config']['max_page_allowed']


def test_duplicate_from_template_and_spa(input_data):
    t = [x for x in input_data['tests'] if x['id'] == 'duplicate_from_template_and_spa'][0]
    args = to_args_dict(t['request_url'])
    normalized = normalize_pagination_params(args, per_page_default=input_data['config']['per_page'], max_page_allowed=input_data['config']['max_page_allowed'], max_per_page=input_data['config']['max_per_page'])
    assert normalized['page'] == 4


def test_missing_page_param(input_data):
    t = [x for x in input_data['tests'] if x['id'] == 'missing_page_param'][0]
    args = to_args_dict(t['request_url'])
    normalized = normalize_pagination_params(args, per_page_default=input_data['config']['per_page'], max_page_allowed=input_data['config']['max_page_allowed'], max_per_page=input_data['config']['max_per_page'])
    assert normalized['page'] == 1


def test_array_encoded_page(input_data):
    t = [x for x in input_data['tests'] if x['id'] == 'array_encoded_page'][0]
    args = to_args_dict(t['request_url'])
    normalized = normalize_pagination_params(args, per_page_default=input_data['config']['per_page'], max_page_allowed=input_data['config']['max_page_allowed'], max_per_page=input_data['config']['max_per_page'])
    assert normalized['page'] == 2
    assert normalized['per_page'] == 20


def test_hybrid_offset_limit_client(input_data):
    t = [x for x in input_data['tests'] if x['id'] == 'hybrid_offset_limit_client'][0]
    args = to_args_dict(t['request_url'])
    normalized = normalize_pagination_params(args, per_page_default=input_data['config']['per_page'], max_page_allowed=input_data['config']['max_page_allowed'], max_per_page=input_data['config']['max_per_page'])
    assert normalized['page'] == 3  # offset=50, limit=25 -> page = 50/25 + 1 = 3
    assert normalized['per_page'] == 25


def test_empty_page_param(input_data):
    t = [x for x in input_data['tests'] if x['id'] == 'empty_page_param'][0]
    args = to_args_dict(t['request_url'])
    normalized = normalize_pagination_params(args, per_page_default=input_data['config']['per_page'], max_page_allowed=input_data['config']['max_page_allowed'], max_per_page=input_data['config']['max_per_page'])
    assert normalized['page'] == 1


def test_timestamp_tie_in_feed(session_db):
    # Ensure repeated fetches of the same page return the same post ids when using deterministic ordering.
    session = session_db
    # ask for page 2 with default per_page
    q1, offset, limit, exhausted, clamped = get_paginated_query(session, Post, page=2, per_page=25)
    ids_first_round = [p.id for p in q1.all()]
    q2, _, _, _, _ = get_paginated_query(session, Post, page=2, per_page=25)
    ids_second_round = [p.id for p in q2.all()]
    assert ids_first_round == ids_second_round


def test_session_drift_cached_page(input_data):
    args = to_args_dict([x for x in input_data['tests'] if x['id'] == 'session_drift_cached_page'][0]['request_url'])
    normalized = normalize_pagination_params(args, per_page_default=input_data['config']['per_page'], max_page_allowed=input_data['config']['max_page_allowed'], max_per_page=input_data['config']['max_per_page'])
    # different user ids should change cache key
    k1 = generate_cache_key('/explore', normalized['canonical_query'], user_id='alice')
    k2 = generate_cache_key('/explore', normalized['canonical_query'], user_id='bob')
    assert k1 != k2


# ---------- error example tests ----------

def test_malformed_param(input_data):
    raw_q = 'page=abc&per_page=50'
    parsed = {k: v for k, v in [kv.split('=') for kv in raw_q.split('&')]}  # simple parse
    # convert lists
    for k, v in parsed.items():
        parsed[k] = [v]
    normalized = normalize_pagination_params(parsed, per_page_default=input_data['config']['per_page'], max_page_allowed=input_data['config']['max_page_allowed'], max_per_page=input_data['config']['max_per_page'])
    assert normalized['page'] == 1
    assert normalized['per_page'] == 50


def test_abusive_pagination(input_data):
    raw_q = 'page=5000000&per_page=5000'
    parsed = {k: v for k, v in [kv.split('=') for kv in raw_q.split('&')]}  # simple parse
    for k, v in parsed.items():
        parsed[k] = [v]
    normalized = normalize_pagination_params(parsed, per_page_default=input_data['config']['per_page'], max_page_allowed=input_data['config']['max_page_allowed'], max_per_page=input_data['config']['max_per_page'])
    assert normalized['page'] == input_data['config']['max_page_allowed']
    assert normalized['per_page'] == input_data['config']['max_per_page']


def test_inconsistent_alias(input_data):
    raw_q = 'p=4&size=10'
    parsed = {}
    for kv in raw_q.split('&'):
        k, v = kv.split('=')
        parsed.setdefault(k, []).append(v)
    normalized = normalize_pagination_params(parsed, per_page_default=input_data['config']['per_page'], max_page_allowed=input_data['config']['max_page_allowed'], max_per_page=input_data['config']['max_per_page'])
    assert normalized['page'] == 4
    assert normalized['per_page'] == 10


# ---------- misc checks ----------

def test_canonicalize_query_string():
    qs = {'page': 4, 'per_page': 30}
    s = canonicalize_query_string('/explore', qs)
    assert s == '/explore?page=4&per_page=30'


if __name__ == '__main__':
    pytest.main(['-q'])
