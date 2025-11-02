# main.py
import argparse, json, os
from pathlib import Path
from typing import List, Dict, Any

from utils.make_persons_jsons import run_make_person_jsons
from scraper.login_headless import login
from scraper.scrape_links import scrape_into_json
from scraper.scrape_profile_photos_simple import download_photos
from scraper.scrape_from_GImages import scrape_linkedin_images_into_json as scrape_from_gimages
from matcher import run_matcher



def main():
    ap = argparse.ArgumentParser(
        description="Full pipeline. Default = Google Images thumbnails; use --full-pictures for LinkedIn login + max-size photos."
    )
    ap.add_argument("--src-dir", default="Source")
    ap.add_argument("--persons-dir", default="Persons_JSONS")
    ap.add_argument("--state", default="login_state.json")
    ap.add_argument("--headless", action="store_true")

    # Only needed for --full-pictures mode
    ap.add_argument("--email", default=os.getenv("LINKEDIN_EMAIL", ""))
    ap.add_argument("--password", default=os.getenv("LINKEDIN_PASSWORD", ""))

    # (LinkedIn) flow controls
    ap.add_argument("--full-pictures", action="store_true",
                    help="Use LinkedIn login + scrape_links + full-size profile photos.")
    ap.add_argument("--max-pages", type=int, default=1)
    ap.add_argument("--scrape-delay", type=float, default=1.0)
    ap.add_argument("--photos-delay", type=float, default=0.9)

    # (Google Images) flow controls
    ap.add_argument("--gimages-limit", type=int, default=12,
                    help="Max profiles to collect per person when using Google Images (default).")

    ap.add_argument("--output", default="output.json")
    args = ap.parse_args()

    src_dir = Path(args.src_dir).resolve()
    persons_dir = Path(args.persons_dir).resolve()
    state_file = Path(args.state).resolve()
    output_path = Path(args.output).resolve()
    persons_dir.mkdir(parents=True, exist_ok=True)

    # 1) make per-person JSONs
    run_make_person_jsons(src_dir, persons_dir)

    # 2) process each person JSON (choose pipeline)
    summaries: List[Dict[str, Any]] = []

    if args.full_pictures:
        # Ensure login state only for the full-pictures flow
        if not state_file.exists():
            ok = login(args.email, args.password, headless=args.headless, state_file=str(state_file))
            if not ok:
                raise SystemExit("Login failed.")

        # Old flow: scrape LinkedIn result pages + download full-size profile photos
        for person_json in sorted(persons_dir.glob("*.json")):
            print(f"\n--- Processing (FULL) {person_json.name}")
            scrape_into_json(
                person_json,
                headless=args.headless,
                max_pages=args.max_pages,
                delay=args.scrape_delay,
            )
            print("Scraped LinkedIn links.")
            download_photos(
                person_json,
                state=str(state_file),
                headless=args.headless,
                delay=args.photos_delay,
            )
            summary = run_matcher(person_json)
            summaries.append({
                "name": summary["name"],
                "linkedin_url": summary["linkedin_url"],
                "image_similarity": summary["image_similarity"],
                "match_status": summary.get("match_status"),
            })
    else:
        # Default flow: Google Images → base64 thumbnails + profile links
        for person_json in sorted(persons_dir.glob("*.json")):
            print(f"\n--- Processing {person_json.name}")
            n = scrape_from_gimages(
                person_json,
                headless=args.headless,
                limit=args.gimages_limit,
            )
            print(f"Collected {n} candidates from Google Images.")
            summary = run_matcher(person_json)
            summaries.append({
                "name": summary["name"],
                "linkedin_url": summary["linkedin_url"],
                "image_similarity": summary["image_similarity"],
                "match_status": summary.get("match_status"),
            })

    # 3) aggregated output
    output_path.write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {output_path}.")


if __name__ == "__main__":
    main()
