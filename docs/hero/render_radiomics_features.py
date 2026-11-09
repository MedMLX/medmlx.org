# /// script
# requires-python = ">=3.13"
# dependencies = ["numpy>=2", "nibabel>=5", "pillow>=12", "scipy>=1.16", "imageio-ffmpeg>=0.6"]
# ///
"""Render the MLX Radiomics feature-sweep loop for the website.

Run after docs/hero/compute_radiomics_features.py:
    MEDMLX_HERO_FONTS=/path/to/fonts uv run docs/hero/render_radiomics_features.py

MEDMLX_HERO_FONTS holds Inter-SemiBold.ttf, Inter-Regular.ttf and
IBMPlexMono-Regular.ttf. One liver ROI is shown under one feature map at a
time, each with its own color range. Only display transformations are performed:
the liver asset's CT window, palette, overlay opacity, body mask and crop; 1:1
pixel placement; cross-dissolves between rendered frames; H.264 and WebP
encoding. Feature maps are never smoothed, modified or recomputed here.
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
RUN_DIR = ROOT / 'dist/radiomics-features-demo'
ASSETS = ROOT / 'site/assets/hero'
PALETTE = [(48, 9, 20), (120, 24, 43), (195, 58, 77), (239, 137, 143), (255, 233, 226)]
WINDOW_HU = (-160, 240)
OPACITY = 0.78
SIZE = (800, 520)
PANEL_X = 20
LEGEND_X = 572
FPS, HOLD, DISSOLVE = 24, 48, 14
CRF = 24
VIDEO_FILTER = ('scale=out_color_matrix=bt709:out_range=tv,'
                'setparams=range=tv:color_primaries=bt709:color_trc=bt709:colorspace=bt709')
TEXT_RGB = np.array([236, 236, 240], dtype=np.float64)
MUTED_RGB = np.array([161, 161, 166], dtype=np.float64)
MAX_VIDEO_BYTES = 900_000
# Display order: family title, feature key, units for the ramp labels.
FRAMES = [('First order', 'original_firstorder_Mean', 'HU'),
          ('First order', 'original_firstorder_Entropy', 'bits'),
          ('GLCM', 'original_glcm_Contrast', ''),
          ('GLRLM', 'original_glrlm_RunEntropy', 'bits'),
          ('GLSZM', 'original_glszm_ZoneEntropy', 'bits'),
          ('NGTDM', 'original_ngtdm_Busyness', '')]


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


def font(name, size):
    return ImageFont.truetype(str(Path(os.environ['MEDMLX_HERO_FONTS']) / f'{name}.ttf'), size)


def number(value):
    """Three significant figures, without scientific notation in this value range."""
    return f'{value:#.3g}' if abs(value) < 1000 else f'{value:.0f}'


def smoothstep(t):
    return t * t * (3 - 2 * t)


def ffmpeg_version(ffmpeg):
    line = subprocess.run([ffmpeg, '-version'], capture_output=True, text=True,
                          check=True).stdout.splitlines()[0]
    return line.split(' Copyright')[0]


def main():
    compute = json.loads((RUN_DIR / 'compute.json').read_text())
    ct, affine = read_slice(RUN_DIR / 'ct.nii.gz')
    mask, mask_affine = read_slice(RUN_DIR / 'liver-roi-main.nii.gz')
    roi = mask == 1
    if roi.sum() != compute['roi_selection']['selected_roi_pixels']:
        raise ValueError('ROI differs from the computed record')
    if not np.allclose(affine, mask_affine):
        raise ValueError('CT and ROI must share physical geometry')

    maps = {}
    for _, key, _ in FRAMES:
        values, map_affine = read_slice(ROOT / compute['maps'][key]['local_artifact'])
        if values.shape != ct.shape or not np.allclose(affine, map_affine):
            raise ValueError(f'{key}: map must share the CT grid')
        if not np.isfinite(values[roi]).all() or not np.all(values[~roi] == 0):
            raise ValueError(f'{key}: expected finite ROI values and zero outside the ROI')
        maps[key] = values

    connected, _ = ndimage.label(ct > -300)
    areas = np.bincount(connected.ravel())
    areas[0] = 0
    body = ndimage.binary_fill_holes(connected == areas.argmax())
    if np.any(roi & ~body):
        raise ValueError('The ROI must lie inside the body component')
    rows, cols = np.where(body)
    crop = (max(0, int(cols.min())-14), max(0, int(rows.min())-14),
            min(ct.shape[1], int(cols.max())+15), min(ct.shape[0], int(rows.max())+15))
    panel_w, panel_h = crop[2] - crop[0], crop[3] - crop[1]
    panel_y = (SIZE[1] - panel_h) // 2
    if PANEL_X + panel_w > LEGEND_X - 24 or panel_h > SIZE[1]:
        raise ValueError('The 1:1 panel does not fit beside the legend')

    gray = np.clip((ct.astype(float) - WINDOW_HU[0]) / (WINDOW_HU[1] - WINDOW_HU[0]), 0, 1)
    base = np.repeat(gray[:, :, None], 3, axis=2) * 255
    title_font, name_font = font('Inter-SemiBold', 34), font('IBMPlexMono-Regular', 26)
    label_font = font('Inter-Regular', 24)
    ramp_h, ramp_w = 170, 20
    ramp_top = 228
    title_y, name_y, value_y = 140, 184, ramp_top + ramp_h + 62
    ramp = np.repeat(colors(np.linspace(1, 0, ramp_h))[:, None], ramp_w, axis=1)

    def text_layer(items):
        """Coverage layers for (text, font, anchor point, anchor) items, one per color."""
        layer = Image.new('L', SIZE, 0)
        draw = ImageDraw.Draw(layer)
        for text, face, xy, anchor in items:
            draw.text(xy, text, font=face, fill=255, anchor=anchor)
        return np.asarray(layer, dtype=np.float64)[:, :, None] / 255

    frames, display = [], []
    for title, key, units in FRAMES:
        inside = maps[key][roi]
        low, high = (float(v) for v in np.percentile(inside, [2, 98]))
        rgb = base.copy()
        mapped = colors(np.clip((maps[key] - low) / (high - low), 0, 1))
        rgb[roi] = (1 - OPACITY) * rgb[roi] + OPACITY * mapped[roi]
        rgb[~body] = 0
        canvas = Image.new('RGB', SIZE, 'black')
        canvas.paste(Image.fromarray(np.uint8(np.clip(rgb, 0, 255))).crop(crop), (PANEL_X, panel_y))
        canvas.paste(Image.fromarray(np.uint8(ramp)), (LEGEND_X, ramp_top))
        name = key.split('_', 2)[2]
        suffix = f' {units}' if units else ''
        labels = (f'{number(high)}{suffix}', f'{number(low)}{suffix}')
        value = f'Whole ROI {number(compute["maps"][key]["roi_value"])}'
        label_x = LEGEND_X + ramp_w + 12
        muted = text_layer([(labels[0], label_font, (label_x, ramp_top), 'lm'),
                            (labels[1], label_font, (label_x, ramp_top + ramp_h), 'lm'),
                            (value, label_font, (LEGEND_X, value_y), 'ls')])
        bright = text_layer([(title, title_font, (LEGEND_X, title_y), 'ls')])
        # The mono feature name types in one character at a time during the dissolve.
        typed = [text_layer([(name[:count], name_font, (LEGEND_X, name_y), 'ls')])
                 for count in range(len(name) + 1)]
        for text, face in [(title, title_font), (name, name_font), (value, label_font)] + \
                          [(t, label_font) for t in labels]:
            right = (label_x if text in labels else LEGEND_X) + face.getbbox(text)[2]
            if right > SIZE[0] - 12:
                raise ValueError(f'Legend text does not fit: {text}')
        frame = np.asarray(canvas, dtype=np.float64)
        if np.any(frame[(muted + bright + typed[-1])[:, :, 0] > 0]):
            raise ValueError('Legend text must sit on black, clear of other content')
        frames.append({'base': frame, 'muted': muted, 'bright': bright, 'typed': typed})
        display.append({'feature': key, 'family_title': title, 'units': units or None,
                        'color_range': [low, high], 'labels': [*labels, value],
                        'roi_pixels_clipped': {'below': int((inside < low).sum()),
                                               'above': int((inside > high).sum())}})

    def compose(index, following=None, alpha=0.0, text_out=1.0, text_in=0.0, typed_in=0):
        following = index if following is None else following
        a, b = frames[index], frames[following]
        typed_out = a['typed'][-1]
        frame = ((1 - alpha) * a['base'] + alpha * b['base']
                 + MUTED_RGB * (text_out * a['muted'] + text_in * b['muted'])
                 + TEXT_RGB * (text_out * (a['bright'] + typed_out) + text_in * b['bright'])
                 + TEXT_RGB * (b['typed'][typed_in] if following != index else 0))
        return np.uint8(np.clip(np.round(frame), 0, 255))

    held = [compose(index) for index in range(len(FRAMES))]
    frames_dir = RUN_DIR / 'frames'
    frames_dir.mkdir(exist_ok=True)
    for index, (_, key, _) in enumerate(FRAMES):
        Image.fromarray(held[index]).save(frames_dir / f'{index}-{key}.png')

    video = ASSETS / 'radiomics-features.mp4'
    poster = ASSETS / 'radiomics-features-poster.webp'
    ffmpeg = __import__('imageio_ffmpeg').get_ffmpeg_exe()
    encode = ['-c:v', 'libx264', '-preset', 'veryslow', '-crf', str(CRF), '-pix_fmt', 'yuv420p',
              '-vf', VIDEO_FILTER, '-colorspace', 'bt709', '-color_primaries', 'bt709',
              '-color_trc', 'bt709', '-color_range', 'tv', '-movflags', '+faststart', '-an',
              '-map_metadata', '-1']
    count = 0
    with tempfile.TemporaryDirectory() as scratch:
        process = subprocess.Popen(
            [ffmpeg, '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
             '-s', f'{SIZE[0]}x{SIZE[1]}', '-r', str(FPS), '-i', '-', *encode,
             str(Path(scratch) / 'out.mp4')], stdin=subprocess.PIPE)
        for index in range(len(FRAMES)):
            following = (index + 1) % len(FRAMES)
            length = len(frames[following]['typed']) - 1
            for _ in range(HOLD):
                process.stdin.write(held[index].tobytes())
            # Map and labels cross-dissolve; the outgoing name fades over the first half
            # and the incoming name types in over the second half.
            for k in range(DISSOLVE):
                step = (k + 1) / (DISSOLVE + 1)
                second = max(0.0, 2 * step - 1)
                frame = compose(index, following, smoothstep(step),
                                smoothstep(max(0.0, 1 - 2 * step)), smoothstep(second),
                                round(length * second))
                process.stdin.write(frame.tobytes())
            count += HOLD + DISSOLVE
        process.stdin.close()
        if process.wait() != 0:
            raise RuntimeError('ffmpeg failed')
        os.replace(Path(scratch) / 'out.mp4', video)
    if video.stat().st_size > MAX_VIDEO_BYTES:
        raise ValueError(f'Video exceeds {MAX_VIDEO_BYTES} bytes; raise CRF')
    Image.fromarray(held[0]).save(poster, quality=85, method=6)

    record = {
        'schema_version': 1,
        'method': compute['method'],
        'job': compute['job'],
        'runtime': compute['runtime'],
        'source': compute['source'],
        'roi_selection': compute['roi_selection'],
        'maps': {key: compute['maps'][key] for _, key, _ in FRAMES},
        'not_shown': sorted(set(compute['maps']) - {key for _, key, _ in FRAMES}),
        'display': {
            'renderer': 'docs/hero/render_radiomics_features.py',
            'ct_window_hu': list(WINDOW_HU),
            'color_range_rule': "2nd-98th percentile of each map's ROI values; each frame has "
                                'its own range, so colors compare only within a frame',
            'frames': display,
            'roi_value': "the whole-ROI feature value from the ROI-mode run, which need not lie "
                         "within the voxel map's range",
            'color_palette_rgb': PALETTE, 'overlay_opacity': OPACITY,
            'body_mask': 'largest CT > -300 HU component, holes filled; contains the ROI; '
                         'pixels outside it set to black',
            'source_crop_xyxy': list(crop),
            'panel_xywh_px': [PANEL_X, panel_y, panel_w, panel_h],
            'display_resampling': 'none; the cropped panel is placed at 1:1 source pixels',
            'numerical_smoothing': False,
            'frame_size_px': list(SIZE), 'background': 'black',
            'fonts': 'Inter SemiBold 34 px (family), IBM Plex Mono 26 px (feature), Inter '
                     'Regular 24 px (labels); SIL Open Font License',
        },
        'animation': {
            'fps': FPS, 'hold_frames': HOLD, 'dissolve_frames': DISSOLVE,
            'dissolve': f'smoothstep cross-dissolve of the rendered RGB frames over {DISSOLVE} '
                        'frames; feature values are never blended before color mapping',
            'text': 'outgoing labels fade out over the first half of each dissolve; incoming '
                    'labels fade in and the feature name types in over the second half',
            'loop_frames': count, 'loop_seconds': count / FPS,
            'loop': 'the last dissolve leads into frame 0, which is the poster',
        },
        'encode': {
            'video': {'codec': 'H.264 (libx264)', 'preset': 'veryslow', 'crf': CRF,
                      'pix_fmt': 'yuv420p', 'color': 'BT.709, limited range', 'fps': FPS,
                      'frames': count, 'size_px': list(SIZE), 'audio': False,
                      'ffmpeg': ffmpeg_version(ffmpeg),
                      'imageio_ffmpeg': metadata.version('imageio-ffmpeg'),
                      'bytes': video.stat().st_size},
            'poster': {'format': 'WebP', 'quality': 85, 'method': 6, 'frame': 0,
                       'bytes': poster.stat().st_size},
        },
        'outputs': {'video': 'site/assets/hero/radiomics-features.mp4',
                    'poster': 'site/assets/hero/radiomics-features-poster.webp'},
    }
    (ASSETS / 'radiomics-features-run.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'frames': display, 'encode': record['encode']}, indent=2))


if __name__ == '__main__':
    main()
