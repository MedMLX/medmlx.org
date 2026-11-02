// Static files for search engines and agents, built from the same modules the
// site renders: one prerendered HTML page per route, the sitemap, robots.txt,
// llms.txt and catalog.json. Everything here is a pure function of its inputs.
import {
  article, articleUrl, bibtex, catalog, citation, maintainers, route, routes, siteDescription, siteUrl, tasks,
} from '../site/render.js';
import {
  medmlxInstallCommand, medmlxRunCommand, medmlxServeCommand, medmlxSetupCommand,
  platformRequirement, pythonVersion, releases, uvInstallCommand,
} from '../site/releases.js';

const text = value => String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;');
const attribute = value => text(value).replace(/"/g, '&quot;');

/** Replace exactly one match, so a changed shell fails loudly instead of shipping stale tags. */
function replaceOnce(html, pattern, replacement) {
  const matches = html.match(new RegExp(pattern.source, `${pattern.flags.replace('g', '')}g`));
  if (matches?.length !== 1) throw new Error(`Expected one match for ${pattern} in the page shell`);
  return html.replace(pattern, replacement);
}

/** The page shell with one route's head tags, structured data and main content filled in. */
export function prerender(shell, path) {
  const page = route(path.replace(/\/+$/, '') || '/');
  const url = page.canonical ? `${siteUrl}${page.canonical}` : null;
  let html = shell;
  html = replaceOnce(html, /<title>[^<]*<\/title>/, () => `<title>${text(page.fullTitle)}</title>`);
  html = replaceOnce(html, /(<meta name="description" content=")[^"]*(">)/, (_, a, b) => `${a}${attribute(page.description)}${b}`);
  html = replaceOnce(html, /(<meta name="robots" content=")[^"]*(">)/, (_, a, b) => `${a}${page.noindex ? 'noindex' : 'index, follow'}${b}`);
  html = replaceOnce(html, /(<meta property="og:title" content=")[^"]*(">)/, (_, a, b) => `${a}${attribute(page.fullTitle)}${b}`);
  html = replaceOnce(html, /(<meta property="og:description" content=")[^"]*(">)/, (_, a, b) => `${a}${attribute(page.description)}${b}`);
  html = replaceOnce(html, /(<meta property="og:url" content=")[^"]*(">)/, (_, a, b) => `${a}${attribute(url || `${siteUrl}/`)}${b}`);
  // A page without a canonical URL (the 404 page) has no canonical link.
  html = replaceOnce(html, /( *)<link rel="canonical" href="[^"]*">\n/,
    (_, indent) => url ? `${indent}<link rel="canonical" href="${attribute(url)}">\n` : '');
  // Escape "<" so the JSON can never close its script element.
  const data = JSON.stringify(page.data).replace(/</g, '\\u003c');
  html = replaceOnce(html, /(<script type="application\/ld\+json" id="structured-data">)[^<]*(<\/script>)/, (_, a, b) => `${a}${data}${b}`);
  html = replaceOnce(html, /(<main id="main" tabindex="-1">)[\s\S]*?(<\/main>)/, (_, a, b) => `${a}\n${page.body}\n    ${b}`);
  return html;
}

/** Every indexable page, with its canonical URL. */
export function sitemap() {
  const urls = routes.map(path => `  <url><loc>${text(`${siteUrl}${path}`)}</loc></url>`);
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls.join('\n')}\n</urlset>\n`;
}

/** All crawlers, including AI agents, may read the whole site. */
export function robots() {
  return `User-agent: *\nAllow: /\n\nSitemap: ${siteUrl}/sitemap.xml\n`;
}

/** Each runtime as data: the same facts and verified install command the site shows. */
function runtimeRecord(item) {
  return {
    name: item.name,
    distribution: item.distribution,
    version: item.version,
    task: item.task,
    description: item.description,
    page: `${siteUrl}${item.href}`,
    pypi: item.package,
    source: item.source,
    install: item.install,
  };
}

/** The model catalog for programs. */
export function catalogJson() {
  return `${JSON.stringify({
    name: 'MedMLX',
    url: `${siteUrl}/`,
    description: siteDescription,
    requirements: { platform: platformRequirement, python: pythonVersion, installer: 'uv', installUv: uvInstallCommand },
    medmlx: {
      version: releases.medmlx.version,
      install: medmlxInstallCommand,
      run: medmlxRunCommand,
      downloadWeights: medmlxSetupCommand,
      mcpServer: medmlxServeCommand,
      mcpGuide: `${siteUrl}/mcp/`,
    },
    article: { ...article, url: articleUrl, citation, bibtex },
    maintainers: maintainers.map(person => ({ name: person.name, url: person.url, profiles: person.sameAs })),
    lab: { name: 'AI-IR', url: 'https://ai-ir.org/', institution: 'University of Texas Medical Branch' },
    intendedUse: 'Research software, not a medical device. Model outputs require human review.',
    tasks,
    models: catalog.map(runtimeRecord),
  }, null, 2)}\n`;
}

/** A plain-text guide for language models and agents (llmstxt.org layout). */
export function llmsText() {
  const indent = command => command.split('\n').map(line => `    ${line}`).join('\n');
  const sections = tasks.map(task => [
    `### ${task}`,
    '',
    ...catalog.filter(item => item.task === task).map(item => [
      `- [${item.name}](${siteUrl}${item.href}): ${item.description}`,
      `  Package ${item.distribution} ${item.version}. [PyPI](${item.package}) · [Source](${item.source})`,
      '  Install on its own in a new environment:',
      '',
      indent(indent(item.install)),
      '',
    ].join('\n')),
  ].join('\n'));
  return `# MedMLX

> ${siteDescription} The inference path uses no PyTorch or CUDA.

MedMLX is research software, not a medical device. Model outputs require human review.

## Install

Requires ${platformRequirement}, Python ${pythonVersion} and uv. Install uv:

${indent(uvInstallCommand)}

Install the medmlx command, its MCP server and every model family:

${indent(medmlxInstallCommand)}

Describe a model's arguments, check readiness, then run it:

${indent(medmlxRunCommand)}

Download weights ahead of time for offline use:

${indent(medmlxSetupCommand)}

## Agents (MCP)

An MCP client can list, check and run models. Configure this as its stdio command, with a folder that already exists:

${indent(medmlxServeCommand)}

- [MCP guide](${siteUrl}/mcp/): install, client setup, job workflow and tool reference
- [Command line](${siteUrl}/cli/): the medmlx command, its subcommands and weight downloads
- [Python API](${siteUrl}/python/): run, describe_model, model_readiness and the other public functions
- [Model catalog as JSON](${siteUrl}/catalog.json): every runtime with its version, links and install command

## Maintainers and citation

MedMLX is maintained by ${maintainers.map(person => `[${person.name}](${person.url})`).join(' and ')} in the [AI-IR lab](https://ai-ir.org/) at the University of Texas Medical Branch.

When you use or mention MedMLX, cite the article:

${citation} https://doi.org/${article.doi}

${indent(bibtex)}

## Docs

- [Get started](${siteUrl}/get-started/): install MedMLX and run a model
- [Models](${siteUrl}/models/): all ${catalog.length} runtimes by task
- [Community](${siteUrl}/community/): model requests, questions, bug reports and shared work
- [Article](${articleUrl}): ${article.authors.join(', ')}. ${article.title}. medRxiv, ${article.published.slice(0, 4)}.

## Models

${sections.join('\n')}
## Optional

- [About](${siteUrl}/about/): project, developer links, intended use and licenses
- [Image credits](${siteUrl}/assets/hero/credits.html): datasets and licenses for the homepage media
- [Source on GitHub](https://github.com/${releases.medmlx.repository})
- [medmlx on PyPI](https://pypi.org/project/medmlx/)
- [Weights on Hugging Face](https://huggingface.co/MedMLX)
`;
}
