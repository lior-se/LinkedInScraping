import json
from pathlib import Path

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def _is_image(p: Path) -> bool:
    # verify if file is an image
    return p.is_file() and p.suffix.lower() in IMG_EXTS


def _safe_filename(stem: str) -> str:
    # keep letters, numbers, spaces, hyphens and dots; replace the rest with underscore
    return "".join(ch if (ch.isalnum() or ch in " .-_") else "_" for ch in stem).strip() or "person"


def run_make_person_jsons(src_dir: str | Path, out_dir: str | Path) -> None:
    """
    Create a JSON for each image in src_dir.
    :param src_dir: source directory containing images.
    :param out_dir: output directory.
    """
    src_dir = Path(src_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for img in sorted(src_dir.iterdir()):
        if not _is_image(img):
            continue

        person = img.stem.strip()
        json_name = _safe_filename(person) + ".json"
        json_path = out_dir / json_name

        if json_path.exists():
            continue

        payload = {
            "query_name": person,
            "source_images": [img.resolve().as_posix()],
            "candidates": []
        }
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Create one JSON per image (non-recursive).")
    ap.add_argument("src_dir")
    ap.add_argument("--out-dir", default=".")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    run_make_person_jsons(args.src_dir, args.out_dir)
