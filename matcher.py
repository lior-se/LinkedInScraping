from pathlib import Path
from typing import Dict, Any, Optional

from utils.json_store import (
    load_person,
    set_candidate_face,
    select_best_candidate,
    candidate_has_face,
    NO_IMAGE_TOKEN,
)
from face_recognize.face_compare import compare_faces
from utils.name_match import is_exact_name, name_similarity

FUZZY_MIN = 92


def run_matcher(person_json: str | Path) -> Dict[str, Any]:
    """
    Compares the first source image to all candidates.
    Apply fuzzy name matching to the best candidate if the name is not exact.
    """
    p = Path(person_json)
    data = load_person(p)

    src_images = data.get("source_images") or []
    cands = data.get("candidates") or []
    if not src_images or not cands:
        return {
            "name": data.get("query_name"),
            "linkedin_url": "no_match",
            "image_similarity": 0.0,
            "match_status": "no_match",
        }

    src = src_images[0]

    # Compute face metrics
    for c in cands:
        # Skip explicit "no image"
        if (c.get("photo_path") or "").strip() == NO_IMAGE_TOKEN:
            continue

        cand_img = c.get("photo_path") or c.get("image_file")
        url = c.get("profile_url")
        if not (cand_img and url):
            continue

        # Do not recompute if metrics already exist
        if candidate_has_face(p, url):
            continue

        try:
            fm = compare_faces(src, cand_img) # {distance, threshold, sigmoid, verified, ...}
            set_candidate_face(p, url, fm)
            print(f"Compared to {cand_img}, score is {fm['sigmoid']}")
        except Exception:
            set_candidate_face(p, url, {"error": "no_face_metrics"})

    # Pick overall best by sigmoid
    data = load_person(p)               # reload to read the saved 'face' fields
    best = select_best_candidate(data)  # returns the cand with max face['sigmoid']
    if not best:
        return {
            "name": data.get("query_name"),
            "linkedin_url": "no_match",
            "image_similarity": 0.0,
            "match_status": "no_match",
        }

    qname = data.get("query_name") or ""
    bname = best.get("name") or ""
    sig = float((best.get("face") or {}).get("sigmoid") or 0.0)

    # Name classification
    if is_exact_name(qname, bname):
        status = "matched"
    else:
        status = "Probable Match (Fuzzy Name)" if (name_similarity(qname, bname) or 0) >= FUZZY_MIN else "no_match"

    return {
        "name": qname,
        "linkedin_url": best.get("profile_url"),
        "image_similarity": round(sig, 4),
        "match_status": status,
    }


def _cli():
    import argparse
    ap = argparse.ArgumentParser(description="Run matcher on one person JSON")
    ap.add_argument("json_path")
    args = ap.parse_args()
    run_matcher(args.json_path)


if __name__ == "__main__":
    _cli()

