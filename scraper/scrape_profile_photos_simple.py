import re, time, random
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from utils.json_store import (
    load_person,
    set_candidate_photo,
    candidate_has_photo,
    NO_IMAGE_TOKEN,
    upsert_candidate,
)

STATE_FILE_DEFAULT = "login_state.json"

PHOTO_BTN_SEL = 'button.pv-top-card-profile-picture__container'
MODAL_IMG_SEL = 'div.pv-member-photo-modal__content-image-container img.pv-member-photo-modal__content-image'


def _slugify(s: str) -> str:
    """
    Usable img name
    """
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-") or "image"


def _profile_handle(url: str) -> str:
    """
        Extract a LinkedIn profile handle from a URL.
        """
    try:
        parts = [x for x in urlparse(url).path.split("/") if x]
        if len(parts) >= 2 and parts[0] == "in":
            return parts[1]
    except Exception:
        pass
    return _slugify(url)


def _extract_profile_name(page, timeout: int = 4000) -> str | None:
    """
    Extract display name exactly from:
    <a href*="/overlay/about-this-profile/"><h1>NAME</h1></a>
    Returns the stripped text or None.
    """
    try:
        el = page.wait_for_selector('a[href*="/overlay/about-this-profile/"] h1', timeout=timeout)
        txt = (el.inner_text() or "").strip()
        return txt or None
    except Exception:
        return None


def _is_ghost_or_placeholder(img_el) -> bool:
    """
    Returns True if the LinkedIn link has no usable image.
    """
    if not img_el:
        return True
    src = (img_el.get_attribute("src") or "").strip()
    if not src:
        return True
    if src.startswith("data:image/"):
        return True
    return False


def _open_modal_and_get_img_src(page) -> str | None:
    """
    Try to open the profile photo modal and return the full-size image src.
    If we can confidently tell there is NO real image, return NO_IMAGE_TOKEN.
    """
    try:
        page.wait_for_load_state("networkidle", timeout=3000)
    except Exception:
        pass
    # Quick pre-check on the thumbnail inside the button
    btn = page.query_selector(PHOTO_BTN_SEL)
    if not btn:
        return NO_IMAGE_TOKEN

    thumb = btn.query_selector("img")
    if _is_ghost_or_placeholder(thumb):
        return NO_IMAGE_TOKEN

    try:
        btn.click()
        # Keep timeout short so we don't "get stuck" on profiles without modal
        img = page.wait_for_selector(MODAL_IMG_SEL, timeout=3000)
        src = img.get_attribute("src") if img else None
        page.keyboard.press("Escape")
        return src or NO_IMAGE_TOKEN
    except Exception:
        return NO_IMAGE_TOKEN


def _download_via_context(context, url: str, out_path: Path):
    """
    Download the image from the given URL to the given output path.
    """
    try:
        resp = context.request.get(url, timeout=15000)
        if not resp.ok:
            return None
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(resp.body())
        return out_path
    except Exception:
        return None


def download_photos(json_path: str | Path, *, state: str = STATE_FILE_DEFAULT,
                    headless: bool = False, delay: float = 1, ) -> None:
    """
    Download photos for all candidates in the given JSON file.
    :param json_path: Path to the JSON file.
    :param state: Log in state file to use.
    :param headless: Headless mode.
    :param delay: Delay between each profile.
    """
    data_path = Path(json_path)
    data = load_person(data_path)
    candidates = data.get("candidates", [])
    if not candidates:
        return None
    dest_dir = Path("Persons_photos") / _slugify(str(data.get("query_name") or data_path.stem))

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"]  # Helps on contouring Bot controls
        )
        context = browser.new_context(
            storage_state=state,
            locale="en-IL",
        )
        page = context.new_page()

        for c in candidates:
            url = c.get("profile_url")
            if not url:
                continue

            if candidate_has_photo(data_path, url):
                continue

            # Visit profile (short timeouts to avoid getting stuck)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=15000)
            except PWTimeout:
                set_candidate_photo(data_path, url, photo_url=None, photo_path=NO_IMAGE_TOKEN)
                time.sleep(delay)
                continue

            # Scrape name
            scraped_name = _extract_profile_name(page)
            if scraped_name and (scraped_name != (c.get("name") or "").strip()):
                upsert_candidate(data_path, url, scraped_name)

            time.sleep(0.2 + random.uniform(0.03, 0.12))

            img_src = _open_modal_and_get_img_src(page)

            if img_src == NO_IMAGE_TOKEN or not img_src:
                # Mark as processed with an explicit "no_image", so reruns skip it instantly
                set_candidate_photo(data_path, url, photo_url=None, photo_path=NO_IMAGE_TOKEN)
                time.sleep(delay)
                continue

            handle = _profile_handle(url)
            out_path = dest_dir / f"{handle}.jpg"
            saved = _download_via_context(context, img_src, out_path)

            if saved is None:
                # treat a failed download as no image to avoid rework on reruns
                set_candidate_photo(data_path, url, photo_url=img_src, photo_path=NO_IMAGE_TOKEN)
            else:
                set_candidate_photo(data_path, url, photo_url=img_src, photo_path=str(saved))

            print(f"Saved photo for url:{url} to path: '{out_path}'")
            time.sleep(delay)

        context.close()
        browser.close()
        return None


def _cli():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("json_path")
    ap.add_argument("--state", default=STATE_FILE_DEFAULT)
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--delay", type=float, default=0.9)
    a = ap.parse_args()
    download_photos(a.json_path, state=a.state, headless=a.headless, delay=a.delay)


if __name__ == "__main__":
    _cli()
