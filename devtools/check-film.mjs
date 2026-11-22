// Exercise the deployed film through WebDriver. Screenshots cover the visible
// composition, including its poster, so a successful seek behind a frozen poster fails.
import assert from 'node:assert/strict';
import { setTimeout as delay } from 'node:timers/promises';
import { PNG } from 'pngjs';
import { Builder, By } from 'selenium-webdriver';
import chrome from 'selenium-webdriver/chrome.js';

const driver = await new Builder().disableEnvironmentOverrides().forBrowser('chrome')
  .setChromeOptions(new chrome.Options().addArguments('--headless=new')).build();
try {
  const url = process.env.FILM_URL || 'https://medmlx.org/';
  console.log('Headless Chrome', (await driver.getCapabilities()).get('browserVersion'), url);
  await driver.get(url);
  const element = selector => driver.findElement(By.css(selector));
  const click = async selector => (await element(selector)).click();
  const state = () => driver.executeScript(() => {
    const film = document.querySelector('.hero-video');
    return film && {
      time: film.currentTime, duration: film.duration, paused: film.paused, seeking: film.seeking,
      visible: getComputedStyle(film).opacity === '1',
      ready: !document.querySelector('.film-controls').hidden && !document.querySelector('[data-film-next]').disabled,
    };
  });
  const waitFor = (condition, message) => driver.wait(async () => {
    const film = await state();
    return film && condition(film) && film;
  }, 15000, message);

  const ready = await waitFor(film => film.ready, 'Film controls unavailable');
  if (ready.paused) await click('[data-film-toggle]');
  const playing = await waitFor(film => !film.paused && film.visible, 'Film did not start');
  await waitFor(film => film.time > playing.time + 0.2, 'Playback did not advance');
  await click('[data-film-toggle]');
  const paused = await waitFor(film => film.paused, 'Pause did not stop playback');
  await delay(350);
  assert.equal((await state()).time, paused.time, 'Film advanced while paused');

  const sceneDuration = paused.duration / 6;
  const sceneAt = film => Math.floor(film.time / sceneDuration);
  let scene = sceneAt(paused);
  const step = async direction => {
    await click(direction === 1 ? '[data-film-next]' : '[data-film-back]');
    scene = (scene + direction + 6) % 6;
    await waitFor(film => film.paused && !film.seeking && sceneAt(film) === scene,
      `Expected scene ${scene + 1} while paused`);
  };

  const picture = await element('.hero-media');
  const capture = async () => PNG.sync.read(Buffer.from(await picture.takeScreenshot(), 'base64'));
  await step(1);
  const frames = new Map([[scene, await capture()]]);
  let previous = frames.get(scene);
  for (let i = 1; i < 6; i++) {
    await step(1);
    const frame = await driver.wait(async () => {
      const current = await capture();
      return difference(previous, current) > 1 && current;
    }, 5000, 'Next changed the time but the picture stayed frozen');
    frames.set(scene, frame);
    previous = frame;
  }
  // Cross the loop seam and revisit every scene at the same paused frame.
  for (const direction of [1, -1, -1, -1, -1, -1, -1]) {
    await step(direction);
    await driver.wait(async () => difference(frames.get(scene), await capture()) < 1,
      5000, `Scene ${scene + 1} did not restore its picture`);
  }

  const stopped = await state();
  await click('[data-film-toggle]');
  await waitFor(film => !film.paused && film.time > stopped.time + 0.2, 'Resume did not advance');
  console.log('Passed playback, pause, all six scene changes, wraparound, previous and resume.');
} finally {
  await driver.quit();
}

/** Mean RGB difference in 8-bit levels across the visible film crop. */
function difference(a, b) {
  assert.equal(a.width, b.width);
  assert.equal(a.height, b.height);
  let total = 0;
  for (let i = 0; i < a.data.length; i += 4) {
    for (let channel = 0; channel < 3; channel++) {
      total += Math.abs(a.data[i + channel] - b.data[i + channel]);
    }
  }
  return total / (a.width * a.height * 3);
}
