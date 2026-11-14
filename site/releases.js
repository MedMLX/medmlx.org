// Reviewed published releases. make release-check compares these with PyPI and
// the repository's v<version> tag before the site can be exported.
export const pythonVersion = '3.13';
// MLX's published macOS wheels require 14.0 or later.
export const macosVersion = '14.0';
export const platformRequirement = `macOS ${macosVersion} or later on Apple Silicon`;
export const releases = {
  medmlx: { version: '0.9.1', repository: 'MedMLX/medmlx' },
  'mlx-reason-ct': { version: '0.6.0', repository: 'MedMLX/mlx-reason-ct' },
  'fdg-pet-ct-mlx': { version: '0.3.0', repository: 'MedMLX/fdg-pet-ct-mlx' },
  'nnunet-mlx': { version: '0.8.0', repository: 'MedMLX/nnunet-mlx' },
  'mlx-segment-ct': { version: '0.3.6', repository: 'MedMLX/mlx-segment-ct' },
  'segresnet-mlx': { version: '0.4.1', repository: 'MedMLX/segresnet-mlx' },
  'unest-mlx': { version: '0.2.8', repository: 'MedMLX/unest-mlx' },
  'swin-unetr-mlx': { version: '0.2.7', repository: 'MedMLX/swin-unetr-mlx' },
  'medsam2-mlx': { version: '0.3.0', repository: 'MedMLX/medsam2-mlx' },
  'sam3-mlx': { version: '0.3.0', repository: 'MedMLX/sam3-mlx' },
  'biomedparse-mlx': { version: '0.1.6', repository: 'MedMLX/biomedparse-mlx' },
  'totalsegmentator-mlx': { version: '0.2.0', repository: 'MedMLX/totalsegmentator-mlx' },
  'synthseg-mlx': { version: '0.3.5', repository: 'MedMLX/synthseg-mlx' },
  'flexray-mlx': { version: '0.2.7', repository: 'MedMLX/flexray-mlx' },
  'flexible-unet-mlx': { version: '0.2.7', repository: 'MedMLX/flexible-unet-mlx' },
  'lung-nodule-mlx': { version: '0.2.7', repository: 'MedMLX/lung-nodule-mlx' },
  'mlx-generate-ctmr': { version: '0.6.0', repository: 'MedMLX/mlx-generate-ctmr' },
  'lesiondiffusion-mlx': { version: '0.2.8', repository: 'MedMLX/lesiondiffusion-mlx' },
  'med-vlm-mlx': { version: '0.3.4', repository: 'MedMLX/med-vlm-mlx' },
  'radimagenet-mlx': { version: '0.3.4', repository: 'MedMLX/radimagenet-mlx' },
  mlxradiomics: { version: '1.0.1', repository: 'MedMLX/mlx-radiomics' },
};

// From uv's installation docs; uv is not a reviewed MedMLX release.
export const uvInstallCommand = 'curl -LsSf https://astral.sh/uv/install.sh | sh';

const environmentCommand = `uv venv --python ${pythonVersion}\nsource .venv/bin/activate`;
export const medmlxInstallCommand = `uv tool install --python ${pythonVersion} "medmlx[all,mcp]"`;
export const medmlxProjectCommand = 'uv add "medmlx[all,mcp]"';
// Copied from the medmlx README; make release-check finds each in the tagged release.
export const medmlxRunCommand = [
  'medmlx describe mlx-segment-ct',
  'medmlx readiness mlx-segment-ct --arg image_path=ct.nii.gz output_dir=segment-ct',
  'medmlx run mlx-segment-ct --arg image_path=ct.nii.gz output_dir=segment-ct',
].join('\n');
export const medmlxSetupCommand = 'medmlx setup --all --progress';
export const medmlxServeCommand = 'medmlx serve --root /path/to/work';
/** The medmlx commands the site shows, with the release document that contains each. */
export const medmlxExamples = [
  medmlxInstallCommand, medmlxProjectCommand, medmlxRunCommand, medmlxSetupCommand, medmlxServeCommand,
].map(command => ({ distribution: 'medmlx', path: 'README.md', command }));

/** Link to the package's current published instructions. */
export function packageUrl(name) {
  if (!releases[name]) throw new Error(`Unreviewed package: ${name}`);
  return `https://pypi.org/project/${name}/`;
}

/**
 * Return the install block from the runtime's published README: a new environment,
 * then the reviewed release. `exact` pins it with == and `also` adds the README's
 * companion packages.
 */
export function runtimeInstallCommand(name, { exact = false, also = [] } = {}) {
  const release = releases[name];
  if (!release) throw new Error(`Unreviewed package: ${name}`);
  const requirement = `"${name}${exact ? '==' : '>='}${release.version}"`;
  return `${environmentCommand}\nuv pip install ${[requirement, ...also].join(' ')}`;
}

// Agent setup for Get started. The Claude Code and Codex lines are the "Use with MedMLX"
// block every runtime README shares, checked against TotalSegmentator's; the JSON is the
// medmlx README's. make release-check finds each in its tagged release.
export const claudeConnectCommand = [
  'MEDMLX="$(uv tool dir --bin --color never)/medmlx"',
  'mkdir -p "$HOME/medmlx-work"',
  'claude mcp add --scope user medmlx -- "$MEDMLX" serve --root "$HOME/medmlx-work"',
].join('\n');
export const codexConnectCommand = 'codex mcp add medmlx -- "$MEDMLX" serve --root "$HOME/medmlx-work"';
export const jsonConnectConfig = `{
  "mcpServers": {
    "medmlx": {
      "command": "/absolute/path/to/medmlx",
      "args": ["serve", "--root", "/absolute/path/to/medmlx-work"]
    }
  }
}`;
export const connectExamples = [
  { distribution: 'totalsegmentator-mlx', path: 'README.md', command: claudeConnectCommand },
  { distribution: 'totalsegmentator-mlx', path: 'README.md', command: codexConnectCommand },
  { distribution: 'medmlx', path: 'README.md', command: jsonConnectConfig },
];

// A small abdominal CT (122x101x30) from TotalSegmentator's Apache-2.0 test files, pinned to
// one commit. It is not a MedMLX release, so the release check does not cover it.
export const sampleCtCommand = [
  'mkdir -p ~/medmlx-work && cd ~/medmlx-work',
  'curl -L -o ct.nii.gz https://raw.githubusercontent.com/wasserth/TotalSegmentator/d89e47f73d24f5fba732a715aeb6fdc0ae34526b/tests/reference_files/example_ct_sm.nii.gz',
].join('\n');
