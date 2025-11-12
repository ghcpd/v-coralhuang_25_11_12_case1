"""
Centralize pagination normalization helpers.
"""
from typing import Dict, Tuple, Any
import math

DEFAULTS = {
    "page": 1,
    "per_page": 25,
}

class NormalizationError(Exception):
    pass


CANONICALS = {
    "page": ["page", "p", "page[]", "page[]"],
    "per_page": ["per_page", "limit", "size"],
    "offset": ["offset", "start"],
}


def _first_valid_int(values, default=None):
    if not values:
        return default
    for v in values:
        if v is None or v == "":
            continue
        try:
            return int(v)
        except Exception:
            continue
    return default


def normalize_pagination_params(args: Dict[str, Any], *, per_page_default=25, max_page_allowed=1000, max_per_page=100) -> Dict[str, Any]:
    """
    args may be a mapping from key to list of strings (multi-dict / raw args representation).

    Returns canonical structure:
    {
        "page": int >= 1 and <= max_page_allowed,
        "per_page": int >= 1 and <= max_per_page,
        "offset": int or None,
        "canonical_query": {"page": page, "per_page": per_page},
        "clamped": bool,  # whether any value was clamped/truncated
    }
    """
    canonical = {"page": None, "per_page": None, "offset": None, "clamped": False}

    # gather values for page from aliases, arrays etc.
    raw_page_vals = []
    for alias in CANONICALS["page"]:
        if alias in args:
            val = args[alias]
            if isinstance(val, (list, tuple)):
                raw_page_vals.extend(val)
            else:
                raw_page_vals.append(val)

    # also handle array style param names like 'page[]' if present
    if "page[]" in args and isinstance(args["page[]"], (list, tuple)):
        raw_page_vals.extend(args["page[]"])

    page_val = _first_valid_int(raw_page_vals, None)

    # if no page found, look for offset+limit
    offset_val = None
    limit_val = None
    raw_offset_vals = []
    raw_limit_vals = []
    for alias in CANONICALS["offset"]:
        if alias in args:
            val = args[alias]
            raw_offset_vals.extend(val if isinstance(val, (list, tuple)) else [val])
    for alias in CANONICALS["per_page"]:
        if alias in args:
            val = args[alias]
            raw_limit_vals.extend(val if isinstance(val, (list, tuple)) else [val])

    offset_val = _first_valid_int(raw_offset_vals, None)
    limit_val = _first_valid_int(raw_limit_vals, None)

    if page_val is None and offset_val is not None and limit_val is not None and limit_val > 0:
        # compute page from offset + limit
        page_val = offset_val // limit_val + 1
        per_page_val = limit_val
    else:
        per_page_val = _first_valid_int(raw_limit_vals, per_page_default)

    if page_val is None:
        page_val = per_page_default and 1 or 1

    # apply defaults and bounds
    if page_val <= 0:
        page_val = 1
        canonical["clamped"] = True
    if page_val > max_page_allowed:
        page_val = max_page_allowed
        canonical["clamped"] = True

    if per_page_val is None:
        per_page_val = per_page_default
    if per_page_val <= 0:
        per_page_val = per_page_default
        canonical["clamped"] = True
    if per_page_val > max_per_page:
        per_page_val = max_per_page
        canonical["clamped"] = True

    canonical.update({"page": page_val, "per_page": per_page_val, "offset": offset_val})

    # return canonical query mapping
    canonical["canonical_query"] = {"page": page_val}
    if per_page_val != per_page_default:
        canonical["canonical_query"]["per_page"] = per_page_val

    return canonical


def canonicalize_query_string(path: str, qs: Dict[str, Any]) -> str:
    """
    Given path and canonical query mapping, return normalized URL query string.
    """
    parts = []
    if qs.get("page") is not None:
        parts.append(f"page={qs['page']}")
    if qs.get("per_page") is not None:
        parts.append(f"per_page={qs['per_page']}")
    if parts:
        return f"{path}?{'&'.join(parts)}"
    return path


# Utility: produce a cache key string that includes user id for user-dependent routes

def generate_cache_key(path: str, qs: Dict[str, Any], user_id: Any = None) -> str:
    key = f"{path}::page={qs.get('page')}::per_page={qs.get('per_page')}"
    if user_id is not None:
        key = f"user:{user_id}::{key}"
    return key
