import { packageUrl, platformRequirement, pythonVersion, runtimeInstallCommand } from './releases.js';

/** Return a standalone Reason-CT command with user values quoted for a POSIX shell. */
export function reportCommand(parameters) {
  const quote = value => "'" + value.replace(/'/g, "'\"'\"'") + "'";
  const args = [
    `--input=${quote(parameters.image_path)}`,
    `--model-dir=${quote(parameters.weights_path)}`,
    `--output-dir=${quote(parameters.output_dir)}`,
  ];
  if (parameters.anatomy_region) args.push(`--anatomy-region=${quote(parameters.anatomy_region)}`);
  if (parameters.prompt) args.push(`--prompt=${quote(parameters.prompt)}`);
  if (parameters.enable_thinking) args.push('--enable-thinking');
  return ['mlx-reason-ct', 'report', ...args].join(' ');
}

// Runtimes with a detailed page have published packages and weights.
// Copy requirements, figures and commands from each package's README and docs.
const reasonCtWeights = '17.4 GB';
const reasonCtMemory = '12.5 GB';

export const models = [
  {
    slug: 'mlx-reason-ct',
    distribution: 'mlx-reason-ct',
    name: 'MLX-Reason-CT',
    upstream: { name: 'NVIDIA NV-Reason-CT', url: 'https://huggingface.co/nvidia/NV-Reason-CT' },
    task: 'Vision-language',
    summary: 'Structured reports and question answering for 3D chest and abdomen CT.',
    description: 'Writes a structured report for a chest or abdomen CT volume, or answers a question about it.',
    resourceSizes: { weights: reasonCtWeights, peakMemory: reasonCtMemory },
    specs: [
      ['Input', '3D CT in NIfTI (.nii or .nii.gz), Hounsfield units'],
      ['Anatomy', 'Chest or abdomen'],
      ['Output', 'Report or answer as text'],
      ['Weights', reasonCtWeights],
      ['Peak memory', reasonCtMemory],
      ['Precision', 'BF16 weights with FP32 accumulation'],
    ],
    requirements: [
      ['Platform', platformRequirement],
      ['Download', `${reasonCtWeights} for the model files`],
      ['Memory', `About ${reasonCtMemory} used by the model, plus extra for preparing the scan`],
      ['Input', 'One 3D chest or abdomen CT scan saved as a NIfTI file'],
      ['License', 'Software: Apache-2.0. NVIDIA model: OpenMDW-1.1. Other notices are in the repository.'],
    ],
    outputs: [
      ['report.txt', 'the generated report or answer'],
      ['model_response.json', 'the response and generation metadata, plus the reasoning when thinking mode is on'],
      ['run.json', 'scan geometry, precision and run status'],
    ],
    limitations: [
      'Use one NIfTI scan at a time. DICOM files, 2D images and video are not supported.',
      'Crop whole-body scans to the chest or abdomen before running. If the region is not found, the run warns and falls back to a crop from the top of the scan.',
    ],
    links: {
      package: packageUrl('mlx-reason-ct'),
      weights: 'https://huggingface.co/MedMLX/MLX-Reason-CT',
    },
    commands: {
      install: runtimeInstallCommand('mlx-reason-ct'),
      download: 'mlx-reason-ct download \\\n  --repo MedMLX/MLX-Reason-CT \\\n  --revision 5e5b5202fd04ac9f63ede203ebc9327aa676ae94 \\\n  --model-dir models',
      report: reportCommand({ image_path: 'ct.nii.gz', weights_path: 'models', output_dir: 'outputs' }),
    },
  },
];

// Additional runtimes link to their published packages. Each install command is the
// README block at the release tag; `install` holds the README's exceptions to the
// standard block. A named model with its own page inside a package sets `slug`, its
// page and model-card key (otherwise the distribution), and `upstream`, the original
// work credited at the top of that page. `request` links the public issue that asked
// for the port; the page shows it as a "User requested" tag.
export const additionalRuntimes = [
  { name: 'FDG PET/CT', distribution: 'fdg-pet-ct-mlx', task: 'Generation', description: 'Synthetic FDG PET from CT and organ labels, with scanner blur, scatter and count noise.' },
  { name: 'nnU-Net', distribution: 'nnunet-mlx', task: 'Segmentation', description: 'Segmentation of liver and pancreas CT, brain tumor MRI and PET/CT lesions.' },
  {
    slug: 'siam', name: 'SIAM', distribution: 'nnunet-mlx', task: 'Segmentation',
    description: 'Contrast-agnostic segmentation of the whole head from any MRI contrast or CT: brain tissues, deep nuclei, CSF, dura, vessels, skull and scalp, with an anomaly label.',
    upstream: {
      name: 'SIAM v0.3', authors: 'Valabregue et al.',
      repository: 'https://github.com/romainVala/SIAM', paper: 'https://arxiv.org/abs/2605.02737',
      citation: 'Valabregue, R., Khemir, I., Bardinet, E., Rousseau, F., Auzias, G. & Dorent, R. (2026). SIAM: Head and Brain MRI Segmentation from Few High-Quality Templates via Synthetic Training. arXiv:2605.02737.',
    },
    request: 'https://github.com/MedMLX/.github/issues/2',
  },
  { name: 'NV-Segment-CT', distribution: 'mlx-segment-ct', task: 'Segmentation', description: 'Automatic and prompted 3D CT segmentation with NVIDIA VISTA-3D.' },
  { name: 'SegResNet', distribution: 'segresnet-mlx', task: 'Segmentation', description: 'Segmentation of renal arteries, veins, ureters, tumors and kidney tissue from three-phase CT.' },
  { name: 'UNesT', distribution: 'unest-mlx', task: 'Segmentation', description: 'Kidney cortex, medulla and collecting system segmentation in contrast-enhanced CT.' },
  { name: 'SwinUNETR', distribution: 'swin-unetr-mlx', task: 'Segmentation', description: 'Organ segmentation in abdominal CT.' },
  { name: 'MedSAM2', distribution: 'medsam2-mlx', task: 'Segmentation', description: 'Lesion or organ segmentation from a box, point or mask prompt, tracked through the volume.' },
  { name: 'SAM 3', distribution: 'sam3-mlx', task: 'Segmentation', description: 'Segment objects in 2D images or video frames from a text, box or point prompt with Meta SAM 3.' },
  { name: 'BioMedParse', distribution: 'biomedparse-mlx', task: 'Segmentation', description: 'Text-prompted 3D segmentation with Microsoft BioMedParse v2.' },
  { name: 'TotalSegmentator', distribution: 'totalsegmentator-mlx', task: 'Segmentation', description: 'Identify 117 organs and other body structures in CT scans.' },
  { name: 'SynthSeg', distribution: 'synthseg-mlx', task: 'Segmentation', description: 'Brain segmentation and parcellation.' },
  { name: 'FleXray', distribution: 'flexray-mlx', task: 'Segmentation', description: 'Radiograph segmentation.' },
  { name: 'FlexibleUNet', distribution: 'flexible-unet-mlx', task: 'Segmentation', description: 'Identify surgical instruments in endoscopy images.' },
  { name: 'RetinaNet', distribution: 'lung-nodule-mlx', task: 'Detection', description: 'MONAI RetinaNet lung nodule detection in 3D chest CT.' },
  { name: 'NV-Generate', distribution: 'mlx-generate-ctmr', task: 'Generation', description: 'Synthetic 3D CT and MRI generation with NVIDIA NV-Generate (MAISI).' },
  { name: 'LesionDiffusion', distribution: 'lesiondiffusion-mlx', task: 'Generation', description: 'Synthetic lesions in CT, with control of organ, size, placement and phenotype.' },
  { name: 'MedGemma', distribution: 'med-vlm-mlx', task: 'Vision-language', description: 'Ask questions about medical images and receive written responses on your Mac.' },
  { name: 'Radiomics', distribution: 'mlxradiomics', task: 'Quantitative imaging', description: 'Measure intensity, texture and shape in a region, with voxel maps of intensity and texture.' },
  { name: 'RadImageNet', distribution: 'radimagenet-mlx', task: 'Feature extraction', description: 'Extract numerical image features for research with models trained on RadImageNet.' },
].map(({ install, ...runtime }) => ({
  slug: runtime.distribution,
  ...runtime,
  package: packageUrl(runtime.distribution),
  install: runtimeInstallCommand(runtime.distribution, install),
}));

// How to run each runtime page's model through medmlx, keyed by page slug. `extras` is the
// medmlx install its tagged README gives; `id` and the `--arg` names must appear in that
// README, which make release-check confirms. A model medmlx itself provides names that
// `package` and the `docs` page documenting it. `before` lists README setup commands that
// must run first, and `output` and `also` add one line of README or describe facts.
export const runExamples = {
  'fdg-pet-ct-mlx': {
    id: 'fdg-pet-ct', extras: 'generate,mcp',
    args: 'image_path=ct.nii.gz labels_path=labels.nii.gz profile_path=profiles.json output_dir=fdg-pet',
    prompt: 'Use MedMLX to make a synthetic FDG PET from ct.nii.gz, labels.nii.gz and profiles.json in my work folder.',
    output: 'The synthetic PET is written to `fdg-pet/pet.nii.gz` in SUV.',
  },
  'nnunet-mlx': {
    id: 'nnunet-liver', extras: 'segment,mcp',
    args: 'image_path=ct.nii.gz output_dir=nnunet-liver',
    prompt: 'Use MedMLX to segment the liver in ct.nii.gz in my work folder with nnU-Net.',
    also: '`nnunet-pancreas`, `nnunet-autopet` and `nnunet-brats2021` run the other nnU-Net models.',
  },
  siam: {
    id: 'siam', extras: 'segment,mcp',
    args: 'image_path=head.nii.gz output_dir=siam',
    prompt: 'Use MedMLX to segment head.nii.gz in my work folder with SIAM.',
  },
  'mlx-segment-ct': {
    id: 'mlx-segment-ct', extras: 'segment,mcp',
    args: 'image_path=ct.nii.gz output_dir=segment-ct',
    prompt: 'Use MedMLX to segment ct.nii.gz in my work folder with NV-Segment-CT.',
    output: 'The mask is written to `segment-ct/mlx_segment_ct_mask.nii.gz`.',
    also: '`mlx-segment-ctmr` also takes MRI.',
  },
  'segresnet-mlx': {
    id: 'segresnet-renal-cect', extras: 'segment,mcp',
    args: 'arterial_path=arterial.nii.gz venous_path=venous.nii.gz excretory_path=excretory.nii.gz output_dir=segresnet',
    prompt: 'Use MedMLX to run segresnet-renal-cect on arterial.nii.gz, venous.nii.gz and excretory.nii.gz in my work folder.',
    output: 'The label map is written to the `segresnet` folder.',
  },
  'unest-mlx': {
    id: 'unest', extras: 'segment,mcp',
    args: 'image_path=ct.nii.gz output_dir=unest',
    prompt: 'Use MedMLX to segment the kidneys in ct.nii.gz in my work folder with UNesT.',
  },
  'swin-unetr-mlx': {
    id: 'swin-unetr', extras: 'segment,mcp',
    args: 'image_path=ct.nii.gz output_dir=swin-unetr',
    prompt: 'Use MedMLX to segment the organs in ct.nii.gz in my work folder with SwinUNETR.',
  },
  'medsam2-mlx': {
    id: 'medsam2', extras: 'segment,mcp',
    args: "image_path=ct.nii.gz frame_idx=40 box_xyxy:='[120, 140, 180, 200]' output_dir=medsam2",
    prompt: 'Use MedMLX to segment the lesion in ct.nii.gz with MedSAM2, from the box [120, 140, 180, 200] on slice 40.',
  },
  'sam3-mlx': {
    id: 'sam3', extras: 'segment,mcp',
    args: 'image_path=image.png text_prompt=kidney output_dir=sam3',
    prompt: 'Use MedMLX to find the kidney in image.png in my work folder with SAM 3.',
    output: 'The masks are written to `sam3/masks.npy`, with `sam3/prediction.json`.',
  },
  'biomedparse-mlx': {
    id: 'biomedparse-v2', extras: 'segment,mcp',
    args: "image_path=ct.nii.gz 'prompt=Visualization of the liver in abdominal CT imaging' output_dir=biomedparse",
    prompt: 'Use MedMLX to segment the liver in ct.nii.gz in my work folder with BioMedParse.',
  },
  'totalsegmentator-mlx': {
    id: 'totalsegmentator', extras: 'segment,mcp',
    args: 'image_path=ct.nii.gz output_dir=totalseg',
    prompt: 'Use MedMLX to segment ct.nii.gz in my work folder with TotalSegmentator.',
    output: 'The mask is written to `totalseg/mask.nii.gz`.',
  },
  'synthseg-mlx': {
    id: 'synthseg', extras: 'segment,mcp',
    args: 'image_path=brain.nii.gz output_dir=synthseg',
    prompt: 'Use MedMLX to segment the brain MRI brain.nii.gz in my work folder with SynthSeg.',
  },
  'flexray-mlx': {
    id: 'flexray', extras: 'segment,mcp',
    args: 'image_path=xray.png output_dir=flexray',
    prompt: 'Use MedMLX to segment the radiograph xray.png in my work folder with FleXray.',
  },
  'flexible-unet-mlx': {
    id: 'flexible-unet', extras: 'segment,mcp',
    args: 'image_path=frame.jpg output_dir=flexible-unet',
    prompt: 'Use MedMLX to find the surgical instruments in frame.jpg in my work folder with FlexibleUNet.',
  },
  'lung-nodule-mlx': {
    id: 'lung-nodule', extras: 'vision,mcp',
    args: 'image_path=chest-ct.nii.gz output_dir=nodules',
    prompt: 'Use MedMLX to find lung nodules in chest-ct.nii.gz in my work folder.',
  },
  'mlx-generate-ctmr': {
    id: 'mlx-generate-ctmr-ct', extras: 'generate,mcp',
    args: 'output_dir=generated-ct',
    prompt: 'Use MedMLX to generate a synthetic CT with NV-Generate.',
    also: '`mlx-generate-ctmr-mr` and `mlx-generate-ctmr-mr-brain` generate MRI.',
  },
  'lesiondiffusion-mlx': {
    id: 'lesiondiffusion', extras: 'generate,mcp',
    args: 'image_path=ct.nii.gz organ_mask_path=liver.nii.gz organ=liver lesion_type=tumor placement=inside_parenchyma output_dir=lesion',
    prompt: 'Use MedMLX to add a liver tumor to ct.nii.gz with LesionDiffusion, using the liver mask liver.nii.gz.',
  },
  'med-vlm-mlx': {
    id: 'medgemma', extras: 'mcp', package: 'medmlx', docs: 'docs/medvlm-bridge.md',
    before: ['uvx --from huggingface_hub hf download mlx-community/medgemma-1.5-4b-it-4bit --revision 762746b7a72b0b68dd8fa3f9aea5dc3980674d23 --local-dir medgemma'],
    args: "image_path=image.png 'prompt=Describe the image.' weights_path=medgemma output_dir=medgemma-out",
    prompt: 'Use MedMLX to ask MedGemma to describe image.png in my work folder, with the weights in the medgemma folder.',
    output: 'The answer is written to `medgemma-out/report.json`. MedGemma needs the local weights the second line downloads.',
  },
  mlxradiomics: {
    id: 'mlxradiomics', extras: 'vision,mcp',
    args: 'image_path=ct.nii.gz mask_path=mask.nii.gz output_dir=radiomics',
    prompt: 'Use MedMLX to measure radiomics features in ct.nii.gz within mask.nii.gz in my work folder.',
  },
  'radimagenet-mlx': {
    id: 'radimagenet-resnet50', extras: 'vision,mcp',
    args: 'image_path=image.png output_dir=features',
    prompt: 'Use MedMLX to extract RadImageNet features from image.png in my work folder.',
    also: '`radimagenet-densenet121`, `radimagenet-inceptionv3` and `radimagenet-inceptionresnetv2` use the other backbones.',
  },
};

/** The terminal commands for a runtime page: install, any setup, describe, then run. */
export function runCommand({ id, extras, before = [], args }) {
  return [`uv tool install --python ${pythonVersion} "medmlx[${extras}]"`, ...before,
    `medmlx describe ${id}`, `medmlx run ${id} --arg ${args}`].join('\n');
}
