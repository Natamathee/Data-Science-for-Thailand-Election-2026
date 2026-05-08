"""
Batch OCR processor for constituency (5.18 / 18) folders.
Supports both JPG (raw_jpg) and PDF (raw_pdf) sources.
Results are appended to a single output CSV.
"""
import csv
import os
import sys
import time
import pypdf
from pathlib import Path
from dotenv import load_dotenv
from typhoon_ocr import ocr_document

from main import (
    load_reference,
    parse_path_info,
    parse_candidates_from_markdown,
    validate,
    SCRIPT_DIR,
    REF_PATH,
)

load_dotenv()

OUTPUT_CSV  = os.path.join(SCRIPT_DIR, "output", "raw_csv", "output_constituency.csv")
SLEEP_SEC   = 1.5

META_FIELDS = [
    "จังหวัด", "เขตเลือกตั้งที่", "ตำบล", "อำเภอ",
    "หน่วยเลือกตั้งที่", "หมู่ที่",
    "จำนวนผู้มีสิทธิเลือกตั้ง", "จำนวนผู้มาแสดงตน",
    "จำนวนบัตรที่ได้รับจัดสรร", "จำนวนบัตรที่ใช้",
    "จำนวนบัตรดี", "จำนวนบัตรเสีย",
    "จำนวนบัตรที่ไม่เลือกผู้สมัคร", "จำนวนบัตรคงเหลือ",
    "source_file", "needs_review", "validation_notes",
]
CANDIDATE_FIELDS = ["หมายเลข", "ชื่อสกุล", "พรรค", "คะแนน", "match_method", "match_score"]
FIELDNAMES = META_FIELDS + CANDIDATE_FIELDS


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def find_jpg_files(root: str) -> list[tuple[Path, int]]:
    """Find all jpg files in folders named '5.18'. Returns (path, page=1)."""
    results = []
    for jpg in sorted(Path(root).rglob("*.jpg")):
        if jpg.parent.name == "5.18":
            results.append((jpg, 1))
    return results


def find_pdf_files(root: str) -> list[tuple[Path, int]]:
    """Find all pdf files in folders named '18' under ตำบล*/เทศบาล* only. Returns (path, page_num) per page."""
    results = []
    for pdf in sorted(Path(root).rglob("*.pdf")):
        # Only process if parent folder is '18' AND grandparent starts with ตำบล or เทศบาล
        if pdf.parent.name == "18":
            grandparent = pdf.parent.parent.name
            if grandparent.startswith("ตำบล") or grandparent.startswith("เทศบาล"):
                try:
                    reader = pypdf.PdfReader(str(pdf))
                    n_pages = len(reader.pages)
                    for page_num in range(1, n_pages + 1):
                        results.append((pdf, page_num))
                except Exception as e:
                    print(f"  [warn] cannot read {pdf}: {e}")
    return results


# ---------------------------------------------------------------------------
# Process one image/page
# ---------------------------------------------------------------------------

def process_file(file_path: Path, page_num: int, ref_df, writer: csv.DictWriter) -> bool:
    """OCR one file/page and write rows to CSV. Returns True if data was found."""
    try:
        markdown = ocr_document(
            pdf_or_image_path=str(file_path),
            page_num=page_num,
            target_image_dim=1024,
        )
        header_info, candidates = parse_candidates_from_markdown(markdown, ref_df)

        # Skip pages with no candidate data (irrelevant pages in PDF)
        if not candidates:
            print(f"  [skip] no candidates found (page {page_num})")
            return False

        # Override with path-derived info
        path_info = parse_path_info(str(file_path))
        for key, val in path_info.items():
            if val is not None:
                header_info[key] = val

        source = str(file_path.relative_to(SCRIPT_DIR))
        header_info["source_file"] = f"{source}#p{page_num}" if page_num > 1 else source

        # Validate
        is_valid, issues = validate(header_info, candidates)
        header_info["needs_review"]     = "YES" if not is_valid else "NO"
        header_info["validation_notes"] = " | ".join(issues) if issues else ""

        for c in candidates:
            writer.writerow({**header_info, **c})

        status = "✅" if is_valid else "❌ needs_review"
        print(f"  {status} — {len(candidates)} candidates")
        return True

    except Exception as e:
        print(f"  [error] {e}")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["jpg", "pdf", "all"], default="all",
                        help="Which source to process (default: all)")
    args = parser.parse_args()

    api_key = os.getenv("TYPHOON_OCR_API_KEY", "")
    if not api_key:
        print("❌ ไม่พบ TYPHOON_OCR_API_KEY ใน .env")
        sys.exit(1)
    os.environ["TYPHOON_OCR_API_KEY"] = api_key

    ref_df = load_reference(REF_PATH)
    print(f"📋 Loaded {len(ref_df)} candidates from reference")

    # Collect files
    tasks = []
    if args.source in ("jpg", "all"):
        jpg_tasks = find_jpg_files(os.path.join(SCRIPT_DIR, "data/raw_jpg"))
        print(f"🖼  Found {len(jpg_tasks)} JPG files in 5.18 folders")
        tasks.extend(jpg_tasks)

    if args.source in ("pdf", "all"):
        pdf_tasks = find_pdf_files(os.path.join(SCRIPT_DIR, "data/raw_pdf"))
        print(f"📄 Found {len(pdf_tasks)} PDF pages in 18 folders")
        tasks.extend(pdf_tasks)

    if not tasks:
        print("ไม่พบไฟล์")
        sys.exit(1)

    print(f"\n🚀 Total: {len(tasks)} tasks\n")

    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    file_exists = os.path.isfile(OUTPUT_CSV)

    success, failed = 0, 0
    failed_paths = []

    with open(OUTPUT_CSV, "a" if file_exists else "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        if not file_exists:
            writer.writeheader()

        for i, (file_path, page_num) in enumerate(tasks, 1):
            label = f"{file_path.name}" + (f" p.{page_num}" if page_num > 1 else "")
            print(f"[{i}/{len(tasks)}] {label}")

            ok = process_file(file_path, page_num, ref_df, writer)
            if ok:
                success += 1
            else:
                failed += 1
                failed_paths.append(f"{file_path}#p{page_num}")

            if i < len(tasks):
                time.sleep(SLEEP_SEC)

    print(f"\n{'='*50}")
    print(f"✅ Success: {success} | ❌ Failed/Skipped: {failed}")
    print(f"📁 Output: {OUTPUT_CSV}")

    if failed_paths:
        failed_log = os.path.join(SCRIPT_DIR, "failed_ocr.txt")
        with open(failed_log, "w", encoding="utf-8") as f:
            f.write("\n".join(failed_paths))
        print(f"📝 Failed list: {failed_log}")


if __name__ == "__main__":
    main()
