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
`radiomics-run.json` records the source, that ROI selection, the actual
runtime/settings, feature-map summaries and the display transform. No feature
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

Six task cards loop real model output, computed from 2026-10-31 to 2026-11-05. Each has
`<name>.mp4`, `<name>-poster.webp` (frame 0, shown for reduced motion and data
saving; the nodule loop starts on its box-center slice), `<name>-run.json` (inputs, runtime, settings and display) and a renderer
in `docs/hero/`. Raw outputs stay in `dist/<name>-demo/`.

- `abdomen-scroll`: swin-unetr-mlx 0.2.5 organ labels on HCC-TACE-Seg case
  HCC_063, 35 axial slices, soft-tissue window.
- `nodule-scroll`: lung-nodule-mlx 0.2.5 on a held-out LUNA16 subset0 CT; the
  predicted box is drawn on the 8 slices it spans. Soft-tissue window, to match
  the abdomen loop.
- `radiomics-organs`: mlxradiomics 0.1.0.dev8 entropy maps for the liver,
  kidneys and pancreas on the same AMOS22 slice as `radiomics-texture`, with
  one shared color range. The liver map is identical to the dev5 one.
- `generation-grid`: mlx-generate-ctmr 0.5.2.post2 volumes generated from
  noise, three paired CTs and three MR-Brain contrasts, scrolled together. CT
  seeds and each tile's slice range were chosen by visual review; ranges stop
  where a section shrinks inside its fixed tile crop. Tiles share one width.
- `vision-attention`: mlx-reason-ct 0.3.6 writes a structured report for a
  LUNA16 subset0 CT with a 25 mm nodule; the lung-findings excerpt streams token
  by token while each token's decoder attention, averaged over the full-attention layers, is
  shown on an axial slice that follows its peak. The poster is the frame where
  "mass" is written.
- `feature-scroll`: radimagenet-mlx 0.3.3 ResNet50 features for 148 axial
  slices of a LUNA16 subset0 CT, superior to inferior (the top 4 slices, at the
  shoulder joints, are left out). Each slice shows its
  7 × 7 spatial map as cells colored by the scan's first three principal
  components; the panel adds one column per slice for the 96 most variable
  pooled features, z-scored and ordered by the slice where each peaks.

The cards play these only while visible, pause off-screen or in a hidden tab,
and each has its own pause button.

## Featured model images

The featured model cards and the model pages use `featured-<card>.webp`
(model pages without one show a task loop or no panel): each subject centered
on one black 960 × 720 canvas at 86% fill, so wide slices and the tall 3D render
appear at a consistent size. Their sources are `liver.webp`;
`anatomy-torso.webp`, the torso of the 3D surface panel of totalsegmentator-mlx
v0.1.6 `docs/example.png` (the render is clipped flat at the hips, so the crop
stops there and its lowest 20% fades to black); `medsam-slice.webp`, a
medsam2-mlx 0.2.8 box-prompted mask on the LUNA16 CT used by the
Vision-language card, recorded in `medsam-slice-run.json`; and
`biomedparse-panel.webp`, the text-prompt panel of biomedparse-mlx v0.1.5
`docs/example-abdomen.png`, flipped vertically because that figure shows
posterior at the top (the film's `prompt.webp` is flipped the same way, as
recorded in `sources.json`); and `segresnet-axial.webp`, the axial panel of
segresnet-mlx v0.3.3 `docs/example.png`. `kidney`, `brain`, `xray` and `pet`
are the film panels. Figure crops carry the documentation-panel black
level and saturation. All come from `docs/hero/render_featured.py`; the film
keeps its own panels.

## TotalSegmentator turntable

`totalseg-spin.mp4` is a 12-second, 30 fps H.264 loop at 960 × 720: the
totalsegmentator-mlx standard-mode labels for autoPET-III-Lite case
fdg_0117d7f11f, on the model's 1.5 mm grid, drawn as marching-cubes surfaces and
rendered from 360 angles 1° apart, with the lights turning with the camera.
Keyframes every 10 frames let the page seek to any angle as the viewer drags.
Surfaces are clipped at the top of the hip bones and the bottom of each frame
fades to black. `docs/hero/render_totalseg_spin.py` renders it and writes
`totalseg-spin-run.json`.

## Slice stacks

`<stack>.mp4` for `totalseg-slices` and `medsam2-slices` scrolls
through the axial slices that hold a runtime's labels, over the source CT, and back
up, at 24 fps with keyframes every 8 frames so the model pages can seek to any slice
as the viewer drags. Labels are translucent fills with solid outlines in the shared
palette (`docs/hero/anatomy.py`); lungs, bone and muscle are filled lightly.
`docs/hero/render_slice_stacks.py` renders each from a saved label map and writes
`<stack>-run.json`. The model pages' other loops can be dragged to scrub as well.

See [credits.html](credits.html) for source-image attribution and terms.
Media is not covered by the website's Apache-2.0 code license.
