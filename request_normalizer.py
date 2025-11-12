"""
request_normalizer.py

Utilities for canonicalizing pagination inputs across heterogeneous clients and proxies.

Primary entrypoint:
- normalize_pagination_params(request, config=None) -> dict

Features:
- Maps aliases (p/limit/size/offset/page[])
- Picks first valid integer from duplicated params
- Handles array-encoded page[] values
- Converts offset+limit to page/per_page
- Enforces upper bounds and clamps extremes
- Produces a canonical_params dict and a canonicalized URL fragment

"""
from urllib.parse import urlencode

DEFAULT_CONFIG = {
    "per_page": 25,
    "max_page_allowed": 1000,
    "max_per_page": 100,
    "canonical_params": {
        "page": ["page", "p"],
        "per_page": ["per_page", "limit", "size"],
        "offset": ["offset", "start"],
    }
}


def _first_valid_int(values, fallback=None):
    """Return the first value from values that can be parsed as an int.

    Treat empty strings and None as invalid. Negative numbers are considered valid
    here; calling code should clamp negatives if needed.
    """
    if not values:
        return fallback
    for v in values:
        if v is None:
            continue
        vstr = str(v).strip()
        if vstr == "":
            continue
        try:
            return int(vstr)
        except (ValueError, TypeError):
            continue
    return fallback


def _get_args_for_aliases(request, aliases):
    """Return a flattened list of values for the supplied aliases in the order they appear.

    This uses request.args.getlist so repeated query parameters preserve order.
    """
    values = []
    for alias in aliases:
        # getlist returns [] if missing
        values.extend(request.args.getlist(alias))
    return values


def normalize_pagination_params(request, config=None):
    """Normalize and validate pagination params from a Flask request.

    Returns a dict with keys:
      - page: (int) 1-based page number
      - per_page: (int) items per page
      - from_offset: (bool) if page was derived from offset+limit
      - canonical_query: dict of canonical query parameters with exactly one page/per_page
      - canonical_url_fragment: query string that can be appended to a URL

    Normalization rules:
      - Choose first valid integer in each canonical parameter's aliases
      - Map offset+limit to page/per_page if page absent
      - Empty and non-int values fall back to safe defaults
      - Negative page -> 1
      - page > max_page_allowed -> clamp to max or mark as truncated
      - per_page clamped to 1..max_per_page
      - When arrays (e.g., page[]), take the first element as canonical
    """
    cfg = DEFAULT_CONFIG.copy()
    if config:
        # shallow merge
        cfg.update(config)
        if config.get("canonical_params"):
            cfg["canonical_params"].update(config["canonical_params"])

    canonical = cfg["canonical_params"]

    # Resolve per_page (limit/size) first so offset->page can use it
    per_page_aliases = canonical.get("per_page", [])
    per_page_values = _get_args_for_aliases(request, per_page_aliases)
    per_page = _first_valid_int(per_page_values, cfg["per_page"])
    if per_page is None:
        per_page = cfg["per_page"]
    # enforce bounds
    per_page = max(1, int(per_page))
    per_page = min(per_page, cfg["max_per_page"])

    # Check page aliases: include 'page[]' forms automatically
    page_aliases = list(canonical.get("page", [])) + ["page[]"]
    page_values = _get_args_for_aliases(request, page_aliases)
    page = _first_valid_int(page_values, None)

    from_offset = False
    if page is None:
        # fallback to offset/limit if present
        offset_aliases = canonical.get("offset", [])
        offset_values = _get_args_for_aliases(request, offset_aliases)
        offset = _first_valid_int(offset_values, None)
        if offset is not None and per_page:
            from_offset = True
            # offset is 0-based
            page = (offset // per_page) + 1

    # final fallback to 1
    if page is None:
        page = 1

    # clamp negative pages to 1
    page = max(1, int(page))

    truncated = False
    if cfg.get("max_page_allowed"):
        if page > cfg.get("max_page_allowed"):
            page = cfg.get("max_page_allowed")
            truncated = True

    # Build canonical query dict
    canonical_query = {"page": page, "per_page": per_page}

    # Build canonical URL fragment (single page param, one per_page param only if different from default)
    # We'll include per_page explicitly to preserve client intent; some clients rely on per_page in the link
    query_items = [("page", str(page))]
    # Only include per_page when it's not the site default to reduce URL noise
    if per_page != cfg["per_page"]:
        query_items.append(("per_page", str(per_page)))

    canonical_url_fragment = urlencode(query_items)

    return {
        "page": page,
        "per_page": per_page,
        "from_offset": from_offset,
        "truncated": truncated,
        "canonical_query": canonical_query,
        "canonical_url_fragment": canonical_url_fragment,
        "cache_isolation_required": detect_user_context_sensitive(request),
        "cache_key_components": detect_user_context_components(request),
    }


# Small helper: normalize a dict-like query mapping into canonical form (useful for gateways and tests)
def normalize_from_mapping(query_mapping, config=None):
    # query_mapping is a dict where values are lists or scalars
    class FakeRequest:
        """Minimal shim exposing request.args.getlist for the mapping"""

        def __init__(self, mapping):
            self._mapping = {}
            for k, v in mapping.items():
                if isinstance(v, list):
                    self._mapping[k] = [str(x) for x in v]
                else:
                    self._mapping[k] = [str(v)]

        @property
        def args(self):
            return self

        def getlist(self, key):
            return self._mapping.get(key, [])

    fake = FakeRequest(query_mapping)
    return normalize_pagination_params(fake, config)


# Detect user-related keys that indicate cache isolation is required
def detect_user_context_sensitive(request):
    """Heuristic to detect whether a request is user-specific and therefore must be cached
    with a user-bound cache key. Checks for common query param names and known headers.
    """
    # Common indicators
    user_keys = ["user", "username", "user_id", "session", "auth", "token"]
    for k in user_keys:
        if request.args.getlist(k):
            return True
    # Authorization in headers is a good hint
    if hasattr(request, "headers") and request.headers.get("Authorization"):
        return True
    return False


def detect_user_context_components(request):
    """Return a minimal list of query keys that should be included in a cache key.

    This can be used to narrow cache identity to only a handful of values
    rather than the entire request.
    """
    candidate_keys = ["user", "username", "user_id"]
    present = []
    for k in candidate_keys:
        vals = request.args.getlist(k)
        if vals:
            present.append((k, vals[0]))
    return present
