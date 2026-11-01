// The exported pages carry their own metadata and content, and the agent files
// match the catalog the site renders.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { catalogJson, llmsText, prerender, robots, sitemap } from './prerender.mjs';
import { catalog, route, routes, siteUrl } from '../site/render.js';

const shell = readFileSync(new URL('../site/index.html', import.meta.url), 'utf8');
const tag = (html, pattern) => html.match(pattern)?.[1];

test('every route prerenders with its own title, description, canonical URL and content', () => {
  const titles = new Set();
  for (const path of routes) {
    const html = prerender(shell, path);
    const title = tag(html, /<title>([^<]*)<\/title>/);
    assert.ok(!titles.has(title), `duplicate title ${title}`);
    titles.add(title);
    assert.equal(tag(html, /<link rel="canonical" href="([^"]*)">/), `${siteUrl}${path}`);
    assert.equal(tag(html, /<meta property="og:url" content="([^"]*)">/), `${siteUrl}${path}`);
    assert.ok(tag(html, /<meta name="description" content="([^"]{40,160})">/), `description length on ${path}`);
    assert.equal(tag(html, /<meta name="robots" content="([^"]*)">/), 'index, follow');
    assert.match(html, /<main id="main" tabindex="-1">\s*<(section|div) /, `main content on ${path}`);
    const data = tag(html, /<script type="application\/ld\+json" id="structured-data">([^<]*)<\/script>/);
    assert.equal(JSON.parse(data)['@context'], 'https://schema.org');
  }
});

test('every catalog entry has a page in the route list', () => {
  for (const item of catalog) assert.ok(routes.includes(item.href), item.href);
  assert.equal(new Set(routes).size, routes.length);
});

test('catalog URLs restore search text and task selection when revisited', () => {
  const body = String(route('/models', '?q=SynthSeg&task=Segmentation').body);
  assert.match(body, /id="model-search"[^>]*value="SynthSeg"/);
  assert.match(body, /name="task" value="Segmentation"\s+checked/);
});

test('the 404 page is not indexed and has no canonical URL', () => {
  const html = prerender(shell, '/404');
  assert.equal(tag(html, /<meta name="robots" content="([^"]*)">/), 'noindex');
  assert.doesNotMatch(html, /rel="canonical"/);
  assert.match(html, /<h1>Page not found<\/h1>/);
});

test('the sitemap lists every route and robots.txt points to it', () => {
  const xml = sitemap();
  assert.equal(xml.match(/<loc>/g).length, routes.length);
  assert.match(robots(), new RegExp(`Sitemap: ${siteUrl}/sitemap.xml`));
});

test('llms.txt and catalog.json carry every runtime with its verified install command', () => {
  const text = llmsText();
  const data = JSON.parse(catalogJson());
  assert.equal(data.models.length, catalog.length);
  for (const item of catalog) {
    assert.ok(text.includes(`${siteUrl}${item.href}`), item.name);
    for (const line of item.install.split('\n')) assert.ok(text.includes(`        ${line}`), `${item.name}: ${line}`);
    assert.equal(data.models.find(model => model.distribution === item.distribution).install, item.install);
  }
});
