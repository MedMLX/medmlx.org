# /// script
# requires-python = ">=3.13,<3.15"
# dependencies = [
#     "mlx-generate-ctmr==0.5.2.post2",
#     "nibabel>=5",
#     "numpy>=2",
#     "pillow>=12",
#     "imageio-ffmpeg>=0.6",
# ]
# ///
"""Render the homepage Generation card: mlx-generate-ctmr volumes scrolling together.

Two stages, run in order from the repository root:
    uv run docs/hero/render_generation_grid.py generate   # mlx-generate-ctmr on Metal
    uv run docs/hero/render_generation_grid.py render     # MP4, poster, run record

`generate` calls the published runner unchanged, one tile at a time, with the
packaged default steps, grids and intensity QC. The top row is paired CT, where
NV-Generate first generates a label mask from one size control and then the CT
from it. The bottom row is MR-Brain in four contrasts. A tile whose result.json
exists is not regenerated. `render` performs display transforms only: closest
canonical RAS, radiological axial display, a fixed CT window or a fixed per-volume
MR percentile window, uniform Lanczos resampling and H.264/WebP encoding.
Every tile scrolls through its own reviewed slice range on one shared cosine
ping-pong, so the loop has no jump. Generated voxels are never edited.
"""

import argparse
import json
import math
import os
import platform
import subprocess
import tempfile
from importlib import metadata
from pathlib import Path

import imageio_ffmpeg
import nibabel as nib
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
RUN_DIR = ROOT / 'dist/generation-grid-demo'
ASSETS = ROOT / 'site/assets/hero'
NAME = 'generation-grid'

# Tile order is grid order: CT across the top row, MR-Brain across the bottom.
# Paired CT without a mask archive needs a size control; scales are 0..1.
TILES = [
    {'tile': 'ct-abdomen', 'title': 'CT, abdomen', 'configuration': 'ct',
     'anatomy': ['liver', 'spleen', 'pancreas', 'right kidney', 'left kidney', 'stomach', 'aorta'],
     'anatomy_size': {'liver': 0.5}},
    {'tile': 'ct-hepatic-tumor', 'title': 'CT, hepatic tumor', 'configuration': 'ct',
     'anatomy': ['liver', 'hepatic tumor'], 'anatomy_size': {'hepatic tumor': 0.3}},
    {'tile': 'ct-lung-tumor', 'title': 'CT, lung tumor', 'configuration': 'ct',
     'anatomy': ['left lung upper lobe', 'left lung lower lobe', 'right lung upper lobe',
                 'right lung middle lobe', 'right lung lower lobe', 'lung tumor'],
     'anatomy_size': {'lung tumor': 0.3}},
    {'tile': 'ct-pancreatic-tumor', 'title': 'CT, pancreatic tumor', 'configuration': 'ct',
     'anatomy': ['pancreas', 'pancreatic tumor'], 'anatomy_size': {'pancreatic tumor': 0.3}},
    {'tile': 'mr-brain-t1', 'title': 'MR-Brain, T1', 'configuration': 'mr-brain', 'modality': 'mri_t1'},
    {'tile': 'mr-brain-t2', 'title': 'MR-Brain, T2', 'configuration': 'mr-brain', 'modality': 'mri_t2'},
    {'tile': 'mr-brain-flair', 'title': 'MR-Brain, FLAIR', 'configuration': 'mr-brain', 'modality': 'mri_flair'},
    {'tile': 'mr-brain-swi', 'title': 'MR-Brain, SWI', 'configuration': 'mr-brain', 'modality': 'mri_swi'},
]
# Seed shown for each tile, chosen by visual review of the candidates `generate --seeds` made.
CHOSEN_SEEDS = {'ct-abdomen': 3, 'ct-hepatic-tumor': 3, 'ct-lung-tumor': 1}
# Axial slices shown per tile (RAS z, inclusive), chosen by visual review: each
# range drops the volume ends where generated anatomy degrades (truncated pelvis
# and lung base, garbled neck, MR skull base) and the levels where the section
# shrinks inside its fixed tile crop (low pelvis, shoulders, MR vertex).
SLICE_RANGE = {'ct-abdomen': (80, 196), 'ct-hepatic-tumor': (10, 190), 'ct-lung-tumor': (40, 170),
               'mr-brain-t1': (40, 92), 'mr-brain-t2': (40, 92), 'mr-brain-flair': (40, 92)}
# Tiles shown, one list per row: one paired CT and one MR-Brain contrast, large enough to
# read on the card. Generated tiles left out here stay in the run folder.
LAYOUT = [['ct-hepatic-tumor', 'mr-brain-t2']]
SIZE = (800, 520)
GAP = 12
CT_WINDOW = (40, 400)  # level, width in HU
MR_PERCENTILES = (1.0, 99.5)  # of nonzero voxels, per volume
FPS = 24
SECONDS = 8
CRF = 28
# BT.709 limited-range conversion, tagged as BT.709 primaries, transfer and matrix.
COLOR_FILTER = ('scale=out_color_matrix=bt709:out_range=tv,'
                'setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv')


def jsonable(value):
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    return value


def public_paths(value, run_dir):
    """Rewrite absolute local paths in runner details so the run record has none.

    Installed package files become package-relative, run outputs become
    repository-relative and anything else under the home folder starts with ~.
    """
    if isinstance(value, dict):
        return {k: public_paths(v, run_dir) for k, v in value.items()}
    if isinstance(value, list):
        return [public_paths(v, run_dir) for v in value]
    if isinstance(value, str) and value.startswith('/'):
        if 'site-packages/' in value:
            return value.split('site-packages/', 1)[1]
        if value.startswith(str(run_dir)):
            return str(Path(value).relative_to(ROOT))
        home = str(Path.home())
        if value.startswith(home):
            return '~' + value[len(home):]
    return value


def generate(args):
    import mlx.core as mx
    from mlx_generate_ctmr.medmlx import run

    from medmlx_core.errors import InvalidInputError, ModelExecutionError

    failed = []
    for spec, seed in ((spec, seed) for spec in TILES for seed in args.seeds
                       if not args.tiles or spec['tile'] in args.tiles):
        out = args.run_dir / spec['tile'] / f'seed-{seed}'
        if (out / 'result.json').is_file():
            print(f'{spec["tile"]} seed {seed}: already generated')
            continue
        kwargs = {key: spec[key] for key in ('configuration', 'modality', 'anatomy', 'anatomy_size')
                  if key in spec}
        print(f'{spec["tile"]} seed {seed}: generating {kwargs}', flush=True)
        try:
            result = run(output_dir=out / 'out', seed=seed, overwrite=True, **kwargs)
        except (InvalidInputError, ModelExecutionError) as error:
            # The runner's own QC rejected this tile; keep going so one bad draw
            # does not cost the rest of the batch, and report it at the end.
            print(f'{spec["tile"]} seed {seed}: FAILED {error}', flush=True)
            failed.append(f'{spec["tile"]} seed {seed}')
            mx.clear_cache()
            continue
        record = {'tile': spec['tile'], 'kwargs': kwargs, 'seed': seed,
                  'outputs': {role: str(Path(path).relative_to(args.run_dir))
                              for role, path in result['outputs'].items()},
                  'details': jsonable(result['details'])}
        (out / 'result.json').write_text(json.dumps(record, indent=1) + '\n')
        mx.clear_cache()
    if failed:
        raise SystemExit(f'failed tiles: {", ".join(failed)}')


def load_tile(run_dir, spec):
    """Return the tile's volume as display slices [z][row, col] in 0..1, plus its record."""
    record = json.loads((run_dir / spec['tile'] / f'seed-{CHOSEN_SEEDS.get(spec["tile"], 0)}'
                         / 'result.json').read_text())
    image = nib.as_closest_canonical(nib.load(run_dir / record['outputs']['synthetic_image']))
    data = np.asarray(image.dataobj, dtype=np.float32)
    spacing = image.header.get_zooms()[:3]
    if spec['configuration'] == 'ct':
        level, width = CT_WINDOW
        low, high = level - width / 2, level + width / 2
    else:
        nonzero = data[data > 0]
        low, high = (float(v) for v in np.percentile(nonzero, MR_PERCENTILES))
    shown = np.clip((data - low) / (high - low), 0, 1)
    # RAS voxel [x, y] to radiological display: patient right on image left, anterior up.
    slices = shown.transpose(2, 1, 0)[:, ::-1, ::-1]
    first, last = SLICE_RANGE[spec['tile']]
    # One fixed crop per tile: the bounding box of displayed signal over the shown
    # slices, padded by 4% of the slice size, so the anatomy fills its tile.
    support = (slices[first:last + 1] > 0.02).any(axis=0)
    rows, cols = np.flatnonzero(support.any(axis=1)), np.flatnonzero(support.any(axis=0))
    pad_r, pad_c = round(0.04 * support.shape[0]), round(0.04 * support.shape[1])
    r0, r1 = max(rows[0] - pad_r, 0), min(rows[-1] + 1 + pad_r, support.shape[0])
    c0, c1 = max(cols[0] - pad_c, 0), min(cols[-1] + 1 + pad_c, support.shape[1])
    slices = slices[:, r0:r1, c0:c1]
    return slices, (first, last), (low, high), spacing, record


def aspect(slices, spacing):
    """Physical width over height of the tile's cropped axial slices."""
    return (slices.shape[2] * spacing[0]) / (slices.shape[1] * spacing[1])


def tile_boxes(aspects):
    """Equal columns: every tile has one width, with one gap between tiles and rows.

    Each row is as tall as its tallest tile at that width, and shorter tiles are
    centered in it, so the CT and MR rows line up column by column. Everything is
    scaled down together, and centered, when the rows would overflow the frame.
    """
    columns = max(len(row) for row in aspects)
    width = (SIZE[0] - GAP * (columns - 1)) / columns
    heights = [width / min(row) for row in aspects]
    scale = min(1.0, (SIZE[1] - GAP * (len(aspects) - 1)) / sum(heights))
    width, heights = width * scale, [h * scale for h in heights]
    y = (SIZE[1] - sum(heights) - GAP * (len(aspects) - 1)) / 2
    boxes = []
    for row, height in zip(aspects, heights, strict=True):
        x = (SIZE[0] - width * len(row) - GAP * (len(row) - 1)) / 2
        for a in row:
            tile_h = width / a
            top = y + (height - tile_h) / 2
            boxes.append((round(x), round(top), round(x + width) - round(x), round(top + tile_h) - round(top)))
            x += width + GAP
        y += height + GAP
    return boxes


def fit(slice_, spacing_xy, box):
    """Resample one slice to its physical aspect, centered in the box on black."""
    rows, cols = slice_.shape
    aspect = (cols * spacing_xy[0]) / (rows * spacing_xy[1])
    _, _, width, height = box
    if width / height > aspect:
        size = (round(height * aspect), height)
    else:
        size = (width, round(width / aspect))
    picture = Image.fromarray(np.round(slice_ * 255).astype(np.uint8)).resize(size, Image.LANCZOS)
    canvas = Image.new('L', (width, height))
    canvas.paste(picture, ((width - size[0]) // 2, (height - size[1]) // 2))
    return canvas


def render(args):
    specs = {spec['tile']: spec for spec in TILES}
    tiles = [(specs[name], *load_tile(args.run_dir, specs[name])) for row in LAYOUT for name in row]
    found = iter(aspect(slices, spacing) for _, slices, _, _, spacing, _ in tiles)
    boxes = tile_boxes([[next(found) for _ in row] for row in LAYOUT])
    frames = FPS * SECONDS
    # Shared cosine ping-pong in 0..1; each tile maps it onto its own slice range.
    phase = [(1 - math.cos(2 * math.pi * k / frames)) / 2 for k in range(frames)]
    poster_phase = 0.5

    def compose(t):
        canvas = Image.new('RGB', SIZE)
        for (spec, slices, (first, last), _, spacing, _), box in zip(tiles, boxes, strict=True):
            z = first + round((last - first) * t)
            canvas.paste(fit(slices[z], spacing[:2], box).convert('RGB'), box[:2])
        return canvas

    video = ASSETS / f'{NAME}.mp4'
    poster = ASSETS / f'{NAME}-poster.webp'
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    encode = ['-c:v', 'libx264', '-preset', 'veryslow', '-crf', str(CRF), '-pix_fmt', 'yuv420p',
              '-vf', COLOR_FILTER, '-movflags', '+faststart', '-an', '-map_metadata', '-1']
    with tempfile.TemporaryDirectory() as scratch:
        process = subprocess.Popen(
            [ffmpeg, '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
             '-s', f'{SIZE[0]}x{SIZE[1]}', '-r', str(FPS), '-i', '-', *encode,
             str(Path(scratch) / 'out.mp4')], stdin=subprocess.PIPE)
        for t in phase:
            process.stdin.write(compose(t).tobytes())
        process.stdin.close()
        if process.wait() != 0:
            raise RuntimeError('ffmpeg failed')
        os.replace(Path(scratch) / 'out.mp4', video)
    poster_image = compose(poster_phase)
    poster_image.save(poster, quality=85, method=6)
    poster_image.save(args.run_dir / 'poster.png')
    raw = subprocess.run([ffmpeg, '-loglevel', 'error', '-i', str(video), '-f', 'rawvideo',
                          '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True).stdout
    decoded_frames = len(raw) // (SIZE[0] * SIZE[1] * 3)
    if decoded_frames != frames:
        raise ValueError(f'Decoded {decoded_frames} frames, expected {frames}')
    ffmpeg_line = subprocess.run([ffmpeg, '-version'], capture_output=True, text=True,
                                 check=True).stdout.splitlines()[0].split(' Copyright')[0]

    import mlx.core as mx
    record = {
        'schema_version': 1,
        'method': 'mlx-generate-ctmr 0.5.2.post2 NV-Generate (MAISI): three paired CT volumes, each '
                  'from a generated label mask with one size control, and three MR-Brain contrasts; '
                  'shown as synchronized axial slice scrolls',
        'runtime': {
            'package': 'mlx-generate-ctmr',
            'version': metadata.version('mlx-generate-ctmr'),
            'medmlx_core_version': metadata.version('medmlx-core'),
            'mlx_version': metadata.version('mlx'),
            'python_version': platform.python_version(),
            'macos_version': platform.mac_ver()[0],
            'device': f'{subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True, check=True).stdout.strip()} GPU ({mx.default_device()})',
            'entry_point': 'mlx_generate_ctmr.medmlx.run',
        },
        'selection': 'CT tiles chosen by visual review from seeds 0 to 3; MR-Brain tiles use seed 0',
        'tiles': [{
            'box_px': list(boxes[i]),
            'title': spec['title'],
            'kwargs': record['kwargs'],
            'seed': record['seed'],
            'details': public_paths(record['details'], args.run_dir.resolve()),
            'displayed_slice_px': list(slices.shape[1:]),
            'spacing_mm_ras': [round(float(s), 4) for s in spacing],
            'display_window': [round(low, 2), round(high, 2)],
            'shown_slices': [first, last],
            'local_artifact': f'dist/generation-grid-demo/{record["outputs"]["synthetic_image"]}',
        } for i, (spec, slices, (first, last), (low, high), spacing, record) in enumerate(tiles)],
        'display': {
            'renderer': 'docs/hero/render_generation_grid.py',
            'orientation': 'Axial after closest canonical RAS, radiological display: patient right '
                           'on image left, anterior at top',
            'ct_window_hu': {'level': CT_WINDOW[0], 'width': CT_WINDOW[1]},
            'mr_window': f'percentiles {MR_PERCENTILES[0]} and {MR_PERCENTILES[1]} of nonzero voxels, '
                         'fixed per volume; intensities are arbitrary scaled units',
            'slice_range': 'per tile, chosen by visual review to drop volume ends where generated '
                           'anatomy degrades; see shown_slices',
            'schedule': 'one cosine ping-pong shared by all tiles, mapped onto each slice range',
            'crop': 'per tile, bounding box of pixels above display black over the shown slices, padded by 4% of the slice size',
            'resampling': 'Lanczos to physical in-plane aspect, centered on black',
            'layout': {'rows': LAYOUT, 'gap_px': GAP,
                       'rule': 'equal columns: every tile has one width and keeps its aspect, centered in a row as tall as its tallest tile; one gap between tiles and rows'},
        },
        'encode': {
            'video': {'codec': 'H.264 (libx264)', 'preset': 'veryslow', 'crf': CRF,
                      'pix_fmt': 'yuv420p', 'color': 'BT.709, limited range', 'fps': FPS,
                      'seconds': SECONDS, 'size_px': list(SIZE), 'audio': False,
                      'movflags': '+faststart', 'ffmpeg': ffmpeg_line,
                      'decoded_frames': decoded_frames, 'bytes': video.stat().st_size},
            'poster': {'format': 'WebP', 'quality': 85, 'method': 6, 'size_px': list(SIZE),
                       'bytes': poster.stat().st_size},
        },
        'outputs': {'video': f'site/assets/hero/{NAME}.mp4',
                    'poster': f'site/assets/hero/{NAME}-poster.webp'},
        'interpretation': 'Synthetic images generated from noise for a software visualization; no '
                          'patient data. Not reviewed, not clinical images and not a quality validation.',
    }
    (ASSETS / f'{NAME}-run.json').write_text(json.dumps(record, indent=1) + '\n')
    print(f'wrote {video.name} ({video.stat().st_size} bytes), {poster.name}, {NAME}-run.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('stage', choices=['generate', 'render'])
    parser.add_argument('--run-dir', type=Path, default=RUN_DIR)
    parser.add_argument('--seeds', type=int, nargs='+', default=[0], help='generate: seeds to run')
    parser.add_argument('--tiles', nargs='+', help='generate: tile names to run (default all)')
    args = parser.parse_args()
    args.run_dir.mkdir(parents=True, exist_ok=True)
    {'generate': generate, 'render': render}[args.stage](args)


if __name__ == '__main__':
    main()
