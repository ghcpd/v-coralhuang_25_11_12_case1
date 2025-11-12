# Pagination Normalization Audit

✅ This project demonstrates a robust pagination normalization and deterministic ordering approach for a Flask + SQLAlchemy application.

Highlights
- Detects duplicated page parameters and resolves to the first valid integer
- Supports alias parameters (`p`, `limit`, `size`, `offset`, `start`) and `page[]` array encodings
- Clamps negative and abusive values: `page <= 0` -> `page=1`; `page > MAX_PAGE_ALLOWED` -> `MAX_PAGE_ALLOWED`
- Enforces `max_per_page` to avoid expensive responses
- Adds deterministic tie-break sorting for timestamp-only orderings: `timestamp DESC, id DESC`
- Provides canonical URL generation and request-scoped cache keys (user-aware)
- Offers a small mock gateway to simulate duplications and tests to validate normalization logic

Files
- `request_normalizer.py` — central normalization helpers
- `models.py` — SQLAlchemy model with deterministic query helper and safe pagination
- `app.py` — demonstration endpoint using the normalizer
- `tests/test_pagination_consistency.py` — tests covering malformed, duplicated, alias, and resource-protection cases
- `run_test.sh` / `run_test.bat` — scripts to run tests and generate `output.json`
- `mock_gateway.py` — simulate upstream duplicates or reordering
- `Dockerfile` — containerized testing image

Operational recommendations
- Mark user-dependent views as non-cacheable or rewrite cache keys to incorporate user id
- Use canonical URLs in the app responses and pagination links, e.g., `/explore?page=3&per_page=25`
- Clamp upper bounds and support keyset-based alternatives for extremely high offsets
- Add a deterministic secondary sort key to ordering to guarantee page stability across refreshes

Run tests
- On macOS/Linux: `./run_test.sh`
- On Windows: `.\run_test.bat`

