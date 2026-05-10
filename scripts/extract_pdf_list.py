#!/usr/bin/env python3
"""Extract complete PDF list with sections from the index HTML."""
import re, json, html
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML_PATH = ROOT / "data" / "index.html"
OUT_JSON = ROOT / "data" / "pdf_list.json"
OUT_TSV = ROOT / "data" / "pdf_list.tsv"

content = HTML_PATH.read_text(encoding="utf-8")

# Find body section between "最新のレシピ" and end of recipe list
# Sections are <h2> for top-level (最新/過去), <h3> for category (汁物等)

# Strategy: walk through the relevant region tracking current section/subsection,
# then collect each <a> link to a .pdf and its text label.

# Locate the start of recipe content
start_idx = content.find("最新のレシピ")
end_idx = content.find("関連リンク")  # safe terminator
if end_idx == -1:
    end_idx = len(content)
region = content[start_idx:end_idx]

# Token-walk: iterate over h2/h3/<a ...pdf...>
token_re = re.compile(
    r'<h2[^>]*>(?P<h2>[^<]+)</h2>'
    r'|<h3[^>]*>(?P<h3>[^<]+)</h3>'
    r'|<a[^>]+href="(?P<href>[^"]+\.pdf)"[^>]*>(?P<text>.*?)</a>',
    re.DOTALL,
)

current_section = "最新のレシピ"
current_category = ""
records = []

for m in token_re.finditer(region):
    if m.group("h2"):
        current_section = m.group("h2").strip()
        current_category = ""
    elif m.group("h3"):
        current_category = m.group("h3").strip()
    elif m.group("href"):
        href = m.group("href")
        # absolutize
        if href.startswith("../"):
            url = "https://www.city.ichinomiya.aichi.jp/kyouiku/gakkoukyuushoku/1000162/" + href
            # normalize ../ — easier: replace ../../../ with /
            # The page is at /kyouiku/gakkoukyuushoku/1000162/1001639.html
            # ../../../_res/... means go up to root then into _res
            # so absolute path = /_res/...
            # Just do: take "../" count and walk
            parts = "/kyouiku/gakkoukyuushoku/1000162/1001639.html".split("/")[:-1]  # remove filename
            href_parts = href.split("/")
            up_count = 0
            for p in href_parts:
                if p == "..":
                    up_count += 1
                else:
                    break
            base_parts = parts[:len(parts)-up_count] if up_count <= len(parts) else []
            rest = href_parts[up_count:]
            abs_path = "/".join(base_parts + rest)
            url = "https://www.city.ichinomiya.aichi.jp" + abs_path
        elif href.startswith("/"):
            url = "https://www.city.ichinomiya.aichi.jp" + href
        elif href.startswith("http"):
            url = href
        else:
            url = "https://www.city.ichinomiya.aichi.jp/" + href.lstrip("./")

        # Extract clean text from <a> body (strip nested img tags)
        raw_text = m.group("text")
        clean_text = re.sub(r'<[^>]+>', '', raw_text).strip()
        clean_text = html.unescape(clean_text)

        # Parse name + date + size from clean_text
        # Patterns: "料理名（令和6年4月アップ） （PDF 158.1KB）"
        date_match = re.search(r'[(（]([令平]和?[元0-9０-９]+年[0-9０-９]+月)アップ?[)）]', clean_text)
        date_str = date_match.group(1) if date_match else ""
        # Clean dish name: remove the date+size suffix
        name = re.sub(r'[(（][^()（）]*アップ?[)）]\s*[(（]\s*PDF[^()（）]*[)）]', '', clean_text)
        name = re.sub(r'\s*[(（]\s*PDF[^()（）]*[)）]', '', name)
        name = name.strip()

        # Size info
        size_match = re.search(r'PDF\s+([\d.]+\s*[KMG]?B)', clean_text)
        size_str = size_match.group(1) if size_match else ""

        records.append({
            "url": url,
            "name": name,
            "date_jp": date_str,
            "size": size_str,
            "section": current_section,
            "category": current_category or current_section,
            "filename": url.rsplit("/", 1)[-1],
        })

# Deduplicate by URL
seen = set()
unique = []
for r in records:
    if r["url"] not in seen:
        seen.add(r["url"])
        unique.append(r)

OUT_JSON.write_text(json.dumps(unique, ensure_ascii=False, indent=2), encoding="utf-8")
with OUT_TSV.open("w", encoding="utf-8") as f:
    f.write("URL\t料理名\t日付\tサイズ\tセクション\tカテゴリ\n")
    for r in unique:
        f.write(f"{r['url']}\t{r['name']}\t{r['date_jp']}\t{r['size']}\t{r['section']}\t{r['category']}\n")

print(f"Total PDFs: {len(unique)}")
# Section counts
from collections import Counter
cats = Counter(r["category"] for r in unique)
for c, n in cats.most_common():
    print(f"  {c}: {n}")
