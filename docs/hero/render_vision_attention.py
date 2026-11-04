# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "mlx-reason-ct==0.3.6",
#     "nibabel>=5",
#     "numpy>=2",
#     "pillow>=12",
#     "scipy>=1.16",
#     "imageio-ffmpeg>=0.6",
# ]
# ///
"""Render the homepage Vision-language card: a report streams while attention moves on the CT.

Two stages, run in order from the repository root:
    uv run docs/hero/render_vision_attention.py infer --ct <scan.nii.gz>   # MLX-Reason-CT on Metal
    uv run docs/hero/render_vision_attention.py render                     # MP4, poster, run record

The CT is LUNA16 subset0 series ...511347030803753100045216493273 (Zenodo record
3723295), converted from MetaImage to NIfTI without resampling. `infer` loads
the published runtime unchanged and writes one greedy structured chest report.
While it generates, observe-only wrappers around the model's attention,
full-attention and embedding methods record, for every generated token, the
head-averaged softmax attention of that token's query over the 24 x 24 x 24
visual tokens at each full-attention decoder layer (3, 7, ..., 31). The wrapped
methods return the original outputs; the attention is recomputed in float32
from the same queries and keys. `render` performs display transforms only:
mean over those layers, normalization by each token's peak, nearest-token
upsampling with a light blur, an axial slice that follows the attention peak,
and H.264/WebP encoding. Decoder attention shows where the model's queries
weighted the scan; it is not an explanation of the report.
"""

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import tempfile
import time
from importlib import metadata
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RUN_DIR = ROOT / 'dist/vision-attention-demo'
ASSETS = ROOT / 'site/assets/hero'
NAME = 'vision-attention'

SERIES_UID = '1.3.6.1.4.1.14519.5.2.1.6279.6001.511347030803753100045216493273'
PROMPT = 'Write a structured chest CT report'
MAX_NEW_TOKENS = 512
PRECISION = 'float32'
REGION = 'chest'
FULL_ATTENTION_LAYERS = tuple(range(3, 32, 4))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def infer(args):
    from medmlx_core.weights import weights_dir, weights_revision
    from mlx_reason_ct.api import PRECISION_PROFILES, generate
    from mlx_reason_ct.mlx_model import NativeModel
    from mlx_reason_ct.mlx_weights import require_runtime_assets
    from mlx_reason_ct.processor_mlx import Processor
    from mlx_reason_ct.runtime import import_mlx

    mx = import_mlx()
    model_dir = Path(weights_dir('mlx-reason-ct'))
    require_runtime_assets(model_dir)
    processor = Processor(model_dir)
    pixels, crop = processor.image(Path(args.ct).expanduser(), REGION)
    model = NativeModel(model_dir, precision=PRECISION_PROFILES[PRECISION])
    started = time.perf_counter()
    _, embeddings = model.vision(mx.array(pixels))
    mx.eval(embeddings)
    count = int(np.prod(processor.grid))
    inputs = processor.prompt(PROMPT, False)
    start = inputs.image_start

    rows = {layer: [] for layer in FULL_ATTENTION_LAYERS}
    shares = {layer: [] for layer in FULL_ATTENTION_LAYERS}
    current = None
    full_attention, attention = model.full_attention, model.attention

    def readout(q, k):
        """The newest query's softmax attention over visual tokens, mean over heads, in float32."""
        query = q[:, :, -1:].astype(mx.float32)
        keys = k.astype(mx.float32)
        batch, heads, _, dim = query.shape
        groups = keys.shape[1]
        query = query.reshape(batch, groups, heads // groups, 1, dim)
        scores = (query @ mx.swapaxes(keys, -1, -2)[:, :, None]) * dim**-0.5
        visual = mx.softmax(scores, axis=-1, precise=True)[..., start:start + count].reshape(heads, count)
        weights, share = visual.mean(axis=0), visual.sum(axis=-1).mean()
        mx.eval(weights, share)
        return np.array(weights), float(share.item())

    def observed_full_attention(x, name, *rest, **kwargs):
        nonlocal current
        previous, current = current, int(name.split('.')[3])  # model.language_model.layers.<i>
        try:
            return full_attention(x, name, *rest, **kwargs)
        finally:
            current = previous

    def observed_attention(q, k, v, *, causal, offset=0):
        output = attention(q, k, v, causal=causal, offset=offset)
        # Prefill's last query predicts the first token; each later call decodes one
        # more, so every generated token, EOS included, gets one row per layer.
        if causal and current in rows:
            weights, share = readout(q, k)
            rows[current].append(weights)
            shares[current].append(share)
        return output

    model.full_attention, model.attention = observed_full_attention, observed_attention
    try:
        tokens, metrics = generate(model, inputs, embeddings, max_new_tokens=MAX_NEW_TOKENS)
    finally:
        del model.full_attention, model.attention
    lengths = {layer: len(values) for layer, values in rows.items()}
    if set(lengths.values()) != {len(tokens)}:
        raise RuntimeError(f'Expected one attention row per generated token, got {lengths} for {len(tokens)}')

    pieces, previous = [], ''
    for end in range(1, len(tokens) + 1):
        text = processor.decode(tokens[:end])
        if text.endswith('�') and end < len(tokens):
            pieces.append('')
            continue
        pieces.append(text[len(previous):])
        previous = text
    args.run_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.run_dir / 'attention.npz',
        attention=np.stack([np.stack(rows[layer]) for layer in FULL_ATTENTION_LAYERS]),
        image_share=np.array([shares[layer] for layer in FULL_ATTENTION_LAYERS]),
        crop_hu=crop.values.astype(np.float32),
    )
    record = {
        'source_ct': {'dataset': 'LUNA16 subset0', 'seriesuid': SERIES_UID,
                      'source_url': 'https://zenodo.org/records/3723295', 'license': 'CC BY 4.0',
                      'nifti_sha256': sha256(args.ct)},
        'runtime': {
            'package': 'mlx-reason-ct', 'version': metadata.version('mlx-reason-ct'),
            'medmlx_core_version': metadata.version('medmlx-core'),
            'mlx_version': metadata.version('mlx'), 'python_version': platform.python_version(),
            'macos_version': platform.mac_ver()[0],
            'device': subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'], capture_output=True,
                                     text=True, check=True).stdout.strip() + f' GPU ({mx.default_device()})',
            'precision': PRECISION, 'entry_points': ['mlx_reason_ct.processor_mlx.Processor',
                                                     'mlx_reason_ct.mlx_model.NativeModel',
                                                     'mlx_reason_ct.api.generate'],
        },
        'weights': {'repository': 'MedMLX/MLX-Reason-CT', 'revision': weights_revision(model_dir)},
        'inference': {
            'prompt': PROMPT, 'enable_thinking': False, 'decoding': 'greedy',
            'max_new_tokens': MAX_NEW_TOKENS, 'anatomy_region': REGION,
            'token_grid_zyx': list(processor.grid), 'crop_spacing_mm': list(processor.spacing),
            'crop_shape': list(processor.shape), 'crop_geometry': crop.geometry(),
            'attention_layers': list(FULL_ATTENTION_LAYERS),
            'attention': 'per generated token and layer: softmax over all keys of the newest query, '
                         'restricted to the visual tokens and averaged over heads, recomputed in float32',
            'generated_tokens': len(tokens), 'seconds_total': round(time.perf_counter() - started, 2),
            'metrics': {k: v for k, v in metrics.items() if isinstance(v, (int, float, str))},
        },
        'text': processor.decode(tokens),
        'pieces': pieces,
    }
    (args.run_dir / 'inference.json').write_text(json.dumps(record, indent=1) + '\n')
    print(record['text'])


# Display. The excerpt is the report's lung findings, streamed token by token.
EXCERPT = ('Lungs and airways: Moderate-sized left lower lobe lung mass. Small lung nodules '
           'bilaterally, including a moderate-sized right lung base nodule.')
NODULE_LPS_MM = (60.77506053, 74.1239696, -214.7823466)  # LUNA16 consensus nodule, 25.2 mm
SIZE = (800, 520)
FPS = 24
LEAD_FRAMES = 24          # "Generating" before the first token
FRAMES_PER_TOKEN = 5      # about 4.8 tokens per second
HOLD_FRAMES = 60
FADE_FRAMES = 12
LUNG_WINDOW = (-400, 1200)  # level, width in HU: air and padding black
SCAN_BOX = (0, 0, 470, 470)
REPORT_BOX = (392, 250, 800, 520)
FONT_PX, LINE_PX, CAPTION_PX = 29, 40, 25
VISIBLE_LINES = 4
# Heat ramp: magenta, red, amber, cream; weak values fade out.
HEAT = np.array([[120, 30, 110], [225, 70, 55], [252, 175, 50], [255, 245, 190]], np.float32)
HEAT_FLOOR = 0.12
BLUR_VOXELS = 3.0
CRF = 26
COLOR_FILTER = ('scale=out_color_matrix=bt709:out_range=tv,'
                'setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv')


def heat_rgba(values):
    position = np.clip(values, 0, 1) * (len(HEAT) - 1)
    low = np.minimum(position.astype(int), len(HEAT) - 2)
    t = (position - low)[..., None]
    rgb = HEAT[low] * (1 - t) + HEAT[low + 1] * t
    strength = np.clip((values - HEAT_FLOOR) / (1 - HEAT_FLOOR), 0, 1)
    return rgb, (0.84 * strength**0.8)[..., None]


def render(args):
    import imageio_ffmpeg
    from PIL import Image, ImageDraw, ImageFont
    from scipy import ndimage

    record = json.loads((args.run_dir / 'inference.json').read_text())
    data = np.load(args.run_dir / 'attention.npz')
    grid = tuple(record['inference']['token_grid_zyx'])
    patch = record['inference']['crop_shape'][0] // grid[0]
    attention = data['attention'].mean(axis=0)  # (tokens, visual tokens), mean of layers
    crop = data['crop_hu']                      # (X, Y, Z), LPS
    pieces = record['pieces']
    text = ''.join(pieces)
    begin = text.index(EXCERPT)
    ends = np.cumsum([len(p) for p in pieces])
    steps = [t for t in range(len(pieces)) if ends[t] > begin and ends[t] - len(pieces[t]) < begin + len(EXCERPT)]

    # Per-token heat volume in crop voxels (Z, Y, X), normalized to its own peak.
    def heat_volume(t):
        values = attention[t].reshape(grid)
        values = values / values.max()
        up = values.repeat(patch, 0).repeat(patch, 1).repeat(patch, 2)
        return ndimage.gaussian_filter(up, BLUR_VOXELS, mode='constant')

    heats = {t: heat_volume(t) for t in steps}
    peaks = {t: np.unravel_index(int(np.argmax(attention[t])), grid) for t in steps}
    target_z = {t: (peaks[t][0] + 0.5) * patch for t in steps}

    level, width = LUNG_WINDOW
    ct = np.clip((crop - (level - width / 2)) / width, 0, 1)
    # One fixed in-plane crop: the body's bounding box over the slices the loop
    # visits, padded by 3%, so the chest fills the scan area.
    visited = range(int(min(target_z.values())) - patch, int(max(target_z.values())) + patch)
    body = (crop[:, :, [z for z in visited if 0 <= z < crop.shape[2]]] > -500).any(axis=2).T
    rows, cols = np.flatnonzero(body.any(axis=1)), np.flatnonzero(body.any(axis=0))
    margin = round(0.03 * body.shape[0])
    r0, r1 = max(rows[0] - margin, 0), min(rows[-1] + 1 + margin, body.shape[0])
    c0, c1 = max(cols[0] - margin, 0), min(cols[-1] + 1 + margin, body.shape[1])
    sx0, sy0, sx1, sy1 = SCAN_BOX
    scan_px = (sx1 - sx0, sy1 - sy0)
    fonts = ROOT / 'site/assets/fonts'
    font = ImageFont.truetype(str(fonts / 'plex-sans-regular.woff2'), FONT_PX)
    caption_font = ImageFont.truetype(str(fonts / 'plex-sans-regular.woff2'), CAPTION_PX)
    rx0, ry0, rx1, ry1 = REPORT_BOX
    pad = 26
    text_width = rx1 - rx0 - 2 * pad

    def wrap(words_text):
        lines, line = [], ''
        for word in words_text.split(' '):
            trial = f'{line} {word}'.strip()
            if line and font.getlength(trial) > text_width:
                lines.append(line)
                line = word
            else:
                line = trial
        return lines + [line] if line else lines

    # Frame schedule: (number of excerpt tokens shown, heat token, heat weight, text alpha).
    schedule = [(0, None, 0.0, 1.0)] * LEAD_FRAMES
    for i, t in enumerate(steps):
        for f in range(FRAMES_PER_TOKEN):
            schedule.append((i + 1, t, min(1.0, (f + 1) / 3), 1.0))
    last = steps[-1]
    for f in range(HOLD_FRAMES):
        schedule.append((len(steps), last, max(0.0, 1 - f / HOLD_FRAMES) ** 0.5, 1.0))
    for f in range(FADE_FRAMES):
        schedule.append((len(steps), None, 0.0, 1 - (f + 1) / FADE_FRAMES))
    # The slice glides toward each token's attention peak.
    z = target_z[steps[0]]
    slices = []
    for _, t, _, _ in schedule:
        if t is not None:
            z += (target_z[t] - z) * 0.25
        slices.append(int(round(z)))

    def compose(k, previous_heat):
        shown, t, weight, alpha = schedule[k]
        zi = min(max(slices[k], 0), ct.shape[2] - 1)
        gray = ct[:, :, zi].T[r0:r1, c0:c1]  # rows anterior to posterior, columns patient right to left
        rgb = np.repeat(gray[..., None], 3, axis=2) * 255
        heat = heats[t][zi][r0:r1, c0:c1] if t is not None else np.zeros_like(gray)
        heat = previous_heat * (1 - weight) + heat * weight if t is not None else previous_heat * 0.0
        color, a = heat_rgba(heat)
        rgb = rgb * (1 - a) + color * a
        aspect = (c1 - c0) / (r1 - r0)
        fit = (scan_px[0], round(scan_px[0] / aspect)) if aspect > scan_px[0] / scan_px[1] \
            else (round(scan_px[1] * aspect), scan_px[1])
        scan = Image.fromarray(rgb.astype(np.uint8)).resize(fit, Image.LANCZOS)
        canvas = Image.new('RGB', SIZE)
        canvas.paste(scan, (sx0, sy0 + (scan_px[1] - fit[1]) // 2))
        panel = Image.new('RGBA', SIZE, (0, 0, 0, 0))
        draw = ImageDraw.Draw(panel)
        draw.rounded_rectangle(REPORT_BOX, radius=30, fill=(44, 44, 46, 230))
        done = shown == len(steps) and t is None or (shown == len(steps) and k >= LEAD_FRAMES + len(steps) * FRAMES_PER_TOKEN)
        dots = '.' * (1 + (k // 8) % 3)
        caption = 'Report excerpt' if done else f'Generating{dots}'
        draw.text((rx0 + pad, ry0 + pad - 2), caption, font=caption_font, fill=(152, 152, 157, int(255 * alpha)))
        streamed = ''.join(pieces[s] for s in steps[:shown])
        streamed = streamed[max(0, begin - (ends[steps[0]] - len(pieces[steps[0]]))):] if shown else ''
        lines = wrap(streamed.strip())[-VISIBLE_LINES:]
        # Highlight the whole word holding the newest token; tokens can be word pieces.
        current = streamed.rstrip().rsplit(' ', 1)[-1] if shown and not done else ''
        y = ry0 + pad + CAPTION_PX + 18
        for n, line in enumerate(lines):
            x = rx0 + pad
            if current and n == len(lines) - 1 and line.endswith(current):
                head = line[:len(line) - len(current)]
                draw.text((x, y), head, font=font, fill=(230, 230, 235, int(255 * alpha)))
                draw.text((x + font.getlength(head), y), current, font=font,
                          fill=(252, 175, 50, int(255 * alpha)))
            else:
                draw.text((x, y), line, font=font, fill=(230, 230, 235, int(255 * alpha)))
            y += LINE_PX
        canvas = Image.alpha_composite(canvas.convert('RGBA'), panel).convert('RGB')
        return canvas, heat

    video = ASSETS / f'{NAME}.mp4'
    poster = ASSETS / f'{NAME}-poster.webp'
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    encode = ['-c:v', 'libx264', '-preset', 'veryslow', '-crf', str(CRF), '-pix_fmt', 'yuv420p',
              '-vf', COLOR_FILTER, '-movflags', '+faststart', '-an', '-map_metadata', '-1']
    # Poster: the frame where the token " mass" of the first finding is current.
    mass = next(i for i, t in enumerate(steps) if pieces[t].strip() == 'mass')
    poster_frame = LEAD_FRAMES + mass * FRAMES_PER_TOKEN + FRAMES_PER_TOKEN - 1
    with tempfile.TemporaryDirectory() as scratch:
        process = subprocess.Popen(
            [ffmpeg, '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
             '-s', f'{SIZE[0]}x{SIZE[1]}', '-r', str(FPS), '-i', '-', *encode,
             str(Path(scratch) / 'out.mp4')], stdin=subprocess.PIPE)
        previous = np.zeros((r1 - r0, c1 - c0), np.float32)
        for k in range(len(schedule)):
            frame, previous = compose(k, previous)
            if k == poster_frame:
                frame.save(poster, quality=85, method=6)
                frame.save(args.run_dir / 'poster.png')
            process.stdin.write(frame.tobytes())
        process.stdin.close()
        if process.wait() != 0:
            raise RuntimeError('ffmpeg failed')
        os.replace(Path(scratch) / 'out.mp4', video)
    ffmpeg_line = subprocess.run([ffmpeg, '-version'], capture_output=True, text=True,
                                 check=True).stdout.splitlines()[0].split(' Copyright')[0]

    # Where the LUNA16 nodule falls in the token grid, for the record.
    affine = np.array(record['inference']['crop_geometry']['crop_affine_ras_mm'])
    lps = np.array(NODULE_LPS_MM)
    voxel = np.linalg.solve(affine, np.array([-lps[0], -lps[1], lps[2], 1.0]))[:3]
    nodule_token = [int(v // patch) for v in voxel[::-1]]
    out = {
        'schema_version': 1,
        'method': f'mlx-reason-ct {record["runtime"]["version"]} structured chest CT report on one '
                  'LUNA16 CT; decoder attention for each streamed token shown on an axial slice',
        'runtime': record['runtime'],
        'weights': record['weights'],
        'source': {**record['source_ct'],
                   'reference_nodule': {'world_lps_mm': list(NODULE_LPS_MM), 'diameter_mm': 25.23,
                                        'source': 'LUNA16 annotations.csv consensus nodule',
                                        'token_zyx': nodule_token}},
        'inference': {k: v for k, v in record['inference'].items() if k != 'crop_geometry'},
        'report_text': record['text'],
        'excerpt': EXCERPT,
        'excerpt_tokens': [{'piece': pieces[t], 'peak_token_zyx': [int(c) for c in peaks[t]],
                            'image_share_mean_layers': round(float(data['image_share'][:, t].mean()), 3)}
                           for t in steps],
        'display': {
            'renderer': 'docs/hero/render_vision_attention.py',
            'attention': 'mean over layers 3, 7, ..., 31 of the per-token visual attention, divided by '
                         'its peak; 8-voxel nearest upsampling and a Gaussian blur of '
                         f'{BLUR_VOXELS} voxels; magenta-to-cream ramp with a 12% floor',
            'slice': 'axial crop slice gliding 25% per frame toward the current token\'s peak',
            'orientation': 'radiological: patient right on image left, anterior at top',
            'crop': 'body bounding box (> -500 HU) over the visited slices, padded by 3%',
            'ct_window_hu': {'level': LUNG_WINDOW[0], 'width': LUNG_WINDOW[1]},
            'timing': {'lead_frames': LEAD_FRAMES, 'frames_per_token': FRAMES_PER_TOKEN,
                       'hold_frames': HOLD_FRAMES, 'fade_frames': FADE_FRAMES},
            'note': 'Decoder attention shows where queries weighted the scan, not why the model wrote a word.',
        },
        'encode': {
            'video': {'codec': 'H.264 (libx264)', 'preset': 'veryslow', 'crf': CRF, 'pix_fmt': 'yuv420p',
                      'color': 'BT.709, limited range', 'fps': FPS, 'frames': len(schedule),
                      'size_px': list(SIZE), 'audio': False, 'movflags': '+faststart',
                      'ffmpeg': ffmpeg_line, 'sha256': sha256(video), 'bytes': video.stat().st_size},
            'poster': {'format': 'WebP', 'quality': 85, 'method': 6, 'frame': poster_frame,
                       'size_px': list(SIZE), 'sha256': sha256(poster), 'bytes': poster.stat().st_size},
        },
        'outputs': {'video': f'site/assets/hero/{NAME}.mp4', 'poster': f'site/assets/hero/{NAME}-poster.webp'},
        'interpretation': 'One automated report on one public, de-identified CT for a software '
                          'visualization. Not reviewed, not a clinical finding and not a validation.',
    }
    (ASSETS / f'{NAME}-run.json').write_text(json.dumps(out, indent=1) + '\n')
    print(f'wrote {video.name} ({video.stat().st_size} bytes), {len(schedule)} frames; nodule token {nodule_token}')


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('stage', choices=['infer', 'render'])
    parser.add_argument('--ct', type=Path, help='infer: the LUNA16 scan as NIfTI')
    parser.add_argument('--run-dir', type=Path, default=RUN_DIR)
    args = parser.parse_args()
    if args.stage == 'infer':
        if args.ct is None:
            parser.error('infer needs --ct')
        infer(args)
    else:
        render(args)


if __name__ == '__main__':
    main()
