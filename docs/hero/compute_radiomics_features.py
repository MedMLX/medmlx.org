# /// script
# requires-python = ">=3.13,<3.15"
# dependencies = [
#     "mlxradiomics==1.0.0",
#     "SimpleITK==2.5.6",
#     "nibabel>=5.3",
#     "numpy>=2",
#     "scipy>=1.16",
# ]
# ///
"""Compute one voxel map per radiomics feature family on the liver ROI of one CT plane.

Run from the repository root, then render with render_radiomics_features.py:
    MEDMLX_HERO_SOURCE=/path/to/figure1.npz uv run docs/hero/compute_radiomics_features.py

The CT plane, SwinUNETR prediction, ROI rule (largest 4-connected component of
the predicted liver) and storage convention are those recorded in
site/assets/hero/radiomics-run.json. mlxradiomics.medmlx.run computes every map
and, in a second ROI-mode run with the same parameters, the whole-ROI value of
each feature. This script writes inputs and records each run; it never edits,
smooths or synthesizes feature values.
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
RUN_DIR = ROOT / 'dist/radiomics-features-demo'
SOURCE = Path(os.environ['MEDMLX_HERO_SOURCE'])
LIVER_RUN = ROOT / 'site/assets/hero/radiomics-run.json'
VERSION = '1.0.0'
LIVER = 6  # BTCV label, swin-unetr-mlx v0.2.5 specification.json
# The liver run's settings; one feature from each texture family.
PARAMETERS = {
    'setting': {'binWidth': 10, 'kernelRadius': 5, 'maskedKernel': True,
                'force2D': True, 'force2Ddimension': 0},
    'featureClass': {'firstorder': ['Mean', 'Entropy'], 'glcm': ['Contrast'],
                     'glrlm': ['RunEntropy'], 'glszm': ['ZoneEntropy'],
                     'gldm': ['DependenceEntropy'], 'ngtdm': ['Busyness']},
}


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


def main():
    if metadata.version('mlxradiomics') != VERSION:
        raise RuntimeError(f'Expected mlxradiomics {VERSION}')
    import mlx.core as mx
    from mlxradiomics.medmlx import run

    recorded = json.loads(LIVER_RUN.read_text())['source']
    archive = np.load(SOURCE)
    ct = archive[recorded['image_key']]
    labels = archive[recorded['labels_key']]
    spacing = recorded['spacing_mm_row_col'][0]
    if recorded['spacing_mm_row_col'][1] != spacing or list(ct.shape) != recorded['input_shape']:
        raise ValueError('Unexpected source geometry')

    predicted = labels == LIVER
    components, count = ndimage.label(predicted)  # 2D default structure: 4-connectivity
    sizes = np.bincount(components.ravel())
    sizes[0] = 0
    roi = components == sizes.argmax()

    shutil.rmtree(RUN_DIR, ignore_errors=True)
    RUN_DIR.mkdir(parents=True)
    write_plane(ct, RUN_DIR / 'ct.nii.gz', spacing)
    write_plane(roi.astype(np.uint8), RUN_DIR / 'liver-roi-main.nii.gz', spacing)

    started = datetime.now(UTC)
    clock = time.perf_counter()
    voxel = run(image_path=RUN_DIR / 'ct.nii.gz', mask_path=RUN_DIR / 'liver-roi-main.nii.gz',
                output_dir=RUN_DIR / 'voxel', params=PARAMETERS, voxel=True)
    voxel_seconds = time.perf_counter() - clock
    clock = time.perf_counter()
    whole = run(image_path=RUN_DIR / 'ct.nii.gz', mask_path=RUN_DIR / 'liver-roi-main.nii.gz',
                output_dir=RUN_DIR / 'roi', params=PARAMETERS)
    roi_seconds = time.perf_counter() - clock
    finished = datetime.now(UTC)

    roi_values = json.loads(Path(whole['files']['features_json']).read_text())['features']
    maps = {}
    for name, path in sorted(voxel['files']['maps'].items()):
        values = read_plane(path)
        inside = values[roi]
        if not np.isfinite(inside).all() or not np.all(values[~roi] == 0):
            raise ValueError(f'{name}: expected finite ROI values and zero outside the ROI')
        maps[name] = {
            'roi_value': float(roi_values[name]),
            'map_range': [float(inside.min()), float(inside.max())],
            'local_artifact': Path(path).relative_to(ROOT).as_posix(),
        }

    record = {
        'schema_version': 1,
        'method': 'Native MLX Radiomics voxel and ROI extraction with mlxradiomics.medmlx.run '
                  'on one liver ROI',
        'job': {'script': 'docs/hero/compute_radiomics_features.py',
                'entry_point': 'mlxradiomics.medmlx.run(image_path, mask_path, output_dir, '
                               'params, voxel=True), then the same call with voxel=False',
                'started_at': started.isoformat(timespec='seconds'),
                'finished_at': finished.isoformat(timespec='seconds'),
                'voxel_wall_seconds': round(voxel_seconds, 3),
                'roi_wall_seconds': round(roi_seconds, 3)},
        'runtime': {
            'package': 'mlxradiomics', 'version': metadata.version('mlxradiomics'),
            'mlx_version': metadata.version('mlx'),
            'simpleitk_version': metadata.version('simpleitk'),
            'nibabel_version': metadata.version('nibabel'),
            'numpy_version': metadata.version('numpy'),
            'python_version': platform.python_version(),
            'device': f'{mx.device_info()["device_name"]} GPU',
        },
        'source': {
            **{key: recorded[key] for key in (
                'source_file', 'image_key', 'labels_key', 'source_case', 'axial_slice',
                'spacing_mm_row_col', 'input_shape')},
            'derivation': 'Same as radiomics-run.json: the raw HU axial slice and native '
                          'SwinUNETR prediction written as one-slice NIfTI with SimpleITK. '
                          'No resampling or input smoothing.',
            'parameters': PARAMETERS,
        },
        'roi_selection': {
            'rule': 'largest 4-connected component of the predicted BTCV liver label (6), '
                    'computed before extraction',
            'original_roi_pixels': int(predicted.sum()),
            'selected_roi_pixels': int(roi.sum()),
            'original_component_count': count,
            'manual_mask_edits': False,
        },
        'maps': maps,
    }
    (RUN_DIR / 'compute.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'job': record['job'], 'maps': maps}, indent=2))


if __name__ == '__main__':
    main()
