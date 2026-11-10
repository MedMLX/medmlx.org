import { releases } from './releases.js';

// The MCP guide page copies docs/mcp.md from the reviewed medmlx tag. make
// release-check finds every command and JSON example below in that document.
const tag = `v${releases.medmlx.version}`;

/** Link to a medmlx docs page at the reviewed tag. */
export function medmlxDoc(file) {
  return `https://github.com/${releases.medmlx.repository}/blob/${tag}/docs/${file}`;
}

export const mcpGuideSource = medmlxDoc('mcp.md');

export const mcpCommands = {
  install: [
    'git clone https://github.com/MedMLX/medmlx.git',
    'cd medmlx',
    'uv sync --locked --no-dev --extra segment --extra mcp',
  ].join('\n'),
  check: '.venv/bin/medmlx models\n.venv/bin/medmlx runtime',
  codex: [
    'mkdir -p "$HOME/medmlx-work"',
    'codex mcp add medmlx -- "$PWD/.venv/bin/medmlx" serve --root "$HOME/medmlx-work"',
  ].join('\n'),
};

const totalSegmentatorArguments = [
  '  "arguments": {',
  '    "weights_path": "models/total",',
  '    "image_path": "inputs/ct.nii.gz",',
  '    "output_dir": "results/ct-total"',
  '  }',
];

/** JSON arguments for each tool call in the TotalSegmentator example. */
export const mcpCalls = [
  ['describe_model', '{"model_id": "totalsegmentator"}'],
  ['model_readiness', ['{', '  "model_ids": ["totalsegmentator"],', ...totalSegmentatorArguments, '}'].join('\n')],
  ['run_model', ['{', '  "model_id": "totalsegmentator",', ...totalSegmentatorArguments, '}'].join('\n')],
  ['get_job', '{"job_id": "RETURNED_JOB_ID", "wait_seconds": 30}'],
];

// The guide's tool table; backticks mark inline code, as in the source.
export const mcpTools = [
  ['runtime_info', 'None', 'Reports the server folder, the platform, package versions and whether MLX and Metal work.'],
  ['list_packages', 'None', 'Lists the model families, which runtimes are installed and any that failed to load.'],
  ['list_models', 'Optional `task`, `family`', 'Lists the installed models. You can filter by task, or by the `segment`, `generate` or `vision` family.'],
  ['list_checkpoints', 'Optional `model_id`', 'Lists where model checkpoints come from and their channel order. Downloads nothing.'],
  ['describe_model', '`model_id`', 'Shows the arguments a model takes and its author\u2019s instructions.'],
  ['model_readiness', 'Optional `model_ids`, `arguments`', 'Checks that a model can run. With arguments, it also checks their names and that input and weight paths exist.'],
  ['run_model', '`model_id`, `arguments`', 'Starts a model in its own process and returns a job.'],
  ['get_job', '`job_id`, optional `wait_seconds`', 'Shows a job\u2019s state, the end of its log, and its result or error when done.'],
  ['list_jobs', 'None', 'Lists this session\u2019s jobs.'],
  ['cancel_job', '`job_id`', 'Stops a running job and anything it started.'],
];

/** Every command and JSON example the page shows, with the release document that contains it. */
export const mcpExamples = [
  ...Object.values(mcpCommands).map(command => ({ distribution: 'medmlx', path: 'docs/mcp.md', command })),
  ...mcpCalls.map(([, command]) => ({ distribution: 'medmlx', path: 'docs/mcp.md', command, kind: 'json' })),
];
