// Each generated card video has a run record that names its exact video and poster.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readdir, readFile } from 'node:fs/promises';

const hero = new URL('../site/assets/hero/', import.meta.url);
const sha256 = async name => createHash('sha256').update(await readFile(new URL(name, hero))).digest('hex');
/** Every string anywhere in a parsed JSON value. */
const strings = value => typeof value === 'string' ? [value]
  : value && typeof value === 'object' ? Object.values(value).flatMap(strings) : [];

// outputs.mp4 is the hero film; render_film.py rebuilds it from sources.json.
const loops = (await readdir(hero)).filter(name => name.endsWith('.mp4') && name !== 'outputs.mp4')
  .map(name => name.slice(0, -'.mp4'.length));

test('the card videos are present', () => {
  assert.deepEqual(loops.sort(), ['abdomen-scroll', 'nodule-scroll', 'radiomics-organs']);
});

for (const loop of loops) {
  test(`${loop}-run.json records the current video and poster`, async () => {
    const record = strings(JSON.parse(await readFile(new URL(`${loop}-run.json`, hero), 'utf8')));
    for (const file of [`${loop}.mp4`, `${loop}-poster.webp`]) {
      assert.ok(record.includes(await sha256(file)), `${loop}-run.json does not record the sha256 of ${file}`);
    }
  });
}
