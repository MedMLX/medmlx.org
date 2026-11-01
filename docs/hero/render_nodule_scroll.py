# /// script
# requires-python = ">=3.13"
# dependencies = ["numpy>=2", "nibabel>=5", "pillow>=12", "scipy>=1.16", "imageio-ffmpeg>=0.6"]
# ///
"""Render a slice scroll of a saved lung-nodule-mlx detection over its source CT.

Run after the detection recorded in nodule-scroll-run.json:
    uv run docs/hero/render_nodule_scroll.py

Only display transformations are performed here: one soft-tissue window (the
same as the Segmentation card, so the solid nodule shows inside black lung), one body
crop shared by every frame, uniform in-plane Lanczos resampling, the model's
predicted box drawn on the native slices it intersects, and H.264/WebP
encoding. The box is read from the runner's detections.json and is never
edited, smoothed or recomputed. There is no through-plane interpolation, and
the LUNA16 annotation is not drawn. The renderer fills the record's display
section and raises if the CT, saved output or geometry differ from the record.
"""

import argparse
import hashlib
import json
import re
import subprocess
from importlib.metadata import version
from pathlib import Path

import imageio_ffmpeg
import nibabel as nib
import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
FRAME = (800, 520)
WINDOW = {'center': 40, 'width': 400}
LOW, HIGH = WINDOW['center'] - WINDOW['width'] / 2, WINDOW['center'] + WINDOW['width'] / 2
BODY_HU = -300
MARGIN_MM = 8.0
HALF_RANGE_MM = 25.0
HOLD = 4
FPS = 24
CRF = 26
BOX_RGB = (0xff, 0x5a, 0x73)
STROKE = 6
CONFIDENT = 0.5


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def load_ct(path):
    """Read HU voxels whose stored axes already give a radiological axial view."""
    image = nib.load(path)
    if len(image.shape) != 3:
        raise ValueError(f'Expected a scalar 3D CT: {path}')
    if image.header.get_xyzt_units()[0] != 'mm':
        raise ValueError('Expected millimeter spatial units')
    affine = np.asarray(image.affine, dtype=np.float64)
    if not np.allclose(affine[:3, :3], np.diag(np.diag(affine[:3, :3]))):
        raise ValueError('This renderer requires an axis-aligned affine')
    # i runs toward patient left and j toward posterior, so data[:, :, k].T
    # shows patient right on image left and anterior at the top.
    if nib.aff2axcodes(affine) != ('L', 'P', 'S'):
        raise ValueError(f'Expected LPS voxel axes, got {nib.aff2axcodes(affine)}')
    if not np.isclose(abs(affine[0, 0]), abs(affine[1, 1])):
        raise ValueError('This asset layout requires square in-plane pixels')
    return np.asarray(image.dataobj, dtype=np.float32), affine


def box_extent(box, affine):
    """Return a cccwhd RAS-mm box as continuous voxel-center ijk bounds."""
    center, size = np.asarray(box[:3]), np.asarray(box[3:])
    corners = np.stack([center - size / 2, center + size / 2])
    voxels = (np.linalg.inv(affine) @ np.c_[corners, np.ones(2)].T)[:3].T
    return voxels.min(axis=0), voxels.max(axis=0)


def body_masks(slab):
    """Largest 3D CT > -300 HU component across the slab, holes filled per slice."""
    labels, _ = ndimage.label(slab > BODY_HU)
    areas = np.bincount(labels.ravel())
    areas[0] = 0
    body = labels == areas.argmax()
    for k in range(body.shape[2]):
        body[:, :, k] = ndimage.binary_fill_holes(body[:, :, k])
    counts = body.sum(axis=(0, 1)).astype(float)
    if np.any(counts[1:] / counts[:-1] > 1.15) or np.any(counts[1:] / counts[:-1] < 1 / 1.15):
        raise ValueError(f'Body mask area jumps between adjacent slices: {counts.tolist()}')
    return body


def framing(body, spacing):
    """One 800:520 crop around every slice's body, in source pixel coordinates."""
    cols, rows = np.where(body.any(axis=2))  # body axes are (i, j) = (column, row)
    margin = MARGIN_MM / spacing
    x0, x1 = cols.min() - margin, cols.max() + 1 + margin
    y0, y1 = rows.min() - margin, rows.max() + 1 + margin
    aspect = FRAME[0] / FRAME[1]
    if (x1 - x0) / (y1 - y0) < aspect:
        grow = (y1 - y0) * aspect - (x1 - x0)
        x0, x1 = x0 - grow / 2, x1 + grow / 2
    else:
        grow = (x1 - x0) / aspect - (y1 - y0)
        y0, y1 = y0 - grow / 2, y1 + grow / 2
    return np.array([x0, y0, x1, y1])


def render(hu, body, crop, pad):
    """Window one axial plane, black outside the body, uniform Lanczos resize."""
    gray = np.clip((hu - LOW) / (HIGH - LOW), 0, 1).astype(np.float32)
    gray[~body] = 0
    gray = np.pad(gray.T, pad)  # rows = j (anterior first), columns = i (patient right first)
    plane = Image.fromarray(gray).resize(
        FRAME, Image.Resampling.LANCZOS, box=tuple(float(v) for v in crop + pad))
    value = np.uint8(np.rint(np.clip(np.asarray(plane), 0, 1) * 255))
    return np.repeat(value[:, :, None], 3, axis=2)


def to_frame(i, j, crop):
    """Map continuous voxel-center coordinates to output pixel coordinates."""
    scale = FRAME[0] / (crop[2] - crop[0])
    return (i + 0.5 - crop[0]) * scale, (j + 0.5 - crop[1]) * scale


def draw_box(rgb, left, top, right, bottom):
    """A pixel-aligned, unsmoothed stroke centered on the predicted box edges."""
    l, t, r, b = (int(np.floor(v - STROKE / 2 + 0.5)) for v in (left, top, right, bottom))
    if l < 0 or t < 0 or r + STROKE > rgb.shape[1] or b + STROKE > rgb.shape[0]:
        raise ValueError('The predicted box must lie inside the frame')
    color = np.array(BOX_RGB, dtype=np.uint8)
    rgb[t:t + STROKE, l:r + STROKE] = color
    rgb[b:b + STROKE, l:r + STROKE] = color
    rgb[t:b + STROKE, l:l + STROKE] = color
    rgb[t:b + STROKE, r:r + STROKE] = color
    return [l, t, r + STROKE, b + STROKE]


def encode(ffmpeg, frames, output):
    """Silent H.264 yuv420p with BT.709 tags and faststart for inline playback.

    setparams tags primaries, transfer and matrix; this ffmpeg build leaves the
    first two unknown when they are given only as output options.
    """
    command = [
        ffmpeg, '-hide_banner', '-loglevel', 'error', '-y',
        '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{FRAME[0]}x{FRAME[1]}',
        '-framerate', str(FPS), '-i', '-',
        '-vf', 'scale=out_color_matrix=bt709:out_range=tv:flags=accurate_rnd+full_chroma_int,'
               'format=yuv420p,'
               'setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv',
        '-c:v', 'libx264', '-preset', 'veryslow', '-crf', str(CRF), '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart', '-an', '-map_metadata', '-1',
        '-fflags', '+bitexact', '-flags:v', '+bitexact', str(output),
    ]
    subprocess.run(command, input=b''.join(f.tobytes() for f in frames), check=True)
    return command[1:-1]


def stream_tags(ffmpeg, video):
    """Read back the stored stream description; ffprobe is not bundled."""
    info = subprocess.run([ffmpeg, '-hide_banner', '-i', str(video)],
                          capture_output=True, text=True).stderr
    stream = next(line.strip() for line in info.splitlines() if 'Video:' in line)
    if not re.search(r'yuv420p\(tv, bt709, progressive\)', stream) or 'Audio:' in info:
        raise ValueError(f'Expected silent yuv420p tagged BT.709 throughout: {stream}')
    return stream


def decode(ffmpeg, video):
    raw = subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-i', str(video),
                          '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, FRAME[1], FRAME[0], 3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', type=Path, default=ROOT / 'site/assets/hero/nodule-scroll-run.json')
    parser.add_argument('--dataset', type=Path, default=Path.home() / 'Documents/datasets/LUNA16')
    parser.add_argument('--run-dir', type=Path, default=ROOT / 'dist/nodule-scroll-demo')
    parser.add_argument('--video', type=Path, default=ROOT / 'site/assets/hero/nodule-scroll.mp4')
    parser.add_argument('--poster', type=Path, default=ROOT / 'site/assets/hero/nodule-scroll-poster.webp')
    args = parser.parse_args()
    record = json.loads(args.record.read_text())
    source = record['source']

    # The CT and saved model output must be the exact files the record names.
    ct_path = args.dataset / source['case_file']
    if sha256(ct_path) != source['input_sha256']:
        raise ValueError(f'CT hash differs from the record: {ct_path}')
    saved = {}
    for role in ('detections', 'bundle_detections'):
        path = ROOT / record['outputs'][role]['local_artifact']
        if sha256(path) != record['outputs'][role]['sha256']:
            raise ValueError(f'Saved model output differs from the record: {path}')
        saved[role] = json.loads(path.read_text())
    output = saved['detections']
    if (output['schema_version'], output['coordinate_convention'], output['box_mode'],
            output['units']) != ('medmlx.detections.v1', 'nifti_ras', 'cccwhd', 'mm'):
        raise ValueError('Expected medmlx.detections.v1 cccwhd boxes in NIfTI RAS mm')
    detections = sorted(output['detections'], key=lambda d: -d['score'])
    if any(Path(d['source_image']).name != Path(source['case_file']).name for d in detections):
        raise ValueError('Detections were not produced from the recorded case')
    bundle = saved['bundle_detections'][0]
    for detection in output['detections']:
        index = bundle['label_scores'].index(detection['score'])
        lps = np.asarray(bundle['box'][index][:3]) * [-1, -1, 1]
        if not np.array_equal(lps, detection['box'][:3]) or bundle['box'][index][3:] != detection['box'][3:]:
            raise ValueError('RAS detections and LPS bundle rows disagree')
    if [d['box'] for d in detections] != [d['box_ras_cccwhd_mm'] for d in record['detections']]:
        raise ValueError('Recorded boxes differ from the saved detections')
    top = detections[0]

    hu, affine = load_ct(ct_path)
    spacing, slice_mm = abs(affine[0, 0]), affine[2, 2]
    low, high = box_extent(top['box'], affine)
    center_k = int(np.rint((top['box'][2] - affine[2, 3]) / slice_mm))
    steps = int(np.rint(HALF_RANGE_MM / slice_mm))
    first, last = center_k - steps, center_k + steps
    if first < 0 or last >= hu.shape[2]:
        raise ValueError('The scroll range must lie inside the CT')
    if np.any(low < 0) or np.any(high > np.array(hu.shape) - 1):
        raise ValueError('The predicted box must lie inside the CT')
    if not low[2] <= center_k <= high[2]:
        raise ValueError('The poster slice must intersect the predicted box')
    z = affine[2, 3] + slice_mm * np.arange(first, last + 1)

    # Never hide a confident prediction that falls inside the displayed volume.
    in_view = []
    for rank, detection in enumerate(detections[1:], start=2):
        lo, hi = box_extent(detection['box'], affine)
        if hi[2] >= first and lo[2] <= last:
            in_view.append({'rank': rank, 'score': detection['score']})
            if detection['score'] >= CONFIDENT:
                raise ValueError(f'Detection {rank} is confident and intersects the scroll range')

    slab = hu[:, :, first:last + 1]
    body = body_masks(slab)
    i, j = np.rint((low[:2] + high[:2]) / 2).astype(int)
    if not body[i, j, center_k - first]:
        raise ValueError('The predicted box center must lie inside the body mask')
    # Report, rather than hide, a body wider than the reconstructed field of view.
    truncated = bool(body[0].any() or body[-1].any())
    crop = framing(body, spacing)
    pad = int(np.ceil(max(0, -crop[0], -crop[1], crop[2] - hu.shape[0], crop[3] - hu.shape[1])))
    left, top_y = to_frame(low[0], low[1], crop)
    right, bottom = to_frame(high[0], high[1], crop)
    if left < 0 or top_y < 0 or right > FRAME[0] or bottom > FRAME[1]:
        raise ValueError('The predicted box must lie inside the crop')

    frames_dir = args.run_dir / 'frames'
    frames_dir.mkdir(parents=True, exist_ok=True)
    frames, box_slices, stroke_px = [], [], None
    for offset, k in enumerate(range(first, last + 1)):
        rgb = render(slab[:, :, offset], body[:, :, offset], crop, pad)
        if low[2] <= k <= high[2]:
            stroke_px = draw_box(rgb, left, top_y, right, bottom)
            box_slices.append(k)
        frames.append(rgb)
        Image.fromarray(rgb).save(frames_dir / f'slice_{k:03d}.png')

    # Ping-pong through native slices so the loop seam is one ordinary step,
    # rotated to start on the poster slice so playback begins where the poster is.
    order = list(range(len(frames))) + list(range(len(frames) - 2, 0, -1))
    start = order.index(center_k - first)
    order = order[start:] + order[:start]
    sequence = [frames[index] for index in order for _ in range(HOLD)]
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    args.video.parent.mkdir(parents=True, exist_ok=True)
    settings = encode(ffmpeg, sequence, args.video)
    stream = stream_tags(ffmpeg, args.video)
    decoded = decode(ffmpeg, args.video)
    if len(decoded) != len(sequence):
        raise ValueError(f'Encoded {len(decoded)} frames, expected {len(sequence)}')
    outside = np.pad(np.uint8(~body[:, :, 0].T) * 255, pad, constant_values=255)
    outside = np.asarray(Image.fromarray(outside).resize(
        FRAME, Image.Resampling.NEAREST, box=tuple(float(v) for v in crop + pad))) > 127
    outside = ndimage.binary_erosion(outside, iterations=6, border_value=1)
    poster = Image.fromarray(frames[center_k - first])
    poster.save(args.poster, quality=85, method=6)
    ffmpeg_version = subprocess.run([ffmpeg, '-version'], capture_output=True, text=True,
                                    check=True).stdout.splitlines()[0]

    def rounded(values, digits=3):
        return [round(float(v), digits) for v in values]

    display = {
        'renderer': 'docs/hero/render_nodule_scroll.py',
        'renderer_sha256': sha256(Path(__file__)),
        'orientation': 'Radiological axial view: patient right on image left, anterior at top. '
                       'Stored voxel axes are LPS, so each frame is data[:, :, k].T with no flips.',
        'slices': {
            'type': 'Native acquired axial slices; no through-plane interpolation',
            'k_range': [first, last],
            'count': last - first + 1,
            'z_range_ras_mm': rounded([z[0], z[-1]]),
            'slice_spacing_mm': float(slice_mm),
            'range_about_box_center_mm': rounded([z[0] - top['box'][2], z[-1] - top['box'][2]]),
            'poster_k': center_k,
            'poster_z_ras_mm': round(float(affine[2, 3] + slice_mm * center_k), 3),
            'box_center_z_ras_mm': round(top['box'][2], 3),
        },
        'window_hu': {**WINDOW, 'range': [LOW, HIGH]},
        'body_mask': f'Largest 3D CT > {BODY_HU} HU component of the displayed slab, holes filled '
                     'per slice; set to true black outside. Contains the predicted box center.',
        'field_of_view': ('The body reaches the first and last image columns, so the flat left '
                          'and right body edges are the edge of the scan\'s '
                          f'{hu.shape[0] * spacing:.0f} mm reconstruction field, not a crop.'
                          if truncated else 'The body lies inside the reconstruction field.'),
        'source_crop_xyxy': rounded(crop),
        'source_crop_note': 'Continuous source-pixel coordinates (columns = i, rows = j) of one '
                            f'crop for every frame: body bounds plus {MARGIN_MM:g} mm, widened to '
                            f'{FRAME[0]}:{FRAME[1]}; area beyond the scan is black padding.',
        'scale_px_per_mm': round(FRAME[0] / ((crop[2] - crop[0]) * spacing), 4),
        'display_resampling': 'uniform in-plane Lanczos on the windowed float image',
        'box': {
            'drawn_detection_ranks': [1],
            'drawn_on_k': box_slices,
            'rule': 'Drawn on native slices whose z lies within the box depth',
            'box_voxel_ijk_min': rounded(low),
            'box_voxel_ijk_max': rounded(high),
            'frame_stroke_outer_xyxy': stroke_px,
            'color': '#ff5a73',
            'stroke_px': STROKE,
            'style': 'Pixel-aligned rectangle centered on the box edges; no antialiasing, glow, '
                     'labels or text',
            'other_detections_in_scroll_range': in_view,
            'confident_threshold_checked': CONFIDENT,
        },
        'annotation_drawn': False,
        'prediction_edits': False,
        'sequence': {
            'pattern': 'ping-pong: first to last slice, then back, without repeating either end; '
                       'rotated to start on the poster slice',
            'first_frame_k': first + order[0],
            'hold_frames_per_slice': HOLD,
            'fps': FPS,
            'frames': len(sequence),
            'duration_s': round(len(sequence) / FPS, 3),
        },
        'encode': {
            'codec': 'H.264 (libx264)', 'crf': CRF, 'preset': 'veryslow', 'pix_fmt': 'yuv420p',
            'color': 'BT.709 primaries, transfer and matrix; limited range', 'faststart': True,
            'audio': None, 'stream': stream,
            'ffmpeg': ffmpeg_version, 'imageio_ffmpeg_version': version('imageio-ffmpeg'),
            'ffmpeg_arguments': settings,
            'poster': 'WebP, quality 85, method 6, the slice nearest the box center',
        },
        'decoded_check': {
            'frames': len(decoded),
            'max_rgb_outside_body': int(decoded[0][outside].max()),
            'outside_body_region': 'Body exterior of the first frame, eroded by 6 output pixels',
        },
        'outputs': {
            'video': 'site/assets/hero/nodule-scroll.mp4',
            'video_sha256': sha256(args.video),
            'video_bytes': args.video.stat().st_size,
            'poster': 'site/assets/hero/nodule-scroll-poster.webp',
            'poster_sha256': sha256(args.poster),
            'poster_bytes': args.poster.stat().st_size,
            'size_px': list(FRAME),
            'local_frames': 'dist/nodule-scroll-demo/frames/',
        },
    }
    record['display'] = display
    args.record.write_text(json.dumps(record, indent=2) + '\n')
    (args.run_dir / 'display.json').write_text(json.dumps(display, indent=2) + '\n')
    print(json.dumps(display, indent=2))


if __name__ == '__main__':
    main()
