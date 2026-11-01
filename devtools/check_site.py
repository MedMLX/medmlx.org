"""Check that site-root references resolve to files under ``site/``.

Scans double-quoted ``src``/``href`` attributes in ``index.html``, ``app.js``,
``render.js`` and the image credits page
and ``url()`` values in ``styles.css`` for literal root-relative references,
skipping template placeholders and the listed page routes. It does not check
external links or dynamically constructed references. Also checks that
``server.py`` parses. Uses only the standard library.
"""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
ROUTES = {
    "/",
    "/models",
    "/models/mlx-reason-ct",
    "/get-started",
    "/get-started/mlx-reason-ct",
    "/mcp",
    "/cli",
    "/python",
    "/about",
}
# Written by devtools/export-site.mjs, not stored under site/.
GENERATED = {"/llms.txt", "/catalog.json", "/sitemap.xml", "/robots.txt"}
SOURCES = {
    "index.html": r'(?:src|href)="(/[^"]*)"',
    "app.js": r'(?:src|href)="(/[^"]*)"',
    "render.js": r'(?:src|href)="(/[^"]*)"',
    "styles.css": r"url\(['\"]?(/[^'\")]+)",
    "assets/hero/credits.html": r'(?:src|href)="(/[^"]*)"',
}

ast.parse((ROOT / "server.py").read_text(), filename="server.py")

missing: list[str] = []
for name, pattern in SOURCES.items():
    for ref in re.findall(pattern, (SITE / name).read_text()):
        # Template placeholders and client-side page routes are not files.
        # Routes are written with a trailing slash and may carry a query string.
        path = ref.split("#")[0].split("?")[0].rstrip("/") or "/"
        if "${" in ref or path in ROUTES or ref in GENERATED:
            continue
        if not (SITE / ref.lstrip("/")).is_file():
            missing.append(f"{name}: {ref}")

if missing:
    raise SystemExit("Missing local files:\n  " + "\n  ".join(missing))
print("Local references resolve")
