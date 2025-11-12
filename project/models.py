from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import desc, asc

# Initialize SQLAlchemy (in app runtime this would be set by app)
db = SQLAlchemy()


def enforce_deterministic_order(query, primary_ordering, model, descending=True):
    """Ensure deterministic ordering by appending a stable secondary sort key (id).

    primary_ordering: a SQLAlchemy ordering expression, e.g., Post.timestamp.desc()
    model: the model class, used to access id column
    descending: bool interpreted for secondary key
    """
    if descending:
        secondary = desc(getattr(model, "id"))
    else:
        secondary = asc(getattr(model, "id"))

    # Primary ordering may be either expression or list
    if isinstance(primary_ordering, (list, tuple)):
        orderings = list(primary_ordering) + [secondary]
    else:
        orderings = [primary_ordering, secondary]

    return query.order_by(*orderings)


def paginate_safe(query, page, per_page, max_page_allowed=1000, max_per_page=100):
    """Safely paginate a SQLAlchemy query.

    - Enforce upper bounds
    - If page >= max_page_allowed, return empty results or short-circuit avoid heavy OFFSET
    - Return dict with items and metadata for href generation
    """
    page = max(1, min(page, max_page_allowed))
    per_page = max(1, min(per_page, max_per_page))

    # If page is at the upper bound use a lightweight fetch to check if items exist
    if page == max_page_allowed:
        # No heavy offsets: use an indexed query that fetches first per_page items starting after some marker.
        # For the purposes of this helper, we will fall back to offset but the production system should instead rely
        # on cursor-based paginated endpoints. We will also return an empty list to avoid heavy scanning.
        return {
            "items": [],
            "page": page,
            "per_page": per_page,
            "total": None,
        }

    items = query.limit(per_page).offset((page - 1) * per_page).all()

    return {
        "items": items,
        "page": page,
        "per_page": per_page,
        "total": None,
    }
