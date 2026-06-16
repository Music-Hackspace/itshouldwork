#!/usr/bin/env python3
"""Minimal static file server for Heroku.

Serves the repo root (the built site: index.html, archive.html, photo.*,
candidates.json, history.json, archive/, etc.) — the same files GitHub Pages
served. Threaded so concurrent asset requests don't queue behind each other.
Stdlib only; binds the port Heroku provides via $PORT.
"""
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # Short cache: the daily candidates/winner change often.
        self.send_header("Cache-Control", "public, max-age=300")
        super().end_headers()


def main():
    port = int(os.environ.get("PORT", "8000"))
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
