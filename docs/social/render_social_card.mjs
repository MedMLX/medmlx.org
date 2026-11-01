// Render site/assets/brand/social-card.png (1200 × 630) from social-card.html.
// Uses Chrome's headless shell, so the card is set in Apple's system font on macOS:
//   node docs/social/render_social_card.mjs [path to chrome or chrome-headless-shell]
import { spawn } from 'node:child_process';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { setTimeout as sleep } from 'node:timers/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const chrome = process.argv[2] || process.env.CHROME
  || `${os.homedir()}/Library/Caches/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-mac-arm64/chrome-headless-shell`;
const output = path.resolve(here, '../../site/assets/brand/social-card.png');
const profile = await mkdtemp(path.join(os.tmpdir(), 'medmlx-card-'));
const port = 9350;
const browser = spawn(chrome, [`--remote-debugging-port=${port}`, `--user-data-dir=${profile}`,
  '--hide-scrollbars', '--allow-file-access-from-files', 'about:blank'], { stdio: 'ignore' });
try {
  let targets;
  for (let i = 0; i < 50 && !targets; i++) {
    try { targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); } catch { await sleep(100); }
  }
  if (!targets) throw new Error(`Chrome did not start: ${chrome}`);
  const socket = new WebSocket(targets.find(target => target.type === 'page').webSocketDebuggerUrl);
  await new Promise(resolve => socket.addEventListener('open', resolve, { once: true }));
  let id = 0;
  const pending = new Map();
  socket.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    pending.get(message.id)?.(message);
  });
  const send = (method, params = {}) => new Promise(resolve => {
    pending.set(++id, resolve);
    socket.send(JSON.stringify({ id, method, params }));
  });
  await send('Emulation.setDeviceMetricsOverride', { width: 1200, height: 630, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url: pathToFileURL(path.join(here, 'social-card.html')).href });
  await sleep(1500);
  const shot = await send('Page.captureScreenshot', { format: 'png', clip: { x: 0, y: 0, width: 1200, height: 630, scale: 1 } });
  await writeFile(output, Buffer.from(shot.result.data, 'base64'));
  socket.close();
  console.log(`Wrote ${path.relative(process.cwd(), output)}`);
} finally {
  // Remove the profile only after Chrome has exited and released it.
  const exited = new Promise(resolve => browser.once('exit', resolve));
  browser.kill();
  await exited;
  await rm(profile, { recursive: true, force: true });
}
