# /// script
# requires-python = ">=3.13,<3.15"
# dependencies = [
#     "vtk>=9.5",
#     "nibabel>=5",
#     "numpy>=2",
#     "pillow>=12",
#     "scipy>=1.16",
#     "imageio-ffmpeg>=0.6",
# ]
# ///
"""Render the drag-to-rotate and slice views on the SIAM model page.

    uv run docs/hero/render_siam_views.py spin --labels MASK.nii.gz --run RESULT.json
    uv run docs/hero/render_siam_views.py slices --mri T1.nii.gz --labels MASK.nii.gz --run RESULT.json

MASK is the label map that nnunet-mlx's ``siam()`` wrote for the OpenNeuro ds000001
sub-01 T1 (CC0, defaced), and RESULT the runner's returned result saved as JSON.
Nothing is segmented here, and the labels are never edited.

spin: each drawn label becomes a marching-cubes surface of the lightly smoothed
label with a per-tissue PBR material. Scalp and skull are translucent so the cortex
shows from every side, and one octant (left, posterior, superior of the brain's
centre) is cut out of the scalp, skull, cortex, white matter and vessels so the
deep nuclei and ventricles show inside. The camera turns a full circle about the
vertical axis in FRAMES one-degree steps from a view into the cut; the lights turn
with it. The neck, where the scan ends, fades to black.

slices: the axial MRI slices from the top of the head to just below the
cerebellum, radiological orientation, every label a translucent fill with a solid
outline. The video runs down the stack and back up so it loops without a seam.

Both are encoded as H.264 with frequent keyframes so the page can seek to any
frame as the viewer drags.
"""

import argparse
import colorsys
import json
import platform
import subprocess
from importlib.metadata import version
from pathlib import Path

import imageio_ffmpeg
import nibabel as nib
import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'site/assets/hero'
FRAME = (960, 720)
SOURCE = {'dataset': 'OpenNeuro ds000001', 'case': 'sub-01 T1w', 'license': 'CC0', 'note': 'defaced'}

LABELS = {1: 'GM', 2: 'WM', 3: 'CSF', 4: 'CSFv', 5: 'cerGM', 6: 'Thal', 7: 'Pal', 8: 'Put', 9: 'Caud',
          10: 'Accu', 11: 'Amyg', 12: 'Hippo', 13: 'Dura', 14: 'vascular', 15: 'Skull', 16: 'Head',
          17: 'Anomalies'}
# The palette of the MedMLX/siam model card figure.
COLOURS = {1: '#3d8bfd', 2: '#f4c95d', 3: '#20c9b5', 4: '#0e9f8e', 5: '#7bd389', 6: '#ff6b9a',
           7: '#b388ff', 8: '#ff9f43', 9: '#f15bb5', 10: '#fee440', 11: '#5ee7ff', 12: '#9d8df1',
           13: '#c08552', 14: '#c9184a', 15: '#efe8da', 16: '#d9a88a', 17: '#ff2b2b'}


def rgb(value):
    code = COLOURS[value]
    return tuple(int(code[i:i + 2], 16) for i in (1, 3, 5))


def encode(frames, video, fps, keyframes, crf):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    arguments = ['-c:v', 'libx264', '-preset', 'veryslow', '-crf', str(crf), '-pix_fmt', 'yuv420p',
                 '-g', str(keyframes), '-vf',
                 ('scale=out_color_matrix=bt709:out_range=tv,'
                  'setparams=range=tv:color_primaries=bt709:color_trc=bt709:colorspace=bt709'),
                 '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
                 '-color_range', 'tv', '-movflags', '+faststart', '-an', '-map_metadata', '-1']
    process = subprocess.Popen([ffmpeg, '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                                '-s', f'{FRAME[0]}x{FRAME[1]}', '-r', str(fps), '-i', '-', *arguments,
                                str(video)], stdin=subprocess.PIPE)
    count = 0
    for frame in frames:
        process.stdin.write(np.ascontiguousarray(frame, dtype=np.uint8).tobytes())
        count += 1
    process.stdin.close()
    if process.wait() != 0:
        raise RuntimeError('ffmpeg failed')
    return arguments, count


def runner(path):
    """The runner's saved result, with output paths reduced to file names."""
    result = json.loads(path.read_text())
    result['outputs'] = {role: Path(value).name for role, value in result.get('outputs', {}).items()}
    return result


def load_labels(path):
    image = nib.as_closest_canonical(nib.load(path))
    labels = np.asarray(image.dataobj).astype(np.int16)
    found = {int(v) for v in np.unique(labels) if v}
    if not found <= set(LABELS):
        raise ValueError(f'Labels outside the SIAM table: {sorted(found - set(LABELS))}')
    return image, labels


# ---------------------------------------------------------------- spin

SPIN_FRAMES, SPIN_FPS, SPIN_KEYFRAMES, SPIN_CRF = 360, 30, 10, 18
START_AZIMUTH = 228.0  # degrees from anterior towards the patient's left: into the cut
ELEVATION = 18.0
SUPERSAMPLE = 2
FADE = 0.12
OPACITY = {16: 0.16, 15: 0.30}
# CSF and dura are thin shells over the brain that would hide it; Anomalies is drawn
# when present.
DRAWN = (16, 15, 1, 2, 5, 4, 6, 7, 8, 9, 10, 11, 12, 14, 17)
CUT = {16, 15, 1, 2, 14}
# (roughness, clear-coat strength, coat roughness, chroma)
MATERIALS = {'skin': (0.55, 0.15, 0.35, 0.9), 'bone': (0.85, 0.0, 0.2, 1.0),
             'brain': (0.45, 0.25, 0.25, 0.85), 'deep': (0.35, 0.35, 0.2, 1.0),
             'vessel': (0.3, 0.6, 0.15, 1.0)}
KIND = {16: 'skin', 15: 'bone', 1: 'brain', 2: 'brain', 5: 'brain', 14: 'vessel'}
LIGHTS = (((-900.0, -1100.0, 1300.0), 2.6), ((1100.0, 600.0, 300.0), 0.5),
          ((300.0, 1100.0, 700.0), 1.0), ((0.0, -200.0, -1200.0), 0.25))


def surface(vtk, to_vtk, mask, spacing, origin, sigma):
    smooth = ndimage.zoom(ndimage.gaussian_filter(mask, sigma), 2, order=1)
    image = vtk.vtkImageData()
    image.SetDimensions(*smooth.shape)
    image.SetSpacing(*(s / 2 for s in spacing))
    image.SetOrigin(*origin)
    image.GetPointData().SetScalars(to_vtk(np.ascontiguousarray(smooth.ravel(order='F')), deep=True))
    contour = vtk.vtkFlyingEdges3D()
    contour.SetInputData(image)
    contour.SetValue(0, 0.5)
    contour.ComputeNormalsOff()
    reduce = vtk.vtkQuadricDecimation()
    reduce.SetInputConnection(contour.GetOutputPort())
    reduce.SetTargetReduction(0.4)
    smoother = vtk.vtkWindowedSincPolyDataFilter()
    smoother.SetInputConnection(reduce.GetOutputPort())
    smoother.SetNumberOfIterations(40)
    smoother.SetPassBand(0.01)
    smoother.NonManifoldSmoothingOn()
    smoother.NormalizeCoordinatesOn()
    normals = vtk.vtkPolyDataNormals()
    normals.SetInputConnection(smoother.GetOutputPort())
    normals.SetFeatureAngle(80)
    normals.SplittingOff()
    normals.Update()
    return normals.GetOutput()


def spin(args):
    import vtk
    from vtk.util.numpy_support import numpy_to_vtk

    image, labels = load_labels(args.labels)
    spacing = [float(z) for z in image.header.get_zooms()[:3]]
    if not np.allclose(image.affine[:3, :3], np.diag(spacing)):
        raise ValueError('Surface rendering requires an axis-aligned canonical voxel grid')
    # Draw only what is connected to the head: the scan also holds a small object
    # beside the face (likely a skin marker) that the model labels as scalp.
    parts, _ = ndimage.label(labels > 0)
    sizes = np.bincount(parts.ravel())
    sizes[0] = 0
    detached = int(((parts != sizes.argmax()) & (labels > 0)).sum())
    labels = np.where(parts == sizes.argmax(), labels, 0)
    brain = np.isin(labels, [2, 4, 5, 6, 7, 8, 9, 10, 11, 12])
    centre_vox = np.argwhere(brain).mean(0).astype(int)
    cut = np.zeros(labels.shape, dtype=bool)
    cut[:centre_vox[0] + 2, :centre_vox[1] + 16, centre_vox[2] - 14:] = True

    renderer = vtk.vtkRenderer()
    renderer.SetBackground(0, 0, 0)
    drawn = []
    for value in DRAWN:
        mask = labels == value
        if value in CUT:
            mask &= ~cut
        # Draw connected pieces large enough to read as structures; stray voxels would
        # float as specks. Vessels need a larger minimum to read as vessels.
        parts, _ = ndimage.label(mask)
        sizes = np.bincount(parts.ravel())
        keep = np.flatnonzero(sizes > (60 if value == 14 else 30))
        mask = np.isin(parts, keep[keep > 0])
        if not mask.any():
            continue
        where = np.argwhere(mask)
        lo = np.maximum(where.min(0) - 3, 0)
        hi = np.minimum(where.max(0) + 4, labels.shape)
        crop = mask[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]].astype(np.float32)
        poly = surface(vtk, numpy_to_vtk, crop, spacing, [float(lo[i] * spacing[i]) for i in range(3)],
                       0.6 if value == 14 else 0.9)
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(poly)
        mapper.ScalarVisibilityOff()
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        prop = actor.GetProperty()
        roughness, coat, coat_roughness, chroma = MATERIALS[KIND.get(value, 'deep')]
        h, light, s = colorsys.rgb_to_hls(*(c / 255 for c in rgb(value)))
        prop.SetColor(*(c ** 2.2 for c in colorsys.hls_to_rgb(h, light, s * chroma)))
        prop.SetOpacity(OPACITY.get(value, 1.0))
        prop.SetInterpolationToPBR()
        prop.SetMetallic(0.0)
        prop.SetRoughness(roughness)
        prop.SetCoatStrength(coat)
        prop.SetCoatRoughness(coat_roughness)
        renderer.AddActor(actor)
        drawn.append(LABELS[value])

    head = np.argwhere(labels > 0)
    lo = np.percentile(head, 0.2, axis=0) * np.array(spacing)
    hi = (np.percentile(head, 99.8, axis=0) + 1) * np.array(spacing)
    centre = (lo + hi) / 2
    extent = hi - lo
    widest = float(np.hypot(extent[0], extent[1]))
    scale = max(extent[2] / 2, widest / 2 * FRAME[1] / FRAME[0]) * 1.1

    renderer.AutomaticLightCreationOff()
    lights = []
    for offset, intensity in LIGHTS:
        light = vtk.vtkLight()
        light.SetLightTypeToSceneLight()
        light.PositionalOff()
        light.SetFocalPoint(*centre)
        light.SetIntensity(intensity)
        renderer.AddLight(light)
        lights.append((light, np.array(offset)))
    renderer.UseFXAAOn()
    renderer.UseSSAOOn()
    renderer.SSAOBlurOn()
    renderer.SetSSAORadius(6.0)
    renderer.SetSSAOBias(1.5)
    renderer.SetSSAOKernelSize(128)
    renderer.SetUseDepthPeeling(1)
    renderer.SetMaximumNumberOfPeels(8)
    camera = renderer.GetActiveCamera()
    camera.ParallelProjectionOn()
    camera.SetFocalPoint(*centre)
    camera.SetViewUp(0, 0, 1)
    camera.SetParallelScale(scale)
    window = vtk.vtkRenderWindow()
    window.SetOffScreenRendering(1)
    window.SetMultiSamples(0)
    window.SetAlphaBitPlanes(1)
    window.AddRenderer(renderer)
    window.SetSize(FRAME[0] * SUPERSAMPLE, FRAME[1] * SUPERSAMPLE)
    fade = np.ones(FRAME[1])
    ramp = int(FADE * FRAME[1])
    t = np.linspace(0, 1, ramp)
    fade[-ramp:] = 1 - t * t * (3 - 2 * t)
    elevation = np.radians(ELEVATION)

    def frames():
        for index in range(SPIN_FRAMES):
            azimuth = np.radians(START_AZIMUTH + 360.0 * index / SPIN_FRAMES)
            direction = np.array([np.cos(elevation) * np.sin(azimuth), np.cos(elevation) * np.cos(azimuth),
                                  np.sin(elevation)])
            camera.SetPosition(*(centre + 2000 * direction))
            turn = azimuth - np.radians(START_AZIMUTH)
            cos, sin = np.cos(turn), np.sin(turn)
            for light, (dx, dy, dz) in lights:
                # Rotate each light about the vertical axis with the camera.
                light.SetPosition(centre[0] + cos * dx + sin * dy, centre[1] - sin * dx + cos * dy, centre[2] + dz)
            renderer.ResetCameraClippingRange()
            window.Render()
            grab = vtk.vtkWindowToImageFilter()
            grab.SetInput(window)
            grab.ReadFrontBufferOff()
            grab.Update()
            data = grab.GetOutput()
            width, height, _ = data.GetDimensions()
            pixels = np.frombuffer(data.GetPointData().GetScalars(), dtype=np.uint8)
            pixels = pixels.reshape(height, width, -1)[::-1, :, :3]
            frame = Image.fromarray(np.ascontiguousarray(pixels)).resize(FRAME, Image.LANCZOS)
            out = np.uint8(np.round(np.asarray(frame, dtype=np.float64) * fade[:, None, None]))
            if index == 0:
                Image.fromarray(out).save(ASSETS / 'siam-spin-poster.webp', quality=88, method=6)
            print(f'{index + 1}/{SPIN_FRAMES}', end='\r', flush=True)
            yield out

    video = ASSETS / 'siam-spin.mp4'
    arguments, count = encode(frames(), video, SPIN_FPS, SPIN_KEYFRAMES, SPIN_CRF)
    record = {
        'schema_version': 1,
        'method': 'marching-cubes surfaces of a saved nnunet-mlx siam() label map, rendered from '
                  f'{SPIN_FRAMES} camera angles about the vertical axis',
        'package': 'nnunet-mlx', 'source': SOURCE, 'runners': [runner(args.run)],
        'display': {
            'renderer': 'docs/hero/render_siam_views.py spin', 'labels_drawn': drawn,
            'translucent': {LABELS[k]: v for k, v in OPACITY.items()},
            'cut': 'left, posterior and superior octant of the brain centre removed from '
                   + ', '.join(LABELS[v] for v in sorted(CUT)),
            'pieces': 'connected pieces of more than 30 voxels, 60 for vessels',
            'detached_voxels_not_drawn': detached,
            'frames': SPIN_FRAMES, 'step_degrees': 360 / SPIN_FRAMES, 'start_azimuth_degrees': START_AZIMUTH,
            'elevation_degrees': ELEVATION, 'frame_px': list(FRAME), 'supersample': SUPERSAMPLE,
            'bottom_fade': FADE, 'projection': 'parallel', 'lights': 'turn with the camera',
        },
        'encode': {'codec': 'H.264 (libx264)', 'fps': SPIN_FPS, 'crf': SPIN_CRF,
                   'keyframe_interval': SPIN_KEYFRAMES, 'frames': count, 'arguments': arguments,
                   'ffmpeg': imageio_ffmpeg.get_ffmpeg_version(), 'bytes': video.stat().st_size},
        'runtime': {'vtk': version('vtk'), 'python_version': platform.python_version()},
        'outputs': {'video': 'site/assets/hero/siam-spin.mp4', 'poster': 'site/assets/hero/siam-spin-poster.webp'},
    }
    (ASSETS / 'siam-spin-run.json').write_text(json.dumps(record, indent=1) + '\n')
    print(f'\nsiam-spin: {count} frames, {video.stat().st_size} bytes')


# ---------------------------------------------------------------- slices

SLICE_FPS, SLICE_KEYFRAMES, SLICE_CRF = 24, 8, 20
MARGIN = 0.92
FILL = 0.42
CONTEXT_FILL = {16: 0.12, 15: 0.22, 13: 0.30}
PAD_BELOW_CEREBELLUM = 6
# Broad tissues are filled only; at this resolution their outlines turn the cortex to noise.
FILL_ONLY = {1, 2, 3, 13, 15, 16}


def display(volume):
    """Canonical RAS voxels [x, y, z] as slices [z][row, col], superior first, radiological."""
    return np.asarray(volume).transpose(2, 1, 0)[::-1, ::-1, ::-1]


def slices(args):
    mri_image = nib.as_closest_canonical(nib.load(args.mri))
    image, labels_ras = load_labels(args.labels)
    if mri_image.shape != image.shape or not np.allclose(mri_image.affine, image.affine, atol=1e-4):
        raise ValueError('MRI and labels must share one voxel grid')
    spacing = [float(z) for z in mri_image.header.get_zooms()[:3]]
    mri = display(mri_image.get_fdata()).astype(np.float32)
    labels = display(labels_ras)
    head = labels > 0
    low, high = np.percentile(mri[head], [0.5, 99.6])
    held = np.flatnonzero(head.any(axis=(1, 2)))
    first = int(held[0])
    cerebellum = np.flatnonzero((labels == 5).any(axis=(1, 2)))
    last = min(int(cerebellum[-1]) + PAD_BELOW_CEREBELLUM, len(labels) - 1)
    union = head[first:last + 1].any(axis=0)
    rows, cols = np.flatnonzero(union.any(axis=1)), np.flatnonzero(union.any(axis=0))
    pad_r, pad_c = round(0.03 * union.shape[0]), round(0.03 * union.shape[1])
    r0, r1 = max(rows[0] - pad_r, 0), min(rows[-1] + 1 + pad_r, union.shape[0])
    c0, c1 = max(cols[0] - pad_c, 0), min(cols[-1] + 1 + pad_c, union.shape[1])
    physical = ((c1 - c0) * spacing[0], (r1 - r0) * spacing[1])
    scale = min(FRAME[0] * MARGIN / physical[0], FRAME[1] * MARGIN / physical[1])
    size = (round(physical[0] * scale), round(physical[1] * scale))
    offset = ((FRAME[0] - size[0]) // 2, (FRAME[1] - size[1]) // 2)
    present = sorted(int(v) for v in np.unique(labels[first:last + 1]) if v)

    frames, counts = [], []
    for k in range(first, last + 1):
        gray = np.clip((mri[k, r0:r1, c0:c1] - low) / (high - low), 0, 1)
        gray[~ndimage.binary_fill_holes(head[k, r0:r1, c0:c1])] = 0
        out = np.asarray(Image.fromarray(np.uint8(np.round(gray * 255))).resize(size, Image.LANCZOS),
                         dtype=np.float64)[:, :, None].repeat(3, axis=2)
        plane = labels[k, r0:r1, c0:c1]
        shown = 0
        for value in present:
            indicator = (plane == value).astype(np.float32)
            if not indicator.any():
                continue
            shown += 1
            mask = np.asarray(Image.fromarray(indicator).resize(size, Image.BILINEAR)) >= 0.5
            edge = mask & ~ndimage.binary_erosion(mask, iterations=2)
            colour = np.asarray(rgb(value), dtype=np.float64)
            fill = CONTEXT_FILL.get(value, FILL)
            out[mask] = (1 - fill) * out[mask] + fill * colour
            if value not in FILL_ONLY:
                out[edge] = colour
        canvas = np.zeros((FRAME[1], FRAME[0], 3), dtype=np.uint8)
        canvas[offset[1]:offset[1] + size[1], offset[0]:offset[0] + size[0]] = np.uint8(np.round(out))
        frames.append(canvas)
        counts.append(shown)

    video = ASSETS / 'siam-slices.mp4'
    # Down the stack and back up, without repeating either end, so the loop is seamless.
    arguments, count = encode([*frames, *frames[-2:0:-1]], video, SLICE_FPS, SLICE_KEYFRAMES, SLICE_CRF)
    poster = int(np.argmax(counts))
    Image.fromarray(frames[poster]).save(ASSETS / 'siam-slices-poster.webp', quality=88, method=6)
    record = {
        'schema_version': 1,
        'method': 'nnunet-mlx siam() label map over its source MRI, shown as axial slices',
        'package': 'nnunet-mlx', 'source': SOURCE, 'runners': [runner(args.run)],
        'display': {
            'renderer': 'docs/hero/render_siam_views.py slices',
            'intensity_window': 'MRI 0.5th to 99.6th percentile inside the head',
            'slices': [first, last], 'slice_count': last - first + 1,
            'range': f'top of the head to {PAD_BELOW_CEREBELLUM} slices below the cerebellum',
            'order': 'superior to inferior, then back up', 'grid_spacing_mm': spacing,
            'canvas_px': list(FRAME), 'slice_px': list(size), 'fill_opacity': FILL,
            'context_fill_opacity': {LABELS[k]: v for k, v in CONTEXT_FILL.items()},
            'outline_px': 2, 'outlines': 'every label except ' + ', '.join(LABELS[v] for v in sorted(FILL_ONLY)),
            'labels_shown': {LABELS[v]: COLOURS[v] for v in present},
            'mask_resampling': 'bilinear indicator, thresholded at 0.5; labels not edited',
            'poster_slice': first + poster,
            'orientation': 'radiological: patient right on image left, anterior at top',
        },
        'encode': {'codec': 'H.264 (libx264)', 'fps': SLICE_FPS, 'crf': SLICE_CRF,
                   'keyframe_interval': SLICE_KEYFRAMES, 'frames': count, 'arguments': arguments,
                   'ffmpeg': imageio_ffmpeg.get_ffmpeg_version(), 'bytes': video.stat().st_size},
        'runtime': {'python_version': platform.python_version(), 'numpy': version('numpy')},
        'outputs': {'video': 'site/assets/hero/siam-slices.mp4',
                    'poster': 'site/assets/hero/siam-slices-poster.webp'},
    }
    (ASSETS / 'siam-slices-run.json').write_text(json.dumps(record, indent=1) + '\n')
    print(f'siam-slices: slices {first}-{last} ({last - first + 1}), {video.stat().st_size} bytes')


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('view', choices=('spin', 'slices'))
    parser.add_argument('--labels', type=Path, required=True)
    parser.add_argument('--mri', type=Path, help='the source MRI (slices only)')
    parser.add_argument('--run', type=Path, required=True, help="siam()'s result, saved as JSON")
    args = parser.parse_args()
    if args.view == 'slices':
        if args.mri is None:
            parser.error('slices needs --mri')
        slices(args)
    else:
        spin(args)


if __name__ == '__main__':
    main()
