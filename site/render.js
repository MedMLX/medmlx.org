// Page markup, routes and page metadata. This module has no DOM access, so the
// exporter can prerender every route and app.js can render the same markup.
import { models, additionalRuntimes, reportCommand } from './models.js';
import {
  medmlxInstallCommand, medmlxProjectCommand, medmlxRunCommand, medmlxServeCommand, medmlxSetupCommand,
  platformRequirement, pythonVersion, releases, uvInstallCommand,
} from './releases.js';
import { mcpCalls, mcpCommands, mcpGuideSource, mcpTools, medmlxDoc } from './mcp.js';
import { cliCommands, cliExamples, pythonExamples, pythonFunctions, readmeSource, setupSource } from './developer.js';

// Links on the About page.
const developerLinks = [
  ['GitHub', 'https://github.com/MedMLX'],
  ['PyPI', 'https://pypi.org/project/medmlx/'],
  ['Hugging Face', 'https://huggingface.co/MedMLX'],
  ['MCP guide', '/mcp/'],
];
const labUrl = 'https://ai-ir.org/';
export const articleUrl = 'https://doi.org/10.64898/2026.10.28.26366762';
export const article = {
  title: 'MedMLX: On-Device Medical Imaging AI for Apple Silicon',
  authors: ['Joseph Sandoval', 'Alfredo Sandoval Jr.', 'Arsalan Saleem'],
  published: '2026-10-29',
  doi: '10.64898/2026.10.28.26366762',
};
export const citation = 'Sandoval J, Sandoval A Jr, Saleem A. MedMLX: On-Device Medical Imaging AI for Apple Silicon. medRxiv. 2026.';
export const bibtex = `@article{sandoval2026medmlx,
  title   = {MedMLX: On-Device Medical Imaging AI for Apple Silicon},
  author  = {Sandoval, Joseph and Sandoval, Jr., Alfredo and Saleem, Arsalan},
  journal = {medRxiv},
  year    = {2026},
  doi     = {${article.doi}},
  url     = {${articleUrl}}
}`;

// The maintainers and their lab, with the identifiers their own sites publish,
// so search engines and agents connect MedMLX to the same people.
const labData = {
  '@type': 'ResearchOrganization',
  '@id': 'https://ai-ir.org/#organization',
  name: 'AI in Interventional Radiology Research Group',
  alternateName: 'AI-IR',
  url: 'https://ai-ir.org/',
  parentOrganization: { '@type': 'CollegeOrUniversity', name: 'University of Texas Medical Branch', url: 'https://www.utmb.edu/' },
};
export const maintainers = [
  {
    '@type': 'Person', '@id': 'https://josephsandoval.org/#person', name: 'Joseph Sandoval', url: 'https://josephsandoval.org/',
    sameAs: [
      'https://orcid.org/0009-0008-9971-7103', 'https://scholar.google.com/citations?user=DB6AKw8AAAAJ',
      'https://www.linkedin.com/in/joseph-s-182387319/', 'https://github.com/sandovaljoseph',
    ],
    affiliation: { '@id': labData['@id'] },
  },
  {
    '@type': 'Person', '@id': 'https://alfredo-sandoval.com/#person', name: 'Alfredo Sandoval Jr.', alternateName: 'Alfredo Sandoval',
    url: 'https://alfredo-sandoval.com/',
    sameAs: [
      'https://orcid.org/0000-0002-7230-8325', 'https://scholar.google.com/citations?user=vKKZksgAAAAJ',
      'https://www.ncbi.nlm.nih.gov/myncbi/alfredo.sandoval.3/bibliography/public/', 'https://github.com/Alfredo-Sandoval',
      'https://x.com/AlfSandoval_',
    ],
    affiliation: { '@id': labData['@id'] },
  },
];
export const siteUrl = 'https://medmlx.org';
export const siteTitle = 'MedMLX — On-device medical imaging AI for Apple Silicon';
export const siteDescription = 'On-device medical imaging AI for Apple Silicon. MedMLX reimplements published medical imaging models in MLX, and all inference runs on your Mac.';

// Interpolated values are escaped recursively, except nested html`` results.
// Only markup constructed by this module should be passed as a Markup value.
class Markup {
  /** Hold markup constructed by this module so nested templates stay escaped. */
  constructor(text) { this.text = text; }
  /** Supply the trusted markup when assigned to the DOM. */
  toString() { return this.text; }
}

/** Build a markup fragment, escaping interpolated values unless already trusted. */
function html(strings, ...values) {
  return new Markup(strings.reduce((out, string, i) => out + markup(values[i - 1]) + string));
}

/** Escape text recursively; nested Markup fragments are already trusted. */
function markup(value) {
  if (value instanceof Markup) return value.text;
  if (Array.isArray(value)) return value.map(markup).join('');
  if (value === undefined || value === null || value === false) return '';
  return String(value).replace(/[&<>"']/g, char => `&#${char.charCodeAt(0)};`);
}

// Components

// Decorative macOS window controls for command panels.
const windowDots = html`<span class="window-dots" aria-hidden="true"><i></i><i></i><i></i></span>`;

/** Render term/value rows as a semantic description list. */
function specList(rows) {
  return html`
    <dl class="specs">
      ${rows.map(([term, value]) => html`<div><dt>${term}</dt><dd>${value}</dd></div>`)}
    </dl>`;
}

/** Render a button linked to the id of the command it copies. */
function copyButton(target, label) {
  return html`<button class="copy-button" type="button" data-copy="${target}" aria-label="Copy ${label}">Copy</button>`;
}

/** Render a labeled, copyable shell command without executing it. */
function terminal(id, label, command, copyLabel = `${label.toLowerCase()} command`) {
  return html`
    <div class="terminal">
      <div class="terminal-bar">
        ${windowDots}
        <span class="terminal-label">${label}</span>
        ${copyButton(id, copyLabel)}
      </div>
      <pre><code id="${id}">${command}</code></pre>
    </div>`;
}

/** Render a one-line command with an inline copy button. */
function commandLine(id, command, copyLabel) {
  return html`
    <div class="command-line">
      <code id="${id}">${command}</code>
      ${copyButton(id, copyLabel)}
    </div>`;
}

/** Render the one-command MedMLX install with its requirements. */
function installAll(id) {
  return html`
    <div class="install-all">
      ${commandLine(id, medmlxInstallCommand, 'MedMLX install command')}
      <p class="meta">Installs the <code>medmlx</code> command, its MCP server and every model family.
        Needs ${platformRequirement} and <a href="/get-started/" data-route>uv</a>.</p>
    </div>`;
}

// Keep recognizable entry points first in both the homepage and catalog.
const featuredNames = ['nnU-Net', 'TotalSegmentator', 'MedSAM2', 'BioMedParse'];
export const catalog = [
  ...models.map(model => ({
    name: model.name, task: model.task, description: model.description, distribution: model.distribution,
    install: model.commands.install, package: model.links.package,
  })),
  ...additionalRuntimes,
].map(item => {
  const { repository, version } = releases[item.distribution];
  return {
    ...item, version, href: `/models/${item.distribution}/`, internal: true,
    source: `https://github.com/${repository}/tree/v${version}`,
  };
}).sort((a, b) => {
  const rank = item => featuredNames.includes(item.name) ? featuredNames.indexOf(item.name) : featuredNames.length;
  return rank(a) - rank(b);
});

// New task names still appear in the catalog even before they are ordered here.
const taskOrder = ['Segmentation', 'Detection', 'Generation', 'Vision-language', 'Quantitative imaging', 'Feature extraction'];
export const tasks = [...new Set(catalog.map(item => item.task))].sort((a, b) => {
  const rank = task => taskOrder.indexOf(task) < 0 ? taskOrder.length : taskOrder.indexOf(task);
  return rank(a) - rank(b) || a.localeCompare(b);
});

const taskImages = { Generation: 'synthetic', 'Feature extraction': 'features' };
const featuredImages = { 'nnU-Net': 'liver', TotalSegmentator: 'anatomy', MedSAM2: 'medsam', BioMedParse: 'prompt' };
// Task cards that loop a saved model run; each has <name>.mp4, <name>-poster.webp and <name>-run.json.
const taskLoops = { Segmentation: 'abdomen-scroll', Detection: 'nodule-scroll', 'Quantitative imaging': 'radiomics-organs' };
export const pauseIcon = html`<svg width="12" height="12" viewBox="0 0 14 14" fill="currentColor" aria-hidden="true"><path d="M3 2h3v10H3zm5 0h3v10H8z"/></svg>`;
export const playIcon = html`<svg width="12" height="12" viewBox="0 0 14 14" fill="currentColor" aria-hidden="true"><path d="M4 2l8 5-8 5z"/></svg>`;

/** Pair a chest CT with excerpts from its saved MLX-Reason-CT report. */
function visionLanguagePreview() {
  return html`
    <div class="vision-preview" aria-hidden="true">
      <img class="vision-scan" src="/assets/hero/vision-language-ct.webp" width="521" height="411"
        alt="" loading="lazy" decoding="async">
      <div class="vision-report">
        <span class="report-caption">Report excerpt</span>
        <span class="report-line">Non-contrast CT.</span>
        <span class="report-line">Trachea and main</span>
        <span class="report-line">bronchi are patent.</span>
        <span class="report-line">A few tiny nonspecific</span>
        <span class="report-line">pulmonary nodules.</span>
      </div>
    </div>`;
}

/** Render links to catalog groups with their counts and representative models. */
function taskCards() {
  return html`<ul class="task-grid">
    ${tasks.map(task => {
      const items = catalog.filter(item => item.task === task);
      const loop = taskLoops[task];
      return html`<li class="task-item"><a class="task-card" href="/models/?task=${encodeURIComponent(task)}" data-route>
        ${task === 'Vision-language' ? visionLanguagePreview() : loop ? html`
          <video class="task-image" muted loop playsinline preload="none" width="800" height="520" aria-hidden="true"
            poster="/assets/hero/${loop}-poster.webp" data-src="/assets/hero/${loop}.mp4"></video>` : html`
          <img class="task-image" src="/assets/hero/${taskImages[task] || 'total-ct'}.webp" width="640" height="420" alt="" loading="lazy" decoding="async">`}
        <h3>${task}</h3>
        <span class="task-count">${items.length} ${items.length === 1 ? 'package' : 'packages'}</span>
        <p>${items.slice(0, 3).map(item => item.name).join('\u00a0· ')}</p>
        <span class="task-link">Explore <span aria-hidden="true">›</span></span>
      </a>${loop ? html`
        <button class="media-toggle" type="button" data-media-toggle aria-label="Pause ${task.toLowerCase()} animation" hidden>${pauseIcon}</button>` : ''}</li>`;
    })}
  </ul>`;
}

const quickstartSteps = [['install', 'Install'], ['download', 'Download'], ['report', 'Run']];
/** Render the model's install, download, and run commands as accessible tabs. */
function quickstart(model) {
  return tabbedTerminal('quickstart', 'Quick start', quickstartSteps.map(([step, label]) => [step, label, model.commands[step]]));
}

/** Render several commands in one panel, chosen with tabs; each tab carries its text. */
function tabbedTerminal(id, label, steps) {
  return html`
    <div class="terminal">
      <div class="terminal-bar">
        ${windowDots}
        <div class="terminal-tabs" role="tablist" aria-label="${label}">
          ${steps.map(([key, name, command], i) => html`
            <button type="button" role="tab" id="${id}-tab-${key}" data-step="${key}" data-command="${command}" aria-controls="${id}-panel"
              aria-selected="${String(i === 0)}" tabindex="${i === 0 ? 0 : -1}">${name}</button>`)}
        </div>
        ${copyButton(`${id}-command`, label.toLowerCase())}
      </div>
      <pre id="${id}-panel" role="tabpanel" aria-labelledby="${id}-tab-${steps[0][0]}"><code id="${id}-command">${steps[0][2]}</code></pre>
    </div>`;
}

// Pages

/** Render the landing page, featured runtimes, and task links. */
function homePage() {
  return html`
    <section class="hero" aria-labelledby="hero-title">
      <div class="container hero-layout">
        <div class="hero-inner">
          <div class="hero-copy">
            <h1 id="hero-title">Medical imaging.<br>Native on Mac.</h1>
            <p class="hero-lead">Run medical imaging models locally on Apple Silicon.</p>
          </div>
          <div class="actions">
            <a class="button" href="/models/" data-route>Browse models</a>
            <a class="hero-article" href="${articleUrl}">Read the article <span aria-hidden="true">↗</span></a>
          </div>
          ${installAll('hero-install')}
        </div>
        <div class="hero-media" aria-hidden="true">
          <video class="hero-video" muted loop playsinline preload="none" width="1600" height="1000"
            poster="/assets/hero/poster.webp" data-src="/assets/hero/outputs.mp4" data-scenes="6" tabindex="-1"></video>
        </div>
      </div>
      <div class="container hero-film-bar">
        <p>Outputs from MedMLX runtimes. <a href="/assets/hero/credits.html">Image credits</a></p>
        <div class="film-controls" role="group" aria-label="Hero visuals" hidden>
          <button class="film-toggle" type="button" data-film-back aria-label="Previous visual" title="Previous visual" disabled>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m14 6-6 6 6 6"/></svg>
          </button>
          <button class="film-toggle" type="button" data-film-toggle title="Pause film">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor" aria-hidden="true"><path d="M3 2h3v10H3zm5 0h3v10H8z"/></svg>
            <span class="sr-only">Pause film</span>
          </button>
          <button class="film-toggle" type="button" data-film-next aria-label="Next visual" title="Next visual" disabled>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m10 6 6 6-6 6"/></svg>
          </button>
        </div>
      </div>
    </section>

    <section class="section statement-section" aria-label="Overview">
      <div class="container">
        <p class="statement">MedMLX reimplements published medical imaging models in MLX, Apple’s machine learning framework.
          <strong>All inference runs on device.</strong></p>
      </div>
    </section>

    <section class="section">
      <div class="container">
        <div class="explore-heading">
          <h2 class="section-title">Featured models</h2>
          <p class="link-row"><a href="/models/" data-route>All models and tools</a></p>
        </div>
        <ul class="featured-models">
          ${catalog.filter(item => featuredNames.includes(item.name)).map(item => html`
            <li>
              <a class="featured-image" href="${item.href}" ${item.internal ? html`data-route` : ''} tabindex="-1" aria-hidden="true">
                <img src="/assets/hero/${featuredImages[item.name]}.webp" width="480" height="360" alt="" loading="lazy" decoding="async">
              </a>
              <h3><a href="${item.href}" ${item.internal ? html`data-route` : ''}>${item.name}</a></h3>
              <p>${item.description}</p>
            </li>`)}
        </ul>
      </div>
    </section>

    <section class="section">
      <div class="container">
        <div class="explore-heading">
          <h2 class="section-title">Models by task</h2>
        </div>
        ${taskCards()}
      </div>
    </section>

    <section class="section">
      <div class="container">
        <div class="tile tile-center">
          <h2>Intended use</h2>
          <p>MedMLX is research software and not a medical device. Outputs require human review, and matching the original model does not establish clinical validity.</p>
          <p class="link-row"><a href="/about/" data-route>About MedMLX</a></p>
        </div>
      </div>
    </section>`;
}

/** Render the catalog with its search text and recognized task from the URL. */
function modelsPage(search = '') {
  const parameters = new URLSearchParams(search);
  const requestedTask = parameters.get('task');
  const selectedTask = tasks.includes(requestedTask) ? requestedTask : '';
  const choice = (value, label) => html`<label class="task-chip"><input type="radio" name="task" value="${value}"
    ${value === selectedTask ? html`checked` : ''}><span>${label}</span></label>`;
  return html`
    <section class="container page-head">
      <h1>Models</h1>
      <p class="lead">Search by task, anatomy or name. The command below installs every model family, and each entry has its own install command.</p>
      ${installAll('models-install')}
    </section>
    <section class="container page-body">
      <form class="catalog-controls" role="search">
        <div class="field catalog-search">
          <label for="model-search" class="sr-only">Search models</label>
          <input id="model-search" type="search" value="${parameters.get('q') || ''}" placeholder="Search liver, CT or nnU-Net" autocomplete="off">
        </div>
        <fieldset class="task-chips">
          <legend class="sr-only">Task</legend>
          ${choice('', 'All')}
          ${tasks.map(task => choice(task, task))}
        </fieldset>
      </form>
      <p id="catalog-status" class="meta catalog-status" role="status" aria-live="polite"></p>
      <p id="catalog-empty" class="catalog-empty" hidden>No models match. Try another search or choose All.</p>
      <div class="catalog-groups">
        ${tasks.map(task => html`<section class="catalog-group" data-task="${task}">
          <h2>${task} <span class="catalog-count"></span></h2>
          <ul class="catalog-list">
            ${catalog.filter(item => item.task === task).map(item => html`
              <li class="catalog-item" data-search="${`${item.name} ${item.task} ${item.distribution} ${item.description}`.toLowerCase()}">
                <div class="catalog-body">
                  <h3>${item.internal
                    ? html`<a href="${item.href}" data-route>${item.name}</a>`
                    : html`<a href="${item.href}">${item.name}</a>`}</h3>
                  <p>${item.description}</p>
                </div>
                <div class="catalog-meta">
                  <code class="catalog-version">${item.distribution} ${item.version}</code>
                  <span class="catalog-links">
                    <a href="${item.package}" aria-label="${item.name} on PyPI">PyPI\u00a0<span aria-hidden="true">↗</span></a>
                    <a href="${item.source}" aria-label="${item.name} source on GitHub">GitHub\u00a0<span aria-hidden="true">↗</span></a>
                  </span>
                </div>
                <details class="install-details">
                  <summary>Install on its own</summary>
                  ${terminal(`install-${item.distribution}`, 'New environment', item.install, `${item.name} install command`)}
                </details>
              </li>`)}
          </ul>
        </section>`)}
      </div>
    </section>`;
}

/** Render one published model's commands, requirements, limits, and resources. */
function modelPage(model) {
  const { links } = model;
  const guide = model.slug === 'mlx-reason-ct' ? '/get-started/mlx-reason-ct/' : '/get-started/';
  return html`
    <section class="container page-head">
      <nav class="breadcrumb" aria-label="Breadcrumb">
        <a href="/models/" data-route>Models</a> <span aria-hidden="true">/</span>
        <a href="/models/?task=${encodeURIComponent(model.task)}" data-route>${model.task}</a> <span aria-hidden="true">/</span>
        <span aria-current="page">${model.name}</span>
      </nav>
      <h1>${model.name}</h1>
      <p class="lead">${model.summary}</p>
      <p class="meta">${model.task} · port of <a href="${model.upstream.url}">${model.upstream.name}</a></p>
      <div class="actions">
        <a class="button" href="${guide}" data-route>Get started</a>
        <a class="button secondary" href="${links.package}">Package on PyPI</a>
      </div>
    </section>

    <div class="container page-body">
      <section class="detail-section quickstart-section">
        <h2>Quick start</h2>
        <p>Install the runtime, download its weights and generate a report.</p>
        ${quickstart(model)}
        <p class="note"><a href="${guide}" data-route>Follow the complete guide</a></p>
      </section>
      <div class="detail-grid">
        <section class="detail-section">
          <h2>Requirements</h2>
          ${specList(model.requirements)}
        </section>
        <section class="detail-section">
          <h2>Outputs</h2>
          <p>Each run writes three files to the output directory.</p>
          <dl class="specs files">
            ${model.outputs.map(([file, text]) => html`<div><dt><code>${file}</code></dt><dd>${text}</dd></div>`)}
          </dl>
          <h2>Limitations</h2>
          ${model.limitations.map(text => html`<p>${text}</p>`)}
        </section>
      </div>

      <section class="detail-section">
        <h2>Intended use</h2>
        <p class="measure">For research and education. Not for clinical diagnosis or treatment decisions. Outputs require human review.</p>
      </section>

      <section class="detail-section">
        <h2>Resources</h2>
        <ul class="resource-list">
          <li><a href="${links.package}">Package and usage on PyPI</a></li>
          <li><a href="${links.weights}">Weights on Hugging Face</a></li>
        </ul>
      </section>
    </div>`;
}

/** Render the general setup guide and links to runtime instructions. */
function gettingStartedPage() {
  return html`
    <section class="container page-head">
      <h1>Get started</h1>
      <p class="lead">Install MedMLX with one command, then run models on your Mac.</p>
    </section>

    <div class="container page-body">
      <ol class="steps">
        <li>
          <h2>Install uv</h2>
          <p>MedMLX needs ${platformRequirement}. It uses <a href="https://docs.astral.sh/uv/">uv</a> to install Python ${pythonVersion} and its packages. If <code>uv --version</code> already works, skip this step.</p>
          ${terminal('uv-install-command', 'Install uv', uvInstallCommand)}
          <p class="note">With Homebrew, use <code>brew install uv</code> instead. Open a new terminal window afterwards.</p>
        </li>
        <li>
          <h2>Install MedMLX</h2>
          <p>This installs the <code>medmlx</code> command, its MCP server and every model family.</p>
          ${terminal('medmlx-install-command', 'Install MedMLX', medmlxInstallCommand)}
          <p class="note">For a smaller install, use <code>segment</code>, <code>generate</code> or <code>vision</code> instead of <code>all</code>.
            For a Python project, use <code>${medmlxProjectCommand}</code>. If your shell cannot find <code>medmlx</code>, run <code>uv tool update-shell</code> and open a new terminal window.</p>
        </li>
        <li>
          <h2>Run a model</h2>
          <p><code>describe</code> lists the arguments a model takes. Save yours in <code>arguments.json</code>. <code>readiness</code> checks that the model can run, without downloading anything. <code>run</code> downloads the weights the first time, then runs the model.</p>
          ${terminal('medmlx-run-command', 'Run', medmlxRunCommand)}
          <p>To download weights ahead of time for offline use:</p>
          ${terminal('medmlx-setup-command', 'Download weights', medmlxSetupCommand)}
          <p class="note">MedGemma runs in a separate med-vlm-mlx environment and needs local weights. MRSegmentator also needs local weights. Pass the folder as <code>weights_path</code>.</p>
          <p class="link-row"><a href="/cli/" data-route>Command line</a><a href="/python/" data-route>Python API</a></p>
        </li>
        <li>
          <h2>Connect an AI agent <span class="optional">(optional)</span></h2>
          <p>An MCP client can list, check and run models for you. Give this command to your client as the server to start. The folder must already exist:</p>
          ${terminal('medmlx-serve-command', 'MCP server', medmlxServeCommand)}
          <p class="link-row"><a href="/mcp/" data-route>MCP guide</a></p>
        </li>
      </ol>

      <section class="detail-section guide-single">
        <h2>Install one model</h2>
        <p>Each catalog entry has its own install command for a new environment.</p>
        <ul class="guide-models">
          ${catalog.filter(item => featuredNames.includes(item.name)).map(item => html`
            <li><a href="${item.href}" ${item.internal ? html`data-route` : ''}>${item.name}</a><span>${item.description}</span></li>`)}
        </ul>
        <p class="link-row"><a href="/models/" data-route>Browse all models and tools</a></p>
      </section>
    </div>`;
}

/** Render the Reason-CT guide and its local shell-command builder. */
function reasonCtStartedPage() {
  const model = models[0];
  return html`
    <section class="container page-head">
      <nav class="breadcrumb" aria-label="Breadcrumb"><a href="/models/mlx-reason-ct/" data-route>MLX-Reason-CT</a> <span aria-hidden="true">/</span> <span aria-current="page">Get started</span></nav>
      <h1>Get started with ${model.name}</h1>
      <p class="lead">Generate a report or ask a question about a chest or abdomen CT. The commands run locally, and this page never reads your scan.</p>
    </section>

    <div class="container page-body">
      <ol class="steps">
        <li>
          <h2>Install</h2>
          <p>Requires ${platformRequirement}, Python ${pythonVersion} and <a href="https://docs.astral.sh/uv/">uv</a>. Create an environment and install the MLX-Reason-CT runtime.</p>
          ${terminal('install-command', 'Install', model.commands.install)}
        </li>
        <li>
          <h2>Download the weights</h2>
          <p>The pinned revision is ${model.resourceSizes.weights}. A run peaks at ${model.resourceSizes.peakMemory} of MLX memory, in addition to what preprocessing, macOS and other apps use.</p>
          ${terminal('download-command', 'Download', model.commands.download)}
        </li>
        <li>
          <h2>Prepare the CT</h2>
          <p>Use one 3D CT volume in NIfTI format (<code>.nii</code> or <code>.nii.gz</code>) with Hounsfield unit values and valid spatial geometry.</p>
          ${model.limitations.map(text => html`<p>${text}</p>`)}
        </li>
        <li>
          <h2>Generate a report</h2>
          <p>Enter the paths on your Mac and copy the command. Run it in the same directory as your model and input, with the environment active; relative paths resolve there.</p>
          <form id="command-form" class="command-form" novalidate>
            <div class="field">
              <label for="ct-input">CT volume</label>
              <input id="ct-input" name="input" value="ct.nii.gz" autocomplete="off" spellcheck="false" aria-describedby="ct-input-error">
              <p id="ct-input-error" class="field-error"></p>
            </div>
            <div class="field-row">
              <div class="field">
                <label for="model-dir">Model directory</label>
                <input id="model-dir" name="modelDir" value="models" autocomplete="off" spellcheck="false" aria-describedby="model-dir-error">
                <p id="model-dir-error" class="field-error"></p>
              </div>
              <div class="field">
                <label for="output-dir">Output directory</label>
                <input id="output-dir" name="outputDir" value="outputs" autocomplete="off" spellcheck="false" aria-describedby="output-dir-error">
                <p id="output-dir-error" class="field-error"></p>
              </div>
            </div>
            <fieldset class="field">
              <legend>Anatomy</legend>
              <div class="choices">
                <label><input type="radio" name="anatomy" value="chest" checked> Chest</label>
                <label><input type="radio" name="anatomy" value="abdomen"> Abdomen</label>
              </div>
            </fieldset>
            <div class="field">
              <label for="ct-prompt">Question <span class="optional">(optional)</span></label>
              <textarea id="ct-prompt" name="prompt" rows="2" placeholder="Leave blank for a structured report"></textarea>
            </div>
            <label class="checkbox"><input type="checkbox" name="thinking"> <span>Thinking mode <span class="optional">(saves the reasoning to <code>model_response.json</code>)</span></span></label>
          </form>
          ${terminal('report-command', 'Report', '')}
          <p class="note">Each run writes <code>report.txt</code>, <code>model_response.json</code> and <code>run.json</code>.
            The <a href="${model.links.package}">package page</a> covers the Python API and other options.</p>
        </li>
      </ol>
    </div>`;
}

/** Render text with `backticked` spans as inline code, escaping the rest. */
function inlineCode(text) {
  return text.split('`').map((part, i) => i % 2 ? html`<code>${part}</code>` : part);
}

/** Render the MCP guide, copied from docs/mcp.md at the reviewed medmlx tag. */
function mcpPage() {
  const sections = [
    ['connect', 'Connect a client'], ['tools', 'Tools'], ['run', 'Run a model'],
    ['jobs', 'Readiness and jobs'], ['source', 'Install from source'], ['files', 'Files and permissions'],
  ];
  const example = tabbedTerminal('mcp-example', 'TotalSegmentator example', mcpCalls.map(([tool, json]) => [tool.replace(/_/g, '-'), tool, json]));
  return html`
    <section class="container page-head">
      <h1>MCP guide</h1>
      <p class="lead">The MedMLX MCP server lets an AI agent on your Mac find the installed models, check what each one needs and run it.</p>
      <p class="meta">From the medmlx ${releases.medmlx.version} documentation. <a href="${mcpGuideSource}">Source on GitHub</a></p>
      <ol class="flow" aria-label="How the server connects">
        <li><strong>MCP client</strong><span>Codex or another agent starts the server as a subprocess.</span></li>
        <li><strong><code>medmlx serve</code></strong><span>Talks to the client over stdin and stdout, one session per client.</span></li>
        <li><strong>Model runtimes</strong><span>Run as supervised workers on your Mac with MLX.</span></li>
      </ol>
    </section>

    <div class="container page-body doc-layout">
      <nav class="doc-toc" aria-label="On this page">
        <h2>On this page</h2>
        <ul>${sections.map(([id, title]) => html`<li><a href="#${id}">${title}</a></li>`)}</ul>
      </nav>
      <div class="doc-body">
        <section class="guide-section" id="connect" aria-labelledby="connect-title">
          <h2 id="connect-title">Connect a client</h2>
          <ol class="sequence">
            <li>Install MedMLX with its MCP server, as on <a href="/get-started/" data-route>Get started</a>:
              ${terminal('mcp-medmlx-install', 'Install MedMLX', medmlxInstallCommand)}</li>
            <li>Give this command to your client as the server to start. The folder must already exist:
              ${terminal('mcp-serve', 'MCP server', medmlxServeCommand)}</li>
          </ol>
          <p>When the client disconnects, its running jobs stop. Installing MedMLX doesn't add it to your client. You register it in the client's settings.</p>
        </section>

        <section class="guide-section" id="tools" aria-labelledby="tools-title">
          <h2 id="tools-title">Tools</h2>
          <p>Your client may show these tools to you, or let the agent call them for you.</p>
          <ul class="tool-grid">
            ${mcpTools.map(([tool, args, purpose]) => html`
              <li><code class="tool-name">${tool}</code><span class="tool-args">${args === 'None' ? 'No arguments' : inlineCode(args)}</span><p>${inlineCode(purpose)}</p></li>`)}
          </ul>
          <p>If a model is missing, check that its family is installed and look at <code>discovery_errors</code>. If a run is blocked, check <code>runtime_info</code>, the reason and hint from readiness, and the job's error and log. <code>list_checkpoints</code> shows where checkpoints come from. It doesn't mean they're installed or tested.</p>
        </section>

        <section class="guide-section" id="run" aria-labelledby="run-title">
          <h2 id="run-title">Run a model</h2>
          <p>A run usually goes like this:</p>
          <ol class="sequence">
            <li>Call <code>runtime_info</code> and <code>list_models</code> to see what this Mac supports and which models are installed.</li>
            <li>Call <code>describe_model</code> for the model you want. <code>parameters</code> lists its arguments, and <code>instructions</code> is the model author's own documentation. Follow it for inputs, weights, units and outputs.</li>
            <li>Call <code>model_readiness</code> with the model ID and the arguments you plan to use, and fix anything it reports.</li>
            <li>Call <code>run_model</code>, keep the <code>job_id</code> it returns, and call <code>get_job</code> until the job finishes. Then read the result or error and open the output files.</li>
          </ol>
          <h3>Example: TotalSegmentator</h3>
          <p>With a converted TotalSegmentator model and a CT image in NIfTI format in place, a client can call these tools with these arguments. Paths are relative to the server's folder; replace them with your own. The <a href="https://github.com/MedMLX/totalsegmentator-mlx/tree/v${releases['totalsegmentator-mlx'].version}">TotalSegmentator runtime</a> documents its model folders, modes and input requirements.</p>
          ${example}
          <p>Call <code>get_job</code> again while the state is <code>running</code>. A short job may already be done the first time you check. TotalSegmentator writes <code>mask.nii.gz</code> to the output folder and doesn't overwrite an existing mask by default. When the run succeeds, the job result lists the output files.</p>
          <p>To try a full MCP session without model weights, follow the <a href="${medmlxDoc('mcp-smoke.md')}">FDG smoke walkthrough</a>. It creates its own test inputs.</p>
        </section>

        <section class="guide-section" id="jobs" aria-labelledby="jobs-title">
          <h2 id="jobs-title">Readiness and jobs</h2>
          <p><code>model_readiness</code> reports <code>ready</code> and <code>runtime_ready</code>, which always match. They say that the model's package loads and Metal works, not that a particular run will succeed. <code>run_ready</code> is <code>false</code> when there's a known problem, and <code>null</code> when none was found but the input and checkpoint files weren't checked. In this version it is never <code>true</code>.</p>
          <p>When you pass arguments, pass exactly one model ID. The check confirms the argument names, that required arguments are present and that input and weight paths exist. It doesn't open the images, check their geometry, check that a checkpoint fits the model, or check whether outputs would be overwritten. <code>run_model</code> repeats the argument and Metal checks before starting. The model checks its own inputs when it runs, so a run can still fail.</p>
          <p>A job is <code>running</code>, <code>completed</code>, <code>failed</code> or <code>cancelled</code>. <code>get_job</code> can wait up to 60 seconds for a change with <code>wait_seconds</code>, which defaults to 0. It returns the end of the log and, when ready, the result or error. <code>list_jobs</code> lists this session's jobs, and <code>cancel_job</code> stops a running job and anything it started. Jobs belong to the session: when the client disconnects, running jobs stop, and a new session can't see them. Cancelling doesn't delete files a model has already written.</p>
        </section>

        <section class="guide-section" id="source" aria-labelledby="source-title">
          <h2 id="source-title">Install from source</h2>
          <p>To run from source, you need macOS on Apple Silicon, Python ${pythonVersion} and <a href="https://docs.astral.sh/uv/getting-started/installation/">uv</a>. Clone the repository and install the MCP server with the model family you need. This installs the segmentation family:</p>
          ${terminal('mcp-install-command', 'Install from source', mcpCommands.install)}
          <p>The clone starts on the main branch. To match this ${releases.medmlx.version} guide, run <code>git checkout v${releases.medmlx.version}</code> before <code>uv sync</code>. For other families, use <code>generate</code>, <code>vision</code> or <code>all</code> in place of <code>segment</code>.</p>
          <p>Most models download their weights the first time they run if you leave out <code>weights_path</code>. To work offline, run <code>medmlx setup --all</code> first, or pass your own folder as <code>weights_path</code>. Readiness never downloads anything. MedGemma needs local weights and runs through a <a href="${medmlxDoc('medvlm-bridge.md')}">bridge to a separate environment</a>.</p>
          <p>Before connecting a client, check the install. <code>models</code> lists the installed models and any that failed to load, and <code>runtime</code> checks MLX and Metal.</p>
          ${terminal('mcp-check-command', 'Check', mcpCommands.check)}
          <h3>Codex</h3>
          <p>Run this from the checkout. It makes a working folder in your home directory and registers the checkout's <code>medmlx</code> by its full path, so Codex uses the environment you just installed.</p>
          ${terminal('mcp-codex-command', 'Codex', mcpCommands.codex)}
          <p>Start a new Codex session and check its MCP servers, or type <code>/mcp</code> in the terminal. Then ask it to list the MedMLX models and report <code>runtime_info</code>. The <a href="https://developers.openai.com/codex/mcp/">Codex MCP documentation</a> covers setup and troubleshooting.</p>
          <h3>Other clients</h3>
          <p>Set the command to the full path of <code>.venv/bin/medmlx</code>, with <code>serve</code>, <code>--root</code> and the full path of your working folder as separate arguments. The folder must already exist. Without <code>--root</code>, the server uses whatever folder it starts in, which may not be the one you work in.</p>
        </section>

        <section class="guide-section" id="files" aria-labelledby="files-title">
          <h2 id="files-title">Files and permissions</h2>
          <p><code>--root</code> sets the folder that relative paths start from. It isn't a sandbox: a model can read and write any path that your account and your client allow, and some models download files. Results and logs go back to the MCP client and can include file paths and model output, so set your client's access and data settings with that in mind.</p>
          <p>MedMLX is research software. Matching the original model's numbers doesn't make it clinically equivalent, and every output needs human review.</p>
        </section>
      </div>
    </div>`;
}

/** Render a reference page's heading, source line and "On this page" links. */
function referenceHead(title, lead, sections) {
  return {
    head: html`
      <section class="container page-head">
        <h1>${title}</h1>
        <p class="lead">${lead}</p>
        <p class="meta">From the medmlx ${releases.medmlx.version} documentation. <a href="${readmeSource}">README</a> · <a href="${setupSource}">Setup guide</a></p>
      </section>`,
    toc: html`
      <nav class="doc-toc" aria-label="On this page">
        <h2>On this page</h2>
        <ul>${sections.map(([id, title]) => html`<li><a href="#${id}">${title}</a></li>`)}</ul>
      </nav>`,
  };
}

/** Render the command line reference, copied from the README and setup guide at the reviewed tag. */
function cliPage() {
  const { head, toc } = referenceHead('Command line',
    html`The <code>medmlx</code> command finds, checks and runs models, downloads their weights and starts the MCP server.`,
    [['install', 'Install'], ['run', 'Run a model'], ['commands', 'Commands'], ['weights', 'Weights'], ['mcp', 'MCP server']]);
  return html`
    ${head}
    <div class="container page-body doc-layout">
      ${toc}
      <div class="doc-body">
        <section class="guide-section" id="install" aria-labelledby="install-title">
          <h2 id="install-title">Install</h2>
          <p>This installs the <code>medmlx</code> command and the MCP server with every model family. You need ${platformRequirement} and <a href="https://docs.astral.sh/uv/getting-started/installation/">uv</a>.</p>
          ${terminal('cli-install', 'Install MedMLX', cliExamples.install)}
          <p>For a smaller install, replace <code>all</code> with <code>segment</code>, <code>generate</code> or <code>vision</code>. Weights download the first time you run a model, and each set keeps its own license.</p>
        </section>

        <section class="guide-section" id="run" aria-labelledby="run-title">
          <h2 id="run-title">Run a model</h2>
          ${terminal('cli-run', 'Run a model', cliExamples.run)}
          <p><code>describe</code> lists the arguments a model takes. <code>readiness</code> checks that the model can run on this Mac, without downloading anything. <code>run</code> reads the arguments from a JSON file, runs the model and waits for it to finish. Relative paths in the file are read from the <code>--root</code> folder.</p>
          <p>Most models download their weights the first time they run, so you can leave out <code>weights_path</code>. Later runs reuse that download, and each run records which weights it used. To use your own weights, pass a local folder as <code>weights_path</code>. MedGemma and MRSegmentator need local weights for now.</p>
        </section>

        <section class="guide-section" id="commands" aria-labelledby="commands-title">
          <h2 id="commands-title">Commands</h2>
          <ul class="tool-grid">
            ${cliCommands.map(([name, args, purpose]) => html`
              <li><code class="tool-name">medmlx ${name}</code><span class="tool-args">${args || 'No arguments'}</span><p>${purpose}</p></li>`)}
          </ul>
          <p>Every command except <code>serve</code> prints JSON. If an installed model fails to load, <code>models</code> lists it under <code>discovery_errors</code> and exits with an error.</p>
        </section>

        <section class="guide-section" id="weights" aria-labelledby="weights-title">
          <h2 id="weights-title">Weights</h2>
          <p>Models download their weights the first time they run. To work offline, download them first. The first command downloads every installed model, and the second downloads one:</p>
          ${terminal('cli-setup', 'Download weights', cliExamples.setup)}
          <p>If one model fails, the rest still download, and the command exits with an error at the end. Models that need manual setup are reported as unsupported. Downloading doesn't run or test a model.</p>
          <p>To see what would download without downloading anything, run <code>${cliExamples.plan}</code>. On its own, <code>medmlx setup</code> lists the installed models and where their weights come from. To update or repair a download, run <code>${cliExamples.refresh}</code>. Folders you pass as <code>weights_path</code> are never changed.</p>
          <p>Weights are saved as plain files in <code>~/.cache/medmlx/&lt;model_id&gt;</code>. Set <code>MEDMLX_ASSET_CACHE</code> to use another folder. Finished downloads work offline, and an interrupted download picks up where it left off.</p>
        </section>

        <section class="guide-section" id="mcp" aria-labelledby="mcp-title">
          <h2 id="mcp-title">MCP server</h2>
          ${terminal('cli-serve', 'MCP server', cliExamples.serve)}
          <p>Give this command to your MCP client as the server to start. When the client disconnects, its running jobs stop. The <a href="/mcp/" data-route>MCP guide</a> shows how to connect a client and run a model step by step.</p>
        </section>
      </div>
    </div>`;
}

/** Render the Python API reference, copied from the README, setup guide and exports at the reviewed tag. */
function pythonPage() {
  const { head, toc } = referenceHead('Python API',
    'Use MedMLX from your own Python code. Each function does the same job as a command and an MCP tool.',
    [['install', 'Install'], ['run', 'Run a model'], ['functions', 'Functions'], ['weights', 'Weights']]);
  return html`
    ${head}
    <div class="container page-body doc-layout">
      ${toc}
      <div class="doc-body">
        <section class="guide-section" id="install" aria-labelledby="install-title">
          <h2 id="install-title">Install</h2>
          <p>Add MedMLX to a Python ${pythonVersion} project with <a href="https://docs.astral.sh/uv/getting-started/installation/">uv</a>:</p>
          ${terminal('python-install', 'Add to a project', pythonExamples.install)}
          <p>For a smaller install, replace <code>all</code> with <code>segment</code>, <code>generate</code> or <code>vision</code>. Import it as <code>medmlx</code>.</p>
        </section>

        <section class="guide-section" id="run" aria-labelledby="run-title">
          <h2 id="run-title">Run a model</h2>
          ${terminal('python-run', 'Python', pythonExamples.run, 'Python example')}
          <p><code>arguments</code> is a dictionary of the model's arguments, and <code>describe_model</code> lists the ones it accepts. <code>run</code> runs the model in a separate process and waits for it to finish. If you interrupt it, that process stops. Relative paths are read from the <code>root</code> folder.</p>
        </section>

        <section class="guide-section" id="functions" aria-labelledby="functions-title">
          <h2 id="functions-title">Functions</h2>
          <ul class="tool-grid">
            ${pythonFunctions.map(([name, signature, purpose]) => html`
              <li><code class="tool-name">medmlx.${name}</code><span class="tool-args"><code>${signature}</code></span><p>${purpose}</p></li>`)}
          </ul>
        </section>

        <section class="guide-section" id="weights" aria-labelledby="weights-title">
          <h2 id="weights-title">Weights</h2>
          <p>Weights download the first time a model runs. To download them ahead of time, call <code>setup_model(model_id)</code> or <code>setup_all()</code>, which work like <a href="/cli/#weights" data-route><code>medmlx setup</code></a>. <code>setup_plan(model_id)</code> and <code>list_setup_plans()</code> show what would download without downloading it.</p>
        </section>
      </div>
    </div>`;
}

/** Render the project, licensing, and intended-use information. */
function aboutPage() {
  return html`
    <section class="container page-head">
      <h1>About MedMLX</h1>
      <p class="lead">MedMLX reimplements published medical imaging models in MLX for on-device AI on Apple Silicon. The inference path uses no PyTorch or CUDA.</p>
      <div class="actions">
        <a class="button" href="${articleUrl}">Read the article</a>
        <a class="hero-guide" href="https://github.com/MedMLX">Source on GitHub <span aria-hidden="true">›</span></a>
      </div>
    </section>
    <div class="container page-body">
      <div class="detail-grid about-grid">
        <section class="detail-section" aria-labelledby="article-title">
          <h2 id="article-title">Article</h2>
          <p>${citation}</p>
          <p class="link-row"><a href="${articleUrl}">doi:${article.doi}</a></p>
          ${terminal('article-bibtex', 'BibTeX', bibtex, 'BibTeX citation')}
        </section>
        <section class="detail-section" aria-labelledby="developers-title">
          <h2 id="developers-title">For developers</h2>
          <p>The medmlx package provides a Python API, a command-line tool and an MCP server. Each model runtime has its own weights, requirements and install instructions.</p>
          <p class="link-row">
            ${developerLinks.map(([title, href]) => href.startsWith('/')
              ? html`<a href="${href}" data-route>${title}</a>`
              : html`<a href="${href}">${title}</a>`)}
          </p>
        </section>
        <section class="detail-section" aria-labelledby="use-title">
          <h2 id="use-title">Intended use</h2>
          <p>MedMLX is research software. It is not a medical device and is not for clinical use. Model outputs require human review.</p>
        </section>
        <section class="detail-section" aria-labelledby="licenses-title">
          <h2 id="licenses-title">Licenses</h2>
          <p>Code and weights are licensed separately. Each package's README and third-party notices give the terms for both.</p>
          <p>Sources and licenses for the homepage images and videos are on the <a href="/assets/hero/credits.html">image credits</a> page.</p>
        </section>
      </div>
      <section class="detail-section lab-credit" aria-label="Maintainers">
        <a class="lab-logo" href="${labUrl}" tabindex="-1" aria-hidden="true">
          <img src="/assets/lab/ai-ir-logo.svg" alt="" width="252" height="112">
        </a>
        <p>Maintained by <a href="https://github.com/sandovaljoseph">Joseph Sandoval</a> and <a href="https://github.com/Alfredo-Sandoval">Alfredo Sandoval Jr.</a>
          in the <a href="${labUrl}">AI-IR lab</a> at the University of Texas Medical Branch.</p>
      </section>
    </div>`;
}

/** Render the fallback for a path without a known client-side route. */
function notFoundPage() {
  return html`
    <section class="container page-head">
      <h1>Page not found</h1>
      <p class="lead">There is no page at this address.</p>
      <div class="actions"><a class="button" href="/" data-route>Home</a><a class="button secondary" href="/models/" data-route>Models</a></div>
    </section>`;
}

/** Render a published runtime's install command, links and related runtimes. */
function runtimePage(item) {
  const related = catalog.filter(other => other.task === item.task && other !== item);
  const bundled = item.distribution !== 'med-vlm-mlx';
  return html`
    <section class="container page-head">
      <nav class="breadcrumb" aria-label="Breadcrumb">
        <a href="/models/" data-route>Models</a> <span aria-hidden="true">/</span>
        <a href="/models/?task=${encodeURIComponent(item.task)}" data-route>${item.task}</a> <span aria-hidden="true">/</span>
        <span aria-current="page">${item.name}</span>
      </nav>
      <h1>${item.name}</h1>
      <p class="lead">${item.description}</p>
      <p class="meta">${item.task} · <code>${item.distribution} ${item.version}</code> · MLX on Apple Silicon</p>
      <div class="actions">
        <a class="button" href="${item.package}">Package on PyPI</a>
        <a class="button secondary" href="${item.source}">Source on GitHub</a>
      </div>
    </section>

    <div class="container page-body">
      <section class="detail-section quickstart-section">
        <h2>Install</h2>
        <p>Requires ${platformRequirement}, Python ${pythonVersion} and <a href="https://docs.astral.sh/uv/">uv</a>. This creates a new environment and installs ${item.distribution} ${item.version}.</p>
        ${terminal(`install-${item.distribution}`, 'New environment', item.install, `${item.name} install command`)}
        <p class="note">Usage, weights and options are in the <a href="${item.source}">package README</a>.${bundled ? html`
          The MedMLX command on <a href="/get-started/" data-route>Get started</a> installs this runtime with every other model family.` : ''}</p>
      </section>
      ${related.length ? html`<section class="detail-section">
        <h2>More ${item.task.toLowerCase()}</h2>
        <ul class="resource-list">
          ${related.map(other => html`<li><a href="${other.href}" data-route>${other.name}</a></li>`)}
        </ul>
      </section>` : ''}
      <section class="detail-section">
        <h2>Intended use</h2>
        <p class="measure">For research and education. Not for clinical diagnosis or treatment decisions. Outputs require human review.</p>
      </section>
    </div>`;
}

// Structured data shared by every page.
const project = {
  '@type': 'SoftwareSourceCode',
  '@id': `${siteUrl}/#medmlx`,
  name: 'MedMLX',
  description: siteDescription,
  url: `${siteUrl}/`,
  codeRepository: `https://github.com/${releases.medmlx.repository}`,
  programmingLanguage: 'Python',
  runtimePlatform: `MLX, ${platformRequirement}`,
  version: releases.medmlx.version,
  license: 'https://www.apache.org/licenses/LICENSE-2.0',
  author: maintainers.map(person => ({ '@id': person['@id'] })),
  maintainer: maintainers.map(person => ({ '@id': person['@id'] })),
  sourceOrganization: { '@id': labData['@id'] },
  citation: { '@id': `${articleUrl}#article` },
};
const scholarlyArticle = {
  '@type': 'ScholarlyArticle',
  '@id': `${articleUrl}#article`,
  headline: article.title,
  author: [
    ...maintainers.map(person => ({ '@id': person['@id'] })),
    { '@type': 'Person', name: 'Arsalan Saleem', affiliation: labData.parentOrganization },
  ],
  datePublished: article.published,
  publisher: { '@type': 'Organization', name: 'medRxiv' },
  identifier: `https://doi.org/${article.doi}`,
  url: articleUrl,
  about: { '@id': `${siteUrl}/#medmlx` },
};

/** Breadcrumb trail from the home page to a page. */
function breadcrumbs(trail) {
  return {
    '@type': 'BreadcrumbList',
    itemListElement: [['MedMLX', '/'], ...trail].map(([name, path], index) => ({
      '@type': 'ListItem', position: index + 1, name, item: `${siteUrl}${path}`,
    })),
  };
}

/** Structured data for one published runtime. */
function runtimeData(item) {
  return {
    '@type': 'SoftwareSourceCode',
    name: item.name,
    description: item.description,
    url: `${siteUrl}${item.href}`,
    codeRepository: item.source,
    programmingLanguage: 'Python',
    runtimePlatform: `MLX, ${platformRequirement}`,
    version: item.version,
    isPartOf: { '@id': `${siteUrl}/#medmlx` },
  };
}

/** Trim to a search-result length at a word boundary. */
function summary(text, limit = 158) {
  return text.length <= limit ? text : `${text.slice(0, text.lastIndexOf(' ', limit - 1))}…`;
}

/**
 * Resolve a pathname (without its trailing slash) to the page's markup and
 * metadata, or the not-found page. Paths of real pages are canonical with a
 * trailing slash, as GitHub Pages serves their folders.
 */
export function route(path, search = '') {
  const page = (canonical, title, description, body, data = []) => ({
    canonical, title, fullTitle: title ? `${title} — MedMLX` : siteTitle, description: summary(description), body,
    data: { '@context': 'https://schema.org', '@graph': [project, ...maintainers, labData, scholarlyArticle, ...data] },
  });
  if (path === '/') {
    return page('/', null, siteDescription, homePage(), [{
      '@type': 'WebSite', name: 'MedMLX', url: `${siteUrl}/`, description: siteDescription,
    }]);
  }
  if (path === '/models') {
    const leading = catalog.slice(0, 4).map(item => item.name);
    return page('/models/', 'Models', `${catalog.length} medical imaging models and tools ported to MLX for Apple Silicon, including ${
      leading.slice(0, -1).join(', ')} and ${leading.at(-1)}.`, modelsPage(search),
    [breadcrumbs([['Models', '/models/']]), {
      '@type': 'ItemList', name: 'MedMLX models',
      itemListElement: catalog.map((item, index) => ({ '@type': 'ListItem', position: index + 1, url: `${siteUrl}${item.href}`, name: item.name })),
    }]);
  }
  if (path === '/get-started') {
    return page('/get-started/', 'Get started', `Install MedMLX with one command, then run medical imaging models on your Mac with Python ${pythonVersion} and uv. Includes the MCP server for AI agents.`,
      gettingStartedPage(), [breadcrumbs([['Get started', '/get-started/']])]);
  }
  if (path === '/get-started/mlx-reason-ct') {
    return page('/get-started/mlx-reason-ct/', 'Get started with MLX-Reason-CT', 'Generate a report or ask a question about a chest or abdomen CT with MLX-Reason-CT on your Mac. Install, download the weights and build the command.',
      reasonCtStartedPage(), [breadcrumbs([['Models', '/models/'], ['MLX-Reason-CT', '/models/mlx-reason-ct/'], ['Get started', '/get-started/mlx-reason-ct/']])]);
  }
  if (path === '/mcp') {
    return page('/mcp/', 'MCP guide', 'Connect an AI agent to MedMLX through its MCP server: install, connect Codex or another stdio client, run models as jobs, and the tool reference.',
      mcpPage(), [breadcrumbs([['MCP guide', '/mcp/']])]);
  }
  if (path === '/cli') {
    return page('/cli/', 'Command line', 'The medmlx command lists, checks and runs medical imaging models on Apple Silicon, downloads weights ahead of time and starts the MCP server.',
      cliPage(), [breadcrumbs([['Command line', '/cli/']])]);
  }
  if (path === '/python') {
    return page('/python/', 'Python API', 'Call MedMLX from Python: run medical imaging models on Apple Silicon, describe their arguments, check readiness and download weights.',
      pythonPage(), [breadcrumbs([['Python API', '/python/']])]);
  }
  if (path === '/about') {
    return page('/about/', 'About', 'MedMLX reimplements published medical imaging models in MLX for on-device AI on Apple Silicon. The article, developer links, intended use and licenses.',
      aboutPage(), [breadcrumbs([['About', '/about/']])]);
  }
  const item = catalog.find(entry => path === entry.href.slice(0, -1));
  if (item) {
    const model = models.find(entry => entry.slug === item.distribution);
    return page(item.href, `${item.name} on Apple Silicon`, `${item.description} Runs on device with MLX on Apple Silicon.`,
      model ? modelPage(model) : runtimePage(item), [breadcrumbs([
        ['Models', '/models/'], [item.task, `/models/?task=${encodeURIComponent(item.task)}`], [item.name, item.href],
      ]), runtimeData(item)]);
  }
  return { ...page(null, 'Page not found', siteDescription, notFoundPage()), noindex: true };
}

/** Every page the exporter writes, by canonical path. */
export const routes = ['/', '/models/', '/get-started/', '/get-started/mlx-reason-ct/', '/mcp/', '/cli/', '/python/', '/about/',
  ...catalog.map(item => item.href)];
