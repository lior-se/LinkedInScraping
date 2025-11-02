import argparse, json, os
from pathlib import Path
from typing import List, Dict, Any

from utils.make_persons_jsons import run_make_person_jsons
from scraper.login_headless import login
from scraper.scrape_links import scrape_into_json
from scraper.scrape_profile_photos_simple import download_photos
from matcher import run_matcher


def main():
    ap = argparse.ArgumentParser(
        description="Full pipeline: make → login → scrape → photos → match → aggregate output.json")
    ap.add_argument("--src-dir", default="Source")
    ap.add_argument("--persons-dir", default="Persons_JSONS")
    ap.add_argument("--state", default="login_state.json")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--email", default=os.getenv("LINKEDIN_EMAIL", ""))
    ap.add_argument("--password", default=os.getenv("LINKEDIN_PASSWORD", ""))
    ap.add_argument("--max-pages", type=int, default=1)
    ap.add_argument("--scrape-delay", type=float, default=1.0)
    ap.add_argument("--photos-delay", type=float, default=0.9)
    ap.add_argument("--output", default="output.json")
    args = ap.parse_args()

    src_dir = Path(args.src_dir).resolve()
    persons_dir = Path(args.persons_dir).resolve()
    state_file = Path(args.state).resolve()
    output_path = Path(args.output).resolve()
    persons_dir.mkdir(parents=True, exist_ok=True)

    # 1) make per-person JSONs
    run_make_person_jsons(src_dir, persons_dir)

    # 2) ensure login state
    if not state_file.exists():
        ok = login(args.email, args.password, headless=args.headless, state_file=str(state_file))
        if not ok:
            raise SystemExit("Login failed.")

    # 3) process each person JSON
    summaries: List[Dict[str, Any]] = []
    for person_json in sorted(persons_dir.glob("*.json")):
        print(f"\n---Processing {person_json.name}")
        # a) scrape links
        scrape_into_json(person_json, headless=args.headless,
                         max_pages=args.max_pages, delay=args.scrape_delay)
        print("Scraped links.")
        # b) download photos
        download_photos(person_json, state=str(state_file), headless=args.headless,
                        delay=args.photos_delay)

        # c) match
        summary = run_matcher(person_json)
        summaries.append({
            "name": summary["name"],
            "linkedin_url": summary["linkedin_url"],
            "image_similarity": summary["image_similarity"],
            "match_status": summary.get("match_status")
        })

    # 4) aggregated output
    output_path.write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n Wrote {output_path} with {len(summaries)} rows.")


if __name__ == "__main__":
    main()
