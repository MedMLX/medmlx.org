import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { additionalRuntimes, models, reportCommand } from '../site/models.js';
import { mcpExamples } from '../site/mcp.js';
import { medmlxExamples, releases, uvInstallCommand } from '../site/releases.js';

test('report arguments survive the shell without evaluating their contents', () => {
  const parameters = {
    image_path: "scans/test case's CT.nii.gz",
    weights_path: '~/model directory',
    output_dir: 'outputs/$(exit 72)',
    anatomy_region: 'abdomen',
    prompt: 'Describe "this" CT.\nKeep $HOME, `exit 73`, and apostrophes: \' unchanged.',
    enable_thinking: true,
  };
  const directory = mkdtempSync(join(tmpdir(), 'medmlx-command-'));
  try {
    // Capture argv without installing a package or running a model.
    writeFileSync(join(directory, 'mlx-reason-ct'), '#!/bin/sh\nprintf "%s\\0" "$@"\n', { mode: 0o700 });
    const result = spawnSync('/bin/sh', ['-c', reportCommand(parameters)], {
      encoding: 'utf8', timeout: 1000, env: { ...process.env, PATH: `${directory}:${process.env.PATH || ''}` },
    });
    if (result.error) throw result.error;
    assert.equal(result.status, 0, result.stderr);
    assert.deepEqual(result.stdout.split('\0').slice(0, -1), [
      'report', `--input=${parameters.image_path}`, `--model-dir=${parameters.weights_path}`,
      `--output-dir=${parameters.output_dir}`, `--anatomy-region=${parameters.anatomy_region}`,
      `--prompt=${parameters.prompt}`, '--enable-thinking',
    ]);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test('published install, download and run examples are valid shell text', () => {
  const commands = [
    uvInstallCommand, ...medmlxExamples.map(example => example.command),
    ...Object.values(models[0].commands), ...additionalRuntimes.map(runtime => runtime.install),
    ...mcpExamples.filter(example => example.kind !== 'json').map(example => example.command),
  ];
  for (const command of commands) {
    const result = spawnSync('/bin/sh', ['-n'], { input: command, encoding: 'utf8', timeout: 1000 });
    if (result.error) throw result.error;
    assert.equal(result.status, 0, result.stderr);
  }
});

test('every catalog runtime has an install command for its reviewed release', () => {
  for (const runtime of additionalRuntimes) {
    const { version } = releases[runtime.distribution];
    assert.match(runtime.install, /^uv venv --python 3\.13\nsource \.venv\/bin\/activate\nuv pip install "/);
    assert.ok(runtime.install.includes(`"${runtime.distribution}>=${version}"`) || runtime.install.includes(`"${runtime.distribution}==${version}"`),
      `${runtime.distribution} install must name ${version}`);
  }
});

test('MCP tool arguments shown on the site are valid JSON', () => {
  const calls = mcpExamples.filter(example => example.kind === 'json');
  assert.ok(calls.length > 0);
  for (const { command } of calls) assert.doesNotThrow(() => JSON.parse(command), command);
});
