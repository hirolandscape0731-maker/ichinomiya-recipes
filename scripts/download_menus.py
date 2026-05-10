#!/usr/bin/env python3
"""Download monthly menu (献立表) PDFs from the Ichinomiya school lunch site.

The menu index page lists PDFs grouped by month (school-type × area).
URL pattern observed: ..._page_/001/066/072/<area_code><YYMM>.pdf
where <YYMM> is the wareki year (e.g., 0803 = 令和8年3月 = 2026年3月).

We fetch the index page first to discover the current list of PDFs,
then download them all with rate limiting.
"""
import json, re, time, urllib.request, urllib.error, html
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Index pages by year — add new school years here as they appear
INDEX_URLS = [
    "https://www.city.ichinomiya.aichi.jp/kyouiku/gakkoukyuushoku/1000162/1009999/1066072.html",  # 2025年度
    "https://www.city.ichinomiya.aichi.jp/kyouiku/gakkoukyuushoku/1000162/1009999/1074863.html",  # 2026年度
]
OUT_DIR = ROOT / "downloads" / "menus"
OUT_DIR.mkdir(parents=True, exist_ok=True)
LIST_JSON = ROOT / "data" / "menu_pdf_list.json"

UA = "Mozilla/5.0 (Recipe Archive Bot for Personal Use; educational)"


def fetch_page(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def absolutize(href: str) -> str:
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return "https://www.city.ichinomiya.aichi.jp" + href
    if href.startswith("../"):
        # Page is at /kyouiku/gakkoukyuushoku/1000162/1009999/1066072.html
        base_parts = "/kyouiku/gakkoukyuushoku/1000162/1009999/1066072.html".split("/")[:-1]
        href_parts = href.split("/")
        up = 0
        for p in href_parts:
            if p == "..":
                up += 1
            else:
                break
        rest = href_parts[up:]
        return "https://www.city.ichinomiya.aichi.jp" + "/".join(base_parts[:len(base_parts) - up] + rest)
    return href


# Wareki YY → Gregorian year (令和)
def wareki_yy_to_year(yy: int) -> int:
    # 令和元年 = 2019. So 0X (X≥1) maps to 2018 + X
    return 2018 + yy


def parse_menu_filename(fname: str):
    """Extract (school_type, area, year, month) from a menu PDF filename.

    Examples:
        nanbusyoutyuu0803.pdf  → 共通(南部), 2026年3月
        hokubusyoutyuu0803.pdf → 共通(北部)
        higashiazaisyoutyuu0803.pdf → 共通(東浅井)
        tandokusyou0803.pdf    → 小学校
        tandokutyuu0803.pdf    → 中学校
    """
    m = re.match(r"(.+?)(\d{4})\.pdf$", fname)
    if not m:
        return None
    prefix, ymd = m.groups()
    yy = int(ymd[:2])
    mm = int(ymd[2:])
    year = wareki_yy_to_year(yy)
    type_map = {
        "nanbusyoutyuu": ("共通", "南部"),
        "hokubusyoutyuu": ("共通", "北部"),
        "higashiazaisyoutyuu": ("共通", "東浅井"),
        "tandokusyou": ("小学校", ""),
        "tandokutyuu": ("中学校", ""),
    }
    school_type, area = type_map.get(prefix, ("不明", prefix))
    return {
        "school_type": school_type,
        "area": area,
        "year": year,
        "month": mm,
        "year_month": f"{year:04d}-{mm:02d}",
    }


def main():
    # Find all PDFs matching the /001/NNN/NNN/ pattern (works across all yearly pages)
    pdf_re = re.compile(r'href="([^"]+/001/\d+/\d+/[^"]+\.pdf)"', re.IGNORECASE)
    hrefs = set()
    for url in INDEX_URLS:
        print(f"Fetching index: {url}")
        try:
            page = fetch_page(url)
            found = pdf_re.findall(page)
            print(f"  Found {len(found)} PDF links")
            hrefs.update(found)
        except Exception as e:
            print(f"  ERROR: {e}")
    hrefs = sorted(hrefs)
    print(f"Total: {len(hrefs)} unique PDF links")

    records = []
    for href in hrefs:
        url = absolutize(href)
        fname = url.rsplit("/", 1)[-1]
        meta = parse_menu_filename(fname)
        if not meta:
            print(f"  skip (unknown name pattern): {fname}")
            continue
        records.append({
            "url": url,
            "filename": fname,
            **meta,
        })

    LIST_JSON.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(records)} menu records -> {LIST_JSON}")

    # Download each PDF
    ok = skipped = failed = 0
    for i, r in enumerate(records, 1):
        out = OUT_DIR / r["filename"]
        if out.exists() and out.stat().st_size > 0:
            skipped += 1
            continue
        req = urllib.request.Request(r["url"], headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            out.write_bytes(data)
            print(f"[{i:3d}/{len(records)}] OK {len(data)//1024:6d}KB  {r['filename']}")
            ok += 1
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            print(f"[{i:3d}/{len(records)}] FAIL {r['filename']}: {e}")
            failed += 1
        time.sleep(0.5)

    print(f"\nDone: ok={ok} skipped={skipped} failed={failed}")


if __name__ == "__main__":
    main()
