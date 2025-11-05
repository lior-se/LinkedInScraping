import json
from pathlib import Path
from typing import Dict, Any, Optional

NO_IMAGE_TOKEN = "no_image"  # sed to mark profiles without a usable picture


# ========== core io ==========


def load_person(path: str | Path) -> Dict[str, Any]:
    """Read a person JSON file and return it as a dict."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_person(path: str | Path, data: Dict[str, Any]):
    """Write a person dict back to disk."""
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ========== candidates indexing ==========


def _find_idx(data, url):
    """Find candidate index by exact profile_url."""
    for i, c in enumerate(data.get("candidates", [])):
        if (c.get("profile_url") or "").strip() == (url or "").strip():
            return i
    return -1


def get_candidate(data: Dict[str, Any], profile_url: str) -> Optional[Dict[str, Any]]:
    """Return the candidate dict for this profile_url, or None if missing."""
    idx = _find_idx(data, profile_url)
    if idx == -1:
        return None
    return data["candidates"][idx]


# ========== idempotency helpers ==========


def has_candidate(person_json: str | Path, profile_url: str) -> bool:
    """True if this profile_url already exists in the person's candidates list."""
    data = load_person(person_json)
    return get_candidate(data, profile_url) is not None


def candidate_has_photo(person_json: str | Path, profile_url: str) -> bool:
    """
    True if this candidate was already processed for photo.
    Any non-empty photo_path (including 'no_image') counts as processed.
    """
    data = load_person(person_json)
    c = get_candidate(data, profile_url)
    if not c:
        return False
    p = (c.get("photo_path") or "").strip()
    return bool(p)


def candidate_has_face(person_json: str | Path, profile_url: str) -> bool:
    """True if face metrics were already computed for this candidate."""
    data = load_person(person_json)
    c = get_candidate(data, profile_url)
    return bool(c and c.get("face"))


# ========== mutators ==========



def upsert_candidate(
        person_json: str | Path,
        profile_url: str,
        name: str,
        photo_path: str | Path | None = None,
) -> None:
    """
    Insert candidate if missing; otherwise update:
      - name: overwrite only if the new name is non-empty
      - photo_path: set only if photo_path is provided AND
                    (no existing photo OR existing == NO_IMAGE_TOKEN)
    Backward-compatible with old calls (photo_path is optional).
    """
    data = load_person(person_json)
    idx = _find_idx(data, profile_url)

    if idx == -1:
        entry = {
            "profile_url": profile_url,
            "name": name or "",
            "photo_url": None,
            "photo_path": None,
            "face": None,
            "name_similarity": None,
            "match_type": None,
        }
        if photo_path is not None:
            entry["photo_path"] = str(photo_path)
        data.setdefault("candidates", []).append(entry)
    else:
        entry = data["candidates"][idx]
        if name:  # only overwrite if a non-empty name was provided
            entry["name"] = name

        if photo_path is not None:
            # Only set photo if we don't already have a real one
            existing = entry.get("photo_path")
            if not existing or existing == NO_IMAGE_TOKEN:
                entry["photo_path"] = str(photo_path)

    save_person(person_json, data)


def set_candidate_photo(person_json: str | Path, profile_url: str, photo_url: str | None, photo_path: str | None):
    """Update the candidate's photo_url and photo_path (can be no_image)."""
    data = load_person(person_json)
    idx = _find_idx(data, profile_url)
    if idx == -1:
        raise KeyError("candidate not found")
    c = data["candidates"][idx]
    c["photo_url"] = photo_url
    c["photo_path"] = photo_path
    save_person(person_json, data)


def set_candidate_face(person_json: str | Path, profile_url: str, face_metrics: Dict[str, Any]):
    """Store face recognition metrics dict for this candidate."""
    data = load_person(person_json)
    idx = _find_idx(data, profile_url)
    if idx == -1:
        raise KeyError("candidate not found")
    fm = dict(face_metrics)
    data["candidates"][idx]["face"] = fm
    save_person(person_json, data)


def set_candidate_name_eval(person_json: str | Path, profile_url: str,
                            name_similarity: Optional[int], match_type: Optional[str]):
    """Store name matching results (similarity score) for this candidate."""
    data = load_person(person_json)
    idx = _find_idx(data, profile_url)
    if idx == -1:
        raise KeyError("candidate not found")
    data["candidates"][idx]["name_similarity"] = name_similarity
    data["candidates"][idx]["match_type"] = match_type
    save_person(person_json, data)


# ========== selection ==========


def select_best_candidate(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Return the candidate with the highest face['sigmoid'].
    Returns None if no candidate has a numeric sigmoid.
    """
    best = None
    best_s = float("-inf")

    for c in data.get("candidates", []):
        s = (c.get("face") or {}).get("sigmoid")
        if s is None:
            continue

        if s > best_s:
            best_s = s
            best = c

    return best
