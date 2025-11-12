"""
Centralized pagination parameter normalization and validation module.

This module provides robust handling of pagination parameters across heterogeneous
environments, including duplicate parameters, malformed inputs, array encodings,
and parameter aliases.
"""

import re
from typing import Dict, List, Optional, Tuple, Any
from flask import Request
from urllib.parse import urlencode, parse_qs, urlparse, urlunparse


class PaginationConfig:
    """Configuration for pagination normalization."""
    
    def __init__(
        self,
        default_per_page: int = 25,
        max_page_allowed: int = 1000,
        max_per_page: int = 100,
        min_per_page: int = 1
    ):
        self.default_per_page = default_per_page
        self.max_page_allowed = max_page_allowed
        self.max_per_page = max_per_page
        self.min_per_page = min_per_page
        
        # Canonical parameter mappings
        self.page_aliases = ["page", "p"]
        self.per_page_aliases = ["per_page", "limit", "size"]
        self.offset_aliases = ["offset", "start"]


class NormalizedPaginationParams:
    """Container for normalized pagination parameters."""
    
    def __init__(self, page: int, per_page: int, offset: int = None):
        self.page = page
        self.per_page = per_page
        self.offset = offset  # Calculated offset for SQL queries
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            "page": self.page,
            "per_page": self.per_page
        }
        if self.offset is not None:
            result["offset"] = self.offset
        return result
    
    def __repr__(self) -> str:
        return f"NormalizedPaginationParams(page={self.page}, per_page={self.per_page}, offset={self.offset})"


class PaginationNormalizer:
    """Main normalization engine for pagination parameters."""
    
    def __init__(self, config: Optional[PaginationConfig] = None):
        self.config = config or PaginationConfig()
    
    def normalize_pagination_params(
        self,
        request: Request,
        config: Optional[PaginationConfig] = None
    ) -> Tuple[NormalizedPaginationParams, Dict[str, Any]]:
        """
        Normalize pagination parameters from a Flask request.
        
        Returns:
            Tuple of (NormalizedPaginationParams, metadata_dict)
            metadata_dict contains information about detected issues and fixes applied.
        """
        if config is None:
            config = self.config
            
        metadata = {
            "issues_detected": [],
            "fixes_applied": [],
            "original_params": {}
        }
        
        # Extract all raw parameters
        raw_params = self._extract_raw_params(request, metadata)
        
        # Normalize page parameter
        page = self._normalize_page(raw_params, config, metadata)
        
        # Normalize per_page parameter
        per_page = self._normalize_per_page(raw_params, config, metadata)
        
        # Handle offset/limit conversion if present
        if self._has_offset_limit(raw_params):
            page, per_page = self._convert_offset_limit(
                raw_params, page, per_page, config, metadata
            )
        
        # Calculate SQL offset
        offset = (page - 1) * per_page
        
        normalized = NormalizedPaginationParams(page, per_page, offset)
        
        return normalized, metadata
    
    def _extract_raw_params(
        self,
        request: Request,
        metadata: Dict[str, Any]
    ) -> Dict[str, List[str]]:
        """Extract all pagination-related parameters from request."""
        raw_params = {}
        
        # Get all query parameters
        all_params = request.args.to_dict(flat=False)
        
        # Extract page-related parameters
        for alias in self.config.page_aliases:
            if alias in all_params:
                raw_params[alias] = all_params[alias]
                metadata["original_params"][alias] = all_params[alias]
        
        # Extract array-encoded page parameters (e.g., page[]=2&page[]=3)
        for key in all_params.keys():
            if key.startswith("page[") or key.startswith("p["):
                raw_params[key] = all_params[key]
                metadata["original_params"][key] = all_params[key]
                metadata["issues_detected"].append(f"Array-encoded parameter detected: {key}")
        
        # Extract per_page-related parameters
        for alias in self.config.per_page_aliases:
            if alias in all_params:
                raw_params[alias] = all_params[alias]
                metadata["original_params"][alias] = all_params[alias]
        
        # Extract offset-related parameters
        for alias in self.config.offset_aliases:
            if alias in all_params:
                raw_params[alias] = all_params[alias]
                metadata["original_params"][alias] = all_params[alias]
        
        return raw_params
    
    def _normalize_page(
        self,
        raw_params: Dict[str, List[str]],
        config: PaginationConfig,
        metadata: Dict[str, Any]
    ) -> int:
        """Normalize page parameter, handling duplicates, arrays, and invalid values."""
        page_values = []
        
        # Collect all page values from canonical aliases
        for alias in config.page_aliases:
            if alias in raw_params:
                page_values.extend(raw_params[alias])
        
        # Handle array-encoded parameters (e.g., page[]=2&page[]=3)
        for key in raw_params.keys():
            if key.startswith("page[") or key.startswith("p["):
                page_values.extend(raw_params[key])
                metadata["fixes_applied"].append(f"Mapped array parameter {key} to page")
        
        # Detect duplicates
        if len(page_values) > 1:
            metadata["issues_detected"].append(
                f"Duplicate page parameters detected: {page_values}"
            )
            metadata["fixes_applied"].append(
                f"Using first valid page value: {page_values[0]}"
            )
        
        # Process first valid integer value
        for value in page_values:
            normalized = self._safe_int_parse(value, default=None)
            if normalized is not None and normalized > 0:
                # Apply bounds
                if normalized > config.max_page_allowed:
                    metadata["issues_detected"].append(
                        f"Page {normalized} exceeds max_page_allowed ({config.max_page_allowed})"
                    )
                    metadata["fixes_applied"].append(
                        f"Clamped page to {config.max_page_allowed}"
                    )
                    return config.max_page_allowed
                return normalized
        
        # No valid page found, default to 1
        if page_values:
            metadata["issues_detected"].append(
                f"Invalid page values: {page_values}, defaulting to 1"
            )
        else:
            metadata["fixes_applied"].append("No page parameter found, defaulting to 1")
        
        return 1
    
    def _normalize_per_page(
        self,
        raw_params: Dict[str, List[str]],
        config: PaginationConfig,
        metadata: Dict[str, Any]
    ) -> int:
        """Normalize per_page parameter."""
        per_page_values = []
        
        # Collect all per_page values from canonical aliases
        for alias in config.per_page_aliases:
            if alias in raw_params:
                per_page_values.extend(raw_params[alias])
        
        # Detect duplicates
        if len(per_page_values) > 1:
            metadata["issues_detected"].append(
                f"Duplicate per_page parameters detected: {per_page_values}"
            )
            metadata["fixes_applied"].append(
                f"Using first valid per_page value: {per_page_values[0]}"
            )
        
        # Process first valid integer value
        for value in per_page_values:
            normalized = self._safe_int_parse(value, default=None)
            if normalized is not None:
                # Apply bounds
                if normalized > config.max_per_page:
                    metadata["issues_detected"].append(
                        f"per_page {normalized} exceeds max_per_page ({config.max_per_page})"
                    )
                    metadata["fixes_applied"].append(
                        f"Clamped per_page to {config.max_per_page}"
                    )
                    return config.max_per_page
                if normalized < config.min_per_page:
                    metadata["issues_detected"].append(
                        f"per_page {normalized} below min_per_page ({config.min_per_page})"
                    )
                    metadata["fixes_applied"].append(
                        f"Clamped per_page to {config.min_per_page}"
                    )
                    return config.min_per_page
                return normalized
        
        # No valid per_page found, use default
        return config.default_per_page
    
    def _has_offset_limit(self, raw_params: Dict[str, List[str]]) -> bool:
        """Check if request contains offset/limit parameters."""
        return any(alias in raw_params for alias in self.config.offset_aliases) or \
               "limit" in raw_params
    
    def _convert_offset_limit(
        self,
        raw_params: Dict[str, List[str]],
        current_page: int,
        current_per_page: int,
        config: PaginationConfig,
        metadata: Dict[str, Any]
    ) -> Tuple[int, int]:
        """Convert offset/limit to page/per_page if present."""
        offset = None
        limit = None
        
        # Extract offset
        for alias in config.offset_aliases:
            if alias in raw_params:
                offset_val = self._safe_int_parse(raw_params[alias][0], default=None)
                if offset_val is not None and offset_val >= 0:
                    offset = offset_val
                    break
        
        # Extract limit
        if "limit" in raw_params:
            limit_val = self._safe_int_parse(raw_params["limit"][0], default=None)
            if limit_val is not None and limit_val > 0:
                limit = limit_val
        
        # Convert offset/limit to page/per_page
        if offset is not None and limit is not None:
            metadata["fixes_applied"].append(
                f"Converting offset={offset}, limit={limit} to page/per_page"
            )
            # page = (offset / limit) + 1
            calculated_page = (offset // limit) + 1
            calculated_per_page = limit
            
            # Use converted values if they override current values
            # (offset/limit takes precedence if both are present)
            if calculated_page > 0:
                current_page = calculated_page
            if calculated_per_page > 0:
                current_per_page = calculated_per_page
        elif offset is not None:
            # Only offset provided, convert using current per_page
            calculated_page = (offset // current_per_page) + 1
            if calculated_page > 0:
                current_page = calculated_page
                metadata["fixes_applied"].append(
                    f"Converting offset={offset} to page={current_page} (using per_page={current_per_page})"
                )
        elif limit is not None:
            # Only limit provided, use as per_page
            current_per_page = limit
            metadata["fixes_applied"].append(
                f"Converting limit={limit} to per_page={current_per_page}"
            )
        
        return current_page, current_per_page
    
    def _safe_int_parse(self, value: str, default: Optional[int] = None) -> Optional[int]:
        """
        Safely parse an integer from a string, handling empty strings and invalid values.
        
        Returns None for invalid values, allowing caller to handle defaults.
        """
        if not value or not isinstance(value, str):
            return default
        
        value = value.strip()
        if not value:
            return default
        
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    def build_canonical_url(
        self,
        base_url: str,
        page: int,
        per_page: int,
        preserve_other_params: bool = True,
        other_params: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build a canonical URL with exactly one page and per_page parameter.
        
        Args:
            base_url: Base URL without query string
            page: Page number
            per_page: Items per page
            preserve_other_params: Whether to preserve non-pagination query params
            other_params: Additional parameters to include (excluding pagination params)
        """
        parsed = urlparse(base_url)
        query_params = {}
        
        # Preserve other query parameters if requested
        if preserve_other_params and parsed.query:
            existing_params = parse_qs(parsed.query, keep_blank_values=False)
            for key, values in existing_params.items():
                # Exclude pagination-related parameters
                if key not in self.config.page_aliases + \
                             self.config.per_page_aliases + \
                             self.config.offset_aliases and \
                   not key.startswith("page[") and not key.startswith("p["):
                    query_params[key] = values[0] if len(values) == 1 else values
        
        # Add additional parameters
        if other_params:
            for key, value in other_params.items():
                if key not in self.config.page_aliases + \
                             self.config.per_page_aliases + \
                             self.config.offset_aliases:
                    query_params[key] = value
        
        # Add canonical pagination parameters
        query_params["page"] = str(page)
        if per_page != self.config.default_per_page:
            query_params["per_page"] = str(per_page)
        
        # Rebuild URL
        new_query = urlencode(query_params, doseq=True)
        new_parsed = parsed._replace(query=new_query)
        return urlunparse(new_parsed)


# Convenience function for direct use
def normalize_pagination_params(
    request: Request,
    config: Optional[PaginationConfig] = None
) -> Tuple[NormalizedPaginationParams, Dict[str, Any]]:
    """
    Convenience function to normalize pagination parameters.
    
    Usage:
        from request_normalizer import normalize_pagination_params
        
        @app.route('/explore')
        def explore():
            params, metadata = normalize_pagination_params(request)
            # Use params.page, params.per_page, params.offset
    """
    normalizer = PaginationNormalizer(config)
    return normalizer.normalize_pagination_params(request, config)

