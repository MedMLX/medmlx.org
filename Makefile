.DEFAULT_GOAL := qa
.PHONY: env check-env serve lint typecheck test site-check release-check build pages deploy qa loc clean

PORT ?= 4173
PYTHON ?= .venv/bin/python
SITE_PYTHON ?= python3
TESTS ?= devtools/*.test.mjs
NODE_TEST_ARGS ?=
NODE_PACKAGE := node devtools/node-package.mjs
SOURCE_DIRS ?= devtools site server.py
export PYTHONNOUSERSITE := 1

env:
	$(NODE_PACKAGE) inspect
	uv lock --check
	uv sync --locked
	npm ci --ignore-scripts

check-env:
	@command -v "$(PYTHON)" >/dev/null || { echo "Missing project Python: run make env explicitly, or set PYTHON to its existing interpreter" >&2; exit 1; }

serve:
	$(SITE_PYTHON) server.py --port $(PORT)

lint: check-env
	$(PYTHON) -m ruff check devtools server.py

typecheck: check-env
	@command -v node >/dev/null || { echo "Maintained host Node is required for Pyright" >&2; exit 1; }
	PYRIGHT_PYTHON_NODEJS_WHEEL=0 PYRIGHT_PYTHON_GLOBAL_NODE=1 $(PYTHON) -m pyright --project . --pythonpath "$(PYTHON)" --warnings
	bash -o pipefail -c 'rg --files --hidden --no-ignore --glob "*.py" --glob "*.pyi" --null devtools server.py | xargs -0 $(PYTHON) -m ruff check --config pyproject.toml --select TID251,ANN401 --ignore-noqa --no-force-exclude --'

site-check: build
	$(SITE_PYTHON) devtools/check_site.py

build: test
	node --check site/app.js
	node --check site/models.js
	node --check site/releases.js
	node --check site/mcp.js
	node --check site/render.js
	node --check devtools/prerender.mjs

# Private MedMLX repos need a token to read tagged sources; reuse the gh login.
GITHUB_TOKEN_FROM_GH = GITHUB_TOKEN="$${GITHUB_TOKEN:-$$(gh auth token 2>/dev/null)}"

release-check: check-env
	$(GITHUB_TOKEN_FROM_GH) $(PYTHON) devtools/check_releases.py

pages: site-check
	$(GITHUB_TOKEN_FROM_GH) MEDMLX_SITE_PYTHON="$(PYTHON)" node devtools/export-site.mjs

# Upload the verified export to medmlx.org (wrangler.jsonc). Run `npx wrangler
# login` once and set CLOUDFLARE_ACCOUNT_ID to the account that owns the zone.
WRANGLER ?= npx --yes wrangler@4.151.1
deploy: pages
	$(WRANGLER) deploy

test: check-env
	$(PYTHON) -m unittest devtools.test_check_releases
	node --test $(NODE_TEST_ARGS) $(TESTS)

qa: SITE_PYTHON = $(PYTHON)
qa: lint typecheck site-check release-check

loc:
	@find $(wildcard $(SOURCE_DIRS)) -type f \( -name '*.py' -o -name '*.pyi' -o -name '*.sh' -o -name '*.ts' -o -name '*.tsx' -o -name '*.js' -o -name '*.jsx' -o -name '*.rs' \) -print0 | xargs -0 wc -l

clean:
	rm -rf .pytest_cache .ruff_cache __pycache__
	find . -name .venv -prune -o -type d -name __pycache__ -prune -exec rm -rf {} +
