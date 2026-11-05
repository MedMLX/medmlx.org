# /// script
# requires-python = ">=3.13"
# dependencies = ["numpy>=2", "nibabel>=5", "pillow>=12", "scipy>=1.16", "imageio-ffmpeg>=0.6"]
# ///
"""Render the multi-organ MLX Radiomics entropy loop for the website.

Run after docs/hero/compute_radiomics_organs.py:
    uv run docs/hero/render_radiomics_organs.py

Only display transformations are performed here: the liver asset's CT window,
palette, overlay opacity, body mask and crop; one shared color range; 1:1 pixel
placement; cross-dissolves between rendered frames; H.264 and WebP encoding.
Feature maps are never smoothed, modified or recomputed by this renderer.
"""

import json
import os
import subprocess
import tempfile
from importlib import metadata
from pathlib import Path

import nibabel as nib
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
RUN_DIR = ROOT / 'dist/radiomics-organs-demo'
ASSETS = ROOT / 'site/assets/hero'
LIVER_RUN = ASSETS / 'radiomics-run.json'
FEATURE = 'original_firstorder_Entropy'
PALETTE = [(48, 9, 20), (120, 24, 43), (195, 58, 77), (239, 137, 143), (255, 233, 226)]
WINDOW_HU = (-160, 240)
OPACITY = 0.78
SIZE = (800, 520)
PANEL_X = 20
LEGEND_X = 572
FPS, HOLD, DISSOLVE = 24, 48, 12
CRF = 24
# BT.709 matrix for the RGB conversion, and BT.709 tags on every encoded frame.
VIDEO_FILTER = ('scale=out_color_matrix=bt709:out_range=tv,'
                'setparams=range=tv:color_primaries=bt709:color_trc=bt709:colorspace=bt709')
TITLE_RGB = np.array([236, 236, 240], dtype=np.float64)
MAX_VIDEO_BYTES = 700_000
# Frame title and the organ maps it shows. Both kidneys share a frame: their
# maps come from separate runs and lie 95 pixels apart, beyond any kernel.
FRAMES = [('Liver', ('liver',)),
          ('Kidneys', ('right-kidney', 'left-kidney')),
          ('Pancreas', ('pancreas',))]


def read_slice(path):
    """Recover the retained radiological display plane without reorientation."""
    volume = nib.load(path)
    array = np.asarray(volume.dataobj)
    if array.ndim != 3 or array.shape[2] != 1:
        raise ValueError(f'Expected one axial plane: {path}')
    return array[:, :, 0].T, volume.affine


def colors(values):
    """Apply a monotonic sequential palette to the normalized scalar map."""
    stops = np.linspace(0, 1, len(PALETTE))
    return np.stack([np.interp(values, stops, np.asarray(PALETTE)[:, channel])
                     for channel in range(3)], axis=-1)


def font(weight, size):
    """Use Inter (SIL Open Font License) from the MEDMLX_HERO_FONTS directory."""
    path = Path(os.environ['MEDMLX_HERO_FONTS']) / f'Inter-{weight}.ttf'
    return ImageFont.truetype(str(path), size)


def smoothstep(t):
    return t * t * (3 - 2 * t)


def ffmpeg_version(ffmpeg):
    line = subprocess.run([ffmpeg, '-version'], capture_output=True, text=True,
                          check=True).stdout.splitlines()[0]
    return line.split(' Copyright')[0]


def main():
    compute = json.loads((RUN_DIR / 'compute.json').read_text())
    ct, affine = read_slice(RUN_DIR / 'ct.nii.gz')
    if not np.isclose(abs(affine[0, 0]), abs(affine[1, 1])):
        raise ValueError('This asset layout requires square in-plane pixels')

    rois, maps = {}, {}
    for _, slugs in FRAMES:
        for slug in slugs:
            organ = compute['organs'][slug]
            mask, mask_affine = read_slice(RUN_DIR / f'{slug}-roi-main.nii.gz')
            path = ROOT / organ['maps'][FEATURE]['local_artifact']
            feature, feature_affine = read_slice(path)
            if ct.shape != mask.shape or ct.shape != feature.shape:
                raise ValueError('CT, ROI and map must share one pixel grid')
            if not np.allclose(affine, mask_affine) or not np.allclose(affine, feature_affine):
                raise ValueError('CT, ROI and map must share physical geometry')
            roi = mask == 1
            if roi.sum() != organ['roi_selection']['selected_roi_pixels']:
                raise ValueError(f'{slug}: ROI differs from the computed record')
            if not np.isfinite(feature[roi]).all() or not np.all(feature[~roi] == 0):
                raise ValueError('Expected finite ROI values and zero outside the ROI')
            rois[slug], maps[slug] = roi, feature

    # One color range for every frame, so equal colors mean equal entropy.
    union = np.concatenate([maps[slug][rois[slug]] for slug in rois])
    low, high = (float(value) for value in np.percentile(union, [2, 98]))
    low = max(0.0, low)

    # Isolate the body from the scan table and air, retaining every ROI pixel.
    connected, _ = ndimage.label(ct > -300)
    areas = np.bincount(connected.ravel())
    areas[0] = 0
    body = ndimage.binary_fill_holes(connected == areas.argmax())
    if any(np.any(roi & ~body) for roi in rois.values()):
        raise ValueError('Every analysis ROI must lie inside the body component')
    rows, cols = np.where(body)
    crop = (max(0, int(cols.min())-14), max(0, int(rows.min())-14),
            min(ct.shape[1], int(cols.max())+15), min(ct.shape[0], int(rows.max())+15))
    panel_w, panel_h = crop[2] - crop[0], crop[3] - crop[1]
    panel_y = (SIZE[1] - panel_h) // 2
    if PANEL_X + panel_w > LEGEND_X - 24 or panel_h > SIZE[1]:
        raise ValueError('The 1:1 panel does not fit beside the legend')

    gray = np.clip((ct.astype(float) - WINDOW_HU[0]) / (WINDOW_HU[1] - WINDOW_HU[0]), 0, 1)
    base = np.repeat(gray[:, :, None], 3, axis=2) * 255
    name_font, label_font = font('SemiBold', 40), font('Regular', 30)
    ramp_h, ramp_w = 180, 22
    ramp_top = SIZE[1] // 2 - 34
    name_y, caption_y = ramp_top - 96, ramp_top - 34
    labels = (f'{high:.1f} bits', f'{low:.1f} bits')
    for text, face in [(title, name_font) for title, _ in FRAMES] + \
                      [('Local entropy', label_font)] + [(t, label_font) for t in labels]:
        width = face.getbbox(text)[2] + (ramp_w + 14 if text in labels else 0)
        if LEGEND_X + width > SIZE[0] - 16:
            raise ValueError(f'Legend text does not fit: {text}')
    ramp = np.repeat(colors(np.linspace(1, 0, ramp_h))[:, None], ramp_w, axis=1)

    # Untitled frames carry the anatomy and the shared legend; titles are separate
    # coverage layers so the outgoing name can fade out before the next fades in.
    untitled, titles = [], []
    for title, slugs in FRAMES:
        rgb = base.copy()
        for slug in slugs:
            roi = rois[slug]
            mapped = colors(np.clip((maps[slug] - low) / (high - low), 0, 1))
            rgb[roi] = (1 - OPACITY) * rgb[roi] + OPACITY * mapped[roi]
        rgb[~body] = 0
        panel = Image.fromarray(np.uint8(np.clip(rgb, 0, 255))).crop(crop)
        canvas = Image.new('RGB', SIZE, 'black')
        canvas.paste(panel, (PANEL_X, panel_y))
        # The legend stays outside the anatomy and uses the computed map's units.
        draw = ImageDraw.Draw(canvas)
        draw.text((LEGEND_X, caption_y), 'Local entropy', font=label_font, fill='#a1a1a6',
                  anchor='ls')
        canvas.paste(Image.fromarray(np.uint8(ramp)), (LEGEND_X, ramp_top))
        draw.text((LEGEND_X + ramp_w + 14, ramp_top), labels[0], font=label_font,
                  fill='#a1a1a6', anchor='lm')
        draw.text((LEGEND_X + ramp_w + 14, ramp_top + ramp_h), labels[1], font=label_font,
                  fill='#a1a1a6', anchor='lm')
        layer = Image.new('L', SIZE, 0)
        ImageDraw.Draw(layer).text((LEGEND_X, name_y), title, font=name_font, fill=255,
                                   anchor='ls')
        coverage = np.asarray(layer, dtype=np.float64)[:, :, None] / 255
        frame = np.asarray(canvas, dtype=np.float64)
        if np.any(frame[coverage[:, :, 0] > 0]):
            raise ValueError('The title must sit on black, clear of other content')
        untitled.append(frame)
        titles.append(coverage)

    def compose(index, following=None, alpha=0.0, title_out=1.0, title_in=0.0):
        following = index if following is None else following
        frame = ((1 - alpha) * untitled[index] + alpha * untitled[following]
                 + TITLE_RGB * (title_out * titles[index] + title_in * titles[following]))
        return np.uint8(np.clip(np.round(frame), 0, 255))

    held = [compose(index) for index in range(len(FRAMES))]
    frames_dir = RUN_DIR / 'frames'
    frames_dir.mkdir(exist_ok=True)
    for index, (title, _) in enumerate(FRAMES):
        Image.fromarray(held[index]).save(frames_dir / f'{index}-{title.lower()}.png')

    # Hold each frame, then cross-dissolve the rendered RGB frames into the next.
    # The last dissolve leads into frame 0, so the loop has no seam.
    steps = [(k + 1) / (DISSOLVE + 1) for k in range(DISSOLVE)]
    video = ASSETS / 'radiomics-organs.mp4'
    poster = ASSETS / 'radiomics-organs-poster.webp'
    ffmpeg = __import__('imageio_ffmpeg').get_ffmpeg_exe()
    encode = ['-c:v', 'libx264', '-preset', 'veryslow', '-crf', str(CRF), '-pix_fmt', 'yuv420p',
              '-vf', VIDEO_FILTER, '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
              '-color_range', 'tv', '-movflags', '+faststart', '-an', '-map_metadata', '-1']
    count = 0
    with tempfile.TemporaryDirectory() as scratch:
        process = subprocess.Popen(
            [ffmpeg, '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
             '-s', f'{SIZE[0]}x{SIZE[1]}', '-r', str(FPS), '-i', '-', *encode,
             str(Path(scratch) / 'out.mp4')], stdin=subprocess.PIPE)
        for index in range(len(FRAMES)):
            following = (index + 1) % len(FRAMES)
            for _ in range(HOLD):
                process.stdin.write(held[index].tobytes())
            for step in steps:
                frame = compose(index, following, smoothstep(step),
                                smoothstep(max(0.0, 1 - 2 * step)),
                                smoothstep(max(0.0, 2 * step - 1)))
                process.stdin.write(frame.tobytes())
            count += HOLD + DISSOLVE
        process.stdin.close()
        if process.wait() != 0:
            raise RuntimeError('ffmpeg failed')
        video.parent.mkdir(parents=True, exist_ok=True)
        os.replace(Path(scratch) / 'out.mp4', video)
    if video.stat().st_size > MAX_VIDEO_BYTES:
        raise ValueError(f'Video exceeds {MAX_VIDEO_BYTES} bytes; raise CRF')
    Image.fromarray(held[0]).save(poster, quality=85, method=6)

    liver_display = json.loads(LIVER_RUN.read_text())['display']
    organs = {}
    for slug, organ in compute['organs'].items():
        entry = organ['maps'][FEATURE]
        organs[slug] = {
            **{key: organ[key] for key in ('label', 'name', 'roi_selection', 'execution',
                                          'wall_seconds')},
            'roi_local_artifact': f'dist/radiomics-organs-demo/{slug}-roi-main.nii.gz',
            'entropy_map': {**entry, 'percentiles_2_50_98_bits': [
                float(v) for v in np.percentile(maps[slug][rois[slug]], [2, 50, 98])]},
        }
    record = {
        'schema_version': 1,
        'method': compute['method'],
        'job': compute['job'],
        'runtime': compute['runtime'],
        'source': compute['source'],
        'label_map': compute['label_map'],
        'organ_selection': compute['organ_selection'],
        'execution': compute['execution'],
        'organs': organs,
        'reference_check': compute['reference_check'],
        'display': {
            'renderer': 'docs/hero/render_radiomics_organs.py',
            'feature': FEATURE, 'units': 'bits', 'ct_window_hu': list(WINDOW_HU),
            'color_range_rule': '2nd-98th percentile of the union of every displayed ROI value '
                                f'({", ".join(rois)}), lower bound floored at 0; one range '
                                'for every frame',
            'color_range_percentiles': [2, 98],
            'color_range_bits': [low, high],
            'union_roi_pixels': int(union.size),
            'union_feature_range_bits': [float(union.min()), float(union.max())],
            'union_pixels_clipped': {'below': int((union < low).sum()),
                                     'above': int((union > high).sum())},
            'color_palette_rgb': PALETTE, 'overlay_opacity': OPACITY,
            'body_mask': 'largest CT > -300 HU component, holes filled; contains every '
                         'analysis ROI; pixels outside it set to black',
            'source_crop_xyxy': list(crop),
            'source_crop_matches_liver_asset': list(crop) == liver_display['source_crop_xyxy'],
            'panel_xywh_px': [PANEL_X, panel_y, panel_w, panel_h],
            'display_resampling': 'none; the cropped panel is placed at 1:1 source pixels',
            'numerical_smoothing': False,
            'frame_size_px': list(SIZE), 'background': 'black',
            'legend': {'font': 'Inter SemiBold 40 px (organ), Inter Regular 30 px (labels)',
                       'font_source': 'Inter, SIL Open Font License',
                       'text': ['frame title', 'Local entropy', *labels],
                       'ramp_px': [ramp_w, ramp_h]},
        },
        'animation': {
            'fps': FPS, 'hold_frames': HOLD, 'dissolve_frames': DISSOLVE,
            'hold_seconds': HOLD / FPS, 'dissolve_seconds': DISSOLVE / FPS,
            'dissolve': f'smoothstep cross-dissolve of the rendered RGB frames, alpha = '
                        f's((k+1)/{DISSOLVE + 1}) for k = 0..{DISSOLVE - 1}; feature values are '
                        'never blended or interpolated',
            'title': 'the outgoing organ name fades out over the first half of each dissolve '
                     'and the incoming name fades in over the second half; the ramp and its '
                     'labels are identical in every frame',
            'order': [{'title': title, 'organs': list(slugs),
                       'start_frame': index * (HOLD + DISSOLVE),
                       'start_seconds': index * (HOLD + DISSOLVE) / FPS}
                      for index, (title, slugs) in enumerate(FRAMES)],
            'loop_frames': count, 'loop_seconds': count / FPS,
            'loop': 'the last dissolve leads into frame 0, which is the poster',
        },
        'encode': {
            'video': {'codec': 'H.264 (libx264)', 'preset': 'veryslow', 'crf': CRF,
                      'pix_fmt': 'yuv420p', 'color': 'BT.709, limited range', 'fps': FPS,
                      'frames': count, 'size_px': list(SIZE), 'audio': False,
                      'movflags': '+faststart', 'ffmpeg': ffmpeg_version(ffmpeg),
                      'imageio_ffmpeg': metadata.version('imageio-ffmpeg'),
                      'bytes': video.stat().st_size},
            'poster': {'format': 'WebP', 'quality': 85, 'method': 6, 'frame': 0,
                       'size_px': list(SIZE), 'bytes': poster.stat().st_size},
        },
        'outputs': {'video': 'site/assets/hero/radiomics-organs.mp4',
                    'poster': 'site/assets/hero/radiomics-organs-poster.webp'},
        'interpretation': 'One axial plane for a software visualization. Not a clinical finding, '
                          'comparison, or performance validation. Each map is computed from its '
                          'own selected ROI neighborhoods; the shared color scale only keeps '
                          'colors consistent between frames.',
    }
    (ASSETS / 'radiomics-organs-run.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({key: record['display'][key] for key in (
        'color_range_bits', 'union_roi_pixels', 'union_pixels_clipped', 'source_crop_xyxy',
        'source_crop_matches_liver_asset', 'panel_xywh_px')}, indent=2))
    print(json.dumps(record['encode'], indent=2))


if __name__ == '__main__':
    main()
