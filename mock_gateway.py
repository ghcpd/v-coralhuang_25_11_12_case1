"""
mock_gateway.py

A simple harness that replays query string anomalies to test the normalization logic.
This is NOT a full HTTP proxy; it constructs a mapping that `request_normalizer.normalize_from_mapping`
consumes to validate results.
"""
import random
from request_normalizer import normalize_from_mapping

TEST_CASES = [
    {"page": ["3", "2"]},
    {"page[]": ["2", "3"], "per_page": ["20"]},
    {"offset": ["2000"], "limit": ["25"]},
    {"page": [""], "per_page": ["25"]},
]


def fuzz_and_normalize(case):
    # simulate reordering by random shuffle
    keys = list(case.keys())
    random.shuffle(keys)
    mapping = {}
    for k in keys:
        mapping[k] = case[k]
    return normalize_from_mapping(mapping)


if __name__ == "__main__":
    for case in TEST_CASES:
        print(case, "->", fuzz_and_normalize(case))
