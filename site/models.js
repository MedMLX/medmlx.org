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
const reasonCtMemory = '22.7 GB';

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
      ['Precision', 'FP32'],
    ],
    requirements: [
      ['Platform', platformRequirement],
      ['Python', `${pythonVersion}, with uv`],
      ['Disk', `${reasonCtWeights} for the weights`],
      ['Memory', `${reasonCtMemory} peak MLX use, plus memory for preprocessing, macOS and other apps`],
      ['Input', 'One 3D CT volume in NIfTI with Hounsfield unit values and valid spatial geometry'],
      ['Precision', 'FP32 weights, activations and caches by default; BF16 profiles are documented in the release README'],
      ['License', 'Port: Apache-2.0; NVIDIA material: OpenMDW-1.1; retained MIT and BSD notices'],
    ],
    outputs: [
      ['report.txt', 'the generated report or answer'],
      ['model_response.json', 'the response and generation metadata, plus the reasoning when thinking mode is on'],
      ['run.json', 'execution metadata'],
    ],
    limitations: [
      'DICOM, 2D images, video and multi-volume prompts are not supported.',
      'The automatic crop locates the chest from enclosed air. On some whole-body scans, especially with the arms raised, it selects the head and neck instead. Crop whole-body volumes to the chest or abdomen before running.',
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
// standard block.
export const additionalRuntimes = [
  { name: 'FDG PET/CT', distribution: 'fdg-pet-ct-mlx', task: 'Generation', description: 'Synthetic FDG PET from CT and organ labels, with scanner blur, scatter and count noise.' },
  { name: 'nnU-Net', distribution: 'nnunet-mlx', task: 'Segmentation', description: 'nnU-Net v2 inference, with checkpoints for liver and pancreas CT, brain tumor MRI and PET/CT lesions.' },
  { name: 'NV-Segment-CT', distribution: 'mlx-segment-ct', task: 'Segmentation', description: 'Automatic and prompted 3D CT segmentation with NVIDIA VISTA-3D.' },
  { name: 'SegResNet', distribution: 'segresnet-mlx', task: 'Segmentation', description: 'MONAI checkpoints for brain tumor MRI (BraTS), renal contrast-enhanced CT and whole-body CT.' },
  { name: 'UNesT', distribution: 'unest-mlx', task: 'Segmentation', description: 'Transformer-based renal CT segmentation from MONAI.' },
  { name: 'SwinUNETR', distribution: 'swin-unetr-mlx', task: 'Segmentation', description: 'Abdominal CT multi-organ segmentation (BTCV) from MONAI.' },
  { name: 'MedSAM2', distribution: 'medsam2-mlx', task: 'Segmentation', description: 'Lesion or organ segmentation from a box, point or mask prompt, tracked through the volume.' },
  { name: 'BioMedParse', distribution: 'biomedparse-mlx', task: 'Segmentation', description: 'Text-prompted 3D segmentation with Microsoft BioMedParse v2.' },
  { name: 'TotalSegmentator', distribution: 'totalsegmentator-mlx', task: 'Segmentation', description: '117 CT structures, with standard, fast and coarse modes and optional ROI or body cropping.' },
  { name: 'SynthSeg', distribution: 'synthseg-mlx', task: 'Segmentation', description: 'Brain segmentation and parcellation.' },
  { name: 'FleXray', distribution: 'flexray-mlx', task: 'Segmentation', description: 'Radiograph segmentation.' },
  { name: 'FlexibleUNet', distribution: 'flexible-unet-mlx', task: 'Segmentation', description: 'Endoscopic instrument segmentation with an EfficientNet-B2 encoder, from MONAI.' },
  { name: '3D RetinaNet', distribution: 'lung-nodule-mlx', task: 'Detection', description: 'MONAI RetinaNet lung nodule detection in 3D chest CT.' },
  { name: 'NV-Generate', distribution: 'mlx-generate-ctmr', task: 'Generation', description: 'Synthetic 3D CT and MRI generation with NVIDIA NV-Generate (MAISI).' },
  { name: 'LesionDiffusion', distribution: 'lesiondiffusion-mlx', task: 'Generation', description: 'Synthetic lesions in CT, with control of organ, size, placement and phenotype.' },
  { name: 'MedGemma', distribution: 'med-vlm-mlx', task: 'Vision-language', description: 'Standalone medical image-language inference, with Python, CLI and HTTP interfaces.' },
  { name: 'RadImageNet', distribution: 'radimagenet-mlx', task: 'Feature extraction', description: 'RadImageNet-pretrained ResNet50, DenseNet121, InceptionV3 and InceptionResNetV2 encoders.' },
  { name: 'PyRadiomics', distribution: 'mlxradiomics', task: 'Quantitative imaging', description: 'PyRadiomics-compatible radiomics features and voxel feature maps on the Apple Silicon GPU.' },
].map(({ install, ...runtime }) => ({
  ...runtime,
  package: packageUrl(runtime.distribution),
  install: runtimeInstallCommand(runtime.distribution, install),
}));
