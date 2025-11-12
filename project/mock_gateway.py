from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlsplit, parse_qs, urlencode

# A tiny proxy that demonstrates how duplication/reordering might happen.
# For testing only; not production-secure.

class DupReorderHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Echo back a canonicalized query string with duplicates and re-ordered parameters
        parsed = urlsplit(self.path)
        qs = parse_qs(parsed.query, keep_blank_values=True)

        # Example: duplicate page param
        # Simulate an upstream that adds a second page param
        if 'page' in qs:
            qs.setdefault('page', []).append('99')

        # Reorder: put page at the end of the query string
        new_qs = []
        for k, vlist in qs.items():
            for v in vlist:
                new_qs.append((k, v))

        new_query = urlencode(new_qs)
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        out = {'original': parsed.query, 'modified': new_query, 'path': parsed.path}
        import json
        self.wfile.write(json.dumps(out).encode())


if __name__ == '__main__':
    server = HTTPServer(('localhost', 8081), DupReorderHandler)
    print('Mock gateway listening on :8081')
    server.serve_forever()
