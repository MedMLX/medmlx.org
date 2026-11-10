# /// script
# requires-python = ">=3.13,<3.15"
# dependencies = [
#     "medsam2-mlx==0.2.8",
#     "numpy>=2",
#     "nibabel>=5",
#     "pillow>=12",
#     "scipy>=1.16",
# ]
# ///
"""Render the TotalSegmentator and MedSAM2 images on the homepage's featured model cards.

Run from the repository root:
    uv run docs/hero/render_featured.py anatomy
    uv run docs/hero/render_featured.py panels
    uv run docs/hero/render_featured.py medsam --dataset <LUNA16 folder>
    uv run docs/hero/render_featured.py cards
    uv run docs/hero/render_featured.py film-panels nodule medsam lesion synthetic

`anatomy` crops the torso from the 3D surface panel of the tagged
totalsegmentator-mlx documentation figure. That panel's render is clipped flat
on its right and lower edges, so the crop stops above the hips and the lowest
20% fades to black. The documentation-panel black level and saturation from
sources.json are applied, as for the other panels.

`panels` crops the text-prompt panel of the tagged biomedparse-mlx abdomen
figure, inside its frame, flipped vertically to standard display orientation
(the figure shows posterior at the top), and the axial panel of the tagged
segresnet-mlx brain tumor figure, both with the same tone.

`medsam` runs the published medsam2-mlx runner on one LUNA16 CT, prompted with a
box drawn around the LUNA16 annotation of its 25 mm nodule, and shows the prompt
slice with the predicted mask and the box. The mask is never edited or smoothed.

`film-panels` re-crops the named homepage film panels from the figure, revision and
crop recorded for each in sources.json, with the documentation-panel tone.

`cards` writes the featured-*.webp images, used by the homepage featured cards and the
model pages, on one canvas and scale.
"""

import argparse
import json
import platform
import urllib.request
from importlib.metadata import version
from io import BytesIO
from pathlib import Path

import nibabel as nib
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'site/assets/hero'
RUN_DIR = ROOT / 'dist/medsam-slice-demo'

ANATOMY_SOURCE = ('MedMLX/totalsegmentator-mlx', 'v0.1.6', 'docs/example.png')
# Fractions of the figure (left, top, right, bottom): the 3D panel's torso, neck to hips.
ANATOMY_CROP = (0.044, 0.1003, 0.238, 0.6217)
ANATOMY_FADE = 0.2
# The middle "Four text prompts" panel of the BioMedParse figure, inside its frame.
PROMPT_SOURCE = ('MedMLX/biomedparse-mlx', 'v0.1.5', 'docs/example-abdomen.png')
PROMPT_CROP = (0.337, 0.2, 0.628, 0.8)
# The axial panel of the SegResNet brain tumor figure, below its heading.
SEGRESNET_SOURCE = ('MedMLX/segresnet-mlx', 'v0.3.3', 'docs/example.png')
SEGRESNET_CROP = (0.008, 0.105, 0.258, 0.89)

CASE_FILE = 'nifti/nodule_01_25mm.nii.gz'
SERIES_UID = '1.3.6.1.4.1.14519.5.2.1.6279.6001.511347030803753100045216493273'
NODULE_LPS_MM = (60.77506053, 74.1239696, -214.7823466)
NODULE_DIAMETER_MM = 25.23320204
BOX_MARGIN = 1.2  # box side as a multiple of the annotated diameter
HU_WINDOW = (-1350.0, 150.0)  # lung window for the model input
# Soft-tissue display window, as on the Detection and Segmentation cards.
DISPLAY_WINDOW = (-160.0, 240.0)
MASK_RGB, BOX_RGB, MASK_OPACITY, BOX_WIDTH = (240, 206, 120), (86, 196, 214), 0.7, 8
UPSCALE = 2


def documentation_tone(rgb):
    """The black-level subtraction and desaturation recorded in sources.json."""
    video = json.loads((ASSETS / 'sources.json').read_text())['video']
    black, saturation = video['black_level_subtraction'], video['color_saturation']
    rgb = np.clip(rgb - black, 0, None) * 255 / (255 - black)
    gray = rgb.mean(axis=2, keepdims=True)
    return gray + saturation * (rgb - gray)


def tagged_figure(source, crop):
    """Download a documentation figure at a release tag or commit and crop it by fractions."""
    repository, tag, path = source
    url = f'https://raw.githubusercontent.com/{repository}/{tag}/{path}'
    with urllib.request.urlopen(url, timeout=60) as response:
        figure = Image.open(BytesIO(response.read())).convert('RGBA')
    flat = Image.new('RGB', figure.size)
    flat.paste(figure, mask=figure.split()[3])
    w, h = flat.size
    box = tuple(round(f * s) for f, s in zip(crop, (w, h, w, h)))
    print(f'{url} crop {box}')
    return flat.crop(box)


def save_panel(panel, name):
    rgb = documentation_tone(np.asarray(panel, dtype=np.float64))
    Image.fromarray(np.uint8(np.clip(np.round(rgb), 0, 255))).save(
        ASSETS / f'{name}.webp', quality=88, method=6)


def panels(_args):
    """Model-page panels cropped from tagged figures, with the documentation-panel tone.

    The BioMedParse figure shows the slice with posterior at the top (spine up,
    kidneys behind it). A vertical flip gives the standard display, anterior at the
    top, and keeps patient right on image left.
    """
    save_panel(np.asarray(tagged_figure(PROMPT_SOURCE, PROMPT_CROP))[::-1], 'biomedparse-panel')
    save_panel(tagged_figure(SEGRESNET_SOURCE, SEGRESNET_CROP), 'segresnet-axial')


def film_panels(args):
    """Homepage film panels re-cropped from the sources.json entries named on the command line."""
    sources = {s['name']: s for s in json.loads((ASSETS / 'sources.json').read_text())['sources']}
    for name in args.names:
        source = sources[name]
        panel = np.asarray(tagged_figure((source['repository'], source['tag'], source['path']), source['crop']))
        save_panel(panel[::-1] if source.get('flip_vertical') else panel, name)


def anatomy(_args):
    figure = tagged_figure(ANATOMY_SOURCE, ANATOMY_CROP)
    rgb = documentation_tone(np.asarray(figure, dtype=np.float64))
    rows = rgb.shape[0]
    fade = np.clip((rows - np.arange(rows)) / (ANATOMY_FADE * rows), 0, 1)
    rgb *= (fade * fade * (3 - 2 * fade))[:, None, None]
    Image.fromarray(np.uint8(np.clip(np.round(rgb), 0, 255))).save(
        ASSETS / 'anatomy-torso.webp', quality=88, method=6)


def medsam(args):
    from medsam2_mlx.medmlx import run

    case = args.dataset / CASE_FILE
    image = nib.load(case)
    if nib.aff2axcodes(image.affine) != ('L', 'P', 'S'):
        raise ValueError('Expected LPS-ordered voxels')
    # The NIfTI affine is RAS; LUNA16 annotations are LPS world millimeters.
    x, y, z = NODULE_LPS_MM
    i, j, k = (np.linalg.inv(image.affine) @ np.array([-x, -y, z, 1.0]))[:3]
    half = BOX_MARGIN * NODULE_DIAMETER_MM / image.header.get_zooms()[0] / 2
    box = [round(i - half), round(j - half), round(i + half), round(j + half)]
    frame = round(k)
    result = run(image_path=str(case), output_dir=str(RUN_DIR), box_xyxy=box, frame_idx=frame,
                 propagation='both', hu_window=HU_WINDOW, overwrite=True)

    hu = np.asarray(image.dataobj, dtype=np.float32)[:, :, frame].T
    mask = np.asarray(nib.load(result['outputs']['mask']).dataobj)[:, :, frame].T > 0
    labels, _ = ndimage.label(hu > -500)
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0
    body = ndimage.binary_fill_holes(labels == sizes.argmax())
    gray = np.clip((hu - DISPLAY_WINDOW[0]) / (DISPLAY_WINDOW[1] - DISPLAY_WINDOW[0]), 0, 1) * 255
    gray[~body] = 0
    rgb = np.repeat(gray[:, :, None], 3, axis=2)
    rgb[mask] = (1 - MASK_OPACITY) * rgb[mask] + MASK_OPACITY * np.asarray(MASK_RGB)
    rgb[mask & ~ndimage.binary_erosion(mask)] = MASK_RGB
    picture = Image.fromarray(np.uint8(np.round(rgb)))
    picture = picture.resize((picture.width * UPSCALE, picture.height * UPSCALE), Image.LANCZOS)
    ImageDraw.Draw(picture).rectangle([v * UPSCALE for v in box], outline=BOX_RGB, width=BOX_WIDTH)
    rows, cols = np.nonzero(body)
    crop = [int(cols.min()) - 8, int(rows.min()) - 8, int(cols.max()) + 9, int(rows.max()) + 9]
    picture = picture.crop([v * UPSCALE for v in crop])
    picture.save(ASSETS / 'medsam-slice.webp', quality=88, method=6)

    details = {key: value for key, value in result['details'].items() if key != 'model_path'}
    record = {
        'schema_version': 1,
        'method': 'medsam2-mlx 0.2.8 box prompt on one LUNA16 CT, propagated through the volume',
        'runtime': {'package': 'medsam2-mlx', 'version': version('medsam2-mlx'),
                    'medmlx_core_version': version('medmlx-core'), 'mlx_version': version('mlx'),
                    'python_version': platform.python_version(),
                    'macos_version': platform.mac_ver()[0], 'entry_point': 'medsam2_mlx.medmlx.run'},
        'weights': {'repository': 'MedMLX/medsam2-ct-lesion-mlx',
                    'revision': details['weights_revision']},
        'source': {'dataset': 'LUNA16 subset0', 'dataset_record': 'Zenodo record 3723295',
                   'dataset_license': 'CC BY 4.0', 'case_file': CASE_FILE, 'series_uid': SERIES_UID,
                   'reference_nodule': {'world_lps_mm': list(NODULE_LPS_MM),
                                        'diameter_mm': NODULE_DIAMETER_MM,
                                        'source': 'LUNA16 annotations.csv consensus nodule'}},
        'prompt': {'box_xyxy': box, 'frame_idx': frame,
                   'rule': f'square box of {BOX_MARGIN} x the annotated diameter centered on the '
                           'annotation, on the slice nearest its center'},
        'inference': details,
        'display': {'renderer': 'docs/hero/render_featured.py', 'slice': frame,
                    'ct_window_hu': list(DISPLAY_WINDOW), 'mask_rgb': MASK_RGB,
                    'mask_opacity': MASK_OPACITY, 'box_rgb': BOX_RGB,
                    'body_mask': 'largest CT > -500 HU component, holes filled; black outside',
                    'crop_xyxy_px': crop, 'resampling': f'Lanczos x{UPSCALE}',
                    'orientation': 'radiological: patient right on image left, anterior at top'},
        'interpretation': 'One prompted segmentation of one public, de-identified CT for a '
                          'software visualization. Not reviewed and not a clinical result.',
    }
    (ASSETS / 'medsam-slice-run.json').write_text(json.dumps(record, indent=1) + '\n')
    print(f'box {box} on slice {frame}; mask slices {details["frames_with_mask"]}')


# Card image -> source asset. Each card image puts its subject on one 4:3 canvas at
# one fill, so wide slices and the tall 3D render appear at a consistent size.
CARDS = {'liver': 'liver', 'anatomy': 'anatomy-torso', 'medsam': 'medsam-slice', 'prompt': 'biomedparse-panel',
         'segresnet': 'segresnet-axial', 'kidney': 'kidney', 'brain': 'brain', 'xray': 'xray', 'pet': 'pet'}
CARD_SIZE = (960, 720)
CARD_FILL = 0.86


def cards(_args):
    """Center each subject on a black 4:3 canvas, scaled to fit CARD_FILL of it.

    The subject is every bright region (max channel > 24, merged across 6-pixel
    gaps) holding at least 2% of the bright pixels, which leaves out stray figure
    marks such as table lines.
    """
    for card, source in CARDS.items():
        image = Image.open(ASSETS / f'{source}.webp').convert('RGB')
        bright = np.asarray(image).max(axis=2) > 24
        labels, _ = ndimage.label(ndimage.binary_dilation(bright, iterations=6))
        counts = np.bincount(labels[bright])
        counts[0] = 0
        keep = np.flatnonzero(counts >= 0.02 * bright.sum())
        rows, cols = np.nonzero(np.isin(labels, keep) & bright)
        subject = image.crop((cols.min(), rows.min(), cols.max() + 1, rows.max() + 1))
        width, height = CARD_SIZE
        scale = min(width * CARD_FILL / subject.width, height * CARD_FILL / subject.height)
        subject = subject.resize((round(subject.width * scale), round(subject.height * scale)),
                                 Image.LANCZOS)
        canvas = Image.new('RGB', CARD_SIZE)
        canvas.paste(subject, ((width - subject.width) // 2, (height - subject.height) // 2))
        canvas.save(ASSETS / f'featured-{card}.webp', quality=88, method=6)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('stage', choices=['anatomy', 'panels', 'medsam', 'film-panels', 'cards'])
    parser.add_argument('names', nargs='*', help='film-panels: sources.json panel names')
    parser.add_argument('--dataset', type=Path, default=Path.home() / 'Documents/datasets/LUNA16')
    args = parser.parse_args()
    {'anatomy': anatomy, 'panels': panels, 'medsam': medsam, 'film-panels': film_panels,
     'cards': cards}[args.stage](args)


if __name__ == '__main__':
    main()
