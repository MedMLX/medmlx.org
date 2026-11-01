"""Serve the MedMLX website locally using Python's standard library."""

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

SITE = Path(__file__).resolve().parent / "site"


class Handler(SimpleHTTPRequestHandler):
    """Serve the app shell for extensionless paths in the local preview.

    Any request path without a file extension, including an extension-less real
    file name and unknown client routes, is answered with ``index.html``. Paths
    with an extension use the standard static-file handler, including its 404s.
    The Pages export instead creates route indexes and a ``404.html`` fallback.
    """

    def send_head(self):
        """Serve the app shell for extensionless routes and static files otherwise."""
        if not PurePosixPath(urlsplit(self.path).path).suffix:
            self.path = "/index.html"
        return super().send_head()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=4173)
    args = parser.parse_args()
    handler = partial(Handler, directory=str(SITE))
    with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
        print(f"MedMLX: http://localhost:{args.port}", flush=True)
        server.serve_forever()
