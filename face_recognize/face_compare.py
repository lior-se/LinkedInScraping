import math
from utils.img_load import read_bgr
from deepface import DeepFace


def sigmoid_similarity(distance: float, threshold: float, k_factor: float = 8.0) -> float:
    if threshold <= 0:
        return 0.0
    k = k_factor / threshold
    s = 1.0 / (1.0 + math.exp(k * (distance - threshold)))
    return max(0.0, min(1.0, s))

def compare_faces(src_path: str, tst_path: str) -> dict:
    """
    Compare TWO images with DeepFace ArcFace (cosine). Returns a dict with:
    distance, threshold, sigmoid, verified, model, detector
    """

    src_img = read_bgr(src_path)
    tst_img = read_bgr(tst_path)

    for det in ("retinaface", "opencv"):
        try:
            res = DeepFace.verify(
                img1_path=src_img,
                img2_path=tst_img,
                model_name="ArcFace",
                distance_metric="cosine",
                detector_backend=det,
                align=True,
                enforce_detection=True
            )
            dist = float(res["distance"])
            thr  = float(res["threshold"])
            return {
                "distance": dist,
                "threshold": thr,
                "sigmoid": sigmoid_similarity(dist, thr),
                "verified": bool(res.get("verified", dist <= thr)),
                "model": "ArcFace",
                "detector": det
            }
        except Exception as e:
            print(f"[{det}] DeepFace.verify failed: Image is not a person")
            continue
    raise RuntimeError("verification failed with all detectors")
