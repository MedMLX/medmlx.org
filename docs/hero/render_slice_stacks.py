# /// script
# requires-python = ">=3.13,<3.15"
# dependencies = [
#     "totalsegmentator-mlx==0.1.6",
#     "nibabel>=5",
#     "numpy>=2",
#     "pillow>=12",
#     "scipy>=1.16",
#     "imageio-ffmpeg>=0.6",
# ]
# ///
"""Render the scrollable slice stacks on the model pages from saved model outputs.

    uv run docs/hero/render_slice_stacks.py STACK --ct CT.nii.gz --labels LABELS.nii.gz [...] [--run RESULT.json ...]

Each stack is one public CT and the label maps published MedMLX runtimes wrote for
it; nothing is segmented here. Several maps (one per model) are merged in order,
each with its own label IDs; where two overlap, the later one is drawn. The renderer shows the axial slices that hold the
labels (STACKS sets the range), in radiological orientation, with every label as a
translucent fill and a solid outline in the shared anatomy palette. The labels are
never edited: display masks are the labels resampled with the CT, then thresholded
at one half. The slices are encoded as one H.264 video that runs down the stack and
back up, so it loops without a seam, with frequent keyframes so the page can seek to
any slice as the viewer drags.
"""

import argparse
import json
import platform
import subprocess
from importlib.metadata import distributions, version
from pathlib import Path

import imageio_ffmpeg
import nibabel as nib
import numpy as np
from anatomy import lookup
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'site/assets/hero'
CANVAS = (960, 720)
MARGIN = 0.92  # the body crop fills this fraction of the canvas
FPS, KEYFRAME_INTERVAL, CRF = 24, 8, 20
FILL = 0.42
# Lungs, bone and muscle cover much of every slice; a lighter fill keeps the CT and
# the organs beside them readable. Their outlines stay solid.
CONTEXT_FILL = {'lung': 0.16, 'bone': 0.28, 'muscle': 0.28}
CONTEXT = {'lung': ('lung',),
           'bone': ('vertebra', 'rib', 'sacrum', 'hip', 'femur', 'humerus', 'scapula', 'clavic',
                    'sternum', 'skull', 'costal'),
           'muscle': ('gluteus', 'autochthon', 'iliopsoas')}
BODY_HU = -500

# name: package, dataset description, display window (HU), label names, and the
# slice range rule ('labels' = the slices that hold any label, padded).
STACKS = {
    'totalseg-slices': {
        'package': 'totalsegmentator-mlx',
        'source': {'dataset': 'autoPET-III-Lite', 'case': 'fdg_0117d7f11f', 'license': 'CC BY-NC 4.0'},
        'segmentation': 'standard mode, labels on the model\'s 1.5 mm grid',
        'window': (-160, 240), 'maps': ['totalsegmentator'], 'pad_slices': 0,
        # The same body region as the 3D view: from just above the lung apices down to
        # the top of the hip bones, where the field of view starts to cut the body.
        'start_at': ('lung', 20), 'stop_at': 'hip',
    },
    'nnunet-slices': {
        'package': 'nnunet-mlx',
        # The liver and pancreas models were trained on contrast-enhanced CT, so they run
        # on the contrast-enhanced autoPET CT, cropped to the liver's slices with 45 mm
        # margins (1.5 mm grid slices 181-357) to keep the runs short.
        'source': {'dataset': 'autoPET-III-Lite', 'case': 'fdg_0117d7f11f', 'license': 'CC BY-NC 4.0',
                   'input': 'the 1.5 mm CT, slices 181-357'},
        'segmentation': 'nnunet-liver (3d_fullres, fold 0) and nnunet-pancreas (3d_fullres_bs4, fold 0), '
                        'mirroring on, one label map each',
        'window': (-160, 240), 'pad_slices': 6,
        'maps': [{1: 'liver', 2: 'liver tumor'}, {1: 'pancreas', 2: 'pancreatic tumor'}],
        'colours': {'liver tumor': (64, 224, 96), 'pancreatic tumor': (72, 210, 255)},
    },
    'medsam2-slices': {
        'package': 'medsam2-mlx',
        'source': {'dataset': 'LUNA16 subset0', 'case': 'nodule_01_25mm', 'license': 'CC BY 4.0',
                   'series_uid': '1.3.6.1.4.1.14519.5.2.1.6279.6001.511347030803753100045216493273'},
        'segmentation': 'one box prompt on slice 67, propagated in both directions',
        'window': (-160, 240), 'pad_slices': 10,
        'maps': [{1: 'lesion'}], 'colours': {'lesion': (240, 206, 120)},
    },
}


def map_names(names):
    if names == 'totalsegmentator':
        from totalsegmentator_mlx.labels import LABELS
        return LABELS
    return names


def display(volume):
    """Canonical RAS voxels [x, y, z] as slices [z][row, col], superior first.

    Rows run anterior to posterior and columns patient right to left on screen
    (radiological), so patient right is on image left and anterior is at the top.
    """
    return np.asarray(volume.dataobj).transpose(2, 1, 0)[::-1, ::-1, ::-1]


def body_mask(plane):
    """The largest connected region above BODY_HU with holes filled."""
    labels, count = ndimage.label(plane > BODY_HU)
    if not count:
        return np.zeros_like(plane, dtype=bool)
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0
    return ndimage.binary_fill_holes(labels == sizes.argmax())


def encode(frames, video):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    height, width = frames[0].shape[:2]
    arguments = ['-c:v', 'libx264', '-preset', 'veryslow', '-crf', str(CRF), '-pix_fmt', 'yuv420p',
                 '-g', str(KEYFRAME_INTERVAL), '-vf',
                 ('scale=out_color_matrix=bt709:out_range=tv,'
                  'setparams=range=tv:color_primaries=bt709:color_trc=bt709:colorspace=bt709'),
                 '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
                 '-color_range', 'tv', '-movflags', '+faststart', '-an', '-map_metadata', '-1']
    process = subprocess.Popen([ffmpeg, '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                                '-s', f'{width}x{height}', '-r', str(FPS), '-i', '-', *arguments, str(video)],
                               stdin=subprocess.PIPE)
    # Down the stack and back up, without repeating either end, so the loop is seamless.
    for frame in [*frames, *frames[-2:0:-1]]:
        process.stdin.write(frame.tobytes())
    process.stdin.close()
    if process.wait() != 0:
        raise RuntimeError('ffmpeg failed')
    return arguments


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('stack', choices=sorted(STACKS))
    parser.add_argument('--ct', type=Path, required=True)
    parser.add_argument('--labels', type=Path, nargs='+', required=True, help='one label map per STACKS map')
    parser.add_argument('--run', type=Path, nargs='*', default=[], help='the runners\' results, saved as JSON')
    args = parser.parse_args()
    spec = STACKS[args.stack]
    if len(args.labels) != len(spec['maps']):
        raise ValueError(f'{args.stack} takes {len(spec["maps"])} label maps')

    ct_image = nib.as_closest_canonical(nib.load(args.ct))
    spacing = [float(z) for z in ct_image.header.get_zooms()[:3]]
    ct = display(ct_image).astype(np.float32)
    # Merge the maps into one volume with distinct IDs; later maps are drawn on top.
    labels = np.zeros(ct.shape, dtype=np.int32)
    names = {}
    for path, table in zip(args.labels, spec['maps'], strict=True):
        label_image = nib.as_closest_canonical(nib.load(path))
        if ct_image.shape != label_image.shape or not np.allclose(ct_image.affine, label_image.affine, atol=1e-4):
            raise ValueError(f'CT and {path.name} must share one voxel grid')
        table = map_names(table)
        values = display(label_image).astype(np.int32)
        found = sorted(int(v) for v in np.unique(values) if v)
        if not set(found) <= set(table):
            raise ValueError(f'Unknown labels in {path.name}: {sorted(set(found) - set(table))}')
        offset = max(names, default=0)
        for value in found:
            labels[values == value] = offset + value
        names.update({offset + value: name for value, name in table.items()})
    present = sorted(int(v) for v in np.unique(labels) if v)
    colours = {v: spec.get('colours', {}).get(names[v]) or lookup(names[v]) for v in present}
    missing = [names[v] for v, c in colours.items() if c is None]
    if missing:
        raise ValueError(f'No color for {missing}')

    held = np.flatnonzero(labels.any(axis=(1, 2)))
    first, last = int(held[0]), int(held[-1])
    if spec.get('stop_at'):
        stop = [v for v in present if names[v].startswith(spec['stop_at'])]
        last = int(np.flatnonzero(np.isin(labels, stop).any(axis=(1, 2)))[0]) - 1
    if spec.get('start_at'):
        prefix, before = spec['start_at']
        start = [v for v in present if names[v].startswith(prefix)]
        first = int(np.flatnonzero(np.isin(labels, start).any(axis=(1, 2)))[0]) - before
    first = max(0, first - spec['pad_slices'])
    last = min(len(labels) - 1, last + spec['pad_slices'])

    # One crop for every slice: the body over the shown range, padded by 3%.
    bodies = np.stack([body_mask(ct[k]) for k in range(first, last + 1)])
    union = bodies.any(axis=0)
    rows, cols = np.flatnonzero(union.any(axis=1)), np.flatnonzero(union.any(axis=0))
    pad_r, pad_c = round(0.03 * union.shape[0]), round(0.03 * union.shape[1])
    r0, r1 = max(rows[0] - pad_r, 0), min(rows[-1] + 1 + pad_r, union.shape[0])
    c0, c1 = max(cols[0] - pad_c, 0), min(cols[-1] + 1 + pad_c, union.shape[1])
    # Displayed slices keep their physical aspect (row spacing y, column spacing x).
    physical = ((c1 - c0) * spacing[0], (r1 - r0) * spacing[1])
    scale = min(CANVAS[0] * MARGIN / physical[0], CANVAS[1] * MARGIN / physical[1])
    size = (round(physical[0] * scale), round(physical[1] * scale))
    offset = ((CANVAS[0] - size[0]) // 2, (CANVAS[1] - size[1]) // 2)
    low, high = spec['window']

    frames, counts = [], []
    for index, k in enumerate(range(first, last + 1)):
        gray = np.clip((ct[k, r0:r1, c0:c1] - low) / (high - low), 0, 1)
        gray[~bodies[index][r0:r1, c0:c1]] = 0
        rgb = np.asarray(Image.fromarray(np.uint8(np.round(gray * 255))).resize(size, Image.LANCZOS),
                         dtype=np.float64)[:, :, None].repeat(3, axis=2)
        plane = labels[k, r0:r1, c0:c1]
        shown = 0
        for value in present:
            indicator = (plane == value).astype(np.float32)
            if not indicator.any():
                continue
            shown += 1
            mask = np.asarray(Image.fromarray(indicator).resize(size, Image.BILINEAR)) >= 0.5
            edge = mask & ~ndimage.binary_erosion(mask, iterations=2)
            colour = np.asarray(colours[value], dtype=np.float64)
            kind = next((k for k, words in CONTEXT.items() if any(w in names[value].lower() for w in words)), None)
            fill = CONTEXT_FILL.get(kind, FILL)
            rgb[mask] = (1 - fill) * rgb[mask] + fill * colour
            rgb[edge] = colour
        canvas = np.zeros((CANVAS[1], CANVAS[0], 3), dtype=np.uint8)
        canvas[offset[1]:offset[1] + size[1], offset[0]:offset[0] + size[0]] = np.uint8(np.round(rgb))
        frames.append(canvas)
        counts.append(shown)

    video = ASSETS / f'{args.stack}.mp4'
    arguments = encode(frames, video)
    poster_index = int(np.argmax(counts))
    Image.fromarray(frames[poster_index]).save(ASSETS / f'{args.stack}-poster.webp', quality=88, method=6)
    runs = [json.loads(path.read_text()) for path in args.run]
    installed = {d.metadata['Name'].lower() for d in distributions()}
    record = {
        'schema_version': 1,
        'method': f'{spec["package"]} label map over its source CT, shown as axial slices',
        'package': spec['package'],
        'package_version': version(spec['package']) if spec['package'] in installed else None,
        'source': spec['source'], 'segmentation': spec['segmentation'],
        'runners': runs,
        'display': {
            'renderer': 'docs/hero/render_slice_stacks.py', 'ct_window_hu': list(spec['window']),
            'slices': [first, last], 'slice_count': last - first + 1,
            'order': 'superior to inferior, then back up', 'grid_spacing_mm': spacing,
            'crop_rows_cols': [int(r0), int(r1), int(c0), int(c1)], 'canvas_px': list(CANVAS),
            'slice_px': list(size), 'fill_opacity': FILL, 'context_fill_opacity': CONTEXT_FILL,
            'outline_px': 2,
            'labels_shown': {names[v]: list(colours[v]) for v in present},
            'mask_resampling': 'bilinear indicator, thresholded at 0.5; labels not edited',
            'poster_slice': first + poster_index,
            'orientation': 'radiological: patient right on image left, anterior at top',
        },
        'encode': {'codec': 'H.264 (libx264)', 'fps': FPS, 'crf': CRF, 'keyframe_interval': KEYFRAME_INTERVAL,
                   'frames': 2 * len(frames) - 2, 'arguments': arguments,
                   'ffmpeg': imageio_ffmpeg.get_ffmpeg_version(), 'bytes': video.stat().st_size},
        'runtime': {'python_version': platform.python_version(), 'numpy': version('numpy')},
        'outputs': {'video': f'site/assets/hero/{args.stack}.mp4',
                    'poster': f'site/assets/hero/{args.stack}-poster.webp'},
    }
    (ASSETS / f'{args.stack}-run.json').write_text(json.dumps(record, indent=1) + '\n')
    print(f'{args.stack}: slices {first}-{last} ({last - first + 1}), {video.stat().st_size} bytes')


if __name__ == '__main__':
    main()
