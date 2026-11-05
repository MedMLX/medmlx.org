# /// script
# requires-python = ">=3.13"
# dependencies = ["numpy>=2", "nibabel>=5", "pillow>=12", "scipy>=1.16"]
# ///
"""Render a native MLX Radiomics map over its source CT for the website.

Run after the MedMLX extraction recorded in radiomics-run.json:
    uv run docs/hero/render_radiomics.py

Only display transformations are performed here. The feature NIfTI is never
smoothed, modified, or recomputed by this renderer.
"""

import argparse
import json
import os
from pathlib import Path

import nibabel as nib
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
FEATURE = "original_firstorder_Entropy"
PALETTE = [(48, 9, 20), (120, 24, 43), (195, 58, 77), (239, 137, 143), (255, 233, 226)]


def read_slice(path):
    """Recover the retained radiological display plane without reorientation."""
    volume = nib.load(path)
    array = np.asarray(volume.dataobj)
    if array.ndim != 3 or array.shape[2] != 1:
        raise ValueError(f"Expected one axial plane: {path}")
    return array[:, :, 0].T, volume.affine


def colors(values):
    """Apply a monotonic sequential palette to the normalized scalar map."""
    stops = np.linspace(0, 1, len(PALETTE))
    return np.stack([np.interp(values, stops, np.asarray(PALETTE)[:, channel])
                     for channel in range(3)], axis=-1)


def font(size):
    """Use Inter (SIL Open Font License) from the MEDMLX_HERO_FONTS directory."""
    path = Path(os.environ['MEDMLX_HERO_FONTS']) / 'Inter-Regular.ttf'
    return ImageFont.truetype(str(path), size)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, default=ROOT / 'dist/radiomics-demo')
    parser.add_argument('--output', type=Path, default=ROOT / 'site/assets/hero/radiomics-texture.webp')
    args = parser.parse_args()
    ct, affine = read_slice(args.run_dir / 'ct.nii.gz')
    mask, mask_affine = read_slice(args.run_dir / 'liver-roi-main.nii.gz')
    feature_path = args.run_dir / f'computed-main/maps/{FEATURE}.nii.gz'
    feature, feature_affine = read_slice(feature_path)
    if ct.shape != mask.shape or ct.shape != feature.shape:
        raise ValueError('CT, ROI and map must share one pixel grid')
    if not np.allclose(affine, mask_affine) or not np.allclose(affine, feature_affine):
        raise ValueError('CT, ROI and map must share physical geometry')
    if not np.isclose(abs(affine[0, 0]), abs(affine[1, 1])):
        raise ValueError('This asset layout requires square in-plane pixels')
    roi = mask == 1
    if not np.isfinite(feature[roi]).all() or not np.all(feature[~roi] == 0):
        raise ValueError('Expected finite ROI values and zero outside the ROI')

    # One fixed soft-tissue window, shared with the retained source figure.
    gray = np.clip((ct.astype(float) + 160) / 400, 0, 1)
    rgb = np.repeat(gray[:, :, None], 3, axis=2) * 255
    low, high = np.percentile(feature[roi], [2, 98])
    low = max(0.0, float(low))
    normalized = np.clip((feature-low) / (high-low), 0, 1)
    mapped = colors(normalized)
    rgb[roi] = .22 * rgb[roi] + .78 * mapped[roi]

    # Isolate the body from the scan table and air, retaining every ROI pixel.
    connected, _ = ndimage.label(ct > -300)
    areas = np.bincount(connected.ravel())
    areas[0] = 0
    body = ndimage.binary_fill_holes(connected == areas.argmax())
    if np.any(roi & ~body):
        raise ValueError('The analysis ROI must lie inside the body component')
    rgb[~body] = 0
    rows, cols = np.where(body)
    crop = (max(0, int(cols.min())-14), max(0, int(rows.min())-14),
            min(ct.shape[1], int(cols.max())+15), min(ct.shape[0], int(rows.max())+15))
    panel = Image.fromarray(np.uint8(np.clip(rgb, 0, 255))).crop(crop)
    # Resample the completed display uniformly; the numerical map stays untouched.
    target_width = 1100
    height = round(panel.height * target_width / panel.width)
    panel = panel.resize((target_width, height), Image.Resampling.LANCZOS)
    canvas = Image.new('RGB', (1200, height + 160), 'black')
    canvas.paste(panel, (50, 20))

    # The legend stays outside the anatomy and uses the computed map's units.
    y = height + 60
    draw = ImageDraw.Draw(canvas)
    draw.text((72, y), 'Local entropy', font=font(28), fill='#d7d7dc')
    draw.text((1128, y), 'bits', font=font(25), fill='#a1a1a6', anchor='ra')
    ramp = np.repeat(colors(np.linspace(0, 1, 480))[None], 8, axis=0)
    canvas.paste(Image.fromarray(np.uint8(ramp)), (360, y+8))
    draw.text((346, y+12), f'{low:.1f}', font=font(24), fill='#a1a1a6', anchor='rm')
    draw.text((854, y+12), f'{high:.1f}', font=font(24), fill='#a1a1a6', anchor='lm')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(args.output, quality=92, method=6)
    canvas.save(args.output.with_suffix('.png'))
    display = {
        'renderer': 'docs/hero/render_radiomics.py',
        'feature': FEATURE, 'units': 'bits', 'ct_window_hu': [-160, 240],
        'color_range_percentiles': [2, 98], 'color_range_bits': [float(low), float(high)],
        'feature_range_bits': [float(feature[roi].min()), float(feature[roi].max())],
        'color_palette_rgb': PALETTE, 'overlay_opacity': .78,
        'body_mask': 'largest CT > -300 HU component, holes filled; contains entire analysis ROI',
        'source_crop_xyxy': crop, 'display_resampling': 'uniform Lanczos',
        'numerical_smoothing': False,
        'output_size_px': list(canvas.size),
    }
    (args.run_dir / 'display.json').write_text(json.dumps(display, indent=2) + '\n')
    print(json.dumps(display, indent=2))


if __name__ == '__main__':
    main()
