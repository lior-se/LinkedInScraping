from pathlib import Path
import numpy as np
import cv2
from PIL import Image


def read_bgr(path: str | Path):
    """Read image."""
    p = path
    data = np.fromfile(p, dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is not None:
        return img
    # Fallback via PIL
    with Image.open(p) as im:
        im = im.convert("RGB")
        return cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)
