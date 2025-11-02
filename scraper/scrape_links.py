import time, urllib.parse
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote
from playwright.sync_api import sync_playwright
from utils.json_store import upsert_candidate, load_person, has_candidate

DDG_HTML = "https://html.duckduckgo.com/html/?q={}&kl=il-en" # Website to make research and scrape


def _extract_linkedin_results(page):
    # Extract LinkedIn urls from the page
    results, seen = [], set()
    for a in page.query_selector_all('#links a[href]'):
        href = a.get_attribute('href') or ''
        if not href:
            continue

        if '/l/' in href and 'uddg=' in href:
            q = parse_qs(urlparse(href).query).get('uddg', [])
            href = unquote(q[0]) if q else href

        if 'linkedin.com/in/' not in href:
            continue

        # normalize to scheme://host/path (drop query/fragment)
        p = urlparse(href)
        href = f'{p.scheme}://{p.netloc}{p.path}'

        if href in seen:
            continue
        seen.add(href)
        results.append({'name': '', 'profile_url': href})
    return results


def _go_next(page) -> bool:
    """
    Click the 'Next' button on DDG HTML.
    """
    btn = page.query_selector('form[action="/html/"] input[type="submit"][value="Next"]')
    if not btn:
        return False
    btn.click()
    page.wait_for_load_state("domcontentloaded", timeout=30_000)
    return True


def scrape_into_json(json_path: str | Path, *, headless: bool = False, delay: float = 0.4, max_pages: int = 1):
    """
    Search DDG (HTML) for "<Full Name> site:linkedin.com/in", scrape up to `max_pages`,
    and upsert LinkedIn profile URLs (empty names) into the person JSON.
    """
    json_path = Path(json_path)
    data = load_person(json_path)
    full_name = (data.get("query_name") or "").strip()
    if not full_name:
        print("JSON must contain 'query_name'")
        return 0

    query = f'{full_name} site:linkedin.com/in'
    search_url = DDG_HTML.format(urllib.parse.quote_plus(query))

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"])  # Helps on contouring Bot controls
        context = browser.new_context(locale="en-IL")
        page = context.new_page()

        page.goto(search_url, wait_until="domcontentloaded", timeout=30_000)

        for _ in range(max_pages):
            rows = _extract_linkedin_results(page)
            for r in rows:
                try:
                    if has_candidate(json_path, r["profile_url"]):
                        continue
                    upsert_candidate(json_path, r["profile_url"], "")  # store empty name; fill later
                except Exception:
                    pass

            time.sleep(max(0.0, delay))
            if not _go_next(page):
                break

        context.close()
        browser.close()


def _cli():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("json_path")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--delay", type=float, default=0.4)
    ap.add_argument("--max-pages", type=int, default=1)
    a = ap.parse_args()
    scrape_into_json(a.json_path, headless=a.headless, delay=a.delay, max_pages=a.max_pages)

if __name__ == "__main__":
    _cli()
