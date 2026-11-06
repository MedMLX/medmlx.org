// Plain-language model cards, with release README excerpts supporting each fact.
// The checker validates sources and release versions; summaries need editorial review.
// Keep implementation details in the linked repository. Reason-CT lives in models.js.
export const modelCards = {
  "fdg-pet-ct-mlx": {
    "version": "0.2.6",
    "rows": [
      [
        "Input",
        {
          "text": "A CT scan, matching organ labels, and tissue and scanner settings.",
          "sources": [
            "Aligned CT + organ labels + profiles"
          ]
        }
      ],
      [
        "Output",
        {
          "text": "A simulated PET scan with FDG uptake values.",
          "sources": [
            "Synthetic PET SUV volume"
          ]
        }
      ],
      [
        "Model download",
        {
          "text": "No model files need to be downloaded.",
          "sources": [
            "No model weights are needed."
          ]
        }
      ]
    ],
    "limitations": [
      {
        "text": "The CT scan and organ labels must already line up.",
        "sources": [
          "Aligned CT + organ labels + profiles",
          "Volumes are never registered or resampled."
        ]
      },
      {
        "text": "You supply the tissue uptake values and scanner settings; none are included.",
        "sources": [
          "The package ships no tissue statistics or scanner presets."
        ]
      },
      {
        "text": "Creates simulated PET images. Scanner acquisition and reconstruction are not modeled.",
        "sources": [
          "This is image-space synthesis; it does not simulate projection physics or reconstruction."
        ]
      }
    ],
    "measurements": [],
    "noWeights": true,
    "weights": [],
    "terms": {
      "text": "Software: [Apache-2.0](https://github.com/MedMLX/fdg-pet-ct-mlx/blob/v0.2.6/LICENSE).",
      "sources": [
        "[Apache-2.0](https://github.com/MedMLX/fdg-pet-ct-mlx/blob/v0.2.6/LICENSE). See [third-party notices](https://github.com/MedMLX/fdg-pet-ct-mlx/blob/v0.2.6/THIRD_PARTY_NOTICES.md)."
      ]
    }
  },
  "nnunet-mlx": {
    "version": "0.6.4",
    "rows": [
      [
        "Input",
        {
          "text": "One or more scans saved as NIfTI files, depending on the model.",
          "sources": [
            "NIfTI channels",
            "Supply input channels in the model’s expected order."
          ]
        }
      ],
      [
        "Output",
        {
          "text": "A segmentation map, with optional maps showing the probability of each label.",
          "sources": [
            "Segmentation and optional probabilities"
          ]
        }
      ]
    ],
    "limitations": [
      {
        "text": "Models that use several scans need them aligned and supplied in the required order.",
        "sources": [
          "| `nnunet-autopet` | `nnunet_mlx.medmlx.autopet(image_paths=[ct, pet])` | Co-registered CT and SUV PET, in that order |",
          "| `nnunet-brats2021` | `nnunet_mlx.named_models.brats(t1_path=..., t1ce_path=..., t2_path=..., flair_path=...)` | Four co-registered MRI |",
          "Supply input channels in the model’s expected order."
        ]
      },
      {
        "text": "Support for a model does not establish its segmentation accuracy.",
        "sources": [
          "Profiles cover inference only, not training or segmentation quality."
        ]
      }
    ],
    "measurements": [],
    "noWeights": false,
    "weights": [
      {
        "name": "Liver CT",
        "url": "https://huggingface.co/MedMLX/nnunet-liver-mlx"
      },
      {
        "name": "PET/CT lesions",
        "url": "https://huggingface.co/MedMLX/nnunet-autopet-mlx"
      },
      {
        "name": "Pancreas CT",
        "url": "https://huggingface.co/MedMLX/nnunet-pancreas-mlx"
      },
      {
        "name": "Brain tumor MRI",
        "url": "https://huggingface.co/MedMLX/nnunet-brats-mlx"
      }
    ],
    "terms": {
      "text": "Software: [Apache-2.0](https://github.com/MedMLX/nnunet-mlx/blob/v0.6.4/LICENSE). Model files have their own license terms.",
      "sources": [
        "[Apache-2.0](https://github.com/MedMLX/nnunet-mlx/blob/v0.6.4/LICENSE). See [third-party notices](https://github.com/MedMLX/nnunet-mlx/blob/v0.6.4/THIRD_PARTY_NOTICES.md). Model weights retain their publisher terms."
      ]
    }
  },
  "mlx-segment-ct": {
    "version": "0.3.5",
    "rows": [
      [
        "Input",
        {
          "text": "A CT scan in NIfTI format. The separate CT/MRI version also accepts MRI.",
          "sources": [
            "One CT in NIfTI (`.nii` or `.nii.gz`); CT or MRI with NV-Segment-CTMR"
          ]
        }
      ],
      [
        "Output",
        {
          "text": "A map of anatomical structures aligned with the original scan.",
          "sources": [
            "Anatomical labels on the input grid"
          ]
        }
      ]
    ],
    "limitations": [
      {
        "text": "The CT/MRI version cannot be guided by clicking points. Its model files are for noncommercial use.",
        "sources": [
          "The published [NV-Segment-CTMR weights](https://huggingface.co/MedMLX/vista3d-ctmr-mlx) cover CT and MRI under noncommercial terms. NVIDIA does not support interactive point segmentation with that checkpoint."
        ]
      }
    ],
    "measurements": [],
    "noWeights": false,
    "weights": [
      {
        "name": "CT model",
        "url": "https://huggingface.co/MedMLX/vista3d-ct-mlx"
      },
      {
        "name": "CT/MRI model",
        "url": "https://huggingface.co/MedMLX/vista3d-ctmr-mlx"
      }
    ],
    "terms": {
      "text": "Software: [Apache-2.0](https://github.com/MedMLX/mlx-segment-ct/blob/v0.3.5/LICENSE). Model files have their own license terms.",
      "sources": [
        "[Apache-2.0](https://github.com/MedMLX/mlx-segment-ct/blob/v0.3.5/LICENSE). See [third-party notices](https://github.com/MedMLX/mlx-segment-ct/blob/v0.3.5/THIRD_PARTY_NOTICES.md). Model weights retain their publisher terms."
      ]
    }
  },
  "segresnet-mlx": {
    "version": "0.3.3",
    "rows": [
      [
        "Brain tumor model",
        {
          "text": "Four MRI sequences: contrast-enhanced T1, T1, T2 and FLAIR, saved as NIfTI files.",
          "sources": [
            "`brats`: contrast T1, T1, T2 and FLAIR MRI in NIfTI"
          ]
        }
      ],
      [
        "Kidney model",
        {
          "text": "Arterial, venous and excretory CT scans saved as NIfTI files.",
          "sources": [
            "`renal_cect`: arterial, venous and excretory CT in NIfTI"
          ]
        }
      ],
      [
        "Output",
        {
          "text": "A segmentation map aligned with the original scan.",
          "sources": [
            "Segmentation on the input grid"
          ]
        }
      ]
    ],
    "limitations": [
      {
        "text": "Scans used together must already be aligned.",
        "sources": [
          "Inputs are finite 3D volumes on one voxel grid, with spatial units in millimetres or unspecified."
        ]
      },
      {
        "text": "Whole-body CT models are also available; see the repository for setup.",
        "sources": [
          "The standalone `run(bundle=..., weights_path=...)` interface remains available for explicit local checkpoints, including the whole-body CT variants."
        ]
      }
    ],
    "measurements": [],
    "noWeights": false,
    "weights": [
      {
        "name": "Brain tumor MRI",
        "url": "https://huggingface.co/MedMLX/segresnet-brats-mlx"
      },
      {
        "name": "Contrast-enhanced kidney CT",
        "url": "https://huggingface.co/MedMLX/segresnet-renal-cect-mlx"
      },
      {
        "name": "Whole-body CT",
        "url": "https://huggingface.co/MedMLX/segresnet-wholebody-mlx"
      }
    ],
    "terms": {
      "text": "Software: [Apache-2.0](https://github.com/MedMLX/segresnet-mlx/blob/v0.3.3/LICENSE). Model files have their own license terms.",
      "sources": [
        "[Apache-2.0](https://github.com/MedMLX/segresnet-mlx/blob/v0.3.3/LICENSE). See [third-party notices](https://github.com/MedMLX/segresnet-mlx/blob/v0.3.3/THIRD_PARTY_NOTICES.md). Model weights retain their publisher terms."
      ]
    }
  },
  "unest-mlx": {
    "version": "0.2.7",
    "rows": [
      [
        "Input",
        {
          "text": "A contrast-enhanced CT scan saved as a NIfTI file.",
          "sources": [
            "Contrast-enhanced CT · NIfTI"
          ]
        }
      ],
      [
        "Output",
        {
          "text": "A map of the kidney cortex, medulla and collecting system, aligned with the original scan.",
          "sources": [
            "The mask holds float32 labels 0 background, 1 kidney cortex, 2 medulla and 3 pelvicalyceal system, on the input grid as the NIfTI reader corrects it."
          ]
        }
      ]
    ],
    "limitations": [
      {
        "text": "Use arterial or portal-venous contrast-enhanced CT. Kidneys were missed in the non-contrast scans tested.",
        "sources": [
          "Use arterial or portal-venous contrast-enhanced CT. On the non-contrast scans we tried, the kidneys were missed."
        ]
      }
    ],
    "measurements": [],
    "noWeights": false,
    "weights": [
      {
        "name": "Kidney model",
        "url": "https://huggingface.co/MedMLX/unest-renal-ct-mlx"
      }
    ],
    "terms": {
      "text": "Software: [Apache-2.0](https://github.com/MedMLX/unest-mlx/blob/v0.2.7/LICENSE). Model files have their own license terms.",
      "sources": [
        "[Apache-2.0](https://github.com/MedMLX/unest-mlx/blob/v0.2.7/LICENSE). See [third-party notices](https://github.com/MedMLX/unest-mlx/blob/v0.2.7/THIRD_PARTY_NOTICES.md). Model weights retain their publisher terms."
      ]
    }
  },
  "swin-unetr-mlx": {
    "version": "0.2.6",
    "rows": [
      [
        "Input",
        {
          "text": "A 3D abdominal CT scan saved as a NIfTI file.",
          "sources": [
            "One 3D abdominal CT in NIfTI, in Hounsfield units"
          ]
        }
      ],
      [
        "Output",
        {
          "text": "A map of abdominal organs aligned with the original scan.",
          "sources": [
            "Organ mask on the input grid"
          ]
        }
      ]
    ],
    "limitations": [],
    "measurements": [],
    "noWeights": false,
    "weights": [
      {
        "name": "Abdominal organ model",
        "url": "https://huggingface.co/MedMLX/swin-unetr-mlx"
      }
    ],
    "terms": {
      "text": "Software: [Apache-2.0](https://github.com/MedMLX/swin-unetr-mlx/blob/v0.2.6/LICENSE). Model files have their own license terms.",
      "sources": [
        "[Apache-2.0](https://github.com/MedMLX/swin-unetr-mlx/blob/v0.2.6/LICENSE). See [third-party notices](https://github.com/MedMLX/swin-unetr-mlx/blob/v0.2.6/THIRD_PARTY_NOTICES.md). Model weights retain their publisher terms."
      ]
    }
  },
  "medsam2-mlx": {
    "version": "0.2.8",
    "rows": [
      [
        "Input",
        {
          "text": "A CT volume or slice, a prepared scan stack, or a sequence of JPEG images.",
          "sources": [
            "NIfTI CT volume or slice, `.npz` RECIST stack, or folder of `.jpg`/`.jpeg` frames"
          ]
        }
      ],
      [
        "Your guidance",
        {
          "text": "Draw a box, mark points, or provide an existing mask to identify the region.",
          "sources": [
            "The predictor follows upstream `SAM2VideoPredictorNPZ`: box, point and mask prompts, corrections on tracked frames, multiple objects, forward and reverse propagation, `clear_all_prompts_in_frame`, `remove_object` and `reset_state`."
          ]
        }
      ],
      [
        "Output",
        {
          "text": "Labeled regions in the scan, plus an image overlay for a single slice.",
          "sources": [
            "The output is `medsam2_mask.nii.gz` (uint16 labels with the input's shape, affine and header), plus `medsam2_overlay.png` for single-slice inputs."
          ]
        }
      ]
    ],
    "limitations": [
      {
        "text": "To track several objects through a scan, place their starting marks on the same slice.",
        "sources": [
          "With propagation, every prompt must be on the same frame."
        ]
      },
      {
        "text": "Where marked objects overlap, the later object takes priority.",
        "sources": [
          "Where objects overlap, the later object wins."
        ]
      },
      {
        "text": "Image sequences are read in grayscale.",
        "sources": [
          "A frame folder follows the upstream demo's video path; frames are read as grayscale, so color frames differ from upstream."
        ]
      }
    ],
    "measurements": [],
    "noWeights": false,
    "weights": [
      {
        "name": "CT lesion model",
        "url": "https://huggingface.co/MedMLX/medsam2-ct-lesion-mlx"
      },
      {
        "name": "All MedSAM2 models",
        "url": "https://huggingface.co/MedMLX/medsam2-mlx"
      }
    ],
    "terms": {
      "text": "Software: [Apache-2.0](https://github.com/MedMLX/medsam2-mlx/blob/v0.2.8/LICENSE). Model files have their own license terms.",
      "sources": [
        "[Apache-2.0](https://github.com/MedMLX/medsam2-mlx/blob/v0.2.8/LICENSE). See [third-party notices](https://github.com/MedMLX/medsam2-mlx/blob/v0.2.8/THIRD_PARTY_NOTICES.md). Model weights retain their publisher terms; see the [model card](https://huggingface.co/MedMLX/medsam2-mlx)."
      ]
    }
  },
  "biomedparse-mlx": {
    "version": "0.1.5",
    "rows": [
      [
        "Input",
        {
          "text": "A 3D scan or a 2D medical image.",
          "sources": [
            "A volume (`.npy`, upstream `.npz` with `imgs`, `.nii` or `.nii.gz`) or a 2D image (PNG, JPEG, BMP, TIFF or DICOM)"
          ]
        }
      ],
      [
        "Your guidance",
        {
          "text": "Name the structures you want to find in a text prompt.",
          "sources": [
            "One text prompt or a list of them"
          ]
        }
      ],
      [
        "Output",
        {
          "text": "A segmentation map marking the requested structures.",
          "sources": [
            "A volume writes `segmentation.npz` (`segs`: uint16 labels on the input grid; `existence`: prompt-by-slice probabilities) and `run.json` with the source revision, prompts and settings; NIfTI input also gets `segmentation.nii.gz` on the source affine."
          ]
        }
      ]
    ],
    "limitations": [
      {
        "text": "The model was trained for 3D scans. It accepts 2D images, but its accuracy on them has not been established.",
        "sources": [
          "The released checkpoint is trained for 3D modalities, so 2D accuracy is not established."
        ]
      }
    ],
    "measurements": [],
    "noWeights": false,
    "weights": [
      {
        "name": "BioMedParse v2",
        "url": "https://huggingface.co/MedMLX/biomedparse-v2-mlx"
      }
    ],
    "terms": {
      "text": "Software: [Apache-2.0](https://github.com/MedMLX/biomedparse-mlx/blob/v0.1.5/LICENSE). Model files have their own license terms. BioMedParse models are for noncommercial use under CC-BY-NC-SA-4.0.",
      "sources": [
        "[Apache-2.0](https://github.com/MedMLX/biomedparse-mlx/blob/v0.1.5/LICENSE). See [third-party notices](https://github.com/MedMLX/biomedparse-mlx/blob/v0.1.5/THIRD_PARTY_NOTICES.md). Model weights retain their publisher terms. BioMedParse weights are CC-BY-NC-SA-4.0."
      ]
    }
  },
  "totalsegmentator-mlx": {
    "version": "0.1.6",
    "rows": [
      [
        "Input",
        {
          "text": "A 3D CT scan saved as a NIfTI file.",
          "sources": [
            "One finite 3D CT in NIfTI-1 or NIfTI-2, in Hounsfield units"
          ]
        }
      ],
      [
        "Output",
        {
          "text": "One file marking 117 organs and other body structures, aligned with the original scan.",
          "sources": [
            "Multilabel mask on the input grid",
            "Only the upstream `total` CT task is included: Dataset291–295, 297 and 298 with 117 labels, plus the Dataset300 body model for cropping, all `3d_fullres`, fold 0, without mirroring."
          ]
        }
      ],
      [
        "Options",
        {
          "text": "Standard at 1.5 mm, fast at 3 mm, or coarse at 6 mm resolution.",
          "sources": [
            "`standard` (default, five 1.5 mm parts), `fast` (3 mm model, upstream `--fast`) or `coarse` (6 mm model, upstream `--fastest`)"
          ]
        }
      ]
    ],
    "limitations": [
      {
        "text": "This version supports CT scans. MRI segmentation is not included.",
        "sources": [
          "Only the upstream `total` CT task is included: Dataset291–295, 297 and 298 with 117 labels, plus the Dataset300 body model for cropping, all `3d_fullres`, fold 0, without mirroring.",
          "DICOM input, DICOM-SEG and RT-STRUCT output, other upstream tasks (including `total_mr` and licensed tasks), per-class output files, statistics, radiomics, previews, `--remove_small_blobs`, `--higher_order_resampling`, `--v1_order`, test-time augmentation and training are rejected or absent."
        ]
      },
      {
        "text": "Use NIfTI files. DICOM input and DICOM segmentation export are not supported.",
        "sources": [
          "One finite 3D CT in NIfTI-1 or NIfTI-2, in Hounsfield units",
          "DICOM input, DICOM-SEG and RT-STRUCT output, other upstream tasks (including `total_mr` and licensed tasks), per-class output files, statistics, radiomics, previews, `--remove_small_blobs`, `--higher_order_resampling`, `--v1_order`, test-time augmentation and training are rejected or absent."
        ]
      },
      {
        "text": "Organ statistics and radiomics measurements are not included.",
        "sources": [
          "DICOM input, DICOM-SEG and RT-STRUCT output, other upstream tasks (including `total_mr` and licensed tasks), per-class output files, statistics, radiomics, previews, `--remove_small_blobs`, `--higher_order_resampling`, `--v1_order`, test-time augmentation and training are rejected or absent."
        ]
      }
    ],
    "measurements": [],
    "noWeights": false,
    "weights": [
      {
        "name": "TotalSegmentator models",
        "url": "https://huggingface.co/MedMLX/totalsegmentator-mlx"
      }
    ],
    "terms": {
      "text": "Software: [Apache-2.0](https://github.com/MedMLX/totalsegmentator-mlx/blob/v0.1.6/LICENSE). Model files have their own license terms.",
      "sources": [
        "[Apache-2.0](https://github.com/MedMLX/totalsegmentator-mlx/blob/v0.1.6/LICENSE). See [third-party notices](https://github.com/MedMLX/totalsegmentator-mlx/blob/v0.1.6/THIRD_PARTY_NOTICES.md). Model weights retain their publisher terms."
      ]
    }
  },
  "synthseg-mlx": {
    "version": "0.3.4",
    "rows": [
      [
        "Input",
        {
          "text": "A 3D brain MRI or CT scan saved as a NIfTI file.",
          "sources": [
            "One 3D brain MRI in NIfTI (`.nii` or `.nii.gz`) of any contrast and resolution, or a CT in Hounsfield units with `ct=True`"
          ]
        }
      ],
      [
        "Output",
        {
          "text": "Labeled brain regions, volume measurements and quality checks.",
          "sources": [
            "Brain labels, volumes and QC"
          ]
        }
      ]
    ],
    "limitations": [],
    "measurements": [],
    "noWeights": false,
    "weights": [
      {
        "name": "SynthSeg models",
        "url": "https://huggingface.co/MedMLX/synthseg-mlx"
      }
    ],
    "terms": {
      "text": "Software: [Apache-2.0](https://github.com/MedMLX/synthseg-mlx/blob/v0.3.4/LICENSE). Model files have their own license terms.",
      "sources": [
        "[Apache-2.0](https://github.com/MedMLX/synthseg-mlx/blob/v0.3.4/LICENSE). See [third-party notices](https://github.com/MedMLX/synthseg-mlx/blob/v0.3.4/THIRD_PARTY_NOTICES.md). Model weights retain their publisher terms."
      ]
    }
  },
  "flexray-mlx": {
    "version": "0.2.6",
    "rows": [
      [
        "Input",
        {
          "text": "An X-ray image, such as a PNG, TIFF or single DICOM image.",
          "sources": [
            "One radiograph: an image Pillow reads (PNG, TIFF, ...) or a single-frame 2D DICOM"
          ]
        }
      ],
      [
        "Output",
        {
          "text": "Masks marking anatomical structures, plus probability maps.",
          "sources": [
            "Structure masks and probabilities"
          ]
        }
      ]
    ],
    "limitations": [
      {
        "text": "The standard download contains one model. Combining all five versions requires a separate download; see the repository for setup.",
        "sources": [
          "The [published bundle](https://huggingface.co/MedMLX/flexray-mlx/tree/722d8341570e8b9e1196cf50e57892da84974fcc) holds only `flux0375`; its `ensemble.json` still lists all five members in order (`flux0375`, `flux000`, `flux025`, `flux050`, `flux075`).",
          "For `ensemble=True`, use the [upstream snapshot](https://huggingface.co/VictorButoi/flexray/tree/6b63ddf09cfdff99aea494e3738cf243a4e22cdb) with all five member folders."
        ]
      }
    ],
    "measurements": [],
    "noWeights": false,
    "weights": [
      {
        "name": "FleXray model",
        "url": "https://huggingface.co/MedMLX/flexray-mlx"
      }
    ],
    "terms": {
      "text": "Software: [Apache-2.0](https://github.com/MedMLX/flexray-mlx/blob/v0.2.6/LICENSE). Model files have their own license terms. FleXray models are for noncommercial use under CC-BY-NC-4.0.",
      "sources": [
        "[Apache-2.0](https://github.com/MedMLX/flexray-mlx/blob/v0.2.6/LICENSE). See [third-party notices](https://github.com/MedMLX/flexray-mlx/blob/v0.2.6/THIRD_PARTY_NOTICES.md). Model weights retain their publisher terms. FleXray weights are noncommercial (CC-BY-NC-4.0)."
      ]
    }
  },
  "flexible-unet-mlx": {
    "version": "0.2.6",
    "rows": [
      [
        "Input",
        {
          "text": "A color image, such as a JPEG.",
          "sources": [
            "One RGB image Pillow can read; the bundle used JPEG"
          ]
        }
      ],
      [
        "Output",
        {
          "text": "A black-and-white image marking tools in white, at the original image size.",
          "sources": [
            "Following the bundle's `SaveImaged` layout, `frame.jpg` produces `out/frame/frame_trans.png`: an 8-bit grayscale mask at the original frame size, 255 for tools and 0 for background."
          ]
        }
      ]
    ],
    "limitations": [
      {
        "text": "Works with 2D images. NIfTI scans are not supported.",
        "sources": [
          "This 2D model reads images, not NIfTI volumes."
        ]
      }
    ],
    "measurements": [],
    "noWeights": false,
    "weights": [
      {
        "name": "Instrument segmentation model",
        "url": "https://huggingface.co/MedMLX/flexible-unet-effnetb2-mlx"
      }
    ],
    "terms": {
      "text": "Software: [Apache-2.0](https://github.com/MedMLX/flexible-unet-mlx/blob/v0.2.6/LICENSE). Model files have their own license terms.",
      "sources": [
        "[Apache-2.0](https://github.com/MedMLX/flexible-unet-mlx/blob/v0.2.6/LICENSE). See [third-party notices](https://github.com/MedMLX/flexible-unet-mlx/blob/v0.2.6/THIRD_PARTY_NOTICES.md). Model weights retain their publisher terms."
      ]
    }
  },
  "lung-nodule-mlx": {
    "version": "0.2.6",
    "rows": [
      [
        "Input",
        {
          "text": "A 3D chest CT scan saved as a NIfTI file.",
          "sources": [
            "One scalar 3D chest CT in NIfTI, in Hounsfield units, with `mm`, `meter` or `micron` spatial units"
          ]
        }
      ],
      [
        "Output",
        {
          "text": "Boxes around possible lung nodules, with a score for each.",
          "sources": [
            "`detections.json` holds `medmlx.detections.v1` candidate boxes (`cccwhd`, class 0 `nodule`) in RAS millimetres with their scores; `bundle_detections.json` holds the MONAI bundle rows in patient LPS."
          ]
        }
      ]
    ],
    "limitations": [
      {
        "text": "Ordinary CT scans need their image spacing adjusted for this model. Follow the preparation instructions in the repository.",
        "sources": [
          "Keep `resample_raw_input=True` for ordinary CT. The default follows the bundle's pre-resampled mode: it reorients to RAS and scales intensities, but does not check or correct voxel spacing."
        ]
      },
      {
        "text": "DICOM scans must be converted to NIfTI before use.",
        "sources": [
          "One scalar 3D chest CT in NIfTI, in Hounsfield units, with `mm`, `meter` or `micron` spatial units",
          "DICOM series are not read."
        ]
      }
    ],
    "measurements": [],
    "noWeights": false,
    "weights": [
      {
        "name": "Lung nodule model",
        "url": "https://huggingface.co/MedMLX/retinanet-lung-nodule-mlx"
      }
    ],
    "terms": {
      "text": "Software: [Apache-2.0](https://github.com/MedMLX/lung-nodule-mlx/blob/v0.2.6/LICENSE). Model files have their own license terms.",
      "sources": [
        "[Apache-2.0](https://github.com/MedMLX/lung-nodule-mlx/blob/v0.2.6/LICENSE). See [third-party notices](https://github.com/MedMLX/lung-nodule-mlx/blob/v0.2.6/THIRD_PARTY_NOTICES.md). Model weights retain their publisher terms."
      ]
    }
  },
  "mlx-generate-ctmr": {
    "version": "0.5.2.post2",
    "rows": [
      [
        "Input",
        {
          "text": "Start from random noise, or use an anatomy map to guide CT generation.",
          "sources": [
            "Noise, or a CT anatomy mask"
          ]
        }
      ],
      [
        "Output",
        {
          "text": "Synthetic 3D CT or MRI scans.",
          "sources": [
            "Synthetic 3D CT or MRI"
          ]
        }
      ],
      [
        "Options",
        {
          "text": "CT, general MRI or brain MRI.",
          "sources": [
            "`configuration=\"ct\"`, `\"mr\"` or `\"mr-brain\"`"
          ]
        }
      ]
    ],
    "limitations": [
      {
        "text": "Generated scans are synthetic data. Software comparison tests do not establish their image quality.",
        "sources": [
          "Numerical parity is checked against MONAI on small seeded networks. That does not qualify pretrained image quality. Synthetic output is not ground truth."
        ]
      }
    ],
    "measurements": [
      {
        "text": "Published test peaks: **27.9 GiB** for CT (256×256×256) and **23.8 GiB** for brain MRI (256×256×128). General MRI has no published figure.",
        "sources": [
          "Peak MLX memory: **27.9 GiB** for `mlx-generate-ctmr-ct` (256³, from-mask, ControlNet + four-window decode); **23.8 GiB** for `mlx-generate-ctmr-mr-brain` (256×256×128, guided batch 2). No recorded peak for `mlx-generate-ctmr-mr`."
        ]
      },
      {
        "text": "These version 0.5.1 tests used untrained models. They excluded model loading, input preparation and other apps, so the figures do not establish a minimum RAM requirement.",
        "sources": [
          "The v0.5.1 memory measurements used MLX 0.32.4 and `MLX_ENABLE_TF32=0`: default `fast` arithmetic with FP32 accumulation and split-FP16 convolution operands, production constructors with random fan-in-scaled weights, seed 0 and 30 steps. Peaks include VAE decoding and exclude weight loading.",
          "These figures cover the stated pipelines and grids; they are MLX allocations, excluding host preprocessing and other applications."
        ]
      }
    ],
    "noWeights": false,
    "weights": [
      {
        "name": "CT and MRI models",
        "url": "https://huggingface.co/MedMLX/mlx-generate-ctmr"
      }
    ],
    "terms": {
      "text": "Software: [Apache-2.0](https://github.com/MedMLX/mlx-generate-ctmr/blob/v0.5.2.post2/LICENSE). Model files have their own license terms. General MRI models have noncommercial terms. The CT license terms need clarification from the publisher.",
      "sources": [
        "[Apache-2.0](https://github.com/MedMLX/mlx-generate-ctmr/blob/v0.5.2.post2/LICENSE). See [third-party notices](https://github.com/MedMLX/mlx-generate-ctmr/blob/v0.5.2.post2/THIRD_PARTY_NOTICES.md). Model weights retain their publisher terms. General-MR weights have noncommercial terms; CT component terms require publisher clarification."
      ]
    }
  },
  "lesiondiffusion-mlx": {
    "version": "0.2.7",
    "rows": [
      [
        "Input",
        {
          "text": "A CT scan and a matching mask marking the organ.",
          "sources": [
            "CT + aligned binary organ mask"
          ]
        }
      ],
      [
        "Output",
        {
          "text": "A CT scan with a synthetic lesion, plus masks marking the lesion and organ.",
          "sources": [
            "The outputs are `synthetic_ct.nii.gz` (float32 HU), `lesion_mask.nii.gz` and `organ_mask.nii.gz` (uint8) on the standardized grid."
          ]
        }
      ]
    ],
    "limitations": [
      {
        "text": "The CT and organ mask must line up. Scans with tilted or skewed image grids are not supported.",
        "sources": [
          "The CT and masks must be finite, axis-aligned grids that match after they are reoriented and resampled to RAS 1 mm; oblique or sheared grids are refused."
        ]
      },
      {
        "text": "Parts of the CT outside the lesion can also change.",
        "sources": [
          "The decoder reconstructs the whole CT, so voxels outside the lesion can change."
        ]
      },
      {
        "text": "The generated lesion is synthetic and should not be treated as a known real finding.",
        "sources": [
          "Synthetic output is not ground truth."
        ]
      }
    ],
    "measurements": [
      {
        "text": "Tests peaked at **3.29 GB** with the default settings and **3.46 GB** in source mode, for a 160×160×128 crop at 1 mm resolution with 200 generation steps.",
        "sources": [
          "**3.46 GB** peak MLX memory for `lesiondiffusion` in source mode and **3.29 GB** in the default conditioned mode on a 160×160×128, 1 mm RAS crop.",
          "Both measurements used an AMOS case 0008 crop and 200 diffusion steps: FP32 LMNet and text encoders, FP16 LINet and VQ."
        ]
      },
      {
        "text": "Memory use for larger scans has not been measured. Allow extra memory for input preparation and other apps.",
        "sources": [
          "They do not measure larger volumes. Peak MLX memory excludes host preprocessing and other applications."
        ]
      }
    ],
    "noWeights": false,
    "weights": [
      {
        "name": "LesionDiffusion model",
        "url": "https://huggingface.co/MedMLX/lesiondiffusion-mlx"
      }
    ],
    "terms": {
      "text": "Software: [Apache-2.0](https://github.com/MedMLX/lesiondiffusion-mlx/blob/v0.2.7/LICENSE). Model files have their own license terms.",
      "sources": [
        "[Apache-2.0](https://github.com/MedMLX/lesiondiffusion-mlx/blob/v0.2.7/LICENSE). See [third-party notices](https://github.com/MedMLX/lesiondiffusion-mlx/blob/v0.2.7/THIRD_PARTY_NOTICES.md). Model weights retain their publisher terms."
      ]
    }
  },
  "med-vlm-mlx": {
    "version": "0.3.3",
    "rows": [
      [
        "Input",
        {
          "text": "An image and a written question or instruction.",
          "sources": [
            "Image + text prompt"
          ]
        }
      ],
      [
        "Output",
        {
          "text": "A written response.",
          "sources": [
            "Generated text"
          ]
        }
      ]
    ],
    "limitations": [
      {
        "text": "Accepts text and images. Audio and video are not supported.",
        "sources": [
          "Text and images only. Requests with audio, video, tool definitions or tool-call turns are rejected."
        ]
      },
      {
        "text": "Clinical accuracy has not been evaluated.",
        "sources": [
          "The checks cover numerical agreement on small synthetic models and one public radiograph per checkpoint. Clinical accuracy has not been evaluated."
        ]
      }
    ],
    "measurements": [],
    "noWeights": false,
    "weights": [
      {
        "name": "MedGemma 1.5 4B",
        "url": "https://huggingface.co/mlx-community/medgemma-1.5-4b-it-4bit"
      },
      {
        "name": "MedGemma 4B",
        "url": "https://huggingface.co/mlx-community/medgemma-4b-it-4bit"
      },
      {
        "name": "MedGemma 27B",
        "url": "https://huggingface.co/mlx-community/medgemma-27b-it-4bit"
      }
    ],
    "terms": {
      "text": "Software: MIT, with Apache-2.0 adaptations. Model use is covered by the [Health AI Developer Foundations terms](https://developers.google.com/health-ai-developer-foundations/terms).",
      "sources": [
        "MIT, with Apache-2.0 adaptations. See [LICENSE](https://github.com/MedMLX/med-vlm-mlx/blob/v0.3.3/LICENSE) and [third-party notices](https://github.com/MedMLX/med-vlm-mlx/blob/v0.3.3/THIRD_PARTY_NOTICES.md). MedGemma weights are subject to the [Health AI Developer Foundations terms](https://developers.google.com/health-ai-developer-foundations/terms)."
      ]
    }
  },
  "radimagenet-mlx": {
    "version": "0.3.3",
    "rows": [
      [
        "Input",
        {
          "text": "A 2D image.",
          "sources": [
            "One Pillow-readable 2D image; a multi-frame file uses its first frame"
          ]
        }
      ],
      [
        "Output",
        {
          "text": "Numerical descriptions of the image and its regions for further analysis.",
          "sources": [
            "Pooled and spatial features"
          ]
        }
      ],
      [
        "Models",
        {
          "text": "ResNet50, DenseNet121, InceptionV3 and InceptionResNetV2.",
          "sources": [
            "ResNet50, DenseNet121, InceptionV3 and InceptionResNetV2"
          ]
        }
      ]
    ],
    "limitations": [
      {
        "text": "The supplied models extract image features; they do not assign diagnostic labels.",
        "sources": [
          "The published bundle contains four encoders without classification heads. Classifier predictions require a checkpoint that includes a classifier."
        ]
      },
      {
        "text": "For files containing several frames, only the first frame is used.",
        "sources": [
          "One Pillow-readable 2D image; a multi-frame file uses its first frame"
        ]
      }
    ],
    "measurements": [],
    "noWeights": false,
    "weights": [
      {
        "name": "RadImageNet models",
        "url": "https://huggingface.co/MedMLX/radimagenet-mlx"
      }
    ],
    "terms": {
      "text": "Software: [Apache-2.0](https://github.com/MedMLX/radimagenet-mlx/blob/v0.3.3/LICENSE). Model files have their own license terms.",
      "sources": [
        "[Apache-2.0](https://github.com/MedMLX/radimagenet-mlx/blob/v0.3.3/LICENSE). See [third-party notices](https://github.com/MedMLX/radimagenet-mlx/blob/v0.3.3/THIRD_PARTY_NOTICES.md). Model weights retain their publisher terms."
      ]
    }
  },
  "mlxradiomics": {
    "version": "0.1.0.dev10",
    "rows": [
      [
        "Input",
        {
          "text": "A 2D or 3D image in NIfTI or NRRD format, with a label mask marking the region to measure.",
          "sources": [
            "One 2D or 3D image: `.nii`, `.nii.gz`, `.nrrd` or `.nhdr`",
            "Integer label mask."
          ]
        }
      ],
      [
        "Output",
        {
          "text": "Measurements of image intensity, texture and shape. Intensity and texture can also be shown as maps.",
          "sources": [
            "ROI features or voxel maps",
            "`FEATURES` lists 190 selectable outputs, including all 116 non-deprecated PyRadiomics names. The default remains the original 93 intensity and texture outputs; request additions and shape features explicitly.",
            "| Shape | 32 | 3D ROI |"
          ]
        }
      ],
      [
        "Model download",
        {
          "text": "No model files need to be downloaded.",
          "sources": [
            "No model weights are required."
          ]
        }
      ]
    ],
    "limitations": [
      {
        "text": "The image and mask must be aligned, unless the settings turn on resampling or mask correction.",
        "sources": [
          "A geometry mismatch is refused unless the params enable `correctMask` or `resampledPixelSpacing`"
        ]
      },
      {
        "text": "Some measurements can be undefined or outside the supported range. Check the results before analysis.",
        "sources": [
          "Undefined features are NaN, and float32 overflow can give infinity."
        ]
      },
      {
        "text": "The Simoncelli and Riesz filters are experimental and exposed to a known MLX bug until a fixed MLX release is published. Other features are unaffected.",
        "sources": [
          "Simoncelli and Riesz filters are experimental.",
          "MLX 0.32.4 has an out-of-bounds FFT write that can silently modify a neighbouring array",
          "All other features do not use the FFT."
        ]
      }
    ],
    "measurements": [],
    "noWeights": true,
    "weights": [],
    "terms": {
      "text": "Software: [Apache-2.0](https://github.com/MedMLX/mlx-radiomics/blob/v0.1.0.dev10/LICENSE).",
      "sources": [
        "[Apache-2.0](https://github.com/MedMLX/mlx-radiomics/blob/v0.1.0.dev10/LICENSE). See [third-party notices](THIRD_PARTY_NOTICES.md)"
      ]
    }
  }
};
