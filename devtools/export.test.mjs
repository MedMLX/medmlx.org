import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

test('a failed release check preserves the previous export even when called directly', () => {
  const directory = mkdtempSync(join(tmpdir(), 'medmlx-export-'));
  try {
    cpSync(new URL('../site/', import.meta.url), join(directory, 'site'), { recursive: true });
    mkdirSync(join(directory, 'devtools'));
    cpSync(new URL('export-site.mjs', import.meta.url), join(directory, 'devtools/export-site.mjs'));
    writeFileSync(join(directory, 'package.json'), '{"type":"module"}');
    mkdirSync(join(directory, 'dist/pages'), { recursive: true });
    writeFileSync(join(directory, 'dist/pages/index.html'), 'Previously verified export');
    const python = join(directory, 'python');
    writeFileSync(python, '#!/bin/sh\necho "Release check failed: stale version" >&2\nexit 1\n', { mode: 0o700 });
    const result = spawnSync(process.execPath, [join(directory, 'devtools/export-site.mjs')], {
      cwd: directory, encoding: 'utf8', timeout: 5000,
      env: { ...process.env, MEDMLX_SITE_PYTHON: python },
    });
    if (result.error) throw result.error;
    assert.equal(result.status, 1, result.stderr);
    assert.match(result.stderr, /Release check failed: stale version/);
    assert.equal(readFileSync(join(directory, 'dist/pages/index.html'), 'utf8'), 'Previously verified export');
    assert.equal(existsSync(join(directory, 'dist/pages/models')), false);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});
