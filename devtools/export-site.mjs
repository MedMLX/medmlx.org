// Replace dist/pages with the site: one prerendered page per route, a 404
// fallback, and the sitemap, robots.txt, llms.txt and catalog.json.
// Unknown paths depend on the static host serving the 404 fallback.
import { cp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

// Verify before removing an existing export, including when called directly.
const python = process.env.MEDMLX_SITE_PYTHON || fileURLToPath(new URL('../.venv/bin/python', import.meta.url));
const verified = spawnSync(python, [fileURLToPath(new URL('check_releases.py', import.meta.url))], {
  cwd: fileURLToPath(new URL('../', import.meta.url)), stdio: 'inherit',
});
if (verified.error) throw new Error(`Cannot verify releases; run make env, or set MEDMLX_SITE_PYTHON (make pages sets it from PYTHON): ${verified.error.message}`);
if (verified.status !== 0) process.exit(verified.status ?? 1);

const { catalogJson, llmsText, prerender, robots, sitemap } = await import('./prerender.mjs');
const { routes } = await import('../site/render.js');
const site = new URL('../site/', import.meta.url);
const output = new URL('../dist/pages/', import.meta.url);
const shell = await readFile(new URL('index.html', site), 'utf8');
// Build every page before touching the previous export.
const pages = routes.map(path => [path, prerender(shell, path)]);
const notFound = prerender(shell, '/404');

await rm(output, { recursive: true, force: true });
// Asset notes (README.md) document the repository; they are not site pages.
await cp(site, output, { recursive: true, filter: source => !source.endsWith('README.md') });
for (const [path, html] of pages) {
  const directory = new URL(`.${path}`, output);
  await mkdir(directory, { recursive: true });
  await writeFile(new URL('index.html', directory), html);
}
await writeFile(new URL('404.html', output), notFound);
await writeFile(new URL('sitemap.xml', output), sitemap());
await writeFile(new URL('robots.txt', output), robots());
await writeFile(new URL('llms.txt', output), llmsText());
await writeFile(new URL('catalog.json', output), catalogJson());
console.log(`Exported ${pages.length} pages, a 404 page, sitemap.xml, robots.txt, llms.txt and catalog.json to ${fileURLToPath(output)}`);
