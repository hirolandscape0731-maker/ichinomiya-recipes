#!/usr/bin/env python3
"""Extract food photos from recipe PDFs.

For each recipe PDF, finds the largest embedded image (the food photo) and saves it
as a JPEG in app/photos/<recipe_id>.jpg.
"""
import json
from pathlib import Path
from pypdf import PdfReader
import io

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "downloads" / "recipes"
RECIPES_JSON = ROOT / "data" / "recipes.json"
OUT_DIR = ROOT / "app" / "photos"
OUT_DIR.mkdir(exist_ok=True)

MIN_PHOTO_SIZE = 50_000  # bytes — real photos are usually >50KB raw data

def extract_best_photo(pdf_path: Path):
    """Return JPEG bytes of the most photo-like image in the first page, or None.

    Scoring favors:
    - Larger JPEG file size (photos compress less than clip art)
    - Aspect ratio close to 1:1–4:3 (food photos are roughly square/landscape)
    - Minimum 100×100 raw pixels
    """
    try:
        reader = PdfReader(pdf_path)
        page = reader.pages[0]
        resources = page.get("/Resources")
        if not resources:
            return None
        xobj = resources.get("/XObject")
        if not xobj:
            return None

        best = None
        best_score = 0
        for name in xobj:
            obj = xobj[name]
            if obj.get("/Subtype") != "/Image":
                continue
            filt = obj.get("/Filter")
            if filt not in ("/DCTDecode", ["/DCTDecode"]):
                continue
            w = int(obj.get("/Width", 0))
            h = int(obj.get("/Height", 0))
            if w < 100 or h < 100:
                continue
            data = obj.get_data()
            file_size = len(data)
            if file_size < 3_000:
                continue
            ratio = w / max(h, 1)
            # Penalize extreme aspect ratios (banners, thin strips)
            # Food photos: ratio 0.5–2.5 → multiplier 1.0; outside → 0.05
            ratio_ok = 0.5 <= ratio <= 2.5
            score = file_size * (1.0 if ratio_ok else 0.05)
            if score > best_score:
                best_score = score
                best = data

        return best
    except Exception as e:
        print(f"  error reading {pdf_path.name}: {e}")
        return None


def main():
    recipes = json.loads(RECIPES_JSON.read_text(encoding="utf-8"))
    ok = skip = missing = no_photo = 0
    for r in recipes:
        pdf_name = r.get("pdf_filename", "")
        if not pdf_name:
            missing += 1
            continue
        pdf_path = PDF_DIR / pdf_name
        if not pdf_path.exists():
            missing += 1
            continue

        out_path = OUT_DIR / f"{r['id']}.jpg"
        if out_path.exists():
            skip += 1
            continue

        data = extract_best_photo(pdf_path)
        if data:
            out_path.write_bytes(data)
            print(f"  OK  {r['id']:40s} ({len(data)//1024}KB)  <- {pdf_name}")
            ok += 1
        else:
            no_photo += 1
            print(f"  --- {r['id']:40s}  no photo in {pdf_name}")

    print(f"\nDone: extracted={ok}  skipped={skip}  no_photo={no_photo}  missing_pdf={missing}")
    print(f"Photos in: {OUT_DIR}")


if __name__ == "__main__":
    main()
