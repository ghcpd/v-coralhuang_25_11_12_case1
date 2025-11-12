"""
Simple mock gateway that re-emits a forwarded request with duplicate params to simulate SPA/proxy interaction.
"""
from urllib.parse import urlencode, urlparse, parse_qsl, urlunparse


def simulate_duplication(dest_url: str, duplicates: list):
    # dest_url: e.g. /explore?page=3
    parsed = urlparse(dest_url)
    base_qs = parse_qsl(parsed.query, keep_blank_values=True)
    base = dict(base_qs)
    # duplicates: list of (key, value) to append
    all_qs = list(base_qs)
    all_qs.extend(duplicates)
    new_q = urlencode(all_qs)
    new_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_q, parsed.fragment))
    return new_url


if __name__ == '__main__':
    example = simulate_duplication('/explore?page=3&sort=ts_desc', [('page','2'), ('page','3')])
    print('Simulated duplication:', example)
