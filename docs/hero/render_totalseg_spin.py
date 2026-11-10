# /// script
# requires-python = ">=3.13,<3.15"
# dependencies = [
#     "totalsegmentator-mlx==0.1.6",
#     "vtk>=9.5",
#     "nibabel>=5",
#     "numpy>=2",
#     "pillow>=12",
#     "scipy>=1.16",
#     "imageio-ffmpeg>=0.6",
# ]
# ///
"""Render the drag-to-rotate TotalSegmentator view on its model page.

    uv run docs/hero/render_totalseg_spin.py LABELS.nii.gz

LABELS is totalsegmentator-mlx standard mode's own output for the autoPET-III-Lite
CT fdg_0117d7f11f (the case in the totalsegmentator-mlx documentation figure), on
the model's 1.5 mm isotropic grid: saved before the pipeline resamples the labels
back to the CT's 2.0 x 2.0 x 3.0 mm grid. Nothing is segmented here.

Each drawn label becomes a marching-cubes surface of the lightly smoothed label,
shown with a per-tissue PBR material under fixed studio lights, as in that figure.
The camera then turns a full circle about the vertical axis in FRAMES equal steps,
starting from the figure's view. Every surface is clipped at the top of the hip
bones, because the scan's field of view cuts the hips and thighs flat, and the
lowest part of each frame fades to black. The frames are encoded as one looping
H.264 video, one degree per frame, with frequent keyframes so the page can seek to
any angle as the viewer drags.
"""

import argparse
import colorsys
import json
import platform
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import imageio_ffmpeg
import nibabel as nib
import numpy as np
import vtk
from anatomy import lookup
from PIL import Image
from scipy.ndimage import gaussian_filter, zoom
from vtk.util.numpy_support import numpy_to_vtk

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'site/assets/hero'
RUN_DIR = ROOT / 'dist/totalseg-spin-demo'

FRAMES, FPS, KEYFRAME_INTERVAL, CRF = 360, 30, 10, 18
FRAME = (960, 720)
START_AZIMUTH = 22.0  # degrees from straight anterior, the documentation figure's view
FADE = 0.14  # fraction of the frame height that fades to black at the bottom
SUPERSAMPLE = 2
SMOOTHING_ITERATIONS = 60
SMOOTHING_PASS_BAND = 0.005
THIN_SIGMA = 0.55
ORGAN_SIGMA = 1.0  # voxels on the isotropic 1.5 mm grid
THIN_DECIMATION = 0.1
ORGAN_DECIMATION = 0.3
ALBEDO_GAMMA = 2.2  # VTK's PBR shader expects linear albedo

# Tissue class -> (roughness, clear-coat strength, coat roughness, palette chroma).
MATERIALS = {
    'bone': (0.8, 0.0, 0.2, 1.0),
    'muscle': (0.6, 0.06, 0.45, 1.0),
    'organ': (0.45, 0.25, 0.25, 0.8),
    'vessel': (0.35, 0.5, 0.15, 1.0),
    'lung': (0.6, 0.0, 0.2, 1.0),
}
TISSUE = (
    ('bone', ('vertebrae', 'rib', 'sacrum', 'hip', 'femur', 'scapula', 'clavicula', 'sternum', 'costal')),
    ('muscle', ('gluteus', 'autochthon', 'iliopsoas')),
    ('vessel', ('aorta', 'artery', 'trunk', 'vein', 'vena')),
    ('lung', ('lung',)),
)
TRANSLUCENT = {'lung': 0.16}
# Bowel loops would hide the retroperitoneum, and the scan cuts through the skull and
# upper arms; these are segmented but not drawn.
HIDDEN = ('small_bowel', 'colon', 'duodenum', 'skull', 'brain', 'humerus')
# Thin structures keep their shape only with light smoothing.
THIN = ('rib', 'costal', 'subclavian', 'common_carotid', 'brachiocephalic', 'adrenal',
        'iliac', 'pulmonary_vein', 'atrial', 'spinal_cord', 'esophagus', 'trachea', 'clavicula')
SSAO_RADIUS, SSAO_BIAS, SSAO_KERNEL = 8.0, 2.0, 128  # mm, mm, samples
# White directional key, fill and rim lights; offsets from the scene center, mm, for the
# starting view. They turn with the camera, so every angle is lit like that view.
LIGHTS = (((-900.0, 1100.0, 1100.0), 2.8), ((1100.0, 800.0, 200.0), 0.45),
          ((500.0, -1100.0, 800.0), 1.2))

def colour(name):
    """Palette color scaled to the tissue's chroma."""
    rgb = lookup(name)
    if rgb is None:
        raise KeyError(f'No color for {name}')
    chroma = MATERIALS[tissue(name)][3]
    h, light, s = colorsys.rgb_to_hls(*(c / 255 for c in rgb))
    return tuple(round(c * 255) for c in colorsys.hls_to_rgb(h, light, s * chroma))


def tissue(name):
    return next((kind for kind, prefixes in TISSUE if name.startswith(prefixes)), 'organ')


def surface(mask, spacing, origin, sigma, decimate, upsample=2):
    """Decimated, smoothed marching-cubes surface at the 0.5 level of the smoothed mask.

    The mask is linearly upsampled after smoothing so voxel steps do not terrace.
    """
    smooth = zoom(gaussian_filter(mask, sigma), upsample, order=1)
    image = vtk.vtkImageData()
    image.SetDimensions(*smooth.shape)
    image.SetSpacing(*(s / upsample for s in spacing))
    image.SetOrigin(*origin)
    image.GetPointData().SetScalars(numpy_to_vtk(np.ascontiguousarray(smooth.ravel(order='F')), deep=True))
    contour = vtk.vtkFlyingEdges3D()
    contour.SetInputData(image)
    contour.SetValue(0, 0.5)
    contour.ComputeNormalsOff()
    reduce = vtk.vtkQuadricDecimation()
    reduce.SetInputConnection(contour.GetOutputPort())
    reduce.SetTargetReduction(decimate)
    smoother = vtk.vtkWindowedSincPolyDataFilter()
    smoother.SetInputConnection(reduce.GetOutputPort())
    smoother.SetNumberOfIterations(SMOOTHING_ITERATIONS)
    smoother.SetPassBand(SMOOTHING_PASS_BAND)
    smoother.NonManifoldSmoothingOn()
    smoother.NormalizeCoordinatesOn()
    normals = vtk.vtkPolyDataNormals()
    normals.SetInputConnection(smoother.GetOutputPort())
    normals.SetFeatureAngle(80)
    normals.SplittingOff()
    normals.Update()
    return normals.GetOutput()


def actor(poly, name, clip):
    roughness, coat, coat_roughness, _ = MATERIALS[tissue(name)]
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(poly)
    mapper.ScalarVisibilityOff()
    mapper.AddClippingPlane(clip)
    item = vtk.vtkActor()
    item.SetMapper(mapper)
    prop = item.GetProperty()
    prop.SetColor(*((c / 255) ** ALBEDO_GAMMA for c in colour(name)))
    prop.SetOpacity(next((v for k, v in TRANSLUCENT.items() if name.startswith(k)), 1.0))
    prop.SetInterpolationToPBR()
    prop.SetMetallic(0.0)
    prop.SetRoughness(roughness)
    prop.SetCoatStrength(coat)
    prop.SetCoatRoughness(coat_roughness)
    return item


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('labels', type=Path)
    args = parser.parse_args()
    from totalsegmentator_mlx.labels import LABELS

    image = nib.as_closest_canonical(nib.load(args.labels))
    labels = np.asarray(image.dataobj).astype(np.int16)
    spacing = [float(z) for z in image.header.get_zooms()[:3]]
    if not np.allclose(image.affine[:3, :3], np.diag(spacing)):
        raise ValueError('Surface rendering requires an axis-aligned canonical voxel grid')
    present = sorted(int(v) for v in np.unique(labels) if v)
    if not set(present) <= set(LABELS):
        raise ValueError('The label map has IDs outside the TotalSegmentator label table')
    drawn = [v for v in present if not LABELS[v].startswith(HIDDEN)]

    # Clip at the top of the hip bones; frame what is drawn above it.
    hips = np.argwhere(np.isin(labels, [v for v in present if LABELS[v].startswith('hip')]))
    if not len(hips):
        raise ValueError('No hip labels to place the clipping plane')
    clip_z = float((hips[:, 2].max() + 1) * spacing[2])
    plane = vtk.vtkPlane()
    plane.SetOrigin(0.0, 0.0, clip_z)
    plane.SetNormal(0.0, 0.0, 1.0)

    renderer = vtk.vtkRenderer()
    renderer.SetBackground(0, 0, 0)
    for value in drawn:
        name = LABELS[value]
        where = np.argwhere(labels == value)
        lo = np.maximum(where.min(0) - 3, 0)
        hi = np.minimum(where.max(0) + 4, labels.shape)
        if hi[2] * spacing[2] <= clip_z:
            continue
        crop = (labels[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]] == value).astype(np.float32)
        origin = [float(lo[i] * spacing[i]) for i in range(3)]
        thin = name.startswith(THIN)
        poly = surface(crop, spacing, origin, THIN_SIGMA if thin else ORGAN_SIGMA,
                       THIN_DECIMATION if thin else ORGAN_DECIMATION)
        renderer.AddActor(actor(poly, name, plane))

    inside = np.argwhere(np.isin(labels[::2, ::2, :], drawn)) * np.array([2, 2, 1])
    inside = inside[inside[:, 2] * spacing[2] >= clip_z]
    # Percentiles keep a few stray voxels from widening the frame.
    lo = np.percentile(inside, 0.2, axis=0) * np.array(spacing)
    hi = (np.percentile(inside, 99.8, axis=0) + 1) * np.array(spacing)
    lo[2] = clip_z
    centre = [float(v) for v in (lo + hi) / 2]
    extent = hi - lo
    # Parallel scale is half the view height; it must hold the tallest and widest views.
    widest = float(np.hypot(extent[0], extent[1]))
    scale = max(extent[2] / 2, widest / 2 * FRAME[1] / FRAME[0]) * 1.09

    renderer.AutomaticLightCreationOff()
    lights = []
    for offset, intensity in LIGHTS:
        light = vtk.vtkLight()
        light.SetLightTypeToSceneLight()
        light.PositionalOff()
        light.SetFocalPoint(*centre)
        light.SetIntensity(intensity)
        renderer.AddLight(light)
        lights.append((light, offset))
    renderer.UseFXAAOn()
    renderer.UseSSAOOn()
    renderer.SSAOBlurOn()
    renderer.SetSSAORadius(SSAO_RADIUS)
    renderer.SetSSAOBias(SSAO_BIAS)
    renderer.SetSSAOKernelSize(SSAO_KERNEL)
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
    window.AddRenderer(renderer)
    window.SetSize(FRAME[0] * SUPERSAMPLE, FRAME[1] * SUPERSAMPLE)
    fade = np.ones(FRAME[1])
    ramp = int(FADE * FRAME[1])
    t = np.linspace(0, 1, ramp)
    fade[-ramp:] = (1 - t * t * (3 - 2 * t))
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    video = ASSETS / 'totalseg-spin.mp4'
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    # BT.709 matrix for the RGB conversion, and BT.709 tags on every encoded frame.
    encode = ['-c:v', 'libx264', '-preset', 'veryslow', '-crf', str(CRF), '-pix_fmt', 'yuv420p',
              '-g', str(KEYFRAME_INTERVAL), '-vf',
              ('scale=out_color_matrix=bt709:out_range=tv,'
               'setparams=range=tv:color_primaries=bt709:color_trc=bt709:colorspace=bt709'),
              '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
              '-color_range', 'tv', '-movflags', '+faststart', '-an', '-map_metadata', '-1']
    process = subprocess.Popen([ffmpeg, '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                                '-s', f'{FRAME[0]}x{FRAME[1]}', '-r', str(FPS), '-i', '-', *encode,
                                str(video)], stdin=subprocess.PIPE)
    for index in range(FRAMES):
        # Turn toward the patient's left from the figure's view; superior stays up.
        turn = np.radians(START_AZIMUTH + 360.0 * index / FRAMES)
        camera.SetPosition(centre[0] - 2000 * np.sin(turn), centre[1] + 2000 * np.cos(turn), centre[2])
        delta = turn - np.radians(START_AZIMUTH)
        cos, sin = np.cos(delta), np.sin(delta)
        for light, (dx, dy, dz) in lights:
            light.SetPosition(centre[0] + cos * dx - sin * dy, centre[1] + sin * dx + cos * dy, centre[2] + dz)
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
        rgb = np.asarray(frame, dtype=np.float64) * fade[:, None, None]
        frame = Image.fromarray(np.uint8(np.round(rgb)))
        if index == 0:
            frame.save(ASSETS / 'totalseg-spin-poster.webp', quality=88, method=6)
        process.stdin.write(frame.tobytes())
        print(f'{index + 1}/{FRAMES}', end='\r', flush=True)
    process.stdin.close()
    if process.wait() != 0:
        raise RuntimeError('ffmpeg failed')

    record = {
        'schema_version': 1,
        'method': 'marching-cubes surfaces of a saved totalsegmentator-mlx standard-mode label map, '
                  'rendered from FRAMES camera angles about the vertical axis',
        'source': {'dataset': 'autoPET-III-Lite (subset of the autoPET III challenge data)',
                   'case': 'fdg_0117d7f11f', 'license': 'CC BY-NC 4.0',
                   'segmentation': 'totalsegmentator-mlx standard mode, labels on the model\'s 1.5 mm grid '
                                   'before resampling to the CT grid',
                   'label_grid_mm': spacing, 'labels_present': len(present),
                   'labels_drawn': [LABELS[v] for v in drawn]},
        'display': {
            'renderer': 'docs/hero/render_totalseg_spin.py',
            'hidden': list(HIDDEN), 'translucent': TRANSLUCENT,
            'clip': 'every surface clipped at the top of the hip bones '
                    f'({clip_z:.1f} mm above the grid origin); the field of view cuts the hips flat',
            'frames': FRAMES, 'step_degrees': 360 / FRAMES, 'start_azimuth_degrees': START_AZIMUTH,
            'frame_px': list(FRAME), 'supersample': SUPERSAMPLE,
            'bottom_fade': FADE, 'projection': 'parallel', 'lights': 'turn with the camera',
        },
        'runtime': {'vtk': version('vtk'), 'totalsegmentator_mlx': version('totalsegmentator-mlx'),
                    'python_version': platform.python_version()},
        'encode': {'codec': 'H.264 (libx264)', 'preset': 'veryslow', 'crf': CRF, 'fps': FPS,
                   'keyframe_interval': KEYFRAME_INTERVAL, 'pix_fmt': 'yuv420p',
                   'color': 'BT.709, limited range', 'frames': FRAMES, 'audio': False,
                   'movflags': '+faststart', 'bytes': video.stat().st_size},
        'outputs': {'video': 'site/assets/hero/totalseg-spin.mp4',
                    'poster': 'site/assets/hero/totalseg-spin-poster.webp'},
    }
    (ASSETS / 'totalseg-spin-run.json').write_text(json.dumps(record, indent=1) + '\n')
    print(f'\nwrote {FRAMES} frames; video {record["encode"]["bytes"]} bytes', file=sys.stderr)


if __name__ == '__main__':
    main()
