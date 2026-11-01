# medmlx.org

Static MedMLX website (HTML, CSS and JavaScript) served by Cloudflare as static
assets (Worker `medmlx`, `wrangler.jsonc`) on medmlx.org and www.medmlx.org
only. `make deploy` uploads the verified `dist/pages/` export; Cloudflare does
not build the site, and there is no workers.dev or preview address.

## Rules

- List only public runtimes; copy requirements and commands from each
  package's docs.
- `site/releases.js` owns reviewed package versions and shared install commands.
  Use `packageUrl()` for current PyPI instructions. When a new release appears,
  review its `v<version>` repository tag, update the catalog and any changed
  examples, then run `make release-check`. Do not use unreleased main-branch
  instructions for a published package.
- Command builders produce shell text only; inference runs on the user's Mac.
- Fonts and brand assets keep their own terms.

## Checks

- `make serve` previews the site locally; `make test` runs hermetic regression
  tests. `make qa` also runs lint, type checks, local asset checks and the live
  release check.
- `make release-check` requires network access to PyPI, tagged GitHub source
  and Hugging Face. It rejects stale or yanked releases, mismatched names,
  Python requirements, extras or README content, and examples missing from the
  release docs. Release docs are the tagged README, plus `docs/usage.md` for
  older tags that still have it. Each install line must equal one in the release
  docs, including any companion packages. Detailed model commands, including every option the command
  form can add, must use subcommands, options and choices the tagged CLI
  declares; pinned weight revisions must exist, match the listed size and the
  weights link, and the peak memory figure must appear in the release docs. It
  does dependency resolution for the displayed install commands using `uv pip
  compile`, wheels only, on the documented macOS/arm64 and Python versions.
  It does not install packages, build source distributions or run inference.
- The release check reads tagged sources from GitHub. For private repos,
  `make release-check` and `make pages` pass your `gh` login as
  `GITHUB_TOKEN`; the checker sends it only to GitHub hosts.
- `make pages` verifies releases before replacing `dist/pages/`, and
  `make deploy` uploads that directory with a pinned Wrangler (run
  `npx wrangler login` once). The login can reach more than one Cloudflare
  account, so set `CLOUDFLARE_ACCOUNT_ID` to the account that owns the
  medmlx.org zone. Every deploy goes straight to medmlx.org, so preview first:
  `make serve` for the source, or `npx wrangler dev` after `make pages` for the
  exact export as Cloudflare serves it. The direct exporter enforces the same check, and
  network failures leave the previous export intact. `site/render.js` renders
  every page without a DOM, and `site/app.js` adds only browser behavior.
  `make pages` prerenders each route (routes end in `/`) and generates
  `sitemap.xml`, `robots.txt`, `llms.txt` and `catalog.json` from the same
  verified catalog.
- `.github/workflows/release-check.yml` runs the release check daily against
  the catalog on `main`, which is what `make deploy` publishes. A failure means
  the site has drifted from a new release: review the release, update the site
  and deploy.
