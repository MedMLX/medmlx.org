# Homepage output film

`outputs.mp4` is a silent, 36-second H.264 loop at 1600 × 1000 and 24 fps.
It is encoded with libx264, CRF 25, yuv420p, tagged BT.709, and faststart for
inline playback. `poster.webp` is its first frame. `docs/hero/render_film.py`
rebuilds both from `sources.json` and the panel WebPs. Most other WebP files
are cropped documentation panels, also used for the homepage model and task
images. The exceptions are the computed radiomics image, the Vision-language
crop and the three card posters, described below.

`sources.json` records documentation source tags and crops, the computed
radiomics asset, and the six three-panel scenes. Documentation figures were
read from their Git tags, not from working trees.

`radiomics-texture.webp` and its lossless PNG were computed for this site.
MedMLX job `5192108bfe00` ran mlxradiomics
0.1.0.dev5 on the Apple Silicon GPU with `voxel=True`, 10-HU bins, a five-pixel kernel
radius, and 2D neighborhoods. Its source is the retained AMOS22 CT plane and
SwinUNETR liver label in `figure1.npz`, which is not included in this repository.
The ROI is the largest connected component of the predicted liver label;
the two detached components were excluded before computing radiomics.
`radiomics-run.json` records source hashes, that ROI selection, the actual
runtime/settings, feature-map hashes and the display transform. No feature
values are synthesized or smoothed. The CT uses a −160 to 240 HU window;
the sequential crimson palette maps the ROI's 2nd–98th entropy percentiles.
The legend reports bits. The film uses this image. The renderer is `docs/hero/render_radiomics.py`; local NIfTI
inputs and raw map outputs remain in `dist/radiomics-demo/`.

The crops remove figure headings and legends. An RGB black-level subtraction
of 8 and saturation of 0.78 unify the documentation figure backgrounds;
the computed radiomics asset retains its renderer's palette. Each scene
lasts six seconds, with a 1.5-second
smoothstep dissolve to the next. A periodic 1.00–1.03 scale about the frame
center (1.015 + 0.015·sin(2πt/36)) provides a gentle camera move and returns to
the same position at the loop seam. Each scene is composited once on a float
canvas at twice the film's resolution, and every frame is resampled through one
float crop box, so the move has no whole-pixel steps.

The browser starts the film only with the hero visible. It pauses when the
hero leaves the viewport, the tab is hidden, or the user presses Pause film.
Back and Next move to the adjacent six-second scene, wrapping at either end
and preserving the current play/pause state.
Reduced-motion and data-saving preferences use the poster without loading
the video. Routing away disposes the observer, listeners, and media source.

## Task card loops

Three task cards loop real model output computed on 2026-10-31. Each has
`<name>.mp4`, `<name>-poster.webp` (frame 0, shown for reduced motion and data
saving; the nodule loop starts on its box-center slice), `<name>-run.json` (inputs, runtime, settings and hashes) and a renderer
in `docs/hero/`. Raw outputs stay in `dist/<name>-demo/`.

- `abdomen-scroll`: swin-unetr-mlx 0.2.5 organ labels on HCC-TACE-Seg case
  HCC_063, 35 axial slices, soft-tissue window.
- `nodule-scroll`: lung-nodule-mlx 0.2.5 on a held-out LUNA16 subset0 CT; the
  predicted box is drawn on the 8 slices it spans. Soft-tissue window, to match
  the abdomen loop.
- `radiomics-organs`: mlxradiomics 0.1.0.dev8 entropy maps for the liver,
  kidneys and pancreas on the same AMOS22 slice as `radiomics-texture`, with
  one shared color range. The liver map is identical to the dev5 one.

The cards play these only while visible, pause off-screen or in a hidden tab,
and each has its own pause button. The Vision-language report still types once
on entry. The Generation and Feature extraction cards keep still images.

See [credits.html](credits.html) for source-image attribution and terms.
Media is not covered by the website's Apache-2.0 code license.

## Vision-language card

The card uses `vision-language-ct.webp`, a crop of the axial chest image in
a saved NV-Reason-CT run figure (not included in this repository), alongside three
verbatim excerpts of its paired generated report. `vision-language.json`
records the source figure hash, crop, dataset and text. The words are HTML,
not burned into a bitmap. The report reveals over 3.6 seconds when the card
first enters the viewport. Reduced motion shows it complete, and route
changes disconnect the observer. This is a presentation
of saved output; the website does not run a model.
