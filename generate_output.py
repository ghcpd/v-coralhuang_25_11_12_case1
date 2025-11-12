import json
from request_normalizer import normalize_pagination_params

infile = 'input.json'
with open(infile) as f:
    data = json.load(f)

results = {'summary': []}
for t in data['tests']:
    from urllib.parse import parse_qs
    parsed = parse_qs(t['request_url'].split('?',1)[-1]) if '?' in t['request_url'] else {}
    norm = normalize_pagination_params(parsed, per_page_default=data['config']['per_page'], max_page_allowed=data['config']['max_page_allowed'], max_per_page=data['config']['max_per_page'])
    results['summary'].append({'id': t['id'], 'request_url': t['request_url'], 'normalized': norm})

with open('output.json','w') as fh:
    json.dump(results, fh, indent=2)
print('Wrote output.json')
