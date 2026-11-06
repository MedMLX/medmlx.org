# /// script
# requires-python = ">=3.13,<3.15"
# dependencies = [
#     "radimagenet-mlx==0.3.3",
#     "numpy>=2",
#     "nibabel>=5",
#     "pillow>=12",
#     "scipy>=1.16",
#     "imageio-ffmpeg>=0.6",
# ]
# ///
"""Render the Feature extraction card: RadImageNet ResNet50 features for every CT slice.

Two stages, run in order from the repository root:
    uv run docs/hero/render_feature_scroll.py extract --dataset <LUNA16 folder>
    uv run docs/hero/render_feature_scroll.py render

`extract` writes each axial slice of one LUNA16 CT as the 8-bit PNG shown on
the card (one soft-tissue window, one square body crop) and passes it unchanged
to the published `radimagenet_mlx.medmlx.resnet50` runner. The runner's pooled
(2048) and spatial (7 x 7 x 2048) outputs are stacked into one archive.

`render` performs display transforms only. The left panel shows the slice the
model read with its 7 x 7 spatial map drawn as cells, colored by the first
three principal components of all spatial vectors in the shown slices. The right panel
grows one column per slice: the 96 pooled features with the largest variance
across slices, z-scored per feature and ordered by the slice where each one
peaks. Feature values are never smoothed, interpolated between slices or
recomputed here.
"""

import argparse
import json
import os
import platform
import subprocess
from importlib.metadata import version
from pathlib import Path

import imageio_ffmpeg
import nibabel as nib
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
RUN_DIR = ROOT / 'dist/feature-scroll-demo'
ASSETS = ROOT / 'site/assets/hero'
CASE_FILE = 'nifti/nodule_02_22mm.nii.gz'
SERIES_UID = '1.3.6.1.4.1.14519.5.2.1.6279.6001.905371958588660410240398317235'
WINDOW = {'center': 40, 'width': 400}
LOW, HIGH = WINDOW['center'] - WINDOW['width'] / 2, WINDOW['center'] + WINDOW['width'] / 2
BODY_HU = -300

SIZE = (800, 520)
CT_XY, CT_SIDE = (16, 36), 448
HEAT_XY, COLUMN_PX, ROW_PX = (484, 116), 2, 3
SHOWN_FEATURES = 96
Z_RANGE = (-0.5, 3.0)
CELL_OPACITY = 0.62
# The radiomics cards' sequential crimson palette, so both quantitative cards read alike.
PALETTE = [(48, 9, 20), (120, 24, 43), (195, 58, 77), (239, 137, 143), (255, 233, 226)]
EMPTY_RGB = (22, 22, 24)
TEXT_RGB, MUTED_RGB = (236, 236, 240), (161, 161, 166)
FPS, FRAMES_PER_SLICE, HOLD, DISSOLVE = 24, 1, 48, 12
POSTER_SLICE = 100
# Stored slices run superior to inferior, the order the card scrolls. The first 2
# (the top of the scan, at the shoulder joints) are left out.
FIRST_SHOWN = 2
CRF = 28
MAX_VIDEO_BYTES = 700_000
# BT.709 matrix for the RGB conversion, and BT.709 tags on every encoded frame.
VIDEO_FILTER = ('scale=out_color_matrix=bt709:out_range=tv,'
                'setparams=range=tv:color_primaries=bt709:color_trc=bt709:colorspace=bt709')


def load_ct(path):
    """Read HU voxels whose stored axes already give a radiological axial view."""
    image = nib.load(path)
    affine = np.asarray(image.affine, dtype=np.float64)
    # i runs toward patient left and j toward posterior, so data[:, :, k].T
    # shows patient right on image left and anterior at the top.
    if nib.aff2axcodes(affine) != ('L', 'P', 'S') or len(image.shape) != 3:
        raise ValueError(f'Expected a 3D LPS-ordered CT: {path}')
    return np.asarray(image.dataobj, dtype=np.float32), image.header.get_zooms()


def square_crop(hu):
    """One square in-plane crop around the body on every slice, clipped to the grid.

    The body is the largest connected component of the in-plane projection above
    BODY_HU, which leaves out the scanner table.
    """
    labels, count = ndimage.label((hu > BODY_HU).mean(axis=2).T > 0.5)
    sizes = ndimage.sum_labels(np.ones_like(labels), labels, range(1, count + 1))
    body = labels == 1 + int(np.argmax(sizes))
    rows, cols = np.nonzero(body)
    top, bottom, left, right = rows.min(), rows.max() + 1, cols.min(), cols.max() + 1
    side = min(max(bottom - top, right - left), *body.shape)
    center_row, center_col = (top + bottom) // 2, (left + right) // 2
    top = int(np.clip(center_row - side // 2, 0, body.shape[0] - side))
    left = int(np.clip(center_col - side // 2, 0, body.shape[1] - side))
    return top, left, int(side)


def extract(args):
    from radimagenet_mlx.medmlx import resnet50

    case = args.dataset / CASE_FILE
    hu, spacing = load_ct(case)
    top, left, side = square_crop(hu)
    slices_dir, runs_dir = RUN_DIR / 'slices', RUN_DIR / 'runs'
    slices_dir.mkdir(parents=True, exist_ok=True)
    pooled, spatial, details = [], [], None
    # Superior to inferior, the order the card scrolls.
    order = list(range(hu.shape[2] - 1, -1, -1))
    for n, k in enumerate(order):
        plane = hu[:, :, k].T[top:top + side, left:left + side]
        pixels = np.round(np.clip((plane - LOW) / (HIGH - LOW), 0, 1) * 255).astype(np.uint8)
        png = slices_dir / f'{n:03d}.png'
        Image.fromarray(pixels).save(png)
        result = resnet50(image_path=str(png), output_dir=str(runs_dir / f'{n:03d}'), overwrite=True)
        pooled.append(np.load(result['outputs']['features_npy'])[0])
        spatial.append(np.load(result['outputs']['spatial_features_npy'])[0])
        details = result['details']
        print(f'{n + 1}/{len(order)}', end='\r', flush=True)
    np.savez(RUN_DIR / 'features.npz', pooled=np.stack(pooled), spatial=np.stack(spatial),
             slice_index=np.array(order))
    record = {
        'case_file': CASE_FILE, 'shape_ijk': list(hu.shape),
        'spacing_mm_ijk': [round(float(s), 6) for s in spacing],
        'crop_rows_cols_side': [top, left, side], 'window_hu': WINDOW,
        'slices': len(order), 'order': 'superior to inferior',
        'details': {key: str(value) if key == 'backbone' else value
                    for key, value in details.items() if key != 'model_path'},
        'runtime': {
            'package': 'radimagenet-mlx', 'version': version('radimagenet-mlx'),
            'medmlx_core_version': version('medmlx-core'), 'mlx_version': version('mlx'),
            'python_version': platform.python_version(), 'macos_version': platform.mac_ver()[0],
            'precision': 'float32', 'entry_point': 'radimagenet_mlx.medmlx.resnet50',
        },
    }
    (RUN_DIR / 'extract.json').write_text(json.dumps(record, indent=1) + '\n')
    print()


def font(weight, size):
    """Use Inter (SIL Open Font License) from the MEDMLX_HERO_FONTS directory."""
    return ImageFont.truetype(str(Path(os.environ['MEDMLX_HERO_FONTS']) / f'Inter-{weight}.ttf'), size)


def ramp(values):
    """Map values in [0, 1] through the sequential palette."""
    stops = np.linspace(0, 1, len(PALETTE))
    return np.stack([np.interp(values, stops, np.asarray(PALETTE, float)[:, c]) for c in range(3)], -1)


def principal_colors(spatial):
    """RGB from the first three principal components of every spatial vector in the scan.

    Each component is scaled by its 2nd-98th percentile over the scan, so a color
    means the same feature direction on every slice.
    """
    vectors = spatial.reshape(-1, spatial.shape[-1]).astype(np.float64)
    centered = vectors - vectors.mean(axis=0)
    _, singular, basis = np.linalg.svd(centered, full_matrices=False)
    scores = centered @ basis[:3].T
    low, high = np.percentile(scores, [2, 98], axis=0)
    rgb = np.clip((scores - low) / (high - low), 0, 1)
    explained = (singular[:3] ** 2 / (singular ** 2).sum()).tolist()
    return rgb.reshape(*spatial.shape[:3], 3), explained


def feature_columns(pooled):
    """Z-scores of the most variable pooled features, ordered by the slice of their peak."""
    chosen = np.argsort(pooled.var(axis=0))[::-1][:SHOWN_FEATURES]
    values = pooled[:, chosen]
    z = (values - values.mean(axis=0)) / values.std(axis=0)
    order = np.argsort(np.argmax(z, axis=0), kind='stable')
    return z[:, order], chosen[order]


def render(args):
    data = np.load(RUN_DIR / 'features.npz')
    extracted = json.loads((RUN_DIR / 'extract.json').read_text())
    pooled, spatial = data['pooled'], data['spatial']
    if spatial.shape != (len(pooled), 7, 7, 2048) or pooled.shape != (len(pooled), 2048):
        raise ValueError('Expected ResNet50 pooled and 7 x 7 spatial features for every slice')
    kept = np.arange(FIRST_SHOWN, len(pooled))
    pooled, spatial, count = pooled[kept], spatial[kept], len(kept)
    cells, explained = principal_colors(spatial)
    z, chosen = feature_columns(pooled)
    heat = ramp(np.clip((z.T - Z_RANGE[0]) / (Z_RANGE[1] - Z_RANGE[0]), 0, 1))
    heat_w, heat_h = count * COLUMN_PX, SHOWN_FEATURES * ROW_PX
    if HEAT_XY[0] + heat_w > SIZE[0] - 8:
        raise ValueError('The feature panel does not fit the frame')
    heat_image = np.repeat(np.repeat(heat, ROW_PX, axis=0), COLUMN_PX, axis=1)
    title_font, label_font = font('SemiBold', 40), font('Regular', 30)

    label_xy = (HEAT_XY[0], HEAT_XY[1] + heat_h + 52)

    def label_coverage(n):
        """Coverage of the slice label alone, so it can fade without ghosting."""
        layer = Image.new('L', SIZE, 0)
        ImageDraw.Draw(layer).text(label_xy, f'Slice {n + 1} of {count}', font=label_font,
                                   fill=255, anchor='ls')
        return np.asarray(layer, dtype=np.float64)[:, :, None] / 255

    def frame(n, label=True):
        canvas = Image.new('RGB', SIZE, 'black')
        gray = np.asarray(Image.open(RUN_DIR / 'slices' / f'{kept[n]:03d}.png'), dtype=np.float64)
        side = gray.shape[0]
        # Each 7 x 7 cell covers the same 1/7 of the PNG that it covers of the
        # runner's nearest-neighbour 224 x 224 input.
        edges = np.round(np.linspace(0, side, 8)).astype(int)
        tint = np.zeros((side, side, 3))
        for r in range(7):
            for c in range(7):
                tint[edges[r]:edges[r + 1], edges[c]:edges[c + 1]] = cells[n, r, c] * 255
        # Tint only the body: the largest nonzero component of the windowed slice,
        # holes (lungs, bowel gas) filled. Air and the table keep their gray.
        labels, found = ndimage.label(gray > 0)
        body = ndimage.binary_fill_holes(labels == 1 + np.argmax(
            ndimage.sum_labels(np.ones_like(labels), labels, range(1, found + 1))))[:, :, None]
        # Screen blend keeps the anatomy readable and the colors bright over dark lung.
        screen = 255 - (255 - gray[:, :, None]) * (255 - CELL_OPACITY * tint) / 255
        rgb = np.where(body, screen, gray[:, :, None])
        for edge in edges[1:-1]:
            rgb[:, edge - 1:edge + 1] *= np.where(body[:, edge - 1:edge + 1], 0.55, 1)
            rgb[edge - 1:edge + 1] *= np.where(body[edge - 1:edge + 1], 0.55, 1)
        panel = Image.fromarray(np.uint8(np.clip(np.round(rgb), 0, 255)))
        canvas.paste(panel.resize((CT_SIDE, CT_SIDE), Image.LANCZOS), CT_XY)
        draw = ImageDraw.Draw(canvas)
        x0, y0 = HEAT_XY
        draw.rectangle([x0, y0, x0 + heat_w - 1, y0 + heat_h - 1], fill=EMPTY_RGB)
        shown = np.uint8(np.round(heat_image[:, :(n + 1) * COLUMN_PX]))
        canvas.paste(Image.fromarray(shown), (x0, y0))
        draw.rectangle([x0 + n * COLUMN_PX, y0 - 8, x0 + (n + 1) * COLUMN_PX - 1, y0 + heat_h + 7],
                       fill=TEXT_RGB)
        draw.text((x0, y0 - 60), 'Features', font=title_font, fill=TEXT_RGB, anchor='ls')
        draw.text((x0, y0 - 18), '2048 per slice', font=label_font, fill=MUTED_RGB, anchor='ls')
        if label:
            draw.text(label_xy, f'Slice {n + 1} of {count}', font=label_font, fill=MUTED_RGB,
                      anchor='ls')
        return np.asarray(canvas)

    rendered = [frame(n) for n in range(count)]
    frames_dir = RUN_DIR / 'frames'
    frames_dir.mkdir(exist_ok=True)
    Image.fromarray(rendered[POSTER_SLICE]).save(frames_dir / 'poster.png')

    # One frame per slice, a hold on the finished panel, then a cross-dissolve of
    # the rendered RGB frames back to the first one, so the loop has no seam. The
    # outgoing slice label fades out over the first half and the next one fades in
    # over the second half.
    sequence = [image for image in rendered for _ in range(FRAMES_PER_SLICE)]
    sequence += [rendered[-1]] * HOLD
    last, first = frame(count - 1, label=False), frame(0, label=False)
    last_label, first_label = label_coverage(count - 1), label_coverage(0)
    muted = np.asarray(MUTED_RGB, dtype=np.float64)

    def smoothstep(t):
        return t * t * (3 - 2 * t)

    for k in range(DISSOLVE):
        t = (k + 1) / (DISSOLVE + 1)
        mixed = (1 - smoothstep(t)) * last.astype(np.float64) + smoothstep(t) * first
        for coverage, alpha in ((last_label, smoothstep(max(0.0, 1 - 2 * t))),
                                (first_label, smoothstep(max(0.0, 2 * t - 1)))):
            mixed = mixed * (1 - alpha * coverage) + muted * alpha * coverage
        sequence.append(np.uint8(np.round(mixed)))
    video, poster = ASSETS / 'feature-scroll.mp4', ASSETS / 'feature-scroll-poster.webp'
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    encode = ['-c:v', 'libx264', '-preset', 'veryslow', '-crf', str(CRF), '-pix_fmt', 'yuv420p',
              '-vf', VIDEO_FILTER, '-colorspace', 'bt709', '-color_primaries', 'bt709',
              '-color_trc', 'bt709', '-color_range', 'tv', '-movflags', '+faststart', '-an',
              '-map_metadata', '-1']
    process = subprocess.Popen(
        [ffmpeg, '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
         '-s', f'{SIZE[0]}x{SIZE[1]}', '-r', str(FPS), '-i', '-', *encode, str(video)],
        stdin=subprocess.PIPE)
    for image in sequence:
        process.stdin.write(image.tobytes())
    process.stdin.close()
    if process.wait() != 0:
        raise RuntimeError('ffmpeg failed')
    if video.stat().st_size > MAX_VIDEO_BYTES:
        raise ValueError(f'Video exceeds {MAX_VIDEO_BYTES} bytes; raise CRF')
    Image.fromarray(rendered[POSTER_SLICE]).save(poster, quality=85, method=6)
    ffmpeg_version = subprocess.run([ffmpeg, '-version'], capture_output=True, text=True,
                                    check=True).stdout.splitlines()[0].split(' Copyright')[0]

    record = {
        'schema_version': 1,
        'method': 'radimagenet-mlx ResNet50 pooled and spatial features for every axial slice '
                  'of one LUNA16 CT, extracted with the published runner',
        'runtime': extracted['runtime'],
        'weights': {'repository': 'MedMLX/radimagenet-mlx',
                    'file': 'RadImageNet-ResNet50_notop.safetensors',
                    'revision': extracted['details']['weights_revision']},
        'source': {
            'dataset': 'LUNA16 subset0', 'dataset_record': 'Zenodo record 3723295',
            'dataset_license': 'CC BY 4.0',
            'citations': ['Setio et al., Medical Image Analysis 42 (2017) 1-13',
                          'Armato et al., Medical Physics 38(2) (2011) 915-931 (LIDC-IDRI, TCIA)'],
            'case_file': extracted['case_file'], 'series_uid': SERIES_UID,
            'derivation': 'Local read-only copy: LUNA16 MetaImage converted to HU NIfTI. '
                          'Not copied into this repository.',
            'shape_ijk': extracted['shape_ijk'], 'spacing_mm_ijk': extracted['spacing_mm_ijk'],
        },
        'inference': {
            'input': 'one 8-bit grayscale PNG per axial slice, superior to inferior: '
                     f'window {WINDOW["center"]}/{WINDOW["width"]} HU, square body crop '
                     f'(rows, cols, side) {extracted["crop_rows_cols_side"]} px; the runner '
                     'resizes it to 224 x 224 itself',
            'slices': extracted['slices'], 'details': extracted['details'],
            'local_artifact': 'dist/feature-scroll-demo/features.npz',
        },
        'display': {
            'renderer': 'docs/hero/render_feature_scroll.py',
            'slices_shown': f'{count} of {extracted["slices"]}, superior to inferior; the '
                            f'{FIRST_SHOWN} most superior slices (shoulder joints) are not '
                            'shown, and principal components and '
                            'feature statistics use the shown slices only',
            'ct_panel': 'the PNG passed to the runner, Lanczos-resized to '
                        f'{CT_SIDE} px, with the 7 x 7 conv5_block3_out map drawn as cells '
                        f'screen-blended at {CELL_OPACITY} inside the body, with darkened cell borders',
            'cell_colors': 'first three principal components of all '
                           f'{count * 49} spatial vectors in the scan as RGB, each scaled by its '
                           '2nd-98th percentile',
            'principal_component_variance_share': [round(v, 4) for v in explained],
            'feature_panel': f'{SHOWN_FEATURES} of 2048 pooled features with the largest variance '
                             'across slices, z-scored per feature over the scan and clipped to '
                             f'{list(Z_RANGE)}, rows ordered by the slice where each feature peaks; '
                             'one column per slice',
            'feature_indices_top_to_bottom': chosen.tolist(),
            'color_palette_rgb': PALETTE,
            'numerical_smoothing': False,
            'frame_size_px': list(SIZE),
            'font': 'Inter SemiBold 40 px, Inter Regular 30 px (SIL Open Font License)',
        },
        'animation': {'fps': FPS, 'frames_per_slice': FRAMES_PER_SLICE, 'hold_frames': HOLD,
                      'dissolve_frames': DISSOLVE,
                      'dissolve': 'smoothstep cross-dissolve of rendered RGB frames from the last '
                                  'slice back to the first; the outgoing slice label fades out over '
                                  'the first half and the incoming label fades in over the second'},
        'encode': {
            'video': {'codec': 'H.264 (libx264)', 'preset': 'veryslow', 'crf': CRF,
                      'pix_fmt': 'yuv420p', 'color': 'BT.709, limited range', 'fps': FPS,
                      'frames': len(sequence), 'size_px': list(SIZE), 'audio': False,
                      'movflags': '+faststart', 'ffmpeg': ffmpeg_version,
                      'bytes': video.stat().st_size},
            'poster': {'format': 'WebP', 'quality': 85, 'method': 6,
                       'slice': POSTER_SLICE + 1, 'bytes': poster.stat().st_size},
        },
        'outputs': {'video': 'site/assets/hero/feature-scroll.mp4',
                    'poster': 'site/assets/hero/feature-scroll-poster.webp'},
        'interpretation': 'Image features from one public, de-identified CT for a software '
                          'visualization. The features carry no diagnostic labels.',
    }
    (ASSETS / 'feature-scroll-run.json').write_text(json.dumps(record, indent=1) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('stage', choices=['extract', 'render'])
    parser.add_argument('--dataset', type=Path, default=Path.home() / 'Documents/datasets/LUNA16')
    args = parser.parse_args()
    {'extract': extract, 'render': render}[args.stage](args)


if __name__ == '__main__':
    main()
