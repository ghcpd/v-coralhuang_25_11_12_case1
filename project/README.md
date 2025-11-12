# Pagination Normalizer for Flask + SQLAlchemy

✅ Overview

This project provides a request normalization and pagination helper for Flask applications that use SQLAlchemy. It addresses common production issues caused by heterogeneous upstreams — duplicate query parameters, array-encoded parameters, malformed values, extreme offsets, and caching inconsistencies — by producing a canonical form of pagination inputs and canonical URLs.

💡 What this normalizer does

- Normalizes duplicated query parameters, picking the first valid integer occurrence.
- Maps alias parameters (p, limit, size) into canonical `page` and `per_page` values.
- Supports offset/limit to page/per_page conversion.
- Handles array-encoded parameters like `page[]`.
- Clamps `page` and `per_page` to configurable upper bounds to avoid heavy DB OFFSET scans.
- Provides a helper to enforce deterministic ordering (append `id` tiebreaker) to avoid stable pagination issues.
- Builds a canonical URL that contains only one `page` and `per_page` parameter for consistent caching.

📦 Files

- `request_normalizer.py` — Normalizes inputs and provides canonical URL generation.
- `models.py` — Pagination helpers and deterministic ordering enforcement for SQLAlchemy queries.
- `test_pagination_consistency.py` — Tests that validate malformed inputs and normalization rules.
- `mock_gateway.py` — Optional tool to simulate upstream duplication and reordering.
- `run_test.sh` / `run_test.bat` — Scripts to run tests and generate logs.
- `Dockerfile` — Containerized environment for reproducible tests.

🔧 Operational Recommendations

- Add short caching header controls for user-dependent feeds, or include an identity key in cache keys.
- Consider cursor-based pagination for large datasets to avoid high-offset scans.
- Use `enforce_deterministic_order` to add stable tie-breakers to time-ordered queries.
- Centralize the normalizer in middleware to ensure every route uses canonical params for links and caching.

---
