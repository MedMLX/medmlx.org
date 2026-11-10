import assert from 'node:assert/strict';
import test from 'node:test';

// Supply only browser boundaries; exercise the complete app and its route cleanup.
class Element extends EventTarget {
  dataset = {};
  hidden = false;
  attributes = new Map();
  classList = { add() {}, remove() {}, contains() { return false; } };
  querySelector() { return null; }
  setAttribute(name, value) { this.attributes.set(name, value); }
  hasAttribute(name) { return this.attributes.has(name); }
  removeAttribute(name) { this.attributes.delete(name); }
  focus() {}
  pause() {}
  load() {}
  set src(value) { this.setAttribute('src', value); }
}

const settle = () => new Promise(resolve => setImmediate(resolve));

test('scrub videos retry failures, cancel on navigation and release their blob URLs', async () => {
  const saved = new Map();
  const replace = (key, value) => {
    saved.set(key, Object.getOwnPropertyDescriptor(globalThis, key));
    Object.defineProperty(globalThis, key, { configurable: true, writable: true, value });
  };
  const document = new EventTarget();
  const window = new EventTarget();
  window.scrollTo = () => {};
  const main = new Element();
  const menu = new Element();
  const label = new Element();
  menu.querySelector = () => label;
  const view = new Element();
  const video = new Element();
  view.dataset = { scrub: 'turn', fps: '24' };
  video.dataset.src = '/film.mp4';
  view.querySelector = () => video;
  let views = [view];
  document.hidden = false;
  document.documentElement = new Element();
  document.head = { querySelector: () => null };
  document.getElementById = () => null;
  document.querySelector = selector => ({
    '#main': main, '.site-header': new Element(), '#site-nav': new Element(),
    '.menu-toggle': menu, '#announcer': new Element(),
  })[selector] || null;
  document.querySelectorAll = selector => selector === '[data-scrub]' ? views : [];
  const observers = [];
  const location = { pathname: '/models/lung-nodule-mlx/', search: '', hash: '' };
  const requests = [];
  const urls = [];
  const revoked = [];
  const create = URL.createObjectURL;
  const revoke = URL.revokeObjectURL;
  try {
    replace('document', document);
    replace('window', window);
    replace('location', location);
    replace('navigator', {});
    replace('matchMedia', () => Object.assign(new EventTarget(), { matches: false }));
    replace('IntersectionObserver', class {
      constructor(callback) { this.callback = callback; observers.push(this); }
      observe() {}
      disconnect() {}
    });
    replace('fetch', (_url, options) => new Promise((resolve, reject) => {
      requests.push({ resolve, reject, signal: options?.signal });
    }));
    URL.createObjectURL = blob => { urls.push(blob); return `blob:test-${urls.length}`; };
    URL.revokeObjectURL = url => revoked.push(url);
    await import('../site/app.js');
    const visible = () => observers.at(-1).callback([{ isIntersecting: true }]);
    visible();
    visible();
    assert.equal(requests.length, 1, 'concurrent visibility events share the download');
    requests[0].reject(new TypeError('network unavailable'));
    await settle();
    assert.equal(video.hasAttribute('src'), false, 'failure leaves the poster');
    visible();
    assert.equal(requests.length, 2, 'a failed download can be retried');
    requests[1].resolve({ ok: false, status: 503 });
    await settle();
    visible();
    assert.equal(requests.length, 3, 'HTTP errors can also be retried');
    requests[2].resolve({ ok: true, blob: async () => new Blob(['film']) });
    await settle();
    assert.equal(video.attributes.get('src'), 'blob:test-1');
    // Navigate to a route without media, then return with a fresh view lifecycle.
    views = [];
    location.pathname = '/about/';
    window.dispatchEvent(new Event('popstate'));
    assert.deepEqual(revoked, ['blob:test-1']);
    assert.equal(video.hasAttribute('src'), false);
    views = [view];
    location.pathname = '/models/lung-nodule-mlx/';
    window.dispatchEvent(new Event('popstate'));
    visible();
    assert.equal(requests.length, 4);
    views = [];
    location.pathname = '/about/';
    window.dispatchEvent(new Event('popstate'));
    assert.equal(requests[3].signal.aborted, true, 'navigation cancels the download');
    // A response that races cancellation must not attach or leak a new blob URL.
    requests[3].resolve({ ok: true, blob: async () => new Blob(['late film']) });
    await settle();
    assert.equal(urls.length, 1);
    assert.equal(video.hasAttribute('src'), false);
  } finally {
    URL.createObjectURL = create;
    URL.revokeObjectURL = revoke;
    for (const [key, descriptor] of saved) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor);
      else delete globalThis[key];
    }
  }
});
