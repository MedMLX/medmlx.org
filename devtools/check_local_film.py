"""Serve a site directory on loopback while Chrome exercises the homepage film."""

import os
import subprocess
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread


def main(directory: str) -> int:
    """Run the browser check against an ephemeral local preview and return its status."""
    handler = partial(SimpleHTTPRequestHandler, directory=directory)
    with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
        worker = Thread(target=server.serve_forever)
        worker.start()
        try:
            result = subprocess.run(
                ["node", Path(__file__).with_name("check-film.mjs")],
                env={**os.environ, "FILM_URL": f"http://127.0.0.1:{server.server_port}/"},
                check=False,
            )
            return result.returncode
        finally:
            server.shutdown()
            worker.join()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
