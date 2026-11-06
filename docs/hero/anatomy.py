"""One colour per anatomical structure for the website's segmentation renders.

Names are matched by keyword, so TotalSegmentator, BTCV and VISTA-3D label names
share one table; the first matching entry wins, so specific names come first.
Solid organs take distinct hues, arteries are red and veins blue, and muscle and
bone are muted so the organs and vessels carry the colour.
"""

BONE, MUSCLE, ARTERY, VEIN, LUNG = (232, 218, 186), (198, 130, 118), (224, 48, 52), (48, 102, 224), (150, 196, 236)
PALETTE = [
    (('tumor', 'tumour', 'lesion', 'cyst'), (64, 224, 96)),
    (('hepatic vessel', 'portal', 'splenic vein'), (56, 196, 232)),
    (('pulmonary_vein',), (232, 104, 150)),
    (('liver',), (146, 62, 46)),
    (('spleen',), (128, 88, 206)),
    (('adrenal',), (184, 228, 60)),
    (('kidney',), (242, 150, 36)),
    (('gallbladder',), (28, 164, 138)),
    (('pancrea',), (250, 210, 60)),
    (('esophag',), (240, 150, 200)),
    (('stomach',), (214, 86, 160)),
    (('duodenum',), (246, 164, 200)),
    (('small_bowel',), (150, 186, 120)),
    (('colon', 'rectum'), (204, 184, 72)),
    (('bladder',), (244, 226, 118)),
    (('prostate',), (150, 120, 224)),
    (('thyroid',), (222, 92, 150)),
    (('trachea',), (170, 216, 238)),
    (('heart', 'atrial', 'ventricle', 'myocard'), (164, 36, 62)),
    (('aorta', 'artery', 'trunk', 'carotid', 'subclavian'), ARTERY),
    (('vena', 'vein'), VEIN),
    (('spinal', 'cord'), (255, 214, 48)),
    (('brain',), (240, 200, 196)),
    (('lung',), LUNG),
    (('gluteus', 'autochthon', 'iliopsoas', 'muscle'), MUSCLE),
    (('costal', 'cartilage'), (220, 214, 198)),
    (('vertebra', 'rib', 'sacrum', 'hip', 'femur', 'humerus', 'scapula', 'clavic', 'sternum',
      'skull', 'spine', 'coccyx'), BONE),
]




def lookup(name):
    """The structure's colour, or None when no entry names it."""
    key = name.lower().replace(' ', '_')
    return next((value for words, value in PALETTE if any(w.replace(' ', '_') in key for w in words)), None)
