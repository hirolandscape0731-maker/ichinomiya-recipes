#!/usr/bin/env python3
"""Convert recipes.json + menu_days.json into data files consumed by the static app."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "recipes.json"
MENU_SRC = ROOT / "data" / "menu_days.json"
DST = ROOT / "app" / "data.js"
MENU_DST = ROOT / "app" / "menus.js"

records = json.loads(SRC.read_text(encoding="utf-8"))
# Drop heavy raw_text from list view but keep it for search; trim _parse_status
slimmed = []
for r in records:
    photo_path = f"photos/{r['id']}.jpg"
    has_photo = (ROOT / "app" / photo_path).exists()
    slimmed.append({
        "id": r["id"],
        "name": r["name"],
        "section": r["section"],
        "category": r["category"],
        "date_jp": r["date_jp"],
        "date_iso": r["date_iso"],
        "servings": r.get("servings", ""),
        "ingredients": r.get("ingredients", []),
        "instructions": r.get("instructions", []),
        "notes": r.get("notes", ""),
        "pdf_url": r["pdf_url"],
        "pdf_filename": r["pdf_filename"],
        "photo": photo_path if has_photo else "",
        # keep small slice of raw text so search can find content even when parsing failed
        "raw_text": (r.get("raw_text") or "")[:500],
    })

js = "window.RECIPES = " + json.dumps(slimmed, ensure_ascii=False) + ";\n"
DST.write_text(js, encoding="utf-8")
print(f"Wrote {len(slimmed)} recipes -> {DST} ({DST.stat().st_size//1024} KB)")

# Menu data
if MENU_SRC.exists():
    menus = json.loads(MENU_SRC.read_text(encoding="utf-8"))
    menu_js = "window.MENUS = " + json.dumps(menus, ensure_ascii=False) + ";\n"
    MENU_DST.write_text(menu_js, encoding="utf-8")
    print(f"Wrote {len(menus)} menu day-records -> {MENU_DST} ({MENU_DST.stat().st_size//1024} KB)")
