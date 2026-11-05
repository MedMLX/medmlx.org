# /// script
# requires-python = ">=3.13,<3.15"
# dependencies = [
#     "mlxradiomics==0.1.0.dev8",
#     "SimpleITK==2.5.6",
#     "nibabel>=5.3",
#     "numpy>=2",
#     "scipy>=1.16",
# ]
# ///
"""Compute native MLX Radiomics entropy maps for several organs on one CT plane.

Run from the repository root, then render with render_radiomics_organs.py:
    uv run docs/hero/compute_radiomics_organs.py

Source, derivation and settings are those of the liver-only asset recorded in
site/assets/hero/radiomics-run.json: the retained AMOS22 plane and SwinUNETR
prediction in figure1.npz (not included in this repository; set
MEDMLX_HERO_SOURCE to its path), written as one-slice NIfTI with
SimpleITK. Each organ's ROI is the largest 4-connected component of its
predicted BTCV label, selected before extraction. mlxradiomics.medmlx.run
computes every map. This script writes inputs and records each run; it never
edits, smooths or synthesizes feature values. The liver maps are compared by
value with the liver run's maps, which must remain at the local_artifact paths
radiomics-run.json records.
"""

import json
import os
import platform
import shutil
import time
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path

import nibabel as nib
import numpy as np
import SimpleITK as sitk
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
RUN_DIR = ROOT / 'dist/radiomics-organs-demo'
SOURCE = Path(os.environ['MEDMLX_HERO_SOURCE'])
LIVER_RUN = ROOT / 'site/assets/hero/radiomics-run.json'
VERSION = '0.1.0.dev8'
FEATURE = 'original_firstorder_Entropy'
# The liver run's parameter file, unchanged. Only the entropy map is displayed.
PARAMETERS = {
    'setting': {'binWidth': 10, 'kernelRadius': 5, 'maskedKernel': True,
                'force2D': True, 'force2Ddimension': 0},
    'featureClass': {'firstorder': ['Entropy'], 'glcm': ['Contrast', 'Idmn']},
}
# BTCV output labels from swin-unetr-mlx v0.2.5, src/swin_unetr_mlx/specification.json.
BTCV = ['background', 'spleen', 'right kidney', 'left kidney', 'gallbladder', 'esophagus',
        'liver', 'stomach', 'aorta', 'inferior vena cava', 'portal and splenic veins',
        'pancreas', 'right adrenal gland', 'left adrenal gland']
VESSELS = {8, 9, 10}
MIN_PIXELS = 1000
GAS_HU, MAX_GAS_FRACTION = -200, 0.25
SELECTION_RULE = (
    f'Parenchymal organs (vessels excluded) whose largest predicted 4-connected component '
    f'has at least {MIN_PIXELS} pixels on this plane and at most {MAX_GAS_FRACTION:.0%} of '
    f'its pixels below {GAS_HU} HU (gas lumen). Smaller ROIs leave most 11 x 11 kernels '
    f'partly empty; gas-filled ROIs map air-wall edges rather than tissue texture.'
)


def write_plane(array, path, spacing):
    """One axial plane, stored exactly as the liver run stored it."""
    image = sitk.GetImageFromArray(array[None])
    image.SetSpacing((spacing, spacing, 1.0))
    sitk.WriteImage(image, str(path), True)


def read_plane(path):
    """Read a written map with NiBabel, which keeps any stored non-finite values."""
    array = np.asarray(nib.load(path).dataobj)
    if array.ndim != 3 or array.shape[2] != 1:
        raise ValueError(f'Expected one axial plane: {path}')
    return array[:, :, 0].T


def largest_component(mask):
    components, count = ndimage.label(mask)  # 2D default structure: 4-connectivity
    sizes = np.bincount(components.ravel())
    sizes[0] = 0
    return components == sizes.argmax(), count, sorted(sizes[1:].tolist(), reverse=True)


def main():
    if metadata.version('mlxradiomics') != VERSION:
        raise RuntimeError(f'Expected mlxradiomics {VERSION}')
    import mlx.core as mx
    from mlxradiomics.medmlx import run

    liver_run = json.loads(LIVER_RUN.read_text())
    recorded = liver_run['source']
    if recorded['parameters'] != PARAMETERS:
        raise ValueError('Parameters must equal the liver run parameters')
    archive = np.load(SOURCE)
    ct = archive[recorded['image_key']]
    labels = archive[recorded['labels_key']]
    spacing = recorded['spacing_mm_row_col'][0]
    if recorded['spacing_mm_row_col'][1] != spacing or list(ct.shape) != recorded['input_shape']:
        raise ValueError('Unexpected source geometry')

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(RUN_DIR / 'computed', ignore_errors=True)
    write_plane(ct, RUN_DIR / 'ct.nii.gz', spacing)
    (RUN_DIR / 'parameters.json').write_text(json.dumps(PARAMETERS, indent=2) + '\n')

    # Every label on the plane, so the organ choice can be checked from the record.
    slice_labels, chosen = {}, []
    for value in (int(v) for v in np.unique(labels) if v):
        main_mask, count, sizes = largest_component(labels == value)
        gas = float((ct[main_mask] < GAS_HU).mean())
        reasons = []
        if value in VESSELS:
            reasons.append('vessel')
        if main_mask.sum() < MIN_PIXELS:
            reasons.append(f'largest component below {MIN_PIXELS} pixels')
        if gas > MAX_GAS_FRACTION:
            reasons.append(f'{gas:.0%} of pixels below {GAS_HU} HU')
        slice_labels[str(value)] = {
            'name': BTCV[value], 'predicted_pixels': int((labels == value).sum()),
            'components': count, 'largest_component_pixels': int(main_mask.sum()),
            'largest_component_area_cm2': round(float(main_mask.sum()) * spacing**2 / 100, 2),
            'largest_component_fraction_below_-200_hu': round(gas, 3),
            'shown': not reasons, 'excluded_because': reasons,
        }
        if not reasons:
            chosen.append(value)

    started = datetime.now(UTC)
    organs = {}
    for value in chosen:
        slug = BTCV[value].replace(' ', '-')
        predicted = labels == value
        selected, count, sizes = largest_component(predicted)
        write_plane(predicted.astype(np.uint8), RUN_DIR / f'{slug}-roi.nii.gz', spacing)
        write_plane(selected.astype(np.uint8), RUN_DIR / f'{slug}-roi-main.nii.gz', spacing)
        output_dir = RUN_DIR / 'computed' / slug
        clock = time.perf_counter()
        result = run(image_path=RUN_DIR / 'ct.nii.gz', mask_path=RUN_DIR / f'{slug}-roi-main.nii.gz',
                     output_dir=output_dir, params=PARAMETERS, voxel=True)
        seconds = time.perf_counter() - clock
        execution = result['details']['execution']
        maps = {}
        for name, path in sorted(result['outputs']['maps'].items()):
            values = read_plane(path)
            inside = values[selected]
            maps[name] = {
                'finite_roi_voxels': int(np.isfinite(inside).sum()),
                'outside_roi_zero': bool(np.all(values[~selected] == 0)),
                'range': [float(np.nanmin(inside)), float(np.nanmax(inside))],
                'local_artifact': Path(path).relative_to(ROOT).as_posix(),
            }
        if maps[FEATURE]['finite_roi_voxels'] != selected.sum():
            raise ValueError(f'{slug}: entropy must be finite throughout the ROI')
        organs[slug] = {
            'label': value, 'name': BTCV[value],
            'roi_selection': {
                'rule': f'largest 4-connected component of the original predicted {BTCV[value]} '
                        'mask, computed before radiomics extraction',
                'original_roi_pixels': int(predicted.sum()),
                'selected_roi_pixels': int(selected.sum()),
                'excluded_roi_pixels': int(predicted.sum() - selected.sum()),
                'original_component_count': count,
                'component_pixels': sizes,
                'manual_mask_edits': False,
            },
            'execution': {key: execution[key] for key in
                          ('batch_size', 'gray_levels', 'scratch_estimate_bytes')},
            'wall_seconds': round(seconds, 3),
            'maps': maps,
        }
        organs[slug]['_shared_execution'] = execution
    finished = datetime.now(UTC)

    shared = [organ.pop('_shared_execution') for organ in organs.values()]
    common = {key: value for key, value in shared[0].items()
              if key not in ('batch_size', 'gray_levels', 'scratch_estimate_bytes')}
    if any({k: v for k, v in s.items() if k in common} != common for s in shared):
        raise ValueError('Every organ must use identical execution settings')

    liver = organs.get('liver')
    # Value comparison, NaN-aware, against the liver run's saved maps.
    reference = {
        'reference': 'radiomics-run.json maps, mlxradiomics '
                     f'{liver_run["runtime"]["version"]}, same CT, ROI and parameters',
        'maps': {name: {'identical': bool(np.array_equal(
                            read_plane(ROOT / liver['maps'][name]['local_artifact']),
                            read_plane(ROOT / entry['local_artifact']), equal_nan=True))}
                 for name, entry in liver_run['maps'].items()} if liver else {},
    }
    record = {
        'schema_version': 1,
        'method': 'Native MLX Radiomics voxel extraction with mlxradiomics.medmlx.run, '
                  'one run per selected BTCV organ label',
        'job': {'script': 'docs/hero/compute_radiomics_organs.py',
                'entry_point': 'mlxradiomics.medmlx.run(image_path, mask_path, output_dir, '
                               'params, voxel=True)',
                'started_at': started.isoformat(timespec='seconds'),
                'finished_at': finished.isoformat(timespec='seconds')},
        'runtime': {
            'package': 'mlxradiomics', 'version': metadata.version('mlxradiomics'),
            'medmlx_core_version': metadata.version('medmlx-core'),
            'mlx_version': metadata.version('mlx'),
            'simpleitk_version': metadata.version('simpleitk'),
            'nibabel_version': metadata.version('nibabel'),
            'numpy_version': metadata.version('numpy'),
            'python_version': platform.python_version(),
            'device': f'{mx.device_info()["device_name"]} GPU',
            'precision': common['precision'],
        },
        'source': {
            **{key: recorded[key] for key in (
                'source_file',
                'image_key', 'labels_key', 'source_case', 'axial_slice',
                'spacing_mm_row_col', 'input_shape')},
            'derivation': 'Same as radiomics-run.json: the retained raw HU axial slice and native '
                          'SwinUNETR prediction are written as one-slice NIfTI with SimpleITK in '
                          'local display coordinates. Display orientation and in-plane spacing are '
                          'preserved; the 1 mm through-plane spacing is a storage convention that '
                          'force2D excludes from neighborhoods. No resampling or input smoothing. '
                          'Each ROI is a 0/1 mask extracted as label 1.',
            'parameters': PARAMETERS,
        },
        'label_map': {
            'source': 'swin-unetr-mlx v0.2.5, src/swin_unetr_mlx/specification.json, '
                      'inference.labels (BTCV)',
            'names': dict(enumerate(BTCV)),
        },
        'organ_selection': {'rule': SELECTION_RULE, 'labels_on_plane': slice_labels},
        'execution': common,
        'organs': organs,
        'reference_check': reference,
    }
    (RUN_DIR / 'compute.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({slug: organ['roi_selection'] for slug, organ in organs.items()}, indent=2))
    print(json.dumps(reference, indent=2))


if __name__ == '__main__':
    main()
