# /// script
# requires-python = ">=3.13,<3.15"
# dependencies = [
#     "swin-unetr-mlx==0.2.5",
#     "SimpleITK>=2.5",
#     "numpy>=2",
#     "pillow>=12",
#     "scipy>=1.16",
#     "imageio-ffmpeg>=0.6",
# ]
# ///
"""Render the homepage abdominal CT scroll with SwinUNETR organ labels.

Three stages, run in order from the repository root:
    uv run docs/hero/render_abdomen_scroll.py prepare   # TCIA DICOM -> NIfTI
    uv run docs/hero/render_abdomen_scroll.py segment   # swin-unetr-mlx on Metal
    uv run docs/hero/render_abdomen_scroll.py render    # MP4, poster, run record

`prepare` converts one HCC-TACE-Seg CT series with SimpleITK after checking it
against the TCIA download manifest. `segment` runs the published runner
unchanged. `render` performs display transforms only: a fixed soft-tissue
window, black outside the body, one fixed crop, uniform Lanczos resampling,
semi-transparent label fills and H.264/WebP encoding. The predicted labels are
never edited, smoothed, interpolated between slices or recomputed here.
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
import numpy as np
import SimpleITK as sitk
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
RUN_DIR = ROOT / 'dist/abdomen-scroll-demo'
ASSETS = ROOT / 'site/assets/hero'
DATASET = Path('~/Documents/datasets/HCC-TACE-Seg').expanduser()
CASE = 'HCC_063'
SERIES_UID = '1.3.6.1.4.1.14519.5.2.1.1706.8374.125226904930109418407714368092'
WEIGHTS = Path('~/.cache/medmlx/swin-unetr').expanduser()
# Hugging Face revision of swinunetr.safetensors that swin-unetr-mlx v0.2.5 pins.
WEIGHTS_REVISION = '0052abb4bfb1c56bd7d52d5353267393399b8743'

WINDOW = (40, 400)  # level, width in HU
SIZE = (800, 520)
FPS = 24
SECONDS = 8
ALPHA = 0.5
# BT.709 limited-range conversion, tagged as BT.709 primaries, transfer and matrix.
COLOR_FILTER = ('scale=out_color_matrix=bt709:out_range=tv,'
                'setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv')
CRF = 28  # smallest file in the 24-28 range; about 690 KB
# Upper-abdominal organs that define the scroll range and the poster slice.
CORE = {1: 'spleen', 2: 'right kidney', 3: 'left kidney', 6: 'liver', 7: 'stomach', 11: 'pancreas'}
MIN_AREA_MM2 = 100.0
# Muted fills for every BTCV label, spaced around the hue wheel. Paired organs
# (kidneys, adrenal glands) share one color.
PALETTE = {
    1: (70, 166, 160),    # spleen: teal
    2: (222, 142, 62),    # right kidney: amber
    3: (222, 142, 62),    # left kidney: amber
    4: (218, 208, 92),    # gallbladder: straw yellow
    5: (196, 116, 178),   # esophagus: orchid
    6: (190, 106, 120),   # liver: dusty rose
    7: (148, 116, 204),   # stomach: lavender
    8: (214, 72, 66),     # aorta: brick red
    9: (72, 96, 196),     # inferior vena cava: indigo
    10: (112, 178, 222),  # portal and splenic veins: sky blue
    11: (122, 184, 102),  # pancreas: sage green
    12: (232, 214, 162),  # right adrenal gland: sand
    13: (232, 214, 162),  # left adrenal gland: sand
}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def manifest_series():
    manifest = json.loads((DATASET / 'download_manifest.json').read_text())
    matches = [s for s in manifest['series'] if s['SeriesInstanceUID'] == SERIES_UID]
    if len(matches) != 1 or matches[0]['PatientID'] != CASE or matches[0]['Modality'] != 'CT':
        raise ValueError(f'{SERIES_UID} is not one {CASE} CT series in the manifest')
    return manifest, matches[0]


def prepare(args):
    """Convert the TCIA DICOM series to an int16 HU NIfTI with SimpleITK/GDCM."""
    manifest, entry = manifest_series()
    folder = DATASET / entry['local_path']
    reader = sitk.ImageSeriesReader()
    if reader.GetGDCMSeriesIDs(str(folder)) != (SERIES_UID,):
        raise ValueError(f'{folder} must hold exactly series {SERIES_UID}')
    files = reader.GetGDCMSeriesFileNames(str(folder), SERIES_UID)
    # TCIA adds a LICENSE text file beside the instances; only .dcm files count.
    on_disk = sorted(folder.glob('*.dcm'))
    if len(files) != len(on_disk) or len(files) != entry['verified_dicom_count']:
        raise ValueError('DICOM file count differs from the TCIA manifest')
    if sum(p.stat().st_size for p in on_disk) != entry['verified_dicom_bytes']:
        raise ValueError('DICOM byte count differs from the TCIA manifest')
    reader.SetFileNames(files)
    reader.MetaDataDictionaryArrayUpdateOn()
    image = reader.Execute()

    def tag(key, index=0):
        return reader.GetMetaData(index, key).strip()

    def optional(key):
        return (tag(key) or None) if reader.HasMetaDataKey(0, key) else None

    if {tag('0020|000e', i) for i in range(len(files))} != {SERIES_UID}:
        raise ValueError('A file does not carry the selected SeriesInstanceUID')
    if tag('0008|0060') != 'CT' or tag('0010|0020') != CASE:
        raise ValueError('Unexpected modality or patient ID')
    if not np.allclose(image.GetDirection(), np.eye(3).ravel()):
        raise ValueError('Expected axial slices with identity LPS direction')
    positions = np.array([[float(v) for v in tag('0020|0032', i).split('\\')]
                          for i in range(len(files))])
    steps = np.diff(positions[:, 2])
    if not np.allclose(steps, steps[0]) or not np.isclose(steps[0], image.GetSpacing()[2]):
        raise ValueError('Slices must be evenly spaced and sorted inferior to superior')
    hu = sitk.GetArrayViewFromImage(image)
    if hu.min() < -32768 or hu.max() > 32767:
        raise ValueError('HU values do not fit int16')
    ct = sitk.Cast(image, sitk.sitkInt16)
    ct_path = args.run_dir / 'ct.nii.gz'
    args.run_dir.mkdir(parents=True, exist_ok=True)
    sitk.WriteImage(ct, str(ct_path), useCompression=True)
    if not np.array_equal(sitk.GetArrayFromImage(sitk.ReadImage(str(ct_path))), hu):
        raise ValueError('The written NIfTI does not reproduce the DICOM HU values')
    source = {
        'dataset': manifest['dataset'],
        'collection_doi': manifest['doi'],
        'source_url': manifest['source_url'],
        'license': manifest['license'],
        'case': CASE,
        'study_instance_uid': entry['StudyInstanceUID'],
        'series_instance_uid': SERIES_UID,
        'series_number': entry['SeriesNumber'],
        'series_description': entry['SeriesDescription'],
        'study_description': entry['StudyDesc'],
        'contrast_bolus_agent': optional('0018|0010'),
        'contrast_bolus_route': optional('0018|1040'),
        'slice_thickness_mm': float(tag('0018|0050')),
        'convolution_kernel': optional('0018|1210'),
        'dicom_files': len(files),
        'dicom_bytes': entry['verified_dicom_bytes'],
        'conversion': {
            'method': 'SimpleITK ImageSeriesReader (GDCM) with rescale slope/intercept to HU, '
                      'cast to int16 and written as gzip NIfTI by SimpleITK; read-back is '
                      'voxel-identical. No resampling, reorientation or intensity change.',
            'simpleitk_version': sitk.Version.VersionString(),
            'size_xyz': list(image.GetSize()),
            'spacing_mm_xyz': list(image.GetSpacing()),
            'origin_lps_mm': list(image.GetOrigin()),
            'direction_lps': list(image.GetDirection()),
            'hu_range': [int(hu.min()), int(hu.max())],
        },
    }
    write_json(args.run_dir / 'source.json', source)
    print(json.dumps(source, indent=2))


def segment(args):
    """Run the published swin-unetr-mlx 0.2.5 runner on the converted CT."""
    import mlx.core as mx
    from swin_unetr_mlx.medmlx import run

    if metadata.version('swin-unetr-mlx') != '0.2.5':
        raise ValueError('This record requires swin-unetr-mlx 0.2.5')
    ct_path = args.run_dir / 'ct.nii.gz'
    # An explicit folder keeps the shared download cache read-only.
    result = run(image_path=str(ct_path), weights_path=str(WEIGHTS),
                 output_dir=str(args.run_dir / 'swin-unetr'), overwrite=True)
    mask_path = Path(result['outputs']['mask'])
    chip = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'],
                          capture_output=True, text=True, check=True).stdout.strip()
    record = {
        'runtime': {
            'package': 'swin-unetr-mlx',
            'version': metadata.version('swin-unetr-mlx'),
            'medmlx_core_version': metadata.version('medmlx-core'),
            'mlx_version': mx.__version__,
            'python_version': platform.python_version(),
            'macos_version': platform.mac_ver()[0],
            'device': f'{chip} GPU ({result["details"]["mlx_device"]})',
            'precision': 'float32',
            'entry_point': 'swin_unetr_mlx.medmlx.run',
        },
        'weights': {
            'repository': 'MedMLX/swin-unetr-mlx',
            'file': 'swinunetr.safetensors',
            'revision': WEIGHTS_REVISION,
            'upstream_bundle': 'MONAI/swin_unetr_btcv_segmentation',
        },
        'preprocessing': 'Runner defaults from the pinned MONAI bundle config: ITK read, RAS '
                         'orientation, bilinear resampling to 1.5 x 1.5 x 2.0 mm, clip '
                         '-175..250 HU and scale to [0, 1]; 96^3 sliding windows, batch 4, '
                         'overlap 0.5, constant blending; softmax, inverse spacing and '
                         'orientation, argmax on the input grid.',
        'details': result['details'],
        'mask_relative_path': mask_path.relative_to(args.run_dir).as_posix(),
    }
    write_json(args.run_dir / 'segment.json', record)
    print(json.dumps(record, indent=2))


def read_volume(path):
    image = sitk.ReadImage(str(path))
    return sitk.GetArrayFromImage(image), image


def body_mask(ct):
    """Largest 3D CT > -300 HU component, holes filled per axial slice."""
    connected, _ = ndimage.label(ct > -300)
    areas = np.bincount(connected.ravel())
    areas[0] = 0
    body = connected == areas.argmax()
    return np.stack([ndimage.binary_fill_holes(plane) for plane in body])


def compose(ct_plane, label_plane, body_plane, crop):
    """Window, overlay and black out one axial plane; return the cropped RGB panel."""
    level, width = WINDOW
    gray = np.clip((ct_plane.astype(np.float64) - (level - width / 2)) / width, 0, 1) * 255
    rgb = np.repeat(gray[:, :, None], 3, axis=2)
    for value, color in PALETTE.items():
        hit = label_plane == value
        rgb[hit] = (1 - ALPHA) * rgb[hit] + ALPHA * np.asarray(color, dtype=np.float64)
    rgb[~body_plane] = 0
    x0, y0, x1, y1 = crop
    padded = np.zeros((y1 - y0, x1 - x0, 3))
    sy0, sx0 = max(y0, 0), max(x0, 0)
    sy1, sx1 = min(y1, rgb.shape[0]), min(x1, rgb.shape[1])
    padded[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = rgb[sy0:sy1, sx0:sx1]
    panel = Image.fromarray(np.uint8(np.round(padded)))
    return panel.resize(SIZE, Image.Resampling.LANCZOS)


def render(args):
    """Encode the ping-pong scroll, its poster and the website run record."""
    source = json.loads((args.run_dir / 'source.json').read_text())
    segmented = json.loads((args.run_dir / 'segment.json').read_text())
    ct_path = args.run_dir / 'ct.nii.gz'
    mask_path = args.run_dir / segmented['mask_relative_path']
    ct, ct_image = read_volume(ct_path)
    labels, mask_image = read_volume(mask_path)
    if ct.shape != labels.shape:
        raise ValueError('CT and mask must share one voxel grid')
    for name in ('GetSpacing', 'GetOrigin', 'GetDirection'):
        if not np.allclose(getattr(ct_image, name)(), getattr(mask_image, name)(), atol=1e-4):
            raise ValueError(f'CT and mask differ in {name[3:].lower()}')
    if not np.allclose(ct_image.GetDirection(), np.eye(3).ravel()):
        raise ValueError('Radiological display needs identity LPS direction')
    spacing = ct_image.GetSpacing()
    if not np.isclose(spacing[0], spacing[1]):
        raise ValueError('This layout requires square in-plane pixels')
    if not np.array_equal(labels, np.round(labels)) or labels.min() < 0 or labels.max() > 13:
        raise ValueError('The mask must hold integer BTCV labels 0-13')
    labels = labels.astype(np.uint8)

    # Scroll range: contiguous slices where at least four core organs each cover
    # MIN_AREA_MM2. Array rows run anterior->posterior and columns patient
    # right->left, so unflipped planes are in radiological display.
    pixel_mm2 = spacing[0] * spacing[1]
    areas = {v: (labels == v).sum(axis=(1, 2)) * pixel_mm2 for v in CORE}
    present = np.stack([areas[v] >= MIN_AREA_MM2 for v in CORE]).sum(axis=0)
    eligible = np.flatnonzero(present >= 4)
    if eligible.size == 0:
        raise ValueError('No slice shows four core organs')
    runs = np.split(eligible, np.flatnonzero(np.diff(eligible) != 1) + 1)
    run = max(runs, key=len)
    first, last = int(run[0]), int(run[-1])
    count = last - first + 1
    # Poster: the in-range slice whose smallest core-organ area is largest.
    smallest = np.min([areas[v] for v in CORE], axis=0)
    poster_slice = first + int(np.argmax(smallest[first:last + 1]))

    body = body_mask(ct)
    shown = slice(first, last + 1)
    if np.any((labels[shown] > 0) & ~body[shown]):
        raise ValueError('Predicted labels must lie inside the body mask')
    rows, cols = np.nonzero(body[shown].any(axis=0))
    margin = 12
    x0, x1 = int(cols.min()) - margin, int(cols.max()) + 1 + margin
    y0, y1 = int(rows.min()) - margin, int(rows.max()) + 1 + margin
    aspect = SIZE[0] / SIZE[1]
    width, height = x1 - x0, y1 - y0
    if width / height < aspect:
        grow = round(height * aspect) - width
        x0, x1 = x0 - grow // 2, x1 + grow - grow // 2
    else:
        grow = round(width / aspect) - height
        y0, y1 = y0 - grow // 2, y1 + grow - grow // 2
    crop = (x0, y0, x1, y1)

    # Cosine ping-pong over the range, phased to start on the poster slice.
    frames = FPS * SECONDS
    phase = math.acos(1 - 2 * (poster_slice - first) / (count - 1))
    schedule = [first + round((count - 1) * (1 - math.cos(2 * math.pi * k / frames + phase)) / 2)
                for k in range(frames)]
    if schedule[0] != poster_slice or set(schedule) != set(range(first, last + 1)):
        raise ValueError('The schedule must start on the poster and show every slice')
    if max(abs(a - b) for a, b in zip(schedule, schedule[1:] + schedule[:1], strict=True)) > 1:
        raise ValueError('Consecutive frames may advance by at most one slice')

    panels = {z: compose(ct[z], labels[z], body[z], crop) for z in sorted(set(schedule))}
    frames_dir = args.run_dir / 'frames'
    frames_dir.mkdir(exist_ok=True)
    for z, panel in panels.items():
        panel.save(frames_dir / f'slice-{z:03d}.png')
    video = ASSETS / 'abdomen-scroll.mp4'
    poster = ASSETS / 'abdomen-scroll-poster.webp'
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    encode = ['-c:v', 'libx264', '-preset', 'veryslow', '-crf', str(CRF), '-pix_fmt', 'yuv420p',
              '-vf', COLOR_FILTER,
              '-movflags', '+faststart', '-an', '-map_metadata', '-1']
    with tempfile.TemporaryDirectory() as scratch:
        process = subprocess.Popen(
            [ffmpeg, '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
             '-s', f'{SIZE[0]}x{SIZE[1]}', '-r', str(FPS), '-i', '-', *encode,
             str(Path(scratch) / 'out.mp4')], stdin=subprocess.PIPE)
        for z in schedule:
            process.stdin.write(panels[z].tobytes())
        process.stdin.close()
        if process.wait() != 0:
            raise RuntimeError('ffmpeg failed')
        video.parent.mkdir(parents=True, exist_ok=True)
        os.replace(Path(scratch) / 'out.mp4', video)
    panels[poster_slice].save(poster, quality=85, method=6)
    panels[poster_slice].save(args.run_dir / 'poster.png')
    decoded = decode(ffmpeg, video)
    if decoded.shape != (frames, SIZE[1], SIZE[0], 3):
        raise ValueError(f'Decoded video has shape {decoded.shape}')
    # Pixels outside the body in every frame, 8 px clear of any edge, must decode black.
    outside = np.all([np.asarray(p).max(axis=2) == 0 for p in panels.values()], axis=0)
    outside = ndimage.binary_erosion(outside, iterations=8, border_value=1)
    outside_max = int(decoded[:, outside].max())
    if outside_max > 2:
        raise ValueError(f'Outside-body pixels decode to {outside_max}, not black')

    names = segmented['details']['labels']
    organs = {}
    for value, name in names.items():
        value = int(value)
        if value == 0:
            continue
        voxels = (labels[shown] == value).sum(axis=(1, 2))
        if voxels.any():
            organs[name] = {'label': value, 'slices': int((voxels > 0).sum()),
                            'max_area_mm2': round(float(voxels.max() * pixel_mm2), 1)}

    def z_mm(z):
        return ct_image.TransformIndexToPhysicalPoint((0, 0, int(z)))[2]

    record = {
        'schema_version': 1,
        'method': 'swin-unetr-mlx 0.2.5 SwinUNETR BTCV inference on one TCIA contrast CT, '
                  'shown as axial slices with semi-transparent predicted labels',
        'runtime': segmented['runtime'],
        'weights': segmented['weights'],
        'source': {key: source[key] for key in (
            'dataset', 'collection_doi', 'source_url', 'license', 'case',
            'study_instance_uid', 'series_instance_uid', 'series_number',
            'series_description', 'study_description', 'contrast_bolus_agent',
            'contrast_bolus_route', 'slice_thickness_mm', 'convolution_kernel',
            'dicom_files', 'dicom_bytes', 'conversion')},
        'inference': {
            'preprocessing': segmented['preprocessing'],
            'labels_present': segmented['details']['labels_present'],
            'network_input_shape': segmented['details']['network_input_shape'],
            'peak_mlx_bytes': segmented['details']['peak_mlx_bytes'],
            'seconds': segmented['details']['seconds'],
            'local_artifact': f'dist/abdomen-scroll-demo/{segmented["mask_relative_path"]}',
        },
        'label_map': {k: v for k, v in names.items()},
        'display': {
            'renderer': 'docs/hero/render_abdomen_scroll.py',
            'orientation': 'Axial, radiological display: patient right on image left, '
                           'anterior at top; DICOM pixel rows and columns unflipped',
            'ct_window_hu': {'level': WINDOW[0], 'width': WINDOW[1],
                             'range': [WINDOW[0] - WINDOW[1] / 2, WINDOW[0] + WINDOW[1] / 2]},
            'overlay': {'mode': 'fill', 'alpha': ALPHA, 'outlines': False,
                        'unlabelled': 'plain grayscale CT'},
            'palette_rgb': {names[str(k)]: list(v) for k, v in PALETTE.items()},
            'slice_range': {
                'rule': f'longest contiguous run of axial slices where at least four of '
                        f'{sorted(CORE.values())} each cover >= {MIN_AREA_MM2:g} mm^2 '
                        f'in the prediction',
                'first_index': first, 'last_index': last, 'slices': count,
                'z_lps_mm': [z_mm(first), z_mm(last)],
                'index_convention': 'SimpleITK array index, 0 = most inferior slice',
            },
            'organs_in_range': organs,
            'poster': {'slice_index': poster_slice, 'z_lps_mm': z_mm(poster_slice),
                       'rule': 'in-range slice whose smallest core-organ area is largest; '
                               'also the first video frame',
                       'smallest_core_area_mm2': round(float(smallest[poster_slice]), 1)},
            'body_mask': 'largest 3D CT > -300 HU component, holes filled per axial slice; '
                         'pixels outside it set to black; contains every displayed label',
            'source_crop_xyxy': list(crop),
            'crop_rule': f'union body bounding box over the range, {margin}-pixel margin, '
                         f'widened to {SIZE[0]}:{SIZE[1]}; same crop for every frame; '
                         f'out-of-image area black',
            'display_resampling': 'uniform Lanczos of the composited RGB panel',
            'label_editing': False,
            'interslice_interpolation': False,
            'frame_schedule': 'cosine ping-pong: slice = first + round((n-1)(1 - cos(2*pi*k/'
                              'frames + phase))/2), phase chosen so frame 0 is the poster '
                              'slice; each frame is one whole real slice; seamless loop',
            'frames': frames,
        },
        'encode': {
            'video': {'codec': 'H.264 (libx264)', 'preset': 'veryslow', 'crf': CRF,
                      'pix_fmt': 'yuv420p', 'color': 'BT.709, limited range', 'fps': FPS,
                      'seconds': SECONDS, 'size_px': list(SIZE), 'audio': False,
                      'movflags': '+faststart', 'ffmpeg': ffmpeg_version(ffmpeg),
                      'decoded_frames': int(decoded.shape[0]),
                      'outside_body_decoded_max_rgb': outside_max,
                      'bytes': video.stat().st_size},
            'poster': {'format': 'WebP', 'quality': 85, 'method': 6, 'size_px': list(SIZE),
                       'bytes': poster.stat().st_size},
        },
        'outputs': {
            'video': 'site/assets/hero/abdomen-scroll.mp4',
            'poster': 'site/assets/hero/abdomen-scroll-poster.webp',
        },
        'interpretation': 'Automated organ labels on one public, de-identified case for a '
                          'software visualization. Not reviewed, not a clinical finding and '
                          'not a performance validation. HCC-TACE-Seg reference '
                          'segmentations were not used.',
    }
    write_json(ASSETS / 'abdomen-scroll-run.json', record)
    print(json.dumps(record['display']['slice_range'], indent=2))
    print(json.dumps(organs, indent=2))
    print(video.stat().st_size, poster.stat().st_size)


def decode(ffmpeg, video):
    raw = subprocess.run([ffmpeg, '-loglevel', 'error', '-i', str(video), '-f', 'rawvideo',
                          '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, SIZE[1], SIZE[0], 3)


def ffmpeg_version(ffmpeg):
    line = subprocess.run([ffmpeg, '-version'], capture_output=True, text=True,
                          check=True).stdout.splitlines()[0]
    return line.split(' Copyright')[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('stage', choices=['prepare', 'segment', 'render'])
    parser.add_argument('--run-dir', type=Path, default=RUN_DIR)
    args = parser.parse_args()
    {'prepare': prepare, 'segment': segment, 'render': render}[args.stage](args)


if __name__ == '__main__':
    main()
