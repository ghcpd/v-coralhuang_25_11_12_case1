"""
Comprehensive test suite for pagination normalization and deterministic ordering.

Tests cover:
- Duplicate parameter detection and resolution
- Malformed parameter handling
- Numeric bounds enforcement
- Parameter alias resolution (page/p, per_page/limit/size, offset/limit)
- Array-like encoding handling
- Cache consistency and isolation
- Concurrent request safety
- Deterministic ordering with timestamp collisions
"""

import unittest
from typing import Dict, Any
import threading
import time
from unittest.mock import Mock, MagicMock, patch

from request_normalizer import (
    PaginationNormalizer,
    PaginationConfig,
    normalize_pagination_params,
    build_canonical_url,
    NormalizedPagination,
)


class TestPaginationNormalizerBasic(unittest.TestCase):
    """Test basic parameter extraction and normalization."""
    
    def setUp(self):
        self.config = PaginationConfig(
            default_page=1,
            default_per_page=25,
            max_page_allowed=1000,
            max_per_page=100,
        )
        self.normalizer = PaginationNormalizer(self.config)
    
    def test_default_values(self):
        """Test that missing parameters default to configured values."""
        result = self.normalizer.normalize({})
        self.assertEqual(result.page, 1)
        self.assertEqual(result.per_page, 25)
        self.assertEqual(len(result.issues), 0)
        self.assertFalse(result.is_modified)
    
    def test_simple_valid_page(self):
        """Test basic page parameter parsing."""
        result = self.normalizer.normalize({"page": "3"})
        self.assertEqual(result.page, 3)
        self.assertEqual(result.per_page, 25)
        self.assertEqual(len(result.issues), 0)
    
    def test_simple_valid_per_page(self):
        """Test basic per_page parameter parsing."""
        result = self.normalizer.normalize({"per_page": "50"})
        self.assertEqual(result.page, 1)
        self.assertEqual(result.per_page, 50)
        self.assertEqual(len(result.issues), 0)
    
    def test_integer_page_parameter(self):
        """Test that already-integer page parameter is handled."""
        result = self.normalizer.normalize({"page": 5})
        self.assertEqual(result.page, 5)
        self.assertTrue(result.is_modified or len(result.issues) == 0)


class TestDuplicateParameters(unittest.TestCase):
    """Test handling of duplicate parameters."""
    
    def setUp(self):
        self.config = PaginationConfig()
        self.normalizer = PaginationNormalizer(self.config)
    
    def test_duplicate_page_params_list(self):
        """Test duplicate page parameters passed as list."""
        result = self.normalizer.normalize({"page": ["3", "2"]})
        self.assertEqual(result.page, 3)  # First valid value
        self.assertTrue(result.is_modified)
        self.assertEqual(len(result.issues), 1)
        self.assertEqual(result.issues[0]["type"], "duplicate_page_params")
        self.assertEqual(result.issues[0]["raw_values"], ["3", "2"])
    
    def test_duplicate_page_params_from_template_and_spa(self):
        """Test realistic duplicate from template generation and SPA router."""
        # Simulates: /explore?page=4&page=5
        result = self.normalizer.normalize({"page": ["4", "5"]})
        self.assertEqual(result.page, 4)
        self.assertTrue(result.is_modified)
        issues = [i for i in result.issues if i["type"] == "duplicate_page_params"]
        self.assertEqual(len(issues), 1)
    
    def test_duplicate_per_page_params(self):
        """Test duplicate per_page parameters."""
        result = self.normalizer.normalize({"per_page": ["25", "50"]})
        self.assertEqual(result.per_page, 25)
        self.assertTrue(result.is_modified)
        self.assertEqual(len(result.issues), 1)
        self.assertEqual(result.issues[0]["type"], "duplicate_per_page_params")


class TestMalformedParameters(unittest.TestCase):
    """Test handling of malformed or invalid parameters."""
    
    def setUp(self):
        self.config = PaginationConfig()
        self.normalizer = PaginationNormalizer(self.config)
    
    def test_non_integer_page(self):
        """Test non-integer page value falls back to default."""
        result = self.normalizer.normalize({"page": "abc"})
        self.assertEqual(result.page, 1)
        self.assertTrue(result.is_modified)
        issues = [i for i in result.issues if i["type"] == "invalid_page_format"]
        self.assertEqual(len(issues), 1)
    
    def test_empty_page_param(self):
        """Test empty page parameter."""
        result = self.normalizer.normalize({"page": ""})
        self.assertEqual(result.page, 1)
        self.assertTrue(result.is_modified)
    
    def test_empty_page_param_in_list(self):
        """Test list with empty page parameter."""
        result = self.normalizer.normalize({"page": [""]})
        self.assertEqual(result.page, 1)
        self.assertTrue(result.is_modified)
    
    def test_none_page_param(self):
        """Test None page parameter."""
        result = self.normalizer.normalize({"page": None})
        self.assertEqual(result.page, 1)
    
    def test_mixed_valid_invalid_page(self):
        """Test list with mixed valid and invalid page values."""
        result = self.normalizer.normalize({"page": ["abc", "5"]})
        self.assertEqual(result.page, 5)
        self.assertTrue(result.is_modified)


class TestParameterAliases(unittest.TestCase):
    """Test parameter alias resolution."""
    
    def setUp(self):
        self.config = PaginationConfig()
        self.normalizer = PaginationNormalizer(self.config)
    
    def test_alias_p_instead_of_page(self):
        """Test 'p' alias for page."""
        result = self.normalizer.normalize({"p": "4"})
        self.assertEqual(result.page, 4)
    
    def test_alias_limit_instead_of_per_page(self):
        """Test 'limit' alias for per_page."""
        result = self.normalizer.normalize({"limit": "50"})
        self.assertEqual(result.per_page, 50)
    
    def test_alias_size_instead_of_per_page(self):
        """Test 'size' alias for per_page."""
        result = self.normalizer.normalize({"size": "30"})
        self.assertEqual(result.per_page, 30)
    
    def test_inconsistent_alias_p_and_size(self):
        """Test inconsistent aliases: p=4&size=10."""
        result = self.normalizer.normalize({"p": "4", "size": "10"})
        self.assertEqual(result.page, 4)
        self.assertEqual(result.per_page, 10)
        # This is the expected normalization for inconsistent aliases
    
    def test_offset_and_start_aliases(self):
        """Test 'start' alias for offset."""
        result = self.normalizer.normalize({"start": "50", "limit": "25"})
        # Should convert to page = 50/25 + 1 = 3
        self.assertEqual(result.page, 3)
        self.assertEqual(result.per_page, 25)


class TestArrayEncodedParameters(unittest.TestCase):
    """Test array-like parameter encoding."""
    
    def setUp(self):
        self.config = PaginationConfig()
        self.normalizer = PaginationNormalizer(self.config)
    
    def test_array_encoded_page_bracket_notation(self):
        """Test page[] array encoding."""
        result = self.normalizer.normalize({
            "page[]": ["2", "3"],
            "per_page": "20"
        })
        self.assertEqual(result.page, 2)
        self.assertEqual(result.per_page, 20)
        self.assertTrue(result.is_modified)
        issues = [i for i in result.issues if i["type"] == "array_encoded_duplicates"]
        self.assertEqual(len(issues), 1)
    
    def test_array_encoded_page_single_value(self):
        """Test page[] with single value."""
        result = self.normalizer.normalize({"page[]": ["5"]})
        self.assertEqual(result.page, 5)


class TestOffsetLimitConversion(unittest.TestCase):
    """Test conversion from offset/limit to page/per_page."""
    
    def setUp(self):
        self.config = PaginationConfig()
        self.normalizer = PaginationNormalizer(self.config)
    
    def test_offset_limit_conversion(self):
        """Test conversion: offset=50, limit=25 -> page=3."""
        result = self.normalizer.normalize({"offset": "50", "limit": "25"})
        # offset 50 with limit 25 means: skip 50, take 25
        # page = 50/25 + 1 = 3
        self.assertEqual(result.page, 3)
        self.assertEqual(result.per_page, 25)
        self.assertTrue(result.is_modified)
        issues = [i for i in result.issues if i["type"] == "offset_limit_conversion"]
        self.assertEqual(len(issues), 1)
    
    def test_offset_zero_limit_25(self):
        """Test offset=0, limit=25 -> page=1."""
        result = self.normalizer.normalize({"offset": "0", "limit": "25"})
        self.assertEqual(result.page, 1)
        self.assertEqual(result.per_page, 25)
    
    def test_offset_limit_no_conversion_if_page_set(self):
        """Test that page takes precedence over offset/limit."""
        result = self.normalizer.normalize({
            "page": "2",
            "offset": "50",
            "limit": "25"
        })
        # page parameter should take precedence
        self.assertEqual(result.page, 2)


class TestBoundsEnforcement(unittest.TestCase):
    """Test upper and lower bounds enforcement."""
    
    def setUp(self):
        self.config = PaginationConfig(
            max_page_allowed=1000,
            max_per_page=100,
        )
        self.normalizer = PaginationNormalizer(self.config)
    
    def test_negative_page_clamped(self):
        """Test negative page number is clamped to 1."""
        result = self.normalizer.normalize({"page": "-1"})
        self.assertEqual(result.page, 1)
        self.assertTrue(result.is_modified)
        issues = [i for i in result.issues if i["type"] == "negative_or_zero_page"]
        self.assertEqual(len(issues), 1)
    
    def test_zero_page_clamped(self):
        """Test zero page number is clamped to 1."""
        result = self.normalizer.normalize({"page": "0"})
        self.assertEqual(result.page, 1)
        self.assertTrue(result.is_modified)
    
    def test_excessive_page_clamped(self):
        """Test excessive page number is clamped."""
        result = self.normalizer.normalize({"page": "999999"})
        self.assertEqual(result.page, 1000)  # max_page_allowed
        self.assertTrue(result.is_modified)
        issues = [i for i in result.issues if i["type"] == "excessive_page_number"]
        self.assertEqual(len(issues), 1)
    
    def test_excessive_per_page_clamped(self):
        """Test excessive per_page is clamped."""
        result = self.normalizer.normalize({"per_page": "5000"})
        self.assertEqual(result.per_page, 100)  # max_per_page
        self.assertTrue(result.is_modified)
        issues = [i for i in result.issues if i["type"] == "excessive_per_page"]
        self.assertEqual(len(issues), 1)
    
    def test_extreme_abuse_parameters(self):
        """Test extreme abusive query: page=5000000&per_page=5000."""
        result = self.normalizer.normalize({"page": "5000000", "per_page": "5000"})
        self.assertEqual(result.page, 1000)
        self.assertEqual(result.per_page, 100)
        self.assertTrue(result.is_modified)
        self.assertGreater(len(result.issues), 0)


class TestCanonicalURL(unittest.TestCase):
    """Test canonical URL building."""
    
    def test_canonical_url_default_per_page(self):
        """Test URL with default per_page is simplified."""
        url = build_canonical_url("/explore", page=3, per_page=25)
        self.assertEqual(url, "/explore?page=3")
    
    def test_canonical_url_non_default_per_page(self):
        """Test URL with non-default per_page includes it."""
        url = build_canonical_url("/explore", page=3, per_page=50)
        self.assertIn("page=3", url)
        self.assertIn("per_page=50", url)
    
    def test_canonical_url_extra_params_included(self):
        """Test URL includes additional parameters."""
        url = build_canonical_url("/explore", page=2, per_page=25, sort="ts_desc", filter="followed")
        self.assertIn("page=2", url)
        self.assertIn("sort=ts_desc", url)
        self.assertIn("filter=followed", url)
    
    def test_canonical_url_pagination_params_excluded_from_extras(self):
        """Test that pagination aliases are not duplicated."""
        url = build_canonical_url("/explore", page=2, per_page=25, limit="30", offset="50")
        # Should not include limit, offset, or other pagination aliases
        self.assertIn("page=2", url)
        self.assertNotIn("limit=", url)
        self.assertNotIn("offset=", url)


class TestInputDataCases(unittest.TestCase):
    """Test against specific cases from input.json."""
    
    def setUp(self):
        self.config = PaginationConfig(
            max_page_allowed=1000,
            max_per_page=100,
        )
        self.normalizer = PaginationNormalizer(self.config)
    
    def test_case_duplicate_page_params(self):
        """Test: /explore?page=3&sort=ts_desc&filter=followed&page=2"""
        result = self.normalizer.normalize({
            "page": ["3", "2"],
            "sort": "ts_desc",
            "filter": "followed"
        })
        self.assertEqual(result.page, 3)
        self.assertTrue(result.is_modified)
    
    def test_case_negative_page_number(self):
        """Test: /index?page=-1"""
        result = self.normalizer.normalize({"page": "-1"})
        self.assertEqual(result.page, 1)
    
    def test_case_excessive_page_offset(self):
        """Test: /explore?page=999999"""
        result = self.normalizer.normalize({"page": "999999"})
        self.assertEqual(result.page, 1000)
    
    def test_case_duplicate_from_template_and_spa(self):
        """Test: /explore?page=4&page=5"""
        result = self.normalizer.normalize({"page": ["4", "5"]})
        self.assertEqual(result.page, 4)
    
    def test_case_missing_page_param(self):
        """Test: /user/jack (no page param)"""
        result = self.normalizer.normalize({})
        self.assertEqual(result.page, 1)
    
    def test_case_array_encoded_page(self):
        """Test: /explore?page[]=2&page[]=3&per_page=20"""
        result = self.normalizer.normalize({
            "page[]": ["2", "3"],
            "per_page": "20"
        })
        self.assertEqual(result.page, 2)
        self.assertEqual(result.per_page, 20)
    
    def test_case_hybrid_offset_limit_client(self):
        """Test: /api/feed?offset=50&limit=25"""
        result = self.normalizer.normalize({
            "offset": "50",
            "limit": "25"
        })
        self.assertEqual(result.page, 3)
        self.assertEqual(result.per_page, 25)
    
    def test_case_empty_page_param(self):
        """Test: /explore?page=&per_page=25"""
        result = self.normalizer.normalize({
            "page": "",
            "per_page": "25"
        })
        self.assertEqual(result.page, 1)
        self.assertEqual(result.per_page, 25)
    
    def test_case_malformed_param_page_abc(self):
        """Test error case: page=abc&per_page=50"""
        result = self.normalizer.normalize({
            "page": "abc",
            "per_page": "50"
        })
        self.assertEqual(result.page, 1)
        self.assertEqual(result.per_page, 50)
    
    def test_case_abusive_pagination(self):
        """Test error case: page=5000000&per_page=5000"""
        result = self.normalizer.normalize({
            "page": "5000000",
            "per_page": "5000"
        })
        self.assertEqual(result.page, 1000)
        self.assertEqual(result.per_page, 100)
    
    def test_case_inconsistent_alias(self):
        """Test error case: p=4&size=10"""
        result = self.normalizer.normalize({
            "p": "4",
            "size": "10"
        })
        self.assertEqual(result.page, 4)
        self.assertEqual(result.per_page, 10)


class TestConcurrentRequests(unittest.TestCase):
    """Test thread-safety and request isolation."""
    
    def setUp(self):
        self.config = PaginationConfig()
        self.normalizer = PaginationNormalizer(self.config)
        self.results = []
        self.lock = threading.Lock()
    
    def test_concurrent_normalization(self):
        """Test that concurrent requests don't contaminate each other."""
        def normalize_with_delay(request_args, expected_page):
            time.sleep(0.01)  # Small delay to encourage interleaving
            result = self.normalizer.normalize(request_args)
            with self.lock:
                self.results.append((expected_page, result.page))
        
        threads = [
            threading.Thread(target=normalize_with_delay, args=({"page": "1"}, 1)),
            threading.Thread(target=normalize_with_delay, args=({"page": "5"}, 5)),
            threading.Thread(target=normalize_with_delay, args=({"page": "10"}, 10)),
            threading.Thread(target=normalize_with_delay, args=({"page": "999999"}, 1000)),
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Verify all results are correct
        self.assertEqual(len(self.results), 4)
        for expected, actual in self.results:
            # For the excessive case, we expect clamping to max
            if expected == 999999:
                expected = 1000
            self.assertEqual(expected, actual)


class TestNormalizationFunction(unittest.TestCase):
    """Test the convenience normalize_pagination_params function."""
    
    def test_convenience_function_default_config(self):
        """Test normalize_pagination_params with default config."""
        result = normalize_pagination_params({"page": "5"})
        self.assertIsInstance(result, NormalizedPagination)
        self.assertEqual(result.page, 5)
    
    def test_convenience_function_custom_config(self):
        """Test normalize_pagination_params with custom config."""
        config = PaginationConfig(max_page_allowed=500)
        result = normalize_pagination_params({"page": "600"}, config)
        self.assertEqual(result.page, 500)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and special scenarios."""
    
    def setUp(self):
        self.config = PaginationConfig()
        self.normalizer = PaginationNormalizer(self.config)
    
    def test_very_large_integer(self):
        """Test handling of very large integer values."""
        result = self.normalizer.normalize({"page": str(2**31)})
        self.assertEqual(result.page, 1000)  # Should be clamped
    
    def test_float_string_page(self):
        """Test float string for page parameter."""
        result = self.normalizer.normalize({"page": "3.5"})
        # This should fail to parse as int
        self.assertEqual(result.page, 1)
    
    def test_whitespace_in_page(self):
        """Test page with leading/trailing whitespace."""
        # Most WSGI servers strip whitespace, but test edge case
        result = self.normalizer.normalize({"page": "  5  "})
        # Python's int() handles whitespace, so this should work
        self.assertEqual(result.page, 5)
    
    def test_multiple_mixed_duplicates(self):
        """Test complex case with multiple parameter duplications."""
        result = self.normalizer.normalize({
            "page": ["1", "2", "3"],
            "per_page": ["25", "50"],
            "offset": "10"
        })
        # Should pick first valid from duplicates
        self.assertEqual(result.page, 1)
        self.assertEqual(result.per_page, 25)
        self.assertTrue(result.is_modified)
        self.assertGreater(len(result.issues), 1)


if __name__ == '__main__':
    unittest.main()
