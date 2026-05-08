import csv
import re
import os
import sys
import pandas as pd
from pathlib import Path
from typing import Optional
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from typhoon_ocr import ocr_document
from rapidfuzz import process, fuzz

load_dotenv()

THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
REF_PATH    = os.path.join(SCRIPT_DIR, "candidates_ref.csv")


# ---------------------------------------------------------------------------
# Reference table
# ---------------------------------------------------------------------------

def load_reference(ref_path: str) -> pd.DataFrame:
    """Load candidates_ref.csv → DataFrame indexed by หมายเลข."""
    df = pd.read_csv(ref_path, dtype={"หมายเลข": int})
    return df


def match_candidate(ocr_num: Optional[int], ocr_name: str, ref_df: pd.DataFrame) -> dict:
    """
    Resolve OCR output to canonical candidate info.

    Priority:
      1. Match by หมายเลข (most reliable)
      2. Fuzzy match by ชื่อสกุล (fallback when number unreadable)
      3. Return OCR values as-is if no match found
    """
    # 1. Match by number
    if ocr_num is not None:
        row = ref_df[ref_df["หมายเลข"] == ocr_num]
        if not row.empty:
            r = row.iloc[0]
            return {
                "หมายเลข":      int(r["หมายเลข"]),
                "ชื่อสกุล":     r["ชื่อสกุล"],
                "พรรค":         r["พรรค"],
                "match_method": "number",
                "match_score":  100,
            }

    # 2. Fuzzy match by name
    if ocr_name:
        result = process.extractOne(
            ocr_name,
            ref_df["ชื่อสกุล"].tolist(),
            scorer=fuzz.token_sort_ratio,
            score_cutoff=65,
        )
        if result:
            matched_name, score, idx = result
            r = ref_df.iloc[idx]
            return {
                "หมายเลข":      int(r["หมายเลข"]),
                "ชื่อสกุล":     r["ชื่อสกุล"],
                "พรรค":         r["พรรค"],
                "match_method": "fuzzy",
                "match_score":  round(score, 1),
            }

    # 3. No match — keep OCR values
    return {
        "หมายเลข":      ocr_num,
        "ชื่อสกุล":     ocr_name,
        "พรรค":         "",
        "match_method": "none",
        "match_score":  0,
    }


# ---------------------------------------------------------------------------
# Path parser — ดึง metadata จาก folder path แทน OCR
# ---------------------------------------------------------------------------

def parse_path_info(image_path: str) -> dict:
    """
    Extract metadata from folder structure:
    data/raw_jpg/{ตำบล}/{หน่วยเลือกตั้งที่ X}/...
    """
    parts = Path(image_path).parts
    info = {
        "จังหวัด":         "นครศรีธรรมราช",
        "เขตเลือกตั้งที่": 2,
        "ตำบล":            None,
        "หน่วยเลือกตั้งที่": None,
    }

    for part in parts:
        # ตำบล — folder ที่ขึ้นต้นด้วย "ตำบล"
        if part.startswith("ตำบล"):
            info["ตำบล"] = part.replace("ตำบล", "").strip()

        # หน่วยเลือกตั้งที่ X
        m = re.search(r"หน่วยเลือกตั้งที่\s*(\d+)", part)
        if m:
            info["หน่วยเลือกตั้งที่"] = int(m.group(1))

    return info



def parse_header_info(markdown: str) -> dict:
    t = markdown.translate(THAI_DIGITS)
    info = {}

    m = re.search(r"หน่วยเลือกตั้งที่\s*(\d+)", t)
    info["หน่วยเลือกตั้งที่"] = int(m.group(1)) if m else None

    m = re.search(r"หมู่ที่\s*(\d+)", t)
    info["หมู่ที่"] = int(m.group(1)) if m else None

    m = re.search(r"ตำบล[/แขวง/เทศบาล]*\s+([\u0E00-\u0E7F]+)", t)
    info["ตำบล"] = m.group(1) if m else None

    m = re.search(r"อำเภอ[/เขต]*\s+([\u0E00-\u0E7F]+)", t)
    info["อำเภอ"] = m.group(1) if m else None

    m = re.search(r"เขตเลือกตั้งที่\s*(\d+)", t)
    info["เขตเลือกตั้งที่"] = int(m.group(1)) if m else None

    m = re.search(r"จังหวัด([\u0E00-\u0E7F]+)", t)
    info["จังหวัด"] = m.group(1) if m else None

    m = re.search(r"1\.1[^\d]*(\d+)\s*คน", t)
    info["จำนวนผู้มีสิทธิเลือกตั้ง"] = int(m.group(1)) if m else None

    m = re.search(r"1\.2[^\d]*(\d+)\s*คน", t)
    info["จำนวนผู้มาแสดงตน"] = int(m.group(1)) if m else None

    m = re.search(r"2\.1[^\d]*(\d+)\s*บัตร", t)
    info["จำนวนบัตรที่ได้รับจัดสรร"] = int(m.group(1)) if m else None

    m = re.search(r"2\.2[^.][^\d]*(\d+)\s*บัตร", t)
    info["จำนวนบัตรที่ใช้"] = int(m.group(1)) if m else None

    m = re.search(r"2\.2\.1[^\d]*(\d+)\s*บัตร", t)
    info["จำนวนบัตรดี"] = int(m.group(1)) if m else None

    m = re.search(r"2\.2\.2[^\d]*(\d+)\s*บัตร", t)
    info["จำนวนบัตรเสีย"] = int(m.group(1)) if m else None

    m = re.search(r"2\.2\.3[^\d]*(\d+)\s*บัตร", t)
    info["จำนวนบัตรที่ไม่เลือกผู้สมัคร"] = int(m.group(1)) if m else None

    m = re.search(r"2\.3[^\d]*(\d+)\s*บัตร", t)
    info["จำนวนบัตรคงเหลือ"] = int(m.group(1)) if m else None

    if info["จำนวนบัตรที่ใช้"] is None:
        parts = [info["จำนวนบัตรดี"], info["จำนวนบัตรเสีย"], info["จำนวนบัตรที่ไม่เลือกผู้สมัคร"]]
        if any(p is not None for p in parts):
            info["จำนวนบัตรที่ใช้"] = sum(p or 0 for p in parts)

    return info


# ---------------------------------------------------------------------------
# Table parser
# ---------------------------------------------------------------------------

def parse_candidates_from_markdown(markdown: str, ref_df: pd.DataFrame) -> tuple[dict, list[dict]]:
    print("\n=== Raw Markdown Output ===")
    print(markdown)
    print("===========================\n")

    header_info = parse_header_info(markdown)

    match = re.search(r"<table.*?>.*?</table>", markdown, re.DOTALL)
    if not match:
        print("[warn] ไม่พบ HTML table ใน output")
        return header_info, []

    soup = BeautifulSoup(match.group(0), "html.parser")
    rows = soup.find_all("tr")
    if not rows:
        return header_info, []

    header = [td.get_text(" ", strip=True).translate(THAI_DIGITS)
              for td in rows[0].find_all(["th", "td"])]

    def find_col(keywords):
        for i, h in enumerate(header):
            if any(kw in h for kw in keywords):
                return i
        return -1

    idx_num   = find_col(["หมายเลข"])
    idx_name  = find_col(["ชื่อตัว", "ชื่อสกุล", "ชื่อ - สกุล", "ชื่อ-สกุล"])
    idx_party = find_col(["พรรค", "สังกัด"])
    idx_score = find_col(["คะแนน"])

    if idx_num   < 0: idx_num   = 0
    if idx_name  < 0: idx_name  = 1
    if idx_party < 0: idx_party = 2
    if idx_score < 0: idx_score = 3

    candidates = []
    for tr in rows[1:]:
        cells = [td.get_text(" ", strip=True).translate(THAI_DIGITS)
                 for td in tr.find_all(["td", "th"])]
        if len(cells) < 2:
            continue

        def get(idx):
            if idx < 0 or idx >= len(cells):
                return ""
            return cells[idx].strip()

        num_str   = get(idx_num)
        score_str = get(idx_score)

        if "รวม" in num_str or not num_str:
            continue

        num_match   = re.search(r"\d+", num_str)
        score_match = re.search(r"\d+", score_str)

        ocr_num  = int(num_match.group()) if num_match else None
        ocr_name = get(idx_name)

        # Match against reference table
        resolved = match_candidate(ocr_num, ocr_name, ref_df)
        resolved["คะแนน"] = int(score_match.group()) if score_match else None

        candidates.append(resolved)

    return header_info, candidates


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(header_info: dict, candidates: list[dict]) -> tuple[bool, list[str]]:
    """
    Run 3 validation checks. Returns (is_valid, list_of_failed_checks).
    """
    issues = []

    ballots_allocated = header_info.get("จำนวนบัตรที่ได้รับจัดสรร")
    ballots_used      = header_info.get("จำนวนบัตรที่ใช้")
    ballots_remaining = header_info.get("จำนวนบัตรคงเหลือ")
    good              = header_info.get("จำนวนบัตรดี")
    spoiled           = header_info.get("จำนวนบัตรเสีย")
    no_vote           = header_info.get("จำนวนบัตรที่ไม่เลือกผู้สมัคร")

    total_score = sum(c["คะแนน"] for c in candidates if c.get("คะแนน") is not None)

    # Check 1: บัตรคงเหลือ = บัตรที่ได้รับ - บัตรที่ใช้
    if all(v is not None for v in [ballots_allocated, ballots_used, ballots_remaining]):
        expected = ballots_allocated - ballots_used
        if ballots_remaining != expected:
            issues.append(
                f"check1_fail: บัตรคงเหลือ={ballots_remaining} ≠ {ballots_allocated}-{ballots_used}={expected}"
            )
    else:
        issues.append("check1_skip: ข้อมูลบัตรไม่ครบ")

    # Check 2: บัตรดี + บัตรเสีย + ไม่เลือก = บัตรที่ใช้
    if all(v is not None for v in [good, spoiled, no_vote, ballots_used]):
        expected = good + spoiled + no_vote
        if expected != ballots_used:
            issues.append(
                f"check2_fail: บัตรดี+เสีย+ไม่เลือก={expected} ≠ บัตรที่ใช้={ballots_used}"
            )
    else:
        issues.append("check2_skip: ข้อมูลบัตรไม่ครบ")

    # Check 3: รวมคะแนนผู้สมัคร = บัตรดี
    if good is not None and candidates:
        if total_score != good:
            issues.append(
                f"check3_fail: รวมคะแนน={total_score} ≠ บัตรดี={good}"
            )
    else:
        issues.append("check3_skip: ข้อมูลไม่ครบ")

    is_valid = not any("fail" in i for i in issues)
    return is_valid, issues




def save_to_csv(header_info: dict, candidates: list[dict], output_path: str,
                is_valid: bool, issues: list[str]) -> None:
    if not candidates:
        print("[warn] ไม่มีข้อมูลที่จะบันทึก")
        return

    meta_fields = [
        "จังหวัด", "เขตเลือกตั้งที่", "ตำบล", "อำเภอ",
        "หน่วยเลือกตั้งที่", "หมู่ที่",
        "จำนวนผู้มีสิทธิเลือกตั้ง", "จำนวนผู้มาแสดงตน",
        "จำนวนบัตรที่ได้รับจัดสรร", "จำนวนบัตรที่ใช้",
        "จำนวนบัตรดี", "จำนวนบัตรเสีย",
        "จำนวนบัตรที่ไม่เลือกผู้สมัคร", "จำนวนบัตรคงเหลือ",
        "source_file", "needs_review", "validation_notes",
    ]
    candidate_fields = ["หมายเลข", "ชื่อสกุล", "พรรค", "คะแนน", "match_method", "match_score"]
    fieldnames = meta_fields + candidate_fields

    header_info["needs_review"]      = "YES" if not is_valid else "NO"
    header_info["validation_notes"]  = " | ".join(issues) if issues else ""

    rows = [{**header_info, **c} for c in candidates]

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"✅ Saved {len(rows)} rows → {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    image_path = os.path.join(SCRIPT_DIR, "data/raw_jpg/ตำบลกำแพงเซา/หน่วยเลือกตั้งที่ 1/ส.ส.5.18 /สส-1.jpg")
    output_csv = os.path.join(SCRIPT_DIR, "output.csv")

    api_key = os.getenv("TYPHOON_OCR_API_KEY", "")
    if not api_key:
        print("❌ ไม่พบ TYPHOON_OCR_API_KEY ใน .env")
        sys.exit(1)
    os.environ["TYPHOON_OCR_API_KEY"] = api_key

    ref_df = load_reference(REF_PATH)
    print(f"📋 Loaded {len(ref_df)} candidates from reference")

    print(f"📄 Processing: {image_path}")
    markdown = ocr_document(pdf_or_image_path=image_path)

    header_info, candidates = parse_candidates_from_markdown(markdown, ref_df)

    # Override location fields from path (more reliable than OCR)
    path_info = parse_path_info(image_path)
    for key, val in path_info.items():
        if val is not None:
            header_info[key] = val
    header_info["source_file"] = str(Path(image_path).relative_to(SCRIPT_DIR))

    # Validate
    is_valid, issues = validate(header_info, candidates)

    print("\n=== Validation ===")
    if is_valid:
        print("  ✅ ผ่านทุก check")
    else:
        print("  ❌ ต้องตรวจ manual:")
        for issue in issues:
            print(f"     - {issue}")

    print("\n=== Header Info ===")
    for k, v in header_info.items():
        print(f"  {k}: {v}")

    print("\n=== ผลที่อ่านได้ (หลัง matching) ===")
    for c in candidates:
        flag = "✅" if c["match_method"] == "number" else ("⚠️ " if c["match_method"] == "fuzzy" else "❌")
        print(f"  {flag} #{str(c['หมายเลข']):>2}  {c['ชื่อสกุล']:<30}  {c['พรรค']:<20}  คะแนน={c['คะแนน']}  [{c['match_method']} {c['match_score']}]")

    save_to_csv(header_info, candidates, output_csv, is_valid, issues)


if __name__ == "__main__":
    main()
