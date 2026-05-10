#!/usr/bin/env python3
"""Parse all downloaded PDFs and produce recipes.json database."""
import json, re
from pathlib import Path
import pdfplumber
import pypdf

ROOT = Path(__file__).resolve().parent.parent
PDF_LIST = ROOT / "data" / "pdf_list.json"
DL_DIR = ROOT / "downloads" / "recipes"
OUT = ROOT / "data" / "recipes.json"


def jp_date_to_iso(s: str) -> str:
    if not s:
        return ""
    s = s.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    m = re.match(r"(令和|平成)([元\d]+)年(\d+)月", s)
    if not m:
        return s
    era, year, month = m.groups()
    year = 1 if year == "元" else int(year)
    gregorian = (1988 if era == "平成" else 2018) + year
    return f"{gregorian:04d}-{int(month):02d}"


# Allow 約 before the serving count
HEADER_INGRED_FULL = re.compile(
    r"[【\(（\[]?\s*材料\s*[\(（]?\s*(?:約)?\s*([\d０-９]+)\s*(?:人|皿|個)分\s*[\)）]?\s*[】\)）\]]?"
)
HEADER_INGRED_LOOSE = re.compile(r"^\s*[【\(（\[]?\s*材料\s*[】\)）\]]?\s*$")
HEADER_METHOD = re.compile(r"[【\(（\[]?\s*作\s*り\s*方\s*[】\)）\]]?")

CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
STEP_RE = re.compile(
    rf"^\s*(?:[{CIRCLED}]|[\d０-９]+\s*[\.．\)）]|[\(（][\d０-９]+[\)）])\s*(.*)"
)

AMOUNT_KEYWORDS = re.compile(r"[\d½¼⅓⅔適少約]|さじ|カップ|本|枚|個|株|片|かけ|束|缶|袋|g|G|ml|㎖|㎝|cc")
COOKING_VERBS = re.compile(
    r"(切る|切り|ひく|炒める|いためる|煮る|煮込む|加える|混ぜる|入れる|まぶす|揚げる|焼く"
    r"|茹でる|ゆでる|できあがり|仕上がり|下ごしらえ|火を通す|盛り|漬ける|和える|あえる"
    r"|絞る|しぼる|蒸す|冷ます|冷やす|溶く|とく|溶かす|とかす|ほぐす|刻む|きざむ|むく"
    r"|煎|炒|炊|沸|茹|揉|剥|浸|濾|絡|煮立|ひと煮|一煮|ひとまぜ|混ぜ合"
    r"|鍋|フライパン|ボウル|いためる|ゆでる|もどす|とる|さます|洗う|あわせる|からめる)"
)
MEMO_PATTERNS = re.compile(
    r"(です。|ます。|でした。|ましょう。|です！|ます！|ｇｏｏｄ|good|特徴です|旬を迎|冬野菜|夏野菜"
    r"|栄養|提供しました|食べていました|人気メニュー|おいしいです|おいしく できます"
    r"|産地です|作られます|[゠-ヿ一-鿿]{2,}とは|給食では)"
)


def extract_text_pdfplumber(path: Path) -> str:
    text = ""
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
    except Exception:
        pass
    return text


def extract_text_pypdf(path: Path) -> str:
    try:
        reader = pypdf.PdfReader(str(path))
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception:
        return ""


def get_text(path: Path) -> str:
    a = extract_text_pdfplumber(path).strip()
    b = extract_text_pypdf(path).strip()

    def score(s: str) -> int:
        if not s:
            return -1
        sc = 0
        if "材料" in s:
            sc += 100
        if "作り方" in s or "作 り 方" in s:
            sc += 100
        sc -= s.count("(cid:") * 2
        sc += len(s) // 50
        return sc

    return a if score(a) >= score(b) else b


def normalize_method_text(method_block: str) -> str:
    """Convert (cid:N) markers in method to step markers ① ② ..."""
    cids = re.findall(r"\(cid:(\d+)\)", method_block)
    if not cids:
        return method_block
    seen = []
    for c in cids:
        n = int(c)
        if n not in seen and n < 30:
            seen.append(n)
    if len(seen) >= 2 and seen == sorted(seen):
        order = {c: idx + 1 for idx, c in enumerate(seen)}
        def repl(m):
            n = int(m.group(1))
            if n in order and order[n] <= 20:
                return CIRCLED[order[n] - 1]
            return ""
        return re.sub(r"\(cid:(\d+)\)", repl, method_block)
    return re.sub(r"\(cid:\d+\)", " ", method_block)


def is_memo_ingredient(name: str, amount: str) -> bool:
    """Return True if an ingredient line looks like a memo/note, not an ingredient."""
    if not name:
        return True
    # Has amount → almost certainly a real ingredient
    if amount and AMOUNT_KEYWORDS.search(amount):
        return False
    # Ends with sentence-ending punctuation (and no amount)
    if not amount and re.search(r"[。！？]$", name):
        return True
    # Ends with 、 or ， (incomplete sentence)
    if name.endswith("、") or name.endswith("，"):
        return True
    # Ends with colloquial sentence fragments
    if name.endswith("なの") or name.endswith("ので"):
        return True
    # Ends with topic particle は (sentence header, not ingredient name)
    if name.endswith("は") and len(name) <= 15:
        return True
    # Ends with TE-form or conjunctive form (sentence fragment, not ingredient name)
    if re.search(r"(して|にして|として|アレンジして|代えて|加えて|使って)$", name):
        return True
    # Ends with conjunctive particle や (meaning "and/or" in listing)
    if name.endswith("や") and "や" in name[:-1]:
        return True
    # Contains adjective TE-form mid-sentence (describing texture/quality, not ingredient)
    if re.search(r"[くい]て.{2,}", name):
        return True
    # Short hiragana fragment followed by 、 (mid-sentence continuation)
    if re.match(r"^[ぁ-ん]{1,2}、", name):
        return True
    # Contains sentence-internal 、 after object/topic marker → sentence structure
    if re.search(r"(を、|は、|が、|で、|に、|と、|も、)", name):
        return True
    # Japanese exclamation mark in name (tip/note style, not ingredient name)
    if "！" in name:
        return True
    # Starts with a grammatical particle followed by kanji/hiragana (sentence continuation)
    if re.match(r"^[をはがでにとも][一-鿿ぁ-ん]", name):
        return True
    # 。 appearing in the middle of the string (sentence continuation fragment)
    if re.search(r"。.+", name):
        return True
    # Parenthetical/note prefixes
    if name.startswith("（※") or name.startswith("※"):
        return True
    # Decoration tilde (PDF layout ornament, not ingredient)
    if "〜" in name:
        return True
    # Ends with closing bracket (citation/note ending)
    if name.endswith("」"):
        return True
    # Ends with adnominal の (modifier particle, not ingredient name)
    if name.endswith("の") and len(name) > 8:
        return True
    # Contains clear food-note keywords
    if re.search(r"(郷土料理|給食では|給食は|食欲をそそ|使用しました|使用されて|ことから"
                 r"|気になる場合|よんでいました|子どもたち|子供たち|含まれ|ビタミン"
                 r"|指定|地域|下さい|原材料|混合"
                 r"|ください|できます|できました|ましょう|ですよ|ますよ|ますが|ますので"
                 r"|おいしい|おいしく|提供|人気|旬|特徴|産地|作られ|食べてもらい"
                 r"|ところです|思います|です。|ます。)", name):
        return True
    # Very long line without amount keywords → description
    if len(name) > 28 and not AMOUNT_KEYWORDS.search(name + amount):
        return True
    return False


def separate_steps_and_notes(steps: list) -> tuple:
    """Split steps list into (real_steps, notes) by finding where memo text begins."""
    if not steps:
        return [], []

    # Find the first explicitly "memo-like" step
    first_memo = len(steps)
    for i, step in enumerate(steps):
        # Strip ※...。 annotations before checking — they inflate memo signals
        step_main = re.sub(r"※[^。]*。?", "", step).strip()
        if MEMO_PATTERNS.search(step_main) and not COOKING_VERBS.search(step_main):
            first_memo = i
            break

    # Walk backwards from first_memo: pull in trailing fragments that don't end
    # with 。 AND have no cooking content (pure setup lines leading into memo).
    while first_memo > 0:
        prev = steps[first_memo - 1]
        if not re.search(r"[。！？]$", prev) and not COOKING_VERBS.search(prev):
            first_memo -= 1
        else:
            break

    return steps[:first_memo], steps[first_memo:]


def try_column_extraction(path: Path):
    """For 2-column PDFs: extract left (ingredients) and right (steps) separately.

    Returns (ing_text, method_text, servings) or (None, None, "").
    """
    try:
        with pdfplumber.open(path) as pdf:
            page = pdf.pages[0]
            w, h = page.width, page.height
            y_start = h * 0.25  # skip title/photo at top

            for x_ratio in [0.42, 0.40, 0.45, 0.38, 0.48]:
                left = page.crop((0, y_start, w * x_ratio, h))
                right = page.crop((w * x_ratio, y_start, w, h))
                left_text = (left.extract_text() or "").strip()
                right_text = (right.extract_text() or "").strip()

                # Validate: left should have ingredient header and several items
                if not HEADER_INGRED_FULL.search(left_text) and not HEADER_INGRED_LOOSE.search(left_text):
                    continue
                lines = [ln.strip() for ln in left_text.split("\n") if ln.strip()]
                ing_lines = [ln for ln in lines if not HEADER_INGRED_FULL.search(ln)
                             and not HEADER_INGRED_LOOSE.search(ln)]
                # Strip bullets
                ing_lines = [re.sub(r"^[・･]+\s*", "", ln) for ln in ing_lines]
                ing_lines = [ln for ln in ing_lines if ln]

                # Need at least 5 ingredient-like lines
                real_ing = [ln for ln in ing_lines if not is_memo_ingredient(ln, "")]
                if len(real_ing) >= 4:
                    m = HEADER_INGRED_FULL.search(left_text)
                    servings = ""
                    if m:
                        num = m.group(1).translate(str.maketrans("０１２３４５６７８９", "0123456789"))
                        servings = f"{num}人分"
                    return left_text, right_text, servings

    except Exception:
        pass
    return None, None, ""


def parse_recipe_text(text: str, pdf_path: Path = None):
    text = text.replace("　", " ")
    text_clean = re.sub(r"\(cid:\d+\)", " ", text)
    text_clean = text_clean.translate(str.maketrans("０１２３４５６７８９", "0123456789"))

    lines = [ln.rstrip() for ln in text_clean.split("\n")]

    # Find ingredient / method header indices
    ing_idx = -1
    method_idx = -1
    servings = ""
    for i, ln in enumerate(lines):
        if ing_idx == -1:
            m = HEADER_INGRED_FULL.search(ln)
            if m:
                ing_idx = i
                num = m.group(1).translate(str.maketrans("０１２３４５６７８９", "0123456789"))
                servings = f"{num}人分"
                continue
            if HEADER_INGRED_LOOSE.match(ln):
                ing_idx = i
                continue
        if HEADER_METHOD.search(ln) and method_idx == -1 and i > ing_idx:
            # Require the method header to be mostly standalone (not embedded in ingredient line)
            remaining = HEADER_METHOD.sub("", ln).strip()
            remaining_clean = re.sub(r"\s+", "", remaining)
            if len(remaining_clean) <= 8:
                method_idx = i

    # Fallback: search for method header anywhere
    if method_idx == -1:
        for i, ln in enumerate(lines):
            if HEADER_METHOD.search(ln):
                remaining = HEADER_METHOD.sub("", ln).strip()
                remaining_clean = re.sub(r"\s+", "", remaining)
                if len(remaining_clean) <= 8:
                    method_idx = i
                    break

    if ing_idx == -1 or method_idx == -1:
        # Try column extraction for 2-column layouts (if pdf_path provided)
        if pdf_path and pdf_path.exists():
            left_text, right_text, col_servings = try_column_extraction(pdf_path)
            if left_text and right_text:
                # Parse left as ingredients, right as method
                col_result = parse_column_texts(left_text, right_text, col_servings or servings)
                if col_result["ingredients"] or col_result["instructions"]:
                    col_result["_parse_status"] = "column_split"
                    return col_result
        return {"servings": servings, "ingredients": [], "instructions": [],
                "notes": "", "_parse_status": "headers_not_found"}

    if method_idx < ing_idx:
        ing_idx, method_idx = method_idx, ing_idx

    # Check if ingredients section is empty (likely 2-column layout)
    ingredient_lines_raw = lines[ing_idx + 1:method_idx]
    meaningful_ing_lines = [ln.strip() for ln in ingredient_lines_raw
                            if ln.strip() and not HEADER_INGRED_FULL.search(ln.strip())]

    if len(meaningful_ing_lines) == 0 and pdf_path and pdf_path.exists():
        # Empty ingredients section → try column extraction
        left_text, right_text, col_servings = try_column_extraction(pdf_path)
        if left_text and right_text:
            col_result = parse_column_texts(left_text, right_text, col_servings or servings)
            if col_result["ingredients"]:
                col_result["_parse_status"] = "column_split"
                return col_result

    ingredient_lines = lines[ing_idx + 1:method_idx]
    method_section_text = "\n".join(lines[method_idx + 1:])

    # Use original raw text for method to preserve CIDs for normalization
    raw_lines = text.split("\n")
    method_start = -1
    for i, ln in enumerate(raw_lines):
        if HEADER_METHOD.search(ln.replace("　", " ")):
            remaining = HEADER_METHOD.sub("", ln.replace("　", " ")).strip()
            if len(re.sub(r"\s+", "", remaining)) <= 8:
                method_start = i
                break
    if method_start >= 0:
        raw_method = "\n".join(raw_lines[method_start + 1:])
        raw_method = normalize_method_text(raw_method)
        raw_method = raw_method.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
        method_section_text = raw_method

    # Parse ingredients
    ingredients = []
    current_group = ""
    for ln in ingredient_lines:
        s = ln.strip()
        if not s:
            continue
        if HEADER_INGRED_FULL.search(s) or HEADER_INGRED_LOOSE.match(s):
            current_group = "(別)"
            continue
        s = re.sub(r"^[・･]+\s*", "", s)
        if re.fullmatch(r"[ＡＢＣＤＥＦA-F]", s):
            current_group = s
            continue

        if "\t" in s:
            parts = [p.strip() for p in s.split("\t") if p.strip()]
        else:
            parts = re.split(r"\s{2,}", s)
            if len(parts) == 1:
                tokens = s.split()
                if len(tokens) >= 2 and re.search(r"[\d¼½⅓⅔⅛⅜適少約]", tokens[-1]):
                    parts = [" ".join(tokens[:-1]), tokens[-1]]
                else:
                    # Scan for amount token followed by long description-like rest
                    parts = [s]
                    for j in range(1, len(tokens)):
                        if re.search(r"[\d¼½⅓⅔⅛⅜適少約]", tokens[j]):
                            rest = " ".join(tokens[j + 1:])
                            if len(rest) >= 4 and not re.search(r"[\d¼½⅓⅔⅛⅜適少約]", rest):
                                parts = [" ".join(tokens[:j]), tokens[j]]
                                break
        name = parts[0]
        amount = " ".join(parts[1:]) if len(parts) > 1 else ""

        if is_memo_ingredient(name.strip(), amount.strip()):
            continue  # skip memo lines from ingredients

        ingredients.append({
            "name": name.strip(),
            "amount": amount.strip(),
            "group": current_group,
        })

    # Parse instructions
    steps = []
    notes_lines = []
    in_method = True
    for ln in method_section_text.split("\n"):
        s = ln.strip()
        if not s:
            continue
        m = STEP_RE.match(s)
        if m:
            in_method = True  # Step marker always re-enables method mode
            steps.append(m.group(1).strip())
        elif steps and in_method and not s.startswith(("・", "※", "*", "＊", "■")):
            last = steps[-1]
            if not last:
                steps[-1] = s
            elif not re.search(r"[。．！？]$", last) and len(s) < 80:
                if MEMO_PATTERNS.search(s) and not COOKING_VERBS.search(s):
                    # Side-panel memo text mid-step: put in notes, keep in_method so
                    # the real step continuation on the next line can still be appended.
                    notes_lines.append(s)
                else:
                    steps[-1] += s
            elif COOKING_VERBS.search(s) and not MEMO_PATTERNS.search(s) and len(s) < 80:
                # Cooking verb continuation after sentence-ending 。 (PDF line wrap)
                steps[-1] += s
            elif MEMO_PATTERNS.search(s):
                in_method = False
                notes_lines.append(s)
            else:
                notes_lines.append(s)
        else:
            in_method = False
            notes_lines.append(s)

    # Fallback: no step markers found → treat each line as a step
    if not steps and method_section_text.strip():
        candidate_lines = [
            ln.strip() for ln in method_section_text.split("\n")
            if ln.strip() and not ln.strip().startswith(("・", "※", "*", "＊", "■"))
        ]
        if 2 <= len(candidate_lines) <= 25:
            # Filter obvious memo lines individually (avoids cutoff losing real steps)
            filtered_steps = []
            filtered_notes = []
            for ln in candidate_lines:
                ln_main = re.sub(r"※[^。]*。?", "", ln).strip()
                if (MEMO_PATTERNS.search(ln_main) and not COOKING_VERBS.search(ln_main)
                        and len(ln) < 60):
                    filtered_notes.append(ln)
                else:
                    filtered_steps.append(ln)
            clean_steps, extra_notes = separate_steps_and_notes(filtered_steps)
            steps = clean_steps
            notes_lines = extra_notes + filtered_notes + notes_lines
    else:
        # Also trim any memo text that leaked into the end of numbered steps
        steps, extra_notes = separate_steps_and_notes(steps)
        notes_lines = extra_notes + notes_lines

    return {
        "servings": servings,
        "ingredients": ingredients,
        "instructions": steps,
        "notes": " ".join(notes_lines).strip(),
        "_parse_status": "ok" if (ingredients or steps) else "empty",
    }


def parse_column_texts(left_text: str, right_text: str, servings: str) -> dict:
    """Parse pre-split column texts into ingredients and instructions."""
    # Clean left (ingredients)
    left_clean = re.sub(r"\(cid:\d+\)", " ", left_text)
    left_clean = left_clean.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    left_clean = left_clean.replace("　", " ")

    ingredients = []
    current_group = ""
    for ln in left_clean.split("\n"):
        s = ln.strip()
        if not s:
            continue
        if HEADER_INGRED_FULL.search(s) or HEADER_INGRED_LOOSE.match(s):
            m = HEADER_INGRED_FULL.search(s)
            if m and not servings:
                num = m.group(1).translate(str.maketrans("０１２３４５６７８９", "0123456789"))
                servings = f"{num}人分"
            continue
        s = re.sub(r"^[・･]+\s*", "", s)
        if not s or re.fullmatch(r"[ＡＢＣＤＥＦA-F]", s):
            if s:
                current_group = s
            continue

        parts = re.split(r"\s{2,}", s)
        if len(parts) == 1:
            tokens = s.split()
            if len(tokens) >= 2 and re.search(r"[\d¼½⅓⅔⅛⅜適少約]", tokens[-1]):
                parts = [" ".join(tokens[:-1]), tokens[-1]]
            else:
                parts = [s]
                for j in range(1, len(tokens)):
                    if re.search(r"[\d¼½⅓⅔⅛⅜適少約]", tokens[j]):
                        rest = " ".join(tokens[j + 1:])
                        if len(rest) >= 4 and not re.search(r"[\d¼½⅓⅔⅛⅜適少約]", rest):
                            parts = [" ".join(tokens[:j]), tokens[j]]
                            break

        name = parts[0]
        amount = " ".join(parts[1:]) if len(parts) > 1 else ""

        if is_memo_ingredient(name.strip(), amount.strip()):
            continue

        ingredients.append({"name": name.strip(), "amount": amount.strip(), "group": current_group})

    # Clean right (method)
    right_raw = right_text
    right_norm = normalize_method_text(right_raw)
    right_norm = re.sub(r"\(cid:\d+\)", " ", right_norm)
    right_norm = right_norm.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    right_norm = right_norm.replace("　", " ")

    # Strip method header line
    right_lines = right_norm.split("\n")
    method_start = 0
    for i, ln in enumerate(right_lines):
        if HEADER_METHOD.search(ln):
            method_start = i + 1
            break
    right_lines = right_lines[method_start:]

    steps = []
    notes_lines = []
    in_method = True
    for ln in right_lines:
        s = ln.strip()
        if not s:
            continue
        m = STEP_RE.match(s)
        if m:
            in_method = True
            steps.append(m.group(1).strip())
        elif steps and in_method and not s.startswith(("・", "※", "*", "＊", "■")):
            last = steps[-1]
            if not last:
                steps[-1] = s
            elif not re.search(r"[。．！？]$", last) and len(s) < 80:
                if MEMO_PATTERNS.search(s) and not COOKING_VERBS.search(s):
                    notes_lines.append(s)
                else:
                    steps[-1] += s
            elif COOKING_VERBS.search(s) and not MEMO_PATTERNS.search(s) and len(s) < 80:
                steps[-1] += s
            elif MEMO_PATTERNS.search(s):
                in_method = False
                notes_lines.append(s)
            else:
                notes_lines.append(s)
        else:
            in_method = False
            notes_lines.append(s)

    if not steps and right_lines:
        candidate_lines = [ln.strip() for ln in right_lines
                           if ln.strip() and not ln.strip().startswith(("・", "※", "*", "＊", "■"))]
        if 2 <= len(candidate_lines) <= 25:
            clean_steps, extra_notes = separate_steps_and_notes(candidate_lines)
            steps = clean_steps
            notes_lines = extra_notes + notes_lines
    else:
        steps, extra_notes = separate_steps_and_notes(steps)
        notes_lines = extra_notes + notes_lines

    return {
        "servings": servings,
        "ingredients": ingredients,
        "instructions": steps,
        "notes": " ".join(notes_lines).strip(),
        "_parse_status": "ok" if (ingredients or steps) else "empty",
    }


def main():
    records = json.loads(PDF_LIST.read_text(encoding="utf-8"))
    out = []
    for i, r in enumerate(records, 1):
        pdf_path = DL_DIR / r["filename"]
        if not pdf_path.exists():
            print(f"[{i}] missing {r['filename']}")
            continue
        try:
            text = get_text(pdf_path)
            parsed = parse_recipe_text(text, pdf_path=pdf_path)
        except Exception as e:
            print(f"[{i}] parse error {r['filename']}: {e}")
            parsed = {"servings": "", "ingredients": [], "instructions": [], "notes": "",
                      "_parse_status": f"error:{e}"}
            text = ""

        out.append({
            "id": r["filename"].replace(".pdf", ""),
            "name": r["name"],
            "section": r["section"],
            "category": r["category"],
            "date_jp": r["date_jp"],
            "date_iso": jp_date_to_iso(r["date_jp"]),
            "size": r["size"],
            "pdf_url": r["url"],
            "pdf_filename": r["filename"],
            **parsed,
            "raw_text": text.strip(),
        })

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(out)} recipes -> {OUT}")
    no_ings = sum(1 for r in out if not r["ingredients"])
    no_steps = sum(1 for r in out if not r["instructions"])
    fully_parsed = sum(1 for r in out if r["ingredients"] and r["instructions"])
    print(f"  fully parsed (ing & steps): {fully_parsed}/{len(out)}")
    print(f"  no ingredients: {no_ings}")
    print(f"  no instructions: {no_steps}")


if __name__ == "__main__":
    main()
