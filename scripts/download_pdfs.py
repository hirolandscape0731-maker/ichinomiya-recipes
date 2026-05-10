#!/usr/bin/env python3
"""Download all PDFs listed in pdf_list.json with rate limiting."""
import json, time, sys, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF_LIST = ROOT / "data" / "pdf_list.json"
DL_DIR = ROOT / "downloads" / "recipes"
DL_DIR.mkdir(parents=True, exist_ok=True)

records = json.loads(PDF_LIST.read_text(encoding="utf-8"))
print(f"Downloading {len(records)} PDFs...")

UA = "Mozilla/5.0 (Recipe Archive Bot for Personal Use; educational)"
ok, skipped, failed = 0, 0, 0
fail_list = []

for i, r in enumerate(records, 1):
    fname = r["filename"]
    out = DL_DIR / fname
    if out.exists() and out.stat().st_size > 0:
        skipped += 1
        continue
    req = urllib.request.Request(r["url"], headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        out.write_bytes(data)
        size_kb = len(data) / 1024
        print(f"[{i:3d}/{len(records)}] OK {size_kb:6.1f}KB  {fname}")
        ok += 1
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"[{i:3d}/{len(records)}] FAIL {fname}: {e}")
        failed += 1
        fail_list.append({"url": r["url"], "error": str(e)})
    time.sleep(0.5)  # politeness: 500ms between requests

print(f"\nDone: ok={ok} skipped={skipped} failed={failed}")
if fail_list:
    (ROOT / "data" / "download_failures.json").write_text(
        json.dumps(fail_list, ensure_ascii=False, indent=2), encoding="utf-8")
