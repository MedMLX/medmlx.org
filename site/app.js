// Browser behavior: routing, page metadata, media and interactive controls.
// render.js builds the markup; the exporter prerenders the same markup.
import { pauseIcon, playIcon, route, siteUrl, tasks } from './render.js';

const main = document.querySelector('#main');
const header = document.querySelector('.site-header');
const nav = document.querySelector('#site-nav');
const menuButton = document.querySelector('.menu-toggle');
const menuLabel = menuButton.querySelector('[data-menu-label]');
const announcer = document.querySelector('#announcer');
const copyResets = new WeakMap();
let disposeHeroFilm = () => {};
let disposeTaskLoops = () => {};
let disposeScrubs = () => {};
let renderedLocation = '';
let announcerReset;


// Catalog filtering and report command builder

/** Hide catalog items outside the current search and task; announce the count. */
function filterCatalog({ updateQuery = false } = {}) {
  const search = document.querySelector('#model-search');
  if (!search) return;
  const task = document.querySelector('input[name="task"]:checked')?.value || '';
  const query = search.value.trim().toLowerCase();
  // A package can have several entries (nnU-Net and SIAM), so count distinct packages.
  const packages = new Set();
  for (const group of document.querySelectorAll('.catalog-group')) {
    const groupPackages = new Set();
    for (const item of group.querySelectorAll('.catalog-item')) {
      const visible = (!task || group.dataset.task === task) && item.dataset.search.includes(query);
      item.hidden = !visible;
      if (visible) groupPackages.add(item.dataset.package);
    }
    group.hidden = groupPackages.size === 0;
    group.querySelector('.catalog-count').textContent = groupPackages.size;
    groupPackages.forEach(name => packages.add(name));
  }
  const count = packages.size;
  document.querySelector('#catalog-status').textContent = `${count} ${count === 1 ? 'package' : 'packages'}`;
  document.querySelector('#catalog-empty').hidden = count !== 0;
  if (updateQuery) {
    const parameters = new URLSearchParams(location.search);
    const text = search.value.trim();
    if (text) parameters.set('q', text);
    else parameters.delete('q');
    if (task) parameters.set('task', task);
    else parameters.delete('task');
    const searchString = parameters.toString();
    history.replaceState(history.state, '', `${location.pathname}${searchString ? `?${searchString}` : ''}${location.hash}`);
    renderedLocation = location.pathname + location.search;
  }
}

// Routing

/**
 * Play task-card and model-page loops only while they are on screen. Reduced motion and data
 * saving keep the poster, and each loop has its own pause button.
 */
function setupTaskLoops() {
  // Only loops with a pause button; turntables have their own controls.
  const items = [...document.querySelectorAll('.task-item, .page-media')]
    .filter(item => item.querySelector('video') && item.querySelector('[data-media-toggle]'));
  if (!items.length) return () => {};
  const motion = matchMedia('(prefers-reduced-motion: reduce)');
  const visible = new Set();
  const paused = new Set();
  let disposed = false;
  const showControl = item => {
    const toggle = item.querySelector('[data-media-toggle]');
    const stopped = paused.has(item);
    toggle.setAttribute('aria-label', toggle.getAttribute('aria-label').replace(/^(Play|Pause)/, stopped ? 'Play' : 'Pause'));
    toggle.innerHTML = stopped ? playIcon : pauseIcon;
  };
  const sync = () => {
    if (disposed) return;
    const still = motion.matches || navigator.connection?.saveData;
    for (const item of items) {
      const video = item.querySelector('video');
      item.querySelector('[data-media-toggle]').hidden = Boolean(still);
      if (still) {
        // Unloading the source shows the poster again.
        if (video.hasAttribute('src')) {
          video.removeAttribute('src');
          video.load();
        }
      } else if (paused.has(item) || document.hidden || !visible.has(item)) {
        video.pause();
      } else {
        if (!video.hasAttribute('src')) video.src = video.dataset.src;
        video.muted = true;
        video.play().catch(error => {
          // Blocked autoplay keeps the poster; the button then offers Play.
          if (disposed || error?.name !== 'NotAllowedError') return;
          paused.add(item);
          showControl(item);
        });
      }
      showControl(item);
    }
  };
  const onClick = event => {
    const item = event.target.closest('[data-media-toggle]')?.closest('.task-item, .page-media');
    if (!item) return;
    if (paused.has(item)) paused.delete(item);
    else paused.add(item);
    sync();
  };
  const observer = new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (entry.isIntersecting) visible.add(entry.target);
      else visible.delete(entry.target);
    }
    sync();
  }, { threshold: 0.25 });
  items.forEach(item => observer.observe(item));
  motion.addEventListener('change', sync);
  document.addEventListener('visibilitychange', sync);
  document.addEventListener('click', onClick);
  // On model pages a loop is also a scrubber: dragging pauses it and moves through it,
  // a full-width drag covering the whole loop. Its button resumes playback.
  let drag = null;
  const onDown = event => {
    const item = event.target.closest('.page-media');
    if (!item || !items.includes(item) || event.target.closest('[data-media-toggle]')) return;
    const video = item.querySelector('video');
    if (!video.hasAttribute('src')) video.src = video.dataset.src;
    paused.add(item);
    sync();
    drag = { item, video, x: event.clientX, time: video.currentTime, id: event.pointerId };
    item.setPointerCapture(event.pointerId);
  };
  const onMove = event => {
    if (!drag || event.pointerId !== drag.id || !drag.video.duration) return;
    const { duration } = drag.video;
    const shift = (event.clientX - drag.x) / drag.item.clientWidth * duration;
    drag.video.currentTime = (((drag.time + shift) % duration) + duration) % duration;
  };
  const onUp = event => {
    if (drag && event.pointerId === drag.id) drag = null;
  };
  document.addEventListener('pointerdown', onDown);
  document.addEventListener('pointermove', onMove);
  document.addEventListener('pointerup', onUp);
  document.addEventListener('pointercancel', onUp);
  sync();
  return () => {
    disposed = true;
    observer.disconnect();
    motion.removeEventListener('change', sync);
    document.removeEventListener('visibilitychange', sync);
    document.removeEventListener('click', onClick);
    document.removeEventListener('pointerdown', onDown);
    document.removeEventListener('pointermove', onMove);
    document.removeEventListener('pointerup', onUp);
    document.removeEventListener('pointercancel', onUp);
    for (const item of items) {
      const video = item.querySelector('video');
      video.pause();
      video.removeAttribute('src');
      video.load();
    }
  };
}

/**
 * Interactive model views. A turntable is a looping video, one angle per frame; a
 * slice stack is a video that runs down the slices and back up. Each plays while on
 * screen, and dragging or the arrow keys move it frame by frame, which stops the
 * playback. Reduced motion and data saving keep the poster until someone drags.
 * A view switch shows one view of a figure at a time.
 */
function setupScrubs() {
  const views = [...document.querySelectorAll('[data-scrub]')];
  if (!views.length) return () => {};
  let disposed = false;
  const motion = matchMedia('(prefers-reduced-motion: reduce)');
  const cleanups = [];
  const syncs = new Map();
  for (const view of views) {
    const video = view.querySelector('video');
    const turn = view.dataset.scrub === 'turn';
    const fps = Number(view.dataset.fps);
    let touched = false;
    let visible = false;
    let drag = null;
    // A local blob makes every frame seekable once the download finishes.
    let objectUrl = '';
    let pending = null;
    const download = new AbortController();
    const load = () => {
      if (disposed || video.hasAttribute('src') || pending) return;
      pending = fetch(video.dataset.src, { signal: download.signal })
        .then(response => {
          if (!response.ok) throw new Error(`${response.status} ${video.dataset.src}`);
          return response.blob();
        })
        .then(blob => {
          if (disposed) return;
          objectUrl = URL.createObjectURL(blob);
          video.src = objectUrl;
          video.addEventListener('loadedmetadata', sync, { once: true });
        })
        // Keep the poster on failure; a later visit or gesture can retry.
        .catch(() => {})
        .finally(() => { pending = null; });
    };
    // Distinct frames: every angle, or each slice once (the video also runs back up).
    const count = () => {
      const total = Math.round((video.duration || 0) * fps);
      return turn ? total : (total + 2) / 2;
    };
    const current = () => {
      const total = Math.round((video.duration || 0) * fps);
      const frame = Math.floor(video.currentTime * fps) % Math.max(total, 1);
      const n = count();
      return turn || frame < n ? frame : 2 * (n - 1) - frame;
    };
    const show = index => {
      load();
      const n = count();
      if (!n || !video.hasAttribute('src')) return;
      const frame = turn ? ((index % n) + n) % n : Math.min(Math.max(index, 0), n - 1);
      // Seek to the middle of the frame so rounding never lands on its neighbour.
      video.currentTime = (frame + 0.5) / fps;
    };
    const sync = () => {
      const still = motion.matches || navigator.connection?.saveData;
      if (visible && !view.hidden && !touched && !still && !document.hidden) {
        load();
        if (video.hasAttribute('src')) {
          // The view's default playback speed; dragging is unaffected.
          video.playbackRate = Number(view.dataset.rate) || 1;
          video.play().catch(() => {});
        }
      } else {
        video.pause();
      }
    };
    syncs.set(view, sync);
    const stop = () => { touched = true; sync(); };
    const down = event => {
      stop();
      load();
      drag = { x: event.clientX, y: event.clientY, frame: current(), id: event.pointerId };
      view.setPointerCapture(event.pointerId);
      view.classList.add('dragging');
    };
    const move = event => {
      if (!drag || event.pointerId !== drag.id || !count()) return;
      if (turn) {
        // A drag across the whole view turns about 300 degrees.
        const perFrame = view.clientWidth / (count() * 0.83);
        show(drag.frame - Math.round((event.clientX - drag.x) / perFrame));
        return;
      }
      // Slices follow the larger movement: down moves inferior, as in a scan viewer.
      // One and a half view heights cross every slice.
      const dx = event.clientX - drag.x;
      const dy = event.clientY - drag.y;
      const perFrame = Math.max(view.clientHeight * 1.5 / count(), 1.5);
      show(drag.frame + Math.round((Math.abs(dy) >= Math.abs(dx) ? dy : dx) / perFrame));
    };
    const up = event => {
      if (drag && event.pointerId === drag.id) drag = null;
      view.classList.remove('dragging');
    };
    const key = event => {
      const forward = turn ? ['ArrowLeft'] : ['ArrowRight', 'ArrowDown'];
      const back = turn ? ['ArrowRight'] : ['ArrowLeft', 'ArrowUp'];
      const step = forward.includes(event.key) ? 1 : back.includes(event.key) ? -1 : 0;
      if (!step) return;
      event.preventDefault();
      stop();
      show(current() + step * (turn ? 3 : 1));
    };
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) visible = entry.isIntersecting;
      sync();
    }, { threshold: 0.25 });
    observer.observe(view);
    view.addEventListener('pointerdown', down);
    view.addEventListener('pointermove', move);
    view.addEventListener('pointerup', up);
    view.addEventListener('pointercancel', up);
    view.addEventListener('keydown', key);
    motion.addEventListener('change', sync);
    document.addEventListener('visibilitychange', sync);
    cleanups.push(() => {
      download.abort();
      observer.disconnect();
      motion.removeEventListener('change', sync);
      document.removeEventListener('visibilitychange', sync);
      video.removeEventListener('loadedmetadata', sync);
      video.pause();
      video.removeAttribute('src');
      video.load();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    });
  }
  const onSwitch = event => {
    const button = event.target.closest('[data-view]');
    const figure = button?.closest('.page-media');
    if (!figure) return;
    for (const other of figure.querySelectorAll('[data-view]')) {
      other.setAttribute('aria-pressed', String(other === button));
    }
    for (const view of figure.querySelectorAll('[data-scrub]')) {
      view.hidden = view.dataset.scrub !== button.dataset.view;
      syncs.get(view)();
    }
  };
  document.addEventListener('click', onSwitch);
  cleanups.push(() => document.removeEventListener('click', onSwitch));
  return () => {
    disposed = true;
    cleanups.forEach(cleanup => cleanup());
  };
}

/** Play the decorative film only when visible, with a still for reduced motion. */
function setupHeroFilm() {
  const hero = document.querySelector('.hero');
  if (!hero) return () => {};
  const video = hero.querySelector('video');
  const controls = hero.querySelector('.film-controls');
  const toggle = hero.querySelector('[data-film-toggle]');
  const back = hero.querySelector('[data-film-back]');
  const next = hero.querySelector('[data-film-next]');
  // The six equal-length scenes are recorded in assets/hero/sources.json.
  const sceneCount = Number(video.dataset.scenes);
  const motion = matchMedia('(prefers-reduced-motion: reduce)');
  const connection = navigator.connection;
  let inView = false;
  let userPaused = false;
  let disposed = false;

  const updateControl = () => {
    const paused = video.paused;
    const label = paused ? 'Play film' : 'Pause film';
    toggle.querySelector('span').textContent = label;
    toggle.title = label;
    toggle.querySelector('path').setAttribute('d', paused ? 'M4 2l8 5-8 5z' : 'M3 2h3v10H3zm5 0h3v10H8z');
    back.disabled = next.disabled = !Number.isFinite(video.duration) || video.duration <= 0;
  };
  const sync = () => {
    const still = motion.matches || connection?.saveData;
    controls.hidden = Boolean(still);
    if (disposed || still || userPaused || !inView || document.hidden) {
      video.pause();
      if (still) hero.classList.remove('film-playing');
      updateControl();
      return;
    }
    if (!video.hasAttribute('src')) video.src = video.dataset.src;
    video.muted = true;
    video.play().catch(error => {
      // A later pause() or source reset aborts a pending play(); nothing to undo.
      if (error?.name === 'AbortError') return;
      if (error?.name !== 'NotAllowedError') throw error;
      // Blocked autoplay keeps the poster; the control then offers Play.
      if (!disposed) updateControl();
    });
  };
  const onPlaying = () => {
    hero.classList.add('film-playing');
    updateControl();
  };
  const onToggle = () => { userPaused = !video.paused; sync(); };
  const stepScene = direction => {
    const sceneDuration = video.duration / sceneCount;
    const current = Math.floor(video.currentTime / sceneDuration);
    const target = (current + direction + sceneCount) % sceneCount;
    // Land one frame into the scene, clear of the preceding dissolve.
    video.currentTime = target * sceneDuration + 1 / 24;
  };
  const onBack = () => stepScene(-1);
  const onNext = () => stepScene(1);
  const onSeeked = () => {
    hero.classList.add('film-playing');
    updateControl();
  };
  const observer = new IntersectionObserver(entries => {
    inView = entries.at(-1).isIntersecting;
    sync();
  }, { threshold: 0 });
  observer.observe(hero);
  video.addEventListener('playing', onPlaying);
  video.addEventListener('pause', updateControl);
  video.addEventListener('loadedmetadata', updateControl);
  video.addEventListener('seeked', onSeeked);
  toggle.addEventListener('click', onToggle);
  back.addEventListener('click', onBack);
  next.addEventListener('click', onNext);
  motion.addEventListener('change', sync);
  document.addEventListener('visibilitychange', sync);
  sync();
  return () => {
    disposed = true;
    observer.disconnect();
    motion.removeEventListener('change', sync);
    document.removeEventListener('visibilitychange', sync);
    toggle.removeEventListener('click', onToggle);
    back.removeEventListener('click', onBack);
    next.removeEventListener('click', onNext);
    video.removeEventListener('playing', onPlaying);
    video.removeEventListener('pause', updateControl);
    video.removeEventListener('loadedmetadata', updateControl);
    video.removeEventListener('seeked', onSeeked);
    video.pause();
    video.removeAttribute('src');
    video.load();
  };
}

/** Point the title, description, canonical URL, social tags and structured data at a page. */
function updateHead(page) {
  const set = (selector, attribute, value) => document.head.querySelector(selector)?.setAttribute(attribute, value);
  const url = page.canonical ? `${siteUrl}${page.canonical}` : `${siteUrl}/`;
  document.title = page.fullTitle;
  set('meta[name="description"]', 'content', page.description);
  set('meta[property="og:title"]', 'content', page.fullTitle);
  set('meta[property="og:description"]', 'content', page.description);
  set('meta[property="og:url"]', 'content', url);
  set('link[rel="canonical"]', 'href', url);
  set('meta[name="robots"]', 'content', page.noindex ? 'noindex' : 'index, follow');
  const data = document.getElementById('structured-data');
  if (data) data.textContent = JSON.stringify(page.data);
}

/** Render the current route, refresh controls, and optionally move keyboard focus. */
function renderPage({ moveFocus = false } = {}) {
  // Route on pathname alone; query strings and fragments do not select pages.
  const path = location.pathname.replace(/\/index\.html$/, '/').replace(/\/+$/, '') || '/';
  const page = route(path, location.search);
  const query = new URLSearchParams(location.search);
  if (path === '/models' && query.has('task') && !tasks.includes(query.get('task'))) {
    query.delete('task');
    history.replaceState({}, '', `${location.pathname}${query.size ? `?${query}` : ''}${location.hash}`);
  }
  renderedLocation = location.pathname + location.search;
  disposeHeroFilm();
  disposeTaskLoops();
  disposeScrubs();
  main.innerHTML = page.body;
  disposeHeroFilm = setupHeroFilm();
  disposeTaskLoops = setupTaskLoops();
  disposeScrubs = setupScrubs();
  updateHead(page);
  filterCatalog();
  for (const link of document.querySelectorAll('.site-header a[data-route]:not(.brand)')) {
    const linkPath = link.pathname.replace(/\/+$/, '') || '/';
    const current = page.noindex ? null
      : path === linkPath ? 'page'
        : linkPath !== '/' && path.startsWith(`${linkPath}/`) ? 'true' : null;
    if (current) link.setAttribute('aria-current', current);
    else link.removeAttribute('aria-current');
  }
  closeMenu();
  if (moveFocus) {
    window.scrollTo(0, 0);
    main.focus({ preventScroll: true });
  }
  scrollToFragment(moveFocus);
}

/** Reach fragment links after rendering, including links to the current section. */
function scrollToFragment(moveFocus = false) {
  const fragment = location.hash && document.getElementById(location.hash.slice(1));
  if (fragment) {
    fragment.scrollIntoView();
    if (moveFocus) fragment.focus({ preventScroll: true });
  }
}

/** Collapse the mobile navigation and update its accessibility state. */
function closeMenu() {
  nav.classList.remove('is-open');
  document.documentElement.classList.remove('menu-open');
  menuButton.setAttribute('aria-expanded', 'false');
  menuLabel.textContent = 'Menu';
}

// Interaction

/** Copy a command, or select it for manual copying when clipboard access fails. */
async function copyCommand(button) {
  const code = document.getElementById(button.dataset.copy);
  try {
    await navigator.clipboard.writeText(code.textContent);
    showCopyResult(button, 'Copied', 'Command copied.');
  } catch {
    getSelection().selectAllChildren(code);
    showCopyResult(button, 'Selected', 'Automatic copying failed. The command is selected for manual copying.');
  }
}

/** Announce copy feedback and restore the button label after a short delay. */
function showCopyResult(button, label, message) {
  announcer.textContent = message;
  button.textContent = label;
  clearTimeout(copyResets.get(button));
  copyResets.set(button, setTimeout(() => { button.textContent = 'Copy'; }, 2000));
  clearTimeout(announcerReset);
  announcerReset = setTimeout(() => { announcer.textContent = ''; }, 2000);
}

/** Activate a quick-start tab and display its corresponding command. */
function selectStep(tab) {
  for (const other of tab.parentElement.querySelectorAll('[role="tab"]')) {
    other.setAttribute('aria-selected', String(other === tab));
    other.tabIndex = other === tab ? 0 : -1;
  }
  const panel = document.getElementById(tab.getAttribute('aria-controls'));
  panel.setAttribute('aria-labelledby', tab.id);
  panel.querySelector('code').textContent = tab.dataset.command;
}

document.addEventListener('click', event => {
  const link = event.target.closest('a[data-route]');
  if (link && event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) {
    event.preventDefault();
    if (location.pathname !== link.pathname || location.search !== link.search || location.hash !== link.hash) {
      history.pushState({}, '', `${link.pathname}${link.search}${link.hash}`);
      renderPage({ moveFocus: true });
    } else {
      closeMenu();
      main.focus({ preventScroll: true });
      scrollToFragment(true);
    }
    return;
  }
  // A click outside the open menu closes it.
  if (nav.classList.contains('is-open') && !nav.contains(event.target) && !menuButton.contains(event.target)) closeMenu();
  const copy = event.target.closest('[data-copy]');
  if (copy) copyCommand(copy);
  const step = event.target.closest('[data-step]');
  if (step) selectStep(step);
});

document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && nav.classList.contains('is-open')) {
    closeMenu();
    menuButton.focus();
  }
  if (event.target.matches('[role="tab"]') && ['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
    event.preventDefault();
    const tabs = [...event.target.parentElement.querySelectorAll('[role="tab"]')];
    const index = tabs.indexOf(event.target);
    const next = {
      ArrowLeft: (index - 1 + tabs.length) % tabs.length,
      ArrowRight: (index + 1) % tabs.length,
      Home: 0,
      End: tabs.length - 1,
    }[event.key];
    selectStep(tabs[next]);
    tabs[next].focus();
  }
});

document.addEventListener('input', event => {
  if (event.target.id === 'model-search') filterCatalog({ updateQuery: true });
});

document.addEventListener('change', event => {
  if (event.target.name !== 'task') return;
  filterCatalog({ updateQuery: true });
});

document.addEventListener('submit', event => event.preventDefault());

menuButton.addEventListener('click', event => {
  const open = nav.classList.toggle('is-open');
  document.documentElement.classList.toggle('menu-open', open);
  menuButton.setAttribute('aria-expanded', String(open));
  menuLabel.textContent = open ? 'Close' : 'Menu';
  // Keyboard activation has no click count; only then move focus into the menu.
  if (open && event.detail === 0) nav.querySelector('a')?.focus();
});

// This is a disclosure, so Tab can leave the links without a focus trap.
header.addEventListener('focusout', event => {
  if (!header.contains(event.relatedTarget)) closeMenu();
});

// The phone menu does not survive a resize to the desktop layout.
matchMedia('(min-width: 721px)').addEventListener('change', closeMenu);

// Fragment-only changes, such as the skip link, keep the rendered page.
window.addEventListener('popstate', () => {
  if (location.pathname + location.search !== renderedLocation) renderPage({ moveFocus: true });
});

header.classList.add('navigation-ready');
renderPage();
