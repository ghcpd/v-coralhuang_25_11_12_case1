from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl

from flask import Request

# Configurable defaults
MAX_PAGE_ALLOWED = 1000
MAX_PER_PAGE = 100
DEFAULT_PER_PAGE = 25
CANONICAL_PAGE_PARAM = "page"
CANONICAL_PER_PAGE_PARAM = "per_page"

PAGE_ALIASES = ["page", "p"]
PER_PAGE_ALIASES = ["per_page", "limit", "size"]
OFFSET_ALIASES = ["offset", "start"]
ARRAY_PAGE_KEYS = ["page[]", "page"]


class NormalizedPagination:
    def __init__(self, page=1, per_page=DEFAULT_PER_PAGE, offset=None, limit=None, canonical_url=None):
        self.page = page
        self.per_page = per_page
        self.offset = offset
        self.limit = limit
        self.canonical_url = canonical_url

    def as_dict(self):
        return {
            "page": self.page,
            "per_page": self.per_page,
            "offset": self.offset,
            "limit": self.limit,
            "canonical_url": self.canonical_url,
        }


def _first_valid_int(values, default=None):
    if values is None:
        return default
    for v in values:
        if v is None or v == "":
            continue
        try:
            return int(v)
        except (ValueError, TypeError):
            continue
    return default


def clamp(value, min_value, max_value):
    return max(min_value, min(max_value, value))


def build_canonical_url(raw_url: str, canonical_params: dict):
    """Reconstruct canonical URL including only canonical pagination params.

    raw_url: path+query or full URL
    canonical_params: dict of keys and values to include in generated URL
    """
    # Split URL
    scheme, netloc, path, query, fragment = urlsplit(raw_url)
    if not path:
        # If the raw_url is only a path with query, urlsplit treats it as path
        path = raw_url if raw_url.startswith("/") else path

    # Keep other non-pagination query params from raw_url but normalize page/per_page
    existing = dict(parse_qsl(query, keep_blank_values=True))
    # Merge canonical
    for k in list(existing.keys()):
        if k in PAGE_ALIASES + PER_PAGE_ALIASES + OFFSET_ALIASES + ["page[]"]:
            del existing[k]
    existing.update({k: str(v) for k, v in canonical_params.items() if v is not None})

    new_query = urlencode(existing)
    return urlunsplit((scheme, netloc, path, new_query, fragment))


def is_user_dependent_request(request: Request, user_identity_query_keys=None):
    """Return True if request depends on user identity and therefore should be cache-key isolated.

    user_identity_query_keys: list of query keys that indicate user-specific requests (e.g. 'user', 'username').
    """
    if user_identity_query_keys is None:
        user_identity_query_keys = ["user", "username", "user_id"]

    for key in user_identity_query_keys:
        if key in request.args:
            return True
    # Also consider session cookies in a real app; here we only check query args
    return False


def normalize_pagination_params(request: Request, max_page_allowed=MAX_PAGE_ALLOWED, max_per_page=MAX_PER_PAGE):
    """Normalize pagination inputs from a Flask Request object.

    Returns NormalizedPagination.
    - Duplicate keys: use the first valid integer in the list of values
    - Arrays (page[]): map first entry to single page
    - Aliases (p -> page, size/limit -> per_page)
    - Offset/limit: convert to page/per_page
    - Empty/blank/non-int: fallback to defaults
    - Clamp values to [1..max_page_allowed] and [1..max_per_page]
    - Generate canonical URL containing only a single page/per_page parameter
    """
    args = request.args

    # Collect alias values
    page_vals = []
    per_page_vals = []
    offset_vals = []
    limit_vals = []

    # Flask's MultiDict returns list when using getlist
    for alias in PAGE_ALIASES + ["page[]"]:
        page_vals.extend(args.getlist(alias))

    for alias in PER_PAGE_ALIASES:
        per_page_vals.extend(args.getlist(alias))

    for alias in OFFSET_ALIASES:
        offset_vals.extend(args.getlist(alias))

    limit_vals.extend(args.getlist("limit"))

    # Detect presence of array encoded keys like 'page[]' and fallback
    page = _first_valid_int(page_vals, default=None)
    per_page = _first_valid_int(per_page_vals, default=None)
    offset = _first_valid_int(offset_vals, default=None)
    limit = _first_valid_int(limit_vals, default=None)

    # If offset/limit are present and page not supplied, convert
    if page is None and offset is not None and limit is not None and limit > 0:
        # Page is 1-indexed
        page = (offset // limit) + 1
        per_page = limit if per_page is None else per_page

    if page is None:
        page = 1

    if per_page is None:
        per_page = DEFAULT_PER_PAGE

    # Clamp
    try:
        page = int(page)
    except (ValueError, TypeError):
        page = 1

    try:
        per_page = int(per_page)
    except (ValueError, TypeError):
        per_page = DEFAULT_PER_PAGE

    page = clamp(page, 1, max_page_allowed)
    per_page = clamp(per_page, 1, max_per_page)

    # Build canonical URL
    # Use request.url to preserve path
    canonical_params = {CANONICAL_PAGE_PARAM: page, CANONICAL_PER_PAGE_PARAM: per_page}
    canonical_url = build_canonical_url(request.url, canonical_params)

    return NormalizedPagination(page=page, per_page=per_page, offset=offset, limit=limit, canonical_url=canonical_url)
