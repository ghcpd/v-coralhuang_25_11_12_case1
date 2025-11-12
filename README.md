# Pagination Normalization and Audit

This project implements a robust request normalization layer and pagination helpers for Flask + SQLAlchemy-based apps.

Key features
- Normalizes duplicate, empty, and indexed parameters (e.g., page[]=2) to a single canonical page value
- Maps offset/limit semantics to canonical page/per_page
- Enforces numeric bounds to avoid abusive offsets (max_page_allowed, max_per_page)
- Produces canonical query fragments for internal links (exactly one page parameter)
- Detects user-dependent requests and recommends cache isolation
- Adds deterministic ordering via secondary sort keys (e.g., id DESC) for stable pagination

Files
- `request_normalizer.py` - Centralized normalization helper and heuristics
- `models.py` - SQLAlchemy model example and safe pagination helpers
- `test_pagination_consistency.py` - PyTest tests for all known anomalies
- `mock_gateway.py` - Optional test harness to emulate reversed proxy behaviors
- `Dockerfile`, `run_test.sh`, `run_test.bat` - Testing environment and script

Operational Recommendations
1. Canonicalize requests at the earliest gateway layer: enforce single page/per_page in the CDN/gateway.
2. Mark user-specific paginated endpoints as uncacheable or isolate cache key by user.
3. Use keyset pagination for deep page navigation to avoid heavy OFFSET scans.
4. Add secondary deterministic sort keys (e.g., Post.id DESC) when ordering by non-unique fields.

See `test_pagination_consistency.py` for examples and concrete expected behaviors.
