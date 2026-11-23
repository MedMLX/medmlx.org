import { medmlxInstallCommand, medmlxProjectCommand, medmlxRunCommand, medmlxServeCommand, releases } from './releases.js';

// The command line and Python API pages describe the reviewed medmlx tag.
// make release-check finds every example below in its README or docs/setup.md,
// checks each medmlx command against its CLI, and checks that the listed
// subcommands and functions exist in it.
const tag = `v${releases.medmlx.version}`;
const tagged = file => `https://github.com/${releases.medmlx.repository}/blob/${tag}/${file}`;

export const readmeSource = tagged('README.md');
export const setupSource = tagged('docs/setup.md');

/** Subcommands and their arguments, from src/medmlx/cli.py at the tag. */
export const cliCommands = [
  ['models', '--task, --family', 'Lists the installed models.'],
  ['describe', 'MODEL_ID', 'Shows the arguments a model takes and how to use them.'],
  ['readiness', 'MODEL_ID…', 'Checks that models are installed and that Metal works on this Mac.'],
  ['check', 'MODEL_ID, KEY=VALUE…, --arguments, --root', 'Checks one run’s arguments, input paths and weights, without running it or downloading anything.'],
  ['run', 'MODEL_ID, KEY=VALUE…, --arguments, --root', 'Runs a model and waits for it to finish.'],
  ['setup', 'MODEL_ID, --all, --refresh, --plan, --progress', 'Downloads weights ahead of time, for working offline.'],
  ['serve', '--root', 'Starts the MCP server for an agent. Needs the mcp extra.'],
  ['checkpoints', 'MODEL_ID', 'Lists where model checkpoints come from. Downloads nothing.'],
  ['packages', '', 'Lists the model families and which runtimes are installed.'],
  ['runtime', '', 'Checks MLX and Metal on this Mac.'],
];

export const cliExamples = {
  install: medmlxInstallCommand,
  run: medmlxRunCommand,
  setup: 'medmlx setup --all --progress\nmedmlx setup mlx-segment-ct --progress',
  plan: 'medmlx setup --all --plan',
  refresh: 'medmlx setup MODEL_ID --refresh',
  serve: medmlxServeCommand,
};

/** Public functions and their signatures, from src/medmlx at the tag. */
export const pythonFunctions = [
  ['run', '(model_id, *, root=None, **arguments)', 'Runs a model and waits for it to finish. If you interrupt it, the model stops.'],
  ['describe_model', '(model_id)', 'Shows the arguments a model takes and how to use them.'],
  ['model_readiness', '(model_ids=None)', 'Checks that models are installed and that Metal works on this Mac.'],
  ['check_run', '(model_id, *, root=None, **arguments)', 'Checks one run without running it: the argument names, the input paths and the weights.'],
  ['list_models', '(task=None, family=None)', 'Lists the installed models, and any installed model that failed to load.'],
  ['list_packages', '()', 'Lists the model families, which runtimes are installed and the models each one provides.'],
  ['list_checkpoints', '(model_id=None)', 'Lists where model checkpoints come from. Downloads nothing.'],
  ['runtime_info', '()', 'Reports this Mac’s platform and what MLX sees, including whether Metal is available.'],
  ['setup_model', '(model_id, *, progress=None, refresh=False)', 'Downloads one model’s weights ahead of time.'],
  ['setup_all', '(*, progress=None, refresh=False)', 'Downloads weights for every installed model. One failure doesn’t stop the rest.'],
  ['setup_plan', '(model_id)', 'Shows what would download for one model, without downloading it.'],
  ['list_setup_plans', '()', 'Shows what would download for every installed model.'],
];

export const pythonExamples = {
  install: medmlxProjectCommand,
  run: [
    'import medmlx',
    '',
    'result = medmlx.run(',
    '    "mlx-segment-ct",',
    '    image_path="ct.nii.gz",',
    '    output_dir="segment-ct",',
    '    root="/path/to/medmlx-work",',
    ')',
  ].join('\n'),
};

/** Every example, with the release document that contains it. */
export const developerExamples = [
  ...[cliExamples.install, cliExamples.run, cliExamples.serve, pythonExamples.install, pythonExamples.run]
    .map(command => ({ distribution: 'medmlx', path: 'README.md', command })),
  ...[cliExamples.setup, cliExamples.plan, cliExamples.refresh]
    .map(command => ({ distribution: 'medmlx', path: 'docs/setup.md', command })),
];

/** Names the release check finds in the tag's CLI and package exports. */
export const developerReference = {
  commands: cliCommands.map(([name]) => name),
  functions: pythonFunctions.map(([name]) => name),
};
