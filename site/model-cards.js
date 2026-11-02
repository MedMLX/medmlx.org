// Reviewed excerpts from each published release's README, not its main branch.
// Keep wording and links intact: release-check verifies every excerpt and URL.
// Reason-CT has a dedicated card and command builder in models.js.
export const modelCards = {
  "fdg-pet-ct-mlx": {
    "version": "0.2.6",
    "rows": [
      [
        "Input",
        "Aligned CT + organ labels + profiles"
      ],
      [
        "Output",
        "Synthetic PET SUV volume"
      ],
      [
        "Weights",
        "No model weights are needed."
      ]
    ],
    "limitations": [
      "This is image-space synthesis; it does not simulate projection physics or reconstruction.",
      "Volumes are never registered or resampled.",
      "The package ships no tissue statistics or scanner presets."
    ],
    "measurements": [],
    "noWeights": true,
    "weights": [],
    "terms": "[Apache-2.0](https://github.com/MedMLX/fdg-pet-ct-mlx/blob/v0.2.6/LICENSE). See [third-party notices](https://github.com/MedMLX/fdg-pet-ct-mlx/blob/v0.2.6/THIRD_PARTY_NOTICES.md)."
  },
  "nnunet-mlx": {
    "version": "0.6.4",
    "rows": [
      [
        "Input",
        "NIfTI channels"
      ],
      [
        "Output",
        "Segmentation and optional probabilities"
      ],
      [
        "Networks",
        "Supports 2D and 3D PlainConvUNet and ResidualEncoderUNet."
      ],
      [
        "Variants",
        "`2d`, `3d_lowres`, `3d_fullres` and cascades"
      ]
    ],
    "limitations": [
      "Supply input channels in the model’s expected order.",
      "Profiles cover inference only, not training or segmentation quality.",
      "There is no PyTorch, CPU or other fallback: unsupported architectures, plan fields, checkpoints and inputs fail with an error."
    ],
    "measurements": [],
    "noWeights": false,
    "weights": [
      {
        "name": "MedMLX/nnunet-liver-mlx",
        "url": "https://huggingface.co/MedMLX/nnunet-liver-mlx"
      },
      {
        "name": "MedMLX/nnunet-autopet-mlx",
        "url": "https://huggingface.co/MedMLX/nnunet-autopet-mlx"
      },
      {
        "name": "MedMLX/nnunet-pancreas-mlx",
        "url": "https://huggingface.co/MedMLX/nnunet-pancreas-mlx"
      },
      {
        "name": "MedMLX/nnunet-brats-mlx",
        "url": "https://huggingface.co/MedMLX/nnunet-brats-mlx"
      }
    ],
    "terms": "[Apache-2.0](https://github.com/MedMLX/nnunet-mlx/blob/v0.6.4/LICENSE). See [third-party notices](https://github.com/MedMLX/nnunet-mlx/blob/v0.6.4/THIRD_PARTY_NOTICES.md). Model weights retain their publisher terms."
  },
  "mlx-segment-ct": {
    "version": "0.3.5",
    "rows": [
      [
        "Input",
        "One CT in NIfTI (`.nii` or `.nii.gz`); CT or MRI with NV-Segment-CTMR"
      ],
      [
        "Output",
        "Anatomical labels on the input grid"
      ],
      [
        "Checkpoints",
        "`\"NV-Segment-CT\"` (default) or `\"NV-Segment-CTMR\"`, matching the weights"
      ]
    ],
    "limitations": [
      "The click coordinates are examples: use `(x, y, z)` voxels inside your image and its preprocessed foreground crop.",
      "The published [NV-Segment-CTMR weights](https://huggingface.co/MedMLX/vista3d-ctmr-mlx) cover CT and MRI under noncommercial terms. NVIDIA does not support interactive point segmentation with that checkpoint."
    ],
    "measurements": [],
    "noWeights": false,
    "weights": [
      {
        "name": "MedMLX/vista3d-ct-mlx",
        "url": "https://huggingface.co/MedMLX/vista3d-ct-mlx"
      },
      {
        "name": "MedMLX/vista3d-ctmr-mlx",
        "url": "https://huggingface.co/MedMLX/vista3d-ctmr-mlx"
      }
    ],
    "terms": "[Apache-2.0](https://github.com/MedMLX/mlx-segment-ct/blob/v0.3.5/LICENSE). See [third-party notices](https://github.com/MedMLX/mlx-segment-ct/blob/v0.3.5/THIRD_PARTY_NOTICES.md). Model weights retain their publisher terms."
  },
  "segresnet-mlx": {
    "version": "0.3.3",
    "rows": [
      [
        "Input",
        "MRI sequences or CT volumes"
      ],
      [
        "BraTS",
        "`brats`: contrast T1, T1, T2 and FLAIR MRI in NIfTI"
      ],
      [
        "Renal CECT",
        "`renal_cect`: arterial, venous and excretory CT in NIfTI"
      ],
      [
        "Output",
        "Segmentation on the input grid"
      ]
    ],
    "limitations": [
      "Inputs are finite 3D volumes on one voxel grid, with spatial units in millimetres or unspecified.",
      "The standalone `run(bundle=..., weights_path=...)` interface remains available for explicit local checkpoints, including the whole-body CT variants."
    ],
    "measurements": [],
    "noWeights": false,
    "weights": [
      {
        "name": "MedMLX/segresnet-brats-mlx",
        "url": "https://huggingface.co/MedMLX/segresnet-brats-mlx"
      },
      {
        "name": "MedMLX/segresnet-renal-cect-mlx",
        "url": "https://huggingface.co/MedMLX/segresnet-renal-cect-mlx"
      },
      {
        "name": "MedMLX/segresnet-wholebody-mlx",
        "url": "https://huggingface.co/MedMLX/segresnet-wholebody-mlx"
      }
    ],
    "terms": "[Apache-2.0](https://github.com/MedMLX/segresnet-mlx/blob/v0.3.3/LICENSE). See [third-party notices](https://github.com/MedMLX/segresnet-mlx/blob/v0.3.3/THIRD_PARTY_NOTICES.md). Model weights retain their publisher terms."
  },
  "unest-mlx": {
    "version": "0.2.7",
    "rows": [
      [
        "Input",
        "Contrast-enhanced CT · NIfTI"
      ],
      [
        "Output",
        "The mask holds float32 labels 0 background, 1 kidney cortex, 2 medulla and 3 pelvicalyceal system, on the input grid as the NIfTI reader corrects it."
      ]
    ],
    "limitations": [
      "Use arterial or portal-venous contrast-enhanced CT. On the non-contrast scans we tried, the kidneys were missed.",
      "Spatial units must be millimetres or unspecified; metres and microns are not converted."
    ],
    "measurements": [],
    "noWeights": false,
    "weights": [
      {
        "name": "MedMLX/unest-renal-ct-mlx",
        "url": "https://huggingface.co/MedMLX/unest-renal-ct-mlx"
      }
    ],
    "terms": "[Apache-2.0](https://github.com/MedMLX/unest-mlx/blob/v0.2.7/LICENSE). See [third-party notices](https://github.com/MedMLX/unest-mlx/blob/v0.2.7/THIRD_PARTY_NOTICES.md). Model weights retain their publisher terms."
  },
  "swin-unetr-mlx": {
    "version": "0.2.6",
    "rows": [
      [
        "Input",
        "One 3D abdominal CT in NIfTI, in Hounsfield units"
      ],
      [
        "Output",
        "Organ mask on the input grid"
      ]
    ],
    "limitations": [
      "Voxels must be finite and representable in float32.",
      "Following the bundle's `SaveImaged` layout, `ct.nii.gz` produces `out/ct/ct_trans.nii.gz`, with the input shape and the ITK reader's affine."
    ],
    "measurements": [],
    "noWeights": false,
    "weights": [
      {
        "name": "MedMLX/swin-unetr-mlx",
        "url": "https://huggingface.co/MedMLX/swin-unetr-mlx"
      }
    ],
    "terms": "[Apache-2.0](https://github.com/MedMLX/swin-unetr-mlx/blob/v0.2.6/LICENSE). See [third-party notices](https://github.com/MedMLX/swin-unetr-mlx/blob/v0.2.6/THIRD_PARTY_NOTICES.md). Model weights retain their publisher terms."
  },
  "medsam2-mlx": {
    "version": "0.2.8",
    "rows": [
      [
        "Input",
        "NIfTI CT volume or slice, `.npz` RECIST stack, or folder of `.jpg`/`.jpeg` frames"
      ],
      [
        "Prompts",
        "The predictor follows upstream `SAM2VideoPredictorNPZ`: box, point and mask prompts, corrections on tracked frames, multiple objects, forward and reverse propagation, `clear_all_prompts_in_frame`, `remove_object` and `reset_state`."
      ],
      [
        "Output",
        "The output is `medsam2_mask.nii.gz` (uint16 labels with the input's shape, affine and header), plus `medsam2_overlay.png` for single-slice inputs."
      ]
    ],
    "limitations": [
      "With propagation, every prompt must be on the same frame.",
      "Where objects overlap, the later object wins.",
      "A frame folder follows the upstream demo's video path; frames are read as grayscale, so color frames differ from upstream."
    ],
    "measurements": [],
    "noWeights": false,
    "weights": [
      {
        "name": "MedMLX/medsam2-ct-lesion-mlx",
        "url": "https://huggingface.co/MedMLX/medsam2-ct-lesion-mlx"
      },
      {
        "name": "MedMLX/medsam2-mlx",
        "url": "https://huggingface.co/MedMLX/medsam2-mlx"
      }
    ],
    "terms": "[Apache-2.0](https://github.com/MedMLX/medsam2-mlx/blob/v0.2.8/LICENSE). See [third-party notices](https://github.com/MedMLX/medsam2-mlx/blob/v0.2.8/THIRD_PARTY_NOTICES.md). Model weights retain their publisher terms; see the [model card](https://huggingface.co/MedMLX/medsam2-mlx)."
  },
  "biomedparse-mlx": {
    "version": "0.1.5",
    "rows": [
      [
        "Input",
        "A volume (`.npy`, upstream `.npz` with `imgs`, `.nii` or `.nii.gz`) or a 2D image (PNG, JPEG, BMP, TIFF or DICOM)"
      ],
      [
        "Prompt",
        "One text prompt or a list of them"
      ],
      [
        "Output",
        "A volume writes `segmentation.npz` (`segs`: uint16 labels on the input grid; `existence`: prompt-by-slice probabilities) and `run.json` with the source revision, prompts and settings; NIfTI input also gets `segmentation.nii.gz` on the source affine."
      ]
    ],
    "limitations": [
      "The released checkpoint is trained for 3D modalities, so 2D accuracy is not established.",
      "`.npy` and `.npz` volumes must already hold upstream's modality-specific preprocessing in the 0–255 range.",
      "A seed reproduces a run only on the same backend, prompt order, input shape and batch settings, and does not align with Torch's generator."
    ],
    "measurements": [],
    "noWeights": false,
    "weights": [
      {
        "name": "MedMLX/biomedparse-v2-mlx",
        "url": "https://huggingface.co/MedMLX/biomedparse-v2-mlx"
      }
    ],
    "terms": "[Apache-2.0](https://github.com/MedMLX/biomedparse-mlx/blob/v0.1.5/LICENSE). See [third-party notices](https://github.com/MedMLX/biomedparse-mlx/blob/v0.1.5/THIRD_PARTY_NOTICES.md). Model weights retain their publisher terms. BioMedParse weights are CC-BY-NC-SA-4.0."
  },
  "totalsegmentator-mlx": {
    "version": "0.1.6",
    "rows": [
      [
        "Input",
        "One finite 3D CT in NIfTI-1 or NIfTI-2, in Hounsfield units"
      ],
      [
        "Output",
        "Multilabel mask on the input grid"
      ],
      [
        "Modes",
        "`standard` (default, five 1.5 mm parts), `fast` (3 mm model, upstream `--fast`) or `coarse` (6 mm model, upstream `--fastest`)"
      ]
    ],
    "limitations": [
      "Only the upstream `total` CT task is included: Dataset291–295, 297 and 298 with 117 labels, plus the Dataset300 body model for cropping, all `3d_fullres`, fold 0, without mirroring.",
      "DICOM input, DICOM-SEG and RT-STRUCT output, other upstream tasks (including `total_mr` and licensed tasks), per-class output files, statistics, radiomics, previews, `--remove_small_blobs`, `--higher_order_resampling`, `--v1_order`, test-time augmentation and training are rejected or absent."
    ],
    "measurements": [],
    "noWeights": false,
    "weights": [
      {
        "name": "MedMLX/totalsegmentator-mlx",
        "url": "https://huggingface.co/MedMLX/totalsegmentator-mlx"
      }
    ],
    "terms": "[Apache-2.0](https://github.com/MedMLX/totalsegmentator-mlx/blob/v0.1.6/LICENSE). See [third-party notices](https://github.com/MedMLX/totalsegmentator-mlx/blob/v0.1.6/THIRD_PARTY_NOTICES.md). Model weights retain their publisher terms."
  },
  "synthseg-mlx": {
    "version": "0.3.4",
    "rows": [
      [
        "Input",
        "One 3D brain MRI in NIfTI (`.nii` or `.nii.gz`) of any contrast and resolution, or a CT in Hounsfield units with `ct=True`"
      ],
      [
        "Output",
        "Brain labels, volumes and QC"
      ],
      [
        "robust=True",
        "`True` runs the SynthSeg-robust cascade. Implies `fast`; cannot be combined with `v1`"
      ],
      [
        "v1=True",
        "`True` uses SynthSeg 1.0 and omits total intracranial volume. Combines with `fast`"
      ]
    ],
    "limitations": [
      "Upstream turns parcellation off by default; this runner turns it on.",
      "Images must be finite, non-constant and 3D, with at least three voxels per axis, millimetre or unspecified spatial units, header voxel sizes that match the affine, and orthogonal axes (rotation is fine)."
    ],
    "measurements": [],
    "noWeights": false,
    "weights": [
      {
        "name": "MedMLX/synthseg-mlx",
        "url": "https://huggingface.co/MedMLX/synthseg-mlx"
      }
    ],
    "terms": "[Apache-2.0](https://github.com/MedMLX/synthseg-mlx/blob/v0.3.4/LICENSE). See [third-party notices](https://github.com/MedMLX/synthseg-mlx/blob/v0.3.4/THIRD_PARTY_NOTICES.md). Model weights retain their publisher terms."
  },
  "flexray-mlx": {
    "version": "0.2.6",
    "rows": [
      [
        "Input",
        "One radiograph: an image Pillow reads (PNG, TIFF, ...) or a single-frame 2D DICOM"
      ],
      [
        "Output",
        "Structure masks and probabilities"
      ],
      [
        "Probabilities",
        "float32 61×256×256 sigmoid probabilities on the padded model grid"
      ]
    ],
    "limitations": [
      "The [published bundle](https://huggingface.co/MedMLX/flexray-mlx/tree/722d8341570e8b9e1196cf50e57892da84974fcc) holds only `flux0375`; its `ensemble.json` still lists all five members in order (`flux0375`, `flux000`, `flux025`, `flux050`, `flux075`).",
      "For `ensemble=True`, use the [upstream snapshot](https://huggingface.co/VictorButoi/flexray/tree/6b63ddf09cfdff99aea494e3738cf243a4e22cdb) with all five member folders.",
      "The released weights were trained with percentile normalization; other schemes are not validated."
    ],
    "measurements": [],
    "noWeights": false,
    "weights": [
      {
        "name": "MedMLX/flexray-mlx",
        "url": "https://huggingface.co/MedMLX/flexray-mlx"
      }
    ],
    "terms": "[Apache-2.0](https://github.com/MedMLX/flexray-mlx/blob/v0.2.6/LICENSE). See [third-party notices](https://github.com/MedMLX/flexray-mlx/blob/v0.2.6/THIRD_PARTY_NOTICES.md). Model weights retain their publisher terms. FleXray weights are noncommercial (CC-BY-NC-4.0)."
  },
  "flexible-unet-mlx": {
    "version": "0.2.6",
    "rows": [
      [
        "Input",
        "One RGB image Pillow can read; the bundle used JPEG"
      ],
      [
        "Output",
        "Following the bundle's `SaveImaged` layout, `frame.jpg` produces `out/frame/frame_trans.png`: an 8-bit grayscale mask at the original frame size, 255 for tools and 0 for background."
      ]
    ],
    "limitations": [
      "This 2D model reads images, not NIfTI volumes."
    ],
    "measurements": [],
    "noWeights": false,
    "weights": [
      {
        "name": "MedMLX/flexible-unet-effnetb2-mlx",
        "url": "https://huggingface.co/MedMLX/flexible-unet-effnetb2-mlx"
      }
    ],
    "terms": "[Apache-2.0](https://github.com/MedMLX/flexible-unet-mlx/blob/v0.2.6/LICENSE). See [third-party notices](https://github.com/MedMLX/flexible-unet-mlx/blob/v0.2.6/THIRD_PARTY_NOTICES.md). Model weights retain their publisher terms."
  },
  "lung-nodule-mlx": {
    "version": "0.2.6",
    "rows": [
      [
        "Input",
        "One scalar 3D chest CT in NIfTI, in Hounsfield units, with `mm`, `meter` or `micron` spatial units"
      ],
      [
        "Output",
        "`detections.json` holds `medmlx.detections.v1` candidate boxes (`cccwhd`, class 0 `nodule`) in RAS millimetres with their scores; `bundle_detections.json` holds the MONAI bundle rows in patient LPS."
      ]
    ],
    "limitations": [
      "Keep `resample_raw_input=True` for ordinary CT. The default follows the bundle's pre-resampled mode: it reorients to RAS and scales intensities, but does not check or correct voxel spacing.",
      "DICOM series are not read.",
      "Boxes map through the affine with MONAI's opposite-corner convention, so on oblique affines they differ from a box enclosing all eight corners."
    ],
    "measurements": [],
    "noWeights": false,
    "weights": [
      {
        "name": "MedMLX/retinanet-lung-nodule-mlx",
        "url": "https://huggingface.co/MedMLX/retinanet-lung-nodule-mlx"
      }
    ],
    "terms": "[Apache-2.0](https://github.com/MedMLX/lung-nodule-mlx/blob/v0.2.6/LICENSE). See [third-party notices](https://github.com/MedMLX/lung-nodule-mlx/blob/v0.2.6/THIRD_PARTY_NOTICES.md). Model weights retain their publisher terms."
  },
  "mlx-generate-ctmr": {
    "version": "0.5.2.post2",
    "rows": [
      [
        "Input",
        "Noise, or a CT anatomy mask"
      ],
      [
        "Output",
        "Synthetic 3D CT or MRI"
      ],
      [
        "Configurations",
        "`configuration=\"ct\"`, `\"mr\"` or `\"mr-brain\"`"
      ]
    ],
    "limitations": [
      "Numerical parity is checked against MONAI on small seeded networks. That does not qualify pretrained image quality. Synthetic output is not ground truth.",
      "General-MR weights have noncommercial terms; CT component terms require publisher clarification."
    ],
    "measurements": [
      "Peak MLX memory: **27.9 GiB** for `mlx-generate-ctmr-ct` (256³, from-mask, ControlNet + four-window decode); **23.8 GiB** for `mlx-generate-ctmr-mr-brain` (256×256×128, guided batch 2). No recorded peak for `mlx-generate-ctmr-mr`.",
      "The v0.5.1 memory measurements used MLX 0.32.4 and `MLX_ENABLE_TF32=0`: default `fast` arithmetic with FP32 accumulation and split-FP16 convolution operands, production constructors with random fan-in-scaled weights, seed 0 and 30 steps. Peaks include VAE decoding and exclude weight loading.",
      "These figures cover the stated pipelines and grids; they are MLX allocations, excluding host preprocessing and other applications."
    ],
    "noWeights": false,
    "weights": [
      {
        "name": "MedMLX/mlx-generate-ctmr",
        "url": "https://huggingface.co/MedMLX/mlx-generate-ctmr"
      }
    ],
    "terms": "[Apache-2.0](https://github.com/MedMLX/mlx-generate-ctmr/blob/v0.5.2.post2/LICENSE). See [third-party notices](https://github.com/MedMLX/mlx-generate-ctmr/blob/v0.5.2.post2/THIRD_PARTY_NOTICES.md). Model weights retain their publisher terms. General-MR weights have noncommercial terms; CT component terms require publisher clarification."
  },
  "lesiondiffusion-mlx": {
    "version": "0.2.6.post2",
    "rows": [
      [
        "Input",
        "CT + aligned binary organ mask"
      ],
      [
        "Output",
        "The outputs are `synthetic_ct.nii.gz` (float32 HU), `lesion_mask.nii.gz` and `organ_mask.nii.gz` (uint8) on the standardized grid."
      ],
      [
        "Modes",
        "`\"conditioned\"` (default) or `\"source\"`"
      ]
    ],
    "limitations": [
      "The CT and masks must be finite, axis-aligned grids that match after they are reoriented and resampled to RAS 1 mm; oblique or sheared grids are refused.",
      "The decoder reconstructs the whole CT, so voxels outside the lesion can change.",
      "Synthetic output is not ground truth."
    ],
    "measurements": [
      "**18.74 GB** peak MLX memory for `lesiondiffusion` in source mode on a 160×160×128, 1 mm RAS crop.",
      "The v0.2.5 memory measurement used the AMOS case 0008 crop and 200 diffusion steps with `inference_mode=\"source\"`: FP32 LMNet and text encoder, FP16 LINet and VQ.",
      "It does not measure the default conditioned mode or larger volumes. Peak MLX memory excludes host preprocessing and other applications."
    ],
    "noWeights": false,
    "weights": [
      {
        "name": "MedMLX/lesiondiffusion-mlx",
        "url": "https://huggingface.co/MedMLX/lesiondiffusion-mlx"
      }
    ],
    "terms": "[Apache-2.0](https://github.com/MedMLX/lesiondiffusion-mlx/blob/v0.2.6.post2/LICENSE). See [third-party notices](https://github.com/MedMLX/lesiondiffusion-mlx/blob/v0.2.6.post2/THIRD_PARTY_NOTICES.md). Model weights retain their publisher terms."
  },
  "med-vlm-mlx": {
    "version": "0.3.2",
    "rows": [
      [
        "Input",
        "Image + text prompt"
      ],
      [
        "Output",
        "Generated text"
      ],
      [
        "Checkpoint format",
        "4-bit Gemma3 image-text checkpoints"
      ]
    ],
    "limitations": [
      "Text and images only. Requests with audio, video, tool definitions or tool-call turns are rejected.",
      "The full prompt mask grows with the square of the prompt length.",
      "The checks cover numerical agreement on small synthetic models and one public radiograph per checkpoint. Clinical accuracy has not been evaluated."
    ],
    "measurements": [],
    "noWeights": false,
    "weights": [
      {
        "name": "mlx-community/medgemma-1.5-4b-it-4bit",
        "url": "https://huggingface.co/mlx-community/medgemma-1.5-4b-it-4bit"
      },
      {
        "name": "mlx-community/medgemma-4b-it-4bit",
        "url": "https://huggingface.co/mlx-community/medgemma-4b-it-4bit"
      },
      {
        "name": "mlx-community/medgemma-27b-it-4bit",
        "url": "https://huggingface.co/mlx-community/medgemma-27b-it-4bit"
      }
    ],
    "terms": "MIT, with Apache-2.0 adaptations. See [LICENSE](https://github.com/MedMLX/med-vlm-mlx/blob/v0.3.2/LICENSE) and [third-party notices](https://github.com/MedMLX/med-vlm-mlx/blob/v0.3.2/THIRD_PARTY_NOTICES.md). MedGemma weights are subject to the [Health AI Developer Foundations terms](https://developers.google.com/health-ai-developer-foundations/terms)."
  },
  "radimagenet-mlx": {
    "version": "0.3.3",
    "rows": [
      [
        "Input",
        "One Pillow-readable 2D image; a multi-frame file uses its first frame"
      ],
      [
        "Output",
        "Pooled and spatial features"
      ],
      [
        "Encoders",
        "ResNet50, DenseNet121, InceptionV3 and InceptionResNetV2"
      ],
      [
        "Features",
        "Pooled widths are 2048 for ResNet50 and InceptionV3, 1024 for DenseNet121 and 1536 for InceptionResNetV2."
      ]
    ],
    "limitations": [
      "The published bundle contains four encoders without classification heads. Classifier predictions require a checkpoint that includes a classifier.",
      "Images are prepared as in the upstream RadImageNet example: RGB, nearest-neighbour resize to the checkpoint's input size, Caffe-style BGR mean subtraction, then scaling by 1/255."
    ],
    "measurements": [],
    "noWeights": false,
    "weights": [
      {
        "name": "MedMLX/radimagenet-mlx",
        "url": "https://huggingface.co/MedMLX/radimagenet-mlx"
      }
    ],
    "terms": "[Apache-2.0](https://github.com/MedMLX/radimagenet-mlx/blob/v0.3.3/LICENSE). See [third-party notices](https://github.com/MedMLX/radimagenet-mlx/blob/v0.3.3/THIRD_PARTY_NOTICES.md). Model weights retain their publisher terms."
  },
  "mlxradiomics": {
    "version": "0.1.0.dev9",
    "rows": [
      [
        "Input",
        "One 2D or 3D image: `.nii`, `.nii.gz`, `.nrrd` or `.nhdr`"
      ],
      [
        "Mask",
        "Integer label mask with the image's shape, spacing, origin and direction; nothing is resampled"
      ],
      [
        "Output",
        "ROI features or voxel maps"
      ],
      [
        "Features",
        "All 116 non-deprecated PyRadiomics feature names are implemented. The default selection is the 93 intensity and texture features; request shape features by name."
      ],
      [
        "Weights",
        "No model weights are required."
      ]
    ],
    "limitations": [
      "Runner parameter files admit original-image extraction only; derived images and resampling need the Python API.",
      "Undefined features are NaN, and float32 overflow can give infinity.",
      "Features are compared with pinned PyRadiomics on synthetic cases. No IBSI conformance or clinical validation is claimed."
    ],
    "measurements": [],
    "noWeights": true,
    "weights": [],
    "terms": "[Apache-2.0](https://github.com/MedMLX/mlx-radiomics/blob/v0.1.0.dev9/LICENSE). See [third-party notices](https://github.com/MedMLX/mlx-radiomics/blob/v0.1.0.dev9/THIRD_PARTY_NOTICES.md)."
  }
};
