"""
Mock gateway/proxy layer for simulating real-world pagination anomalies.

This module reproduces upstream parameter duplication, reordering, and caching
behaviors to validate the pagination normalization system under realistic
production-like conditions.
"""

import random
import time
from typing import Dict, List, Tuple, Optional
from urllib.parse import urlencode, parse_qs, urlparse, urlunparse
import hashlib
import logging

logger = logging.getLogger(__name__)


class MockProxyBehavior:
    """
    Simulates common reverse proxy and CDN behaviors that introduce
    pagination parameter anomalies.
    """
    
    def __init__(self):
        self.request_count = 0
        self.cache = {}
    
    def duplicate_page_parameter(self, url: str) -> str:
        """
        Simulate frontend and proxy both appending page parameter.
        
        Example: /explore?page=3 -> /explore?page=3&page=2
        """
        parsed = urlparse(url)
        params = parse_qs(parsed.query, keep_blank_values=True)
        
        if "page" in params:
            # Append a duplicate page value
            page_value = params["page"][0]
            new_page = str(int(page_value) - 1) if page_value.isdigit() else "1"
            params["page"].append(new_page)
        
        new_query = urlencode(params, doseq=True)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
    
    def reorder_parameters(self, url: str) -> str:
        """
        Simulate upstream reordering of query parameters.
        
        This can cause different WSGI servers or caches to pick different
        values for duplicate parameters.
        """
        parsed = urlparse(url)
        params = parse_qs(parsed.query, keep_blank_values=True)
        
        # Randomly reorder parameter keys
        keys = list(params.keys())
        random.shuffle(keys)
        
        reordered = {k: params[k] for k in keys}
        new_query = urlencode(reordered, doseq=True)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
    
    def inject_empty_parameter(self, url: str, param_name: str = "page") -> str:
        """
        Simulate proxy appending empty parameters.
        
        Example: /explore?page=3 -> /explore?page=3&page=
        """
        parsed = urlparse(url)
        params = parse_qs(parsed.query, keep_blank_values=True)
        
        if param_name not in params:
            params[param_name] = []
        params[param_name].append("")
        
        new_query = urlencode(params, doseq=True)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
    
    def convert_to_array_encoding(self, url: str) -> str:
        """
        Simulate conversion to array-like parameter encoding.
        
        Example: /explore?page=2 -> /explore?page[]=2
        """
        parsed = urlparse(url)
        params = parse_qs(parsed.query, keep_blank_values=True)
        
        # Convert page to array encoding
        if "page" in params:
            params["page[]"] = params.pop("page")
        
        new_query = urlencode(params, doseq=True)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
    
    def inject_multiple_formats(self, url: str) -> str:
        """
        Simulate mixed parameter formats (page, p, page[]).
        
        Example: /explore?page=2 -> /explore?page=2&p=1&page[]=3
        """
        parsed = urlparse(url)
        params = parse_qs(parsed.query, keep_blank_values=True)
        
        if "page" in params:
            page_val = params["page"][0]
            # Inject aliases
            params["p"] = [str(int(page_val) - 1)] if page_val.isdigit() else ["1"]
            params["page[]"] = [str(int(page_val) + 1)] if page_val.isdigit() else ["2"]
        
        new_query = urlencode(params, doseq=True)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
    
    def simulate_cdn_cache_return(self, url: str, user_context: Optional[Dict] = None) -> Tuple[str, Dict]:
        """
        Simulate CDN cache returning cached content for different user contexts.
        
        This introduces the session_drift_cached_page vulnerability.
        """
        # Create cache key from URL only (not user)
        cache_key = hashlib.sha256(url.encode()).hexdigest()
        
        if cache_key in self.cache:
            # Return cached content but potentially with wrong user context
            cached_data = self.cache[cache_key]
            return cached_data["url"], {"cached": True, "user_mismatch": True}
        else:
            # Cache the response
            self.cache[cache_key] = {
                "url": url,
                "user": user_context.get("user_id") if user_context else None,
                "timestamp": time.time()
            }
            return url, {"cached": False, "user_mismatch": False}
    
    def inject_offset_limit_format(self, url: str) -> str:
        """
        Simulate mobile or legacy client using offset/limit format.
        
        Example: /explore?page=2&per_page=25 -> /explore?offset=25&limit=25
        """
        parsed = urlparse(url)
        params = parse_qs(parsed.query, keep_blank_values=True)
        
        if "page" in params and "per_page" in params:
            page = int(params["page"][0]) if params["page"][0].isdigit() else 1
            per_page = int(params["per_page"][0]) if params["per_page"][0].isdigit() else 25
            
            offset = (page - 1) * per_page
            
            params.pop("page")
            params.pop("per_page")
            params["offset"] = [str(offset)]
            params["limit"] = [str(per_page)]
        
        new_query = urlencode(params, doseq=True)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))


class CacheLayerSimulator:
    """
    Simulates multi-layer caching and cache invalidation issues.
    """
    
    def __init__(self):
        self.browser_cache = {}
        self.cdn_cache = {}
        self.backend_cache = {}
        self.access_log = []
    
    def get_cache_variants(self, url: str) -> List[str]:
        """
        Get all known cache variants of a URL.
        
        Returns list of parameter-order variants that might exist in cache.
        """
        variants = [url]
        
        parsed = urlparse(url)
        params = parse_qs(parsed.query, keep_blank_values=True)
        
        # Generate a few common reorderings
        keys = list(params.keys())
        for _ in range(3):
            random.shuffle(keys)
            reordered = {k: params[k] for k in keys}
            variant_query = urlencode(reordered, doseq=True)
            variant_url = urlunparse((
                parsed.scheme, parsed.netloc, parsed.path,
                parsed.params, variant_query, parsed.fragment
            ))
            variants.append(variant_url)
        
        return variants
    
    def mark_user_dependent_cacheable(self, route: str, cacheable: bool = False):
        """
        Mark route as user-dependent and whether it should be cached.
        
        User-dependent routes should typically not be cached or should include
        user ID in cache key.
        """
        pass
    
    def log_access(self, url: str, user_id: Optional[int], cache_hit: bool):
        """Log cache access patterns."""
        self.access_log.append({
            "timestamp": time.time(),
            "url": url,
            "user_id": user_id,
            "cache_hit": cache_hit
        })


class RequestAnomalyGenerator:
    """
    Generates realistic request anomalies based on input.json test cases.
    """
    
    def __init__(self):
        self.proxy = MockProxyBehavior()
        self.cache = CacheLayerSimulator()
    
    def generate_all_anomalies(self, base_url: str) -> Dict[str, Dict]:
        """
        Generate all documented anomaly types for a given base URL.
        """
        anomalies = {}
        
        # Duplicate page params
        anomalies["duplicate_page_params"] = {
            "description": "Frontend and proxy both append page",
            "url": self.proxy.duplicate_page_parameter(base_url),
            "severity": "high"
        }
        
        # Reordered parameters
        anomalies["reordered_params"] = {
            "description": "Upstream reorders query parameters",
            "url": self.proxy.reorder_parameters(base_url),
            "severity": "medium"
        }
        
        # Empty parameters
        anomalies["empty_page_param"] = {
            "description": "Proxy appends empty page parameter",
            "url": self.proxy.inject_empty_parameter(base_url),
            "severity": "medium"
        }
        
        # Array encoding
        anomalies["array_encoded_page"] = {
            "description": "Parameters encoded as arrays",
            "url": self.proxy.convert_to_array_encoding(base_url),
            "severity": "medium"
        }
        
        # Multiple formats
        anomalies["multiple_formats"] = {
            "description": "Mixed parameter formats (page, p, page[])",
            "url": self.proxy.inject_multiple_formats(base_url),
            "severity": "high"
        }
        
        # Offset/limit format
        anomalies["offset_limit_format"] = {
            "description": "Mobile client using offset/limit",
            "url": self.proxy.inject_offset_limit_format(base_url),
            "severity": "medium"
        }
        
        return anomalies
    
    def simulate_request_race(self, base_url: str) -> List[Tuple[str, Dict]]:
        """
        Simulate a race condition where the same logical request
        arrives via different parameter orderings.
        """
        variations = self.cache.get_cache_variants(base_url)
        
        results = []
        for url in variations:
            anomaly_data = {
                "url": url,
                "timestamp": time.time(),
                "cache_hit": random.random() > 0.5
            }
            results.append((url, anomaly_data))
        
        return results


def demonstrate_gateway_issues():
    """
    Demonstrate various gateway anomalies.
    """
    generator = RequestAnomalyGenerator()
    
    base_url = "/explore?page=3&per_page=25&sort=ts_desc"
    
    print("=" * 60)
    print("Mock Gateway - Pagination Anomalies Demonstration")
    print("=" * 60)
    
    anomalies = generator.generate_all_anomalies(base_url)
    
    for anomaly_type, anomaly_data in anomalies.items():
        print(f"\n{anomaly_type}:")
        print(f"  Description: {anomaly_data['description']}")
        print(f"  Severity: {anomaly_data['severity']}")
        print(f"  Original: {base_url}")
        print(f"  Modified: {anomaly_data['url']}")
    
    print("\n" + "=" * 60)
    print("Cache Variants (potential concurrent request race):")
    print("=" * 60)
    
    race_conditions = generator.simulate_request_race(base_url)
    for i, (url, data) in enumerate(race_conditions):
        print(f"\nRequest {i+1}:")
        print(f"  URL: {url}")
        print(f"  Cache Hit: {data['cache_hit']}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    demonstrate_gateway_issues()
