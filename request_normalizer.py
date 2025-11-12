"""
Centralized pagination parameter normalization and validation module.

This module provides a unified interface for sanitizing, validating, and
normalizing pagination parameters across heterogeneous client implementations
and upstream proxies. It handles duplicates, malformed values, parameter aliases,
and enforces configurable bounds to prevent abuse and inefficiency.
"""

from typing import Dict, Tuple, Optional, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class PaginationConfig:
    """Configuration for pagination normalization."""
    default_page: int = 1
    default_per_page: int = 25
    max_page_allowed: int = 1000
    max_per_page: int = 100
    min_per_page: int = 1


@dataclass
class NormalizedPagination:
    """Result of pagination parameter normalization."""
    page: int
    per_page: int
    issues: list  # List of detected anomalies
    original_params: Dict[str, Any]
    is_modified: bool  # True if any normalization occurred


class PaginationNormalizer:
    """
    Normalizes and validates pagination parameters from Flask request objects.
    
    Responsibilities:
    - Detect and consolidate duplicate parameters
    - Handle parameter aliases (page/p, per_page/limit/size, offset/start)
    - Convert offset/limit to page/per_page
    - Enforce numeric bounds and data type safety
    - Track all normalization decisions for audit/logging
    """
    
    def __init__(self, config: Optional[PaginationConfig] = None):
        self.config = config or PaginationConfig()
    
    def normalize(self, request_args: Dict) -> NormalizedPagination:
        """
        Normalize pagination parameters from a request.
        
        Args:
            request_args: A dict-like object containing query parameters
                         (typically from Flask's request.args or request.args.to_dict(flat=False))
        
        Returns:
            NormalizedPagination object with validated page/per_page values
        """
        issues = []
        original_params = dict(request_args)
        
        # Extract and validate page parameter
        page, page_issues = self._extract_page(request_args)
        issues.extend(page_issues)
        
        # Extract and validate per_page parameter
        per_page, per_page_issues = self._extract_per_page(request_args)
        issues.extend(per_page_issues)
        
        # Check for offset/limit pattern and convert if present
        offset_issues, converted_page, converted_per_page = self._handle_offset_limit(
            request_args, page, per_page
        )
        if offset_issues:
            issues.extend(offset_issues)
            page, per_page = converted_page, converted_per_page
        
        # Apply bounds and clamping
        (page, per_page), bound_issues = self._apply_bounds(page, per_page)
        issues.extend(bound_issues)
        
        is_modified = len(issues) > 0
        
        return NormalizedPagination(
            page=page,
            per_page=per_page,
            issues=issues,
            original_params=original_params,
            is_modified=is_modified
        )
    
    def _extract_page(self, request_args: Dict) -> Tuple[int, list]:
        """
        Extract and validate the page parameter from request args.
        
        Handles:
        - Duplicate page parameters (picks first valid)
        - Parameter aliases (page, p)
        - Array-like encoding (page[])
        - Empty/null values
        - Non-integer values
        
        Returns:
            Tuple of (page: int, issues: list)
        """
        issues = []
        
        # Check for array-encoded variant (page[])
        for array_key in ["page[]", "page[0]"]:
            if array_key in request_args:
                values = request_args[array_key]
                if isinstance(values, list):
                    values = values
                else:
                    values = [values]
                
                valid_page = self._find_first_valid_integer(values)
                if valid_page is not None:
                    if len(values) > 1:
                        issues.append({
                            "type": "array_encoded_duplicates",
                            "param": array_key,
                            "raw_values": values,
                            "picked": valid_page,
                            "severity": "medium"
                        })
                    return valid_page, issues
        
        # Check canonical and aliased page parameters
        for param_name in ["page", "p"]:
            if param_name in request_args:
                values = request_args[param_name]
                if isinstance(values, list):
                    raw_values = values
                else:
                    raw_values = [values]
                
                # Check for duplicates
                if len(raw_values) > 1:
                    issues.append({
                        "type": "duplicate_page_params",
                        "param": param_name,
                        "raw_values": raw_values,
                        "picked": raw_values[0],
                        "severity": "high"
                    })
                
                # Extract first value
                valid_page = self._find_first_valid_integer(raw_values)
                if valid_page is not None:
                    return valid_page, issues
                elif len(raw_values) > 0:
                    # All values were invalid
                    issues.append({
                        "type": "invalid_page_format",
                        "param": param_name,
                        "raw_values": raw_values,
                        "severity": "high"
                    })
        
        # No page parameter found, use default
        return self.config.default_page, issues
    
    def _extract_per_page(self, request_args: Dict) -> Tuple[int, list]:
        """
        Extract and validate the per_page parameter from request args.
        
        Handles parameter aliases: per_page, limit, size
        
        Returns:
            Tuple of (per_page: int, issues: list)
        """
        issues = []
        
        # Check canonical and aliased per_page parameters
        for param_name in ["per_page", "limit", "size"]:
            if param_name in request_args:
                values = request_args[param_name]
                if isinstance(values, list):
                    raw_values = values
                else:
                    raw_values = [values]
                
                # Check for duplicates
                if len(raw_values) > 1:
                    issues.append({
                        "type": "duplicate_per_page_params",
                        "param": param_name,
                        "raw_values": raw_values,
                        "picked": raw_values[0],
                        "severity": "medium"
                    })
                
                # Extract first valid integer
                valid_per_page = self._find_first_valid_integer(raw_values)
                if valid_per_page is not None:
                    return valid_per_page, issues
                elif len(raw_values) > 0:
                    issues.append({
                        "type": "invalid_per_page_format",
                        "param": param_name,
                        "raw_values": raw_values,
                        "severity": "medium"
                    })
        
        # No per_page parameter found, use default
        return self.config.default_per_page, issues
    
    def _handle_offset_limit(
        self, request_args: Dict, page: int, per_page: int
    ) -> Tuple[list, int, int]:
        """
        Handle conversion from offset/limit to page/per_page.
        
        If both offset and limit are present (and page is still default),
        converts them to page/per_page.
        
        Returns:
            Tuple of (issues: list, page: int, per_page: int)
        """
        issues = []
        
        offset = None
        limit = None
        
        # Check for offset parameter
        for param_name in ["offset", "start"]:
            if param_name in request_args:
                values = request_args[param_name]
                if isinstance(values, list):
                    raw_values = values
                else:
                    raw_values = [values]
                
                if len(raw_values) > 1:
                    issues.append({
                        "type": "duplicate_offset_params",
                        "param": param_name,
                        "raw_values": raw_values,
                        "picked": raw_values[0],
                        "severity": "medium"
                    })
                
                offset = self._find_first_valid_integer(raw_values)
                if offset is None and len(raw_values) > 0:
                    issues.append({
                        "type": "invalid_offset_format",
                        "param": param_name,
                        "raw_values": raw_values,
                        "severity": "medium"
                    })
                break
        
        # Check for limit parameter (if we're converting from offset/limit)
        for param_name in ["limit", "size"]:
            if param_name in request_args and param_name not in ["per_page"]:
                values = request_args[param_name]
                if isinstance(values, list):
                    raw_values = values
                else:
                    raw_values = [values]
                
                if len(raw_values) > 1:
                    issues.append({
                        "type": "duplicate_limit_params",
                        "param": param_name,
                        "raw_values": raw_values,
                        "picked": raw_values[0],
                        "severity": "medium"
                    })
                
                limit = self._find_first_valid_integer(raw_values)
                if limit is None and len(raw_values) > 0:
                    issues.append({
                        "type": "invalid_limit_format",
                        "param": param_name,
                        "raw_values": raw_values,
                        "severity": "medium"
                    })
                break
        
        # Convert offset/limit to page/per_page if both present
        if offset is not None and limit is not None and page == self.config.default_page:
            issues.append({
                "type": "offset_limit_conversion",
                "offset": offset,
                "limit": limit,
                "converted_page": offset // limit + 1,
                "converted_per_page": limit,
                "severity": "info"
            })
            page = offset // limit + 1
            per_page = limit
        
        return issues, page, per_page
    
    def _apply_bounds(self, page: int, per_page: int) -> Tuple[int, list]:
        """
        Apply upper/lower bounds and clamp values to safe ranges.
        
        Returns:
            Tuple of (page: int, issues: list)
        """
        issues = []
        
        # Clamp page to valid range
        if page <= 0:
            issues.append({
                "type": "negative_or_zero_page",
                "original_page": page,
                "clamped_to": self.config.default_page,
                "severity": "medium"
            })
            page = self.config.default_page
        
        if page > self.config.max_page_allowed:
            issues.append({
                "type": "excessive_page_number",
                "original_page": page,
                "max_allowed": self.config.max_page_allowed,
                "clamped_to": self.config.max_page_allowed,
                "severity": "high"
            })
            page = self.config.max_page_allowed
        
        # Clamp per_page to valid range
        if per_page < self.config.min_per_page:
            issues.append({
                "type": "invalid_per_page_range",
                "original_per_page": per_page,
                "min_allowed": self.config.min_per_page,
                "clamped_to": self.config.min_per_page,
                "severity": "medium"
            })
            per_page = self.config.min_per_page
        
        if per_page > self.config.max_per_page:
            issues.append({
                "type": "excessive_per_page",
                "original_per_page": per_page,
                "max_allowed": self.config.max_per_page,
                "clamped_to": self.config.max_per_page,
                "severity": "high"
            })
            per_page = self.config.max_per_page
        
        return (page, per_page), issues
    
    @staticmethod
    def _find_first_valid_integer(values: list) -> Optional[int]:
        """
        Find the first valid integer in a list of values.
        
        Handles:
        - String representations of integers
        - Empty strings
        - None values
        - Already-parsed integers
        
        Returns:
            First valid integer or None
        """
        for val in values:
            if val is None or val == "":
                continue
            
            try:
                if isinstance(val, int):
                    return val
                else:
                    return int(val)
            except (ValueError, TypeError):
                continue
        
        return None


def normalize_pagination_params(
    request_args: Dict,
    config: Optional[PaginationConfig] = None
) -> NormalizedPagination:
    """
    Convenience function to normalize pagination parameters.
    
    Args:
        request_args: Query parameters from Flask request
        config: Optional PaginationConfig for customization
    
    Returns:
        NormalizedPagination object
    """
    normalizer = PaginationNormalizer(config)
    return normalizer.normalize(request_args)


def build_canonical_url(base_url: str, page: int, per_page: int, **kwargs) -> str:
    """
    Build a canonical URL with normalized pagination parameters.
    
    Ensures exactly one page parameter and per_page if non-default.
    
    Args:
        base_url: Base URL without query string
        page: Normalized page number
        per_page: Normalized per_page value
        kwargs: Additional query parameters to include
    
    Returns:
        Canonical URL with normalized pagination parameters
    """
    params = [f"page={page}"]
    
    # Include per_page if non-default or explicitly provided
    if per_page != 25 or "per_page" in kwargs:
        params.append(f"per_page={per_page}")
    
    # Add other parameters, excluding page-related ones
    for key, value in kwargs.items():
        if key not in ["page", "p", "per_page", "limit", "size", "offset", "start"]:
            params.append(f"{key}={value}")
    
    return f"{base_url}?{'&'.join(params)}"
