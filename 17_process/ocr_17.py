"""
OCR script for folder 17 PDFs:
- เขต 2 นอกเขตนอกราช ปากพนัง.pdf       → constituency (แบ่งเขต)
- เขต 2 นอกเขตนอกราช ปากพนัง บช.pdf    → party_list (บัญชีรายชื่อ)
"""
import csv
import re
import os
import sys
import time
import pypdf
from pathlib import Path
from typing import Optional
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from typhoon_ocr import ocr_document
from rapidfuzz import process, fuzz
import pandas as pd

load_dotenv()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")

CONSTITUENCY_PDF = os.path.join(SCRIPT_DIR, "data/raw_pdf/17/เขต 2 นอกเขตนอกราช ปากพนัง.pdf")
PARTY_LIST_PDF   = os.path.join(SCRIPT_DIR, "data/raw_pdf/17/เขต 2 นอกเขตนอกราช ปากพนัง บช.pdf")

OUT_CONSTITUENCY = os.path.join(SCRIPT_DIR, "output/raw_csv/17_constituency.csv")
OUT_PARTY_LIST   = os.path.join(SCRIPT_DIR, "output/raw_csv/17_party_list.csv")

REF_PATH = os.path.join(SCRIPT_DIR, "reference/candidates_ref.csv")

CONSTITUENCY_FIELDS = ["จังหวัด", "เขต", "ชุดที่", "บัตรดี", "บัตรเสีย", "บัตรที่ไม่เลือก",
                       "หมายเลข", "ชื่อสกุล", "พรรค", "คะแนน", "match_method", "match_score"]
PARTY_LIST_FIELDS   = ["จังหวัด", "เขต", "ชุดที่", "บัตรดี", "บัตรเสีย", "บัตรที่ไม่เลือก",
                       "หมายเลข", "พรรค", "คะแนน"]


# ---------------------------------------------------------------------------
# Reference matching
# ---------------------------------------------------------------------------

def load_reference(ref_path: str) -> pd.DataFrame:
    return pd.read_csv(ref_path, dtype={"หมายเลข": int})


def match_candidate(ocr_num: Optional[int], ocr_name: str, ref_df: pd.DataFrame) -> dict:
    if ocr_num is not None:
        row = ref_df[ref_df["หมายเลข"] == ocr_num]
        if not row.empty:
            r = row.iloc[0]
            return {"หมายเลข": int(r["หมายเลข"]), "ชื่อสกุล": r["ชื่อสกุล"],
                    "พรรค": r["พรรค"], "match_method": "number", "match_score": 100}
    if ocr_name:
        result = process.extractOne(ocr_name, ref_df["ชื่อสกุล"].tolist(),
                                    scorer=fuzz.token_sort_ratio, score_cutoff=65)
        if result:
            matched_name, score, idx = result
            r = ref_df.iloc[idx]
            return {"หมายเลข": int(r["หมายเลข"]), "ชื่อสกุล": r["ชื่อสกุล"],
                    "พรรค": r["พรรค"], "match_method": "fuzzy", "match_score": round(score, 1)}
    return {"หมายเลข": ocr_num, "ชื่อสกุล": ocr_name, "พรรค": "",
            "match_method": "none", "match_score": 0}


# ---------------------------------------------------------------------------
# Header parser
# ---------------------------------------------------------------------------

def parse_header(markdown: str) -> dict:
    t = markdown.translate(THAI_DIGITS)
    info = {
        "จังหวัด": "นครศรีธรรมราช",
        "เขต": 2,
    }

    m = re.search(r"ชุดที่\s*(\d+)", t)
    info["ชุดที่"] = int(m.group(1)) if m else None

    m = re.search(r"2\.2\.1[^\d]*(\d+)\s*บัตร", t)
    info["บัตรดี"] = int(m.group(1)) if m else None

    m = re.search(r"2\.2\.2[^\d]*(\d+)\s*บัตร", t)
    info["บัตรเสีย"] = int(m.group(1)) if m else None

    m = re.search(r"2\.2\.3[^\d]*(\d+)\s*บัตร", t)
    info["บัตรที่ไม่เลือก"] = int(m.group(1)) if m else None

    return info


# ---------------------------------------------------------------------------
# Table parser
# ---------------------------------------------------------------------------

def parse_table(markdown: str, doc_type: str, ref_df: Optional[pd.DataFrame]) -> list:
    match = re.search(r"<table.*?>.*?</table>", markdown, re.DOTALL)
    if not match:
        return []

    soup = BeautifulSoup(match.group(0), "html.parser")
    rows = soup.find_all("tr")
    if not rows:
        return []

    header = [td.get_text(" ", strip=True).translate(THAI_DIGITS)
              for td in rows[0].find_all(["th", "td"])]

    def find_col(keywords):
        for i, h in enumerate(header):
            if any(kw in h for kw in keywords):
                return i
        return -1

    idx_num   = find_col(["หมายเลข"])
    idx_name  = find_col(["ชื่อตัว", "ชื่อสกุล", "ชื่อ - สกุล"])
    idx_party = find_col(["พรรค", "สังกัด"])
    idx_score = find_col(["คะแนน"])

    if idx_num   < 0: idx_num   = 0
    if idx_party < 0: idx_party = 2 if doc_type == "constituency" else 1
    if idx_score < 0: idx_score = 3 if doc_type == "constituency" else 2

    results = []
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
        ocr_num     = int(num_match.group()) if num_match else None
        score       = int(score_match.group()) if score_match else None

        if doc_type == "constituency" and ref_df is not None:
            ocr_name = get(idx_name)
            resolved = match_candidate(ocr_num, ocr_name, ref_df)
            resolved["คะแนน"] = score
            results.append(resolved)
        else:
            results.append({
                "หมายเลข": ocr_num,
                "พรรค":    get(idx_party),
                "คะแนน":  score,
            })

    return results


# ---------------------------------------------------------------------------
# Process one PDF
# ---------------------------------------------------------------------------

def process_pdf(pdf_path: str, doc_type: str, output_csv: str,
                fieldnames: list, ref_df):
    reader = pypdf.PdfReader(pdf_path)
    n_pages = len(reader.pages)
    print(f"\n📄 {Path(pdf_path).name} — {n_pages} pages [{doc_type}]")

    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    success = 0

    with open(output_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()

        for page_num in range(1, n_pages + 1):
            print(f"  [{page_num}/{n_pages}]", end=" ")
            try:
                markdown = ocr_document(
                    pdf_or_image_path=pdf_path,
                    page_num=page_num,
                    target_image_dim=1024,
                )
                header_info = parse_header(markdown)
                candidates  = parse_table(markdown, doc_type, ref_df)

                if not candidates:
                    print("skip (no table)")
                    time.sleep(1.0)
                    continue

                for c in candidates:
                    writer.writerow({**header_info, **c})

                print(f"✅ {len(candidates)} rows | ชุดที่={header_info.get('ชุดที่')}")
                success += 1

            except Exception as e:
                print(f"❌ {e}")

            time.sleep(1.5)

    print(f"\n✅ Done: {success} pages → {output_csv}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    api_key = os.getenv("TYPHOON_OCR_API_KEY", "")
    if not api_key:
        print("❌ ไม่พบ TYPHOON_OCR_API_KEY")
        sys.exit(1)
    os.environ["TYPHOON_OCR_API_KEY"] = api_key

    ref_df = load_reference(REF_PATH)
    print(f"📋 Loaded {len(ref_df)} candidates from reference")

    # Constituency (แบ่งเขต)
    process_pdf(CONSTITUENCY_PDF, "constituency", OUT_CONSTITUENCY,
                CONSTITUENCY_FIELDS, ref_df)

    # Party list (บัญชีรายชื่อ)
    process_pdf(PARTY_LIST_PDF, "party_list", OUT_PARTY_LIST,
                PARTY_LIST_FIELDS, None)


if __name__ == "__main__":
    main()
