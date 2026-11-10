# /// script
# requires-python = ">=3.13"
# dependencies = ["numpy>=2", "pillow>=12", "imageio-ffmpeg>=0.6"]
# ///
"""Render the repository README's animated hero from the homepage film's scenes.

    uv run docs/hero/render_readme_hero.py

Each scene uses render_film's panel layout and compositing, held still for
HOLD_MS and cross-faded into the next with the film's smoothstep, cropped to the
panel area (the film's left side stays black under the page headline). There is
no camera move, so held frames compress to almost nothing and the file stays
small enough for a README.
"""

from pathlib import Path

import numpy as np
from PIL import Image

import render_film as film

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'docs/homepage.webp'
SIZE = (1600, 1000)
CROP = (610, 20, 1570, 980)  # the panel columns of every scene
SIDE = 720
HOLD_MS, FADE_FRAMES, FADE_MS = 2600, 10, 60
QUALITY = 82


def scene_image(scene):
    rgb = film.view(film.composite(scene, SIZE), 1.0, SIZE)
    picture = Image.fromarray(np.uint8(np.clip(np.round(rgb), 0, 255))).crop(CROP)
    return np.asarray(picture.resize((SIDE, SIDE), Image.Resampling.LANCZOS), dtype=np.float32)


def main():
    scenes = [scene_image(scene) for scene in film.LAYOUT]
    frames, durations = [], []
    for index, current in enumerate(scenes):
        following = scenes[(index + 1) % len(scenes)]
        frames.append(current)
        durations.append(HOLD_MS)
        for step in range(1, FADE_FRAMES + 1):
            t = film.smoothstep(step / (FADE_FRAMES + 1))
            frames.append(current * (1 - t) + following * t)
            durations.append(FADE_MS)
    images = [Image.fromarray(np.uint8(np.clip(np.round(frame), 0, 255))) for frame in frames]
    images[0].save(OUTPUT, save_all=True, append_images=images[1:], duration=durations, loop=0,
                   quality=QUALITY, method=6)
    print(f'{OUTPUT.relative_to(ROOT)}: {len(images)} frames, {OUTPUT.stat().st_size} bytes')


if __name__ == '__main__':
    main()
