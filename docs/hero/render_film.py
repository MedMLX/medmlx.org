# /// script
# requires-python = ">=3.13"
# dependencies = ["numpy>=2", "pillow>=12", "imageio-ffmpeg>=0.6"]
# ///
"""Render the homepage output film and its poster from the cropped panels.

    uv run docs/hero/render_film.py

Scenes, timing and frame size come from sources.json; panel boxes and the
camera move are constants below. Each scene is composited once on a float
canvas at twice the film's resolution, with panels resampled into float boxes.
Every frame then resamples the 1600 x 1000 view from that canvas with one float
crop box (Lanczos), so the slow camera scale moves continuously: no size,
offset or position is rounded to whole pixels. Dissolves blend the two views.

The panel WebPs already carry the documentation figures' black-level
subtraction and desaturation recorded in sources.json, so they are not applied
again here. poster.webp is the first frame.
"""

import argparse
import json
import math
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
HERO = ROOT / 'site/assets/hero'
SUPERSAMPLE = 2
CRF = 25
POSTER_QUALITY = 88
SCALE_AMPLITUDE = 0.015
ASPECT_TOLERANCE = 0.005
BATCH = 48

# Panel boxes (x, y, width, height) on the 1600 x 1000 canvas at camera scale
# 1.0, in paste order: right column, top middle, bottom middle. Measured from
# the first published film. Scenes 2 and 4 fit their right panel to
# x 1015-1535 (same right edge and vertical center) so it no longer runs under
# the middle column.
LAYOUT = [
    {'anatomy': (996, 95, 528, 825),
     'total-ct': (650, 126, 340, 217),
     'brain': (655, 571, 350, 348)},
    {'brain-coronal': (1015, 249.07, 520, 516.86),
     'liver': (650, 121, 340, 227),
     'tumor': (655, 589, 350, 311)},
    {'swin': (985, 317, 550, 381),
     'vista': (650, 136, 340, 198),
     'kidney': (655, 617, 350, 256)},
    {'xray': (1015, 184.21, 520, 646.57),
     'medsam': (650, 46, 340, 378),
     'nodule': (655, 566, 350, 358)},
    {'synthetic': (985, 232, 550, 550),
     'lesion': (650, 89, 340, 291),
     'pet': (655, 614, 350, 261)},
    {'radiomics-texture': (985, 271, 550, 472),
     'prompt': (650, 104, 340, 262),
     'features': (655, 611, 350, 268)},
]


def camera_scale(t, duration):
    """One smooth 1.00-1.03 cycle per loop about the frame center.

    This is 1.015 + 0.015 sin(2 pi t / duration), the phase of the first
    published film: it starts at 1.015 zooming in, peaks a quarter of the way
    through and returns exactly at the seam. Written about 1 so it never dips
    below 1 in floating point.
    """
    return 1 + SCALE_AMPLITUDE * (1 + math.sin(2 * math.pi * t / duration))


def smoothstep(u):
    return u * u * (3 - 2 * u)


def channels(array):
    """Split an H x W x C float array into single-channel float PIL images."""
    return [Image.fromarray(np.ascontiguousarray(array[:, :, c], np.float32)) for c in range(array.shape[2])]


def place(canvas, panel, box):
    """Resample a panel into a float box with antialiased coverage, then paste it over."""
    x, y, w, h = (v * SUPERSAMPLE for v in box)
    left, top = math.floor(x), math.floor(y)
    right, bottom = math.ceil(x + w), math.ceil(y + h)
    sx, sy = panel.width / w, panel.height / h
    # Black margins keep the Lanczos support inside the source; the matching
    # coverage layer makes the color premultiplied, so edges blend correctly.
    pad = math.ceil(4 * max(sx, sy, 1)) + 2
    source = np.zeros((panel.height + 2 * pad, panel.width + 2 * pad, 4), np.float32)
    source[pad:-pad, pad:-pad, :3] = np.asarray(panel, np.float32)
    source[pad:-pad, pad:-pad, 3] = 1
    window = (pad + (left - x) * sx, pad + (top - y) * sy,
              pad + (right - x) * sx, pad + (bottom - y) * sy)
    layers = [np.asarray(layer.resize((right - left, bottom - top), Image.Resampling.LANCZOS, box=window))
              for layer in channels(source)]
    color = np.stack(layers[:3], axis=-1)
    coverage = np.clip(layers[3], 0, 1)[:, :, None]
    region = canvas[top:bottom, left:right]
    region *= 1 - coverage
    region += color


def composite(scene, size):
    canvas = np.zeros((size[1] * SUPERSAMPLE, size[0] * SUPERSAMPLE, 3), np.float32)
    for name, box in scene.items():
        place(canvas, Image.open(HERO / f'{name}.webp').convert('RGB'), box)
    return channels(np.clip(canvas, 0, 255))


def view(canvas, scale, size):
    """Resample the frame-centered window of a canvas at a float camera scale."""
    cx, cy = size[0] * SUPERSAMPLE / 2, size[1] * SUPERSAMPLE / 2
    half_w, half_h = cx / scale, cy / scale
    window = (cx - half_w, cy - half_h, cx + half_w, cy + half_h)
    return np.stack([np.asarray(layer.resize(size, Image.Resampling.LANCZOS, box=window))
                     for layer in canvas], axis=-1)


class Film:
    def __init__(self, video, canvases):
        self.size = tuple(video['size'])
        self.fps = video['fps']
        self.duration = video['duration']
        self.canvases = canvases
        self.scene_frames = round(self.duration * self.fps / len(canvases))
        self.fade_frames = round(video['crossfade_seconds'] * self.fps)
        self.count = round(self.duration * self.fps)

    def frame(self, index):
        """Return frame `index` as float RGB; the scene clock wraps at the loop."""
        scale = camera_scale(index / self.fps, self.duration)
        scene, offset = divmod(index % self.count, self.scene_frames)
        rgb = view(self.canvases[scene], scale, self.size)
        fade_from = self.scene_frames - self.fade_frames
        if offset > fade_from:
            weight = smoothstep((offset - fade_from) / self.fade_frames)
            incoming = view(self.canvases[(scene + 1) % len(self.canvases)], scale, self.size)
            rgb = (1 - weight) * rgb + weight * incoming
        return rgb

    def frame8(self, index):
        return np.uint8(np.clip(np.rint(self.frame(index)), 0, 255))


def validate(sources):
    video = sources['video']
    scenes = sources['scenes']
    names = [list(scene) for scene in LAYOUT]
    if scenes != names:
        raise ValueError(f'LAYOUT scenes {names} differ from sources.json {scenes}')
    if tuple(video['size']) != (1600, 1000):
        raise ValueError(f'LAYOUT is measured on a 1600 x 1000 canvas, not {video["size"]}')
    frames = video['duration'] * video['fps']
    scene_frames = frames / len(scenes)
    if frames != round(frames) or scene_frames != round(scene_frames):
        raise ValueError('Scenes must span whole frames')
    if not 0 < video['crossfade_seconds'] * video['fps'] < scene_frames:
        raise ValueError('The crossfade must be shorter than a scene')
    for scene in LAYOUT:
        for name, (x, y, w, h) in scene.items():
            path = HERO / f'{name}.webp'
            if not path.is_file():
                raise ValueError(f'Missing panel: {path}')
            with Image.open(path) as panel:
                aspect = panel.width / panel.height
            if abs((w / h) / aspect - 1) > ASPECT_TOLERANCE:
                raise ValueError(f'{name} box {w} x {h} distorts its {aspect:.4f} aspect')
            if x < 0 or y < 0 or x + w > video['size'][0] or y + h > video['size'][1]:
                raise ValueError(f'{name} box lies outside the canvas')
    scales = [camera_scale(t / 1000, video['duration']) for t in range(video['duration'] * 1000 + 1)]
    if min(scales) < 1 or max(scales) > 1.03 + 1e-9:
        raise ValueError('The camera scale must stay within 1.00-1.03 so the view stays inside the canvas')


def encode(ffmpeg, film, output):
    """Stream frames into silent H.264 yuv420p with BT.709 tags and faststart.

    setparams tags primaries, transfer and matrix; this ffmpeg build leaves the
    first two unknown when they are given only as output options. Content moves
    at most 0.1 px per frame, so the grain tune (no DCT decimation,
    flatter I/P/B quality) and full P-skip checks keep x264 from holding blocks
    still and catching up later, which would bring back the stepping.
    """
    command = [
        ffmpeg, '-hide_banner', '-loglevel', 'error', '-y',
        '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{film.size[0]}x{film.size[1]}',
        '-framerate', str(film.fps), '-i', '-',
        '-vf', ('scale=out_color_matrix=bt709:out_range=tv:flags=accurate_rnd+full_chroma_int,'
                'format=yuv420p,'
                'setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv'),
        '-c:v', 'libx264', '-preset', 'veryslow', '-tune', 'grain', '-crf', str(CRF),
        '-x264-params', 'no-fast-pskip=1', '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart', '-an', '-map_metadata', '-1',
        '-fflags', '+bitexact', '-flags:v', '+bitexact', str(output),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    with ThreadPoolExecutor() as pool:
        for start in range(0, film.count, BATCH):
            for frame in pool.map(film.frame8, range(start, min(start + BATCH, film.count))):
                process.stdin.write(frame.tobytes())
    process.stdin.close()
    if process.wait():
        raise subprocess.CalledProcessError(process.returncode, command)


def check_stream(ffmpeg, video, film):
    """Read back the stored stream description and frame count; ffprobe is not bundled."""
    info = subprocess.run([ffmpeg, '-hide_banner', '-i', str(video), '-map', '0:v:0',
                           '-c', 'copy', '-f', 'null', '-'], capture_output=True, text=True,
                          check=True).stderr
    stream = next(line.strip() for line in info.splitlines() if 'Video:' in line)
    if not re.search(r'yuv420p\(tv, bt709, progressive\)', stream) or 'Audio:' in info:
        raise ValueError(f'Expected silent yuv420p tagged BT.709 throughout: {stream}')
    if f'{film.size[0]}x{film.size[1]}' not in stream or f'{film.fps} fps' not in stream:
        raise ValueError(f'Unexpected frame size or rate: {stream}')
    counts = re.findall(r'frame=\s*(\d+)', info)
    if not counts or int(counts[-1]) != film.count:
        raise ValueError(f'Encoded {counts[-1] if counts else 0} frames, expected {film.count}')
    return stream


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', type=Path, default=HERO / 'sources.json')
    parser.add_argument('--video', type=Path, default=HERO / 'outputs.mp4')
    parser.add_argument('--poster', type=Path, default=HERO / 'poster.webp')
    args = parser.parse_args()
    sources = json.loads(args.sources.read_text())
    validate(sources)
    video = sources['video']
    film = Film(video, [composite(scene, tuple(video['size'])) for scene in LAYOUT])

    # The loop seam must be invisible: the frame after the last equals the first.
    first = film.frame(0)
    seam = np.abs(film.frame(film.count) - first).max()
    if seam > 1e-3:
        raise ValueError(f'Loop seam differs from the first frame by {seam}')

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    args.video.parent.mkdir(parents=True, exist_ok=True)
    encode(ffmpeg, film, args.video)
    stream = check_stream(ffmpeg, args.video, film)
    Image.fromarray(film.frame8(0)).save(args.poster, quality=POSTER_QUALITY, method=6)
    print(json.dumps({
        'video': str(args.video.relative_to(ROOT)) if args.video.is_relative_to(ROOT) else str(args.video),
        'video_bytes': args.video.stat().st_size,
        'poster_bytes': args.poster.stat().st_size,
        'frames': film.count,
        'stream': stream,
        'camera_scale': f'1 + {SCALE_AMPLITUDE} * (1 + sin(2 pi t / {film.duration})) about the frame center',
        'supersample': SUPERSAMPLE,
        'crf': CRF,
    }, indent=2))


if __name__ == '__main__':
    main()
