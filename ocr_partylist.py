import csv
import re
import os
import sys
import pandas as pd
from pathlib import Path
from typing import Optional
from collections import defaultdict
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from typhoon_ocr import ocr_document
from rapidfuzz import process, fuzz
import fitz  # PyMuPDF for PDF processing
import tempfile

"""
Party List OCR Worker
=====================
This module processes party_list election documents (ส.ส. บัญชีรายชื่อ) ONLY.
Uses party_list.csv for reference matching.

For constituency documents, use main.py
"""

load_dotenv()

THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PARTY_REF_PATH = os.path.join(SCRIPT_DIR, "reference", "party_list.csv")


# ---------------------------------------------------------------------------
# New PDF-based Processing Logic
# ---------------------------------------------------------------------------

def discover_tambon_pdfs(root_dir: Path) -> dict[str, list[Path]]:
    """
    Scan directory structure to find tambon folders and their party-list PDFs.
    
    Structure:
    - Tambon level folders (e.g. "ตำบลคลองกระบือ")
    - Inside each tambon: party-list folders marked with "บช"
    - Inside "บช" folders: PDF files containing multiple polling stations
    
    Returns:
        dict where key=tambon name, value=list of PDF paths in that tambon
    """
    tambon_pdfs = defaultdict(list)
    
    for item in root_dir.iterdir():
        # Only process directories that look like tambon folders
        if not item.is_dir():
            continue
        
        # Extract tambon name from folder name
        tambon_name = item.name
        if not tambon_name.startswith("ตำบล"):
            continue
        
        # Scan for "บช" subfolders within this tambon
        for subfolder in item.iterdir():
            if not subfolder.is_dir():
                continue
            
            # Only process folders containing "บช"
            if "บช" not in subfolder.name:
                continue
            
            # Find PDF files in this "บช" folder
            for pdf_file in subfolder.glob("*.pdf"):
                tambon_pdfs[tambon_name].append(pdf_file)
    
    return dict(tambon_pdfs)


def group_pdf_pages_by_polling_station(pdf_path: Path) -> list[list[Path]]:
    """
    Convert PDF to images and group pages into polling stations.
    
    Rules:
    - Every 3 consecutive pages = 1 polling station
    - Assign polling station IDs sequentially: 1, 2, 3, ...
    
    Returns:
        list of lists, where each inner list contains 3 image paths for one polling station
    """
    # Convert PDF to images
    image_paths = pdf_to_images(str(pdf_path))
    
    # Group into polling stations (3 pages each)
    polling_stations = []
    for i in range(0, len(image_paths), 3):
        station_pages = image_paths[i:i+3]
        if station_pages:  # Handle last incomplete station
            polling_stations.append(station_pages)
    
    return polling_stations


# ---------------------------------------------------------------------------
# PDF Processing
# ---------------------------------------------------------------------------

def pdf_to_images(pdf_path: str, dpi: int = 300) -> list[Path]:
    """
    Convert PDF pages to images using PyMuPDF.
    
    Args:
        pdf_path: Path to PDF file
        dpi: Resolution for conversion (default 300)
    
    Returns:
        List of Path objects for converted images
    """
    doc = fitz.open(pdf_path)
    image_paths = []
    
    # Create temporary directory for images
    temp_dir = Path(tempfile.mkdtemp())
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        
        # Convert page to image
        pix = page.get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72))
        
        # Save image
        image_path = temp_dir / f"page_{page_num + 1}.png"
        pix.save(image_path)
        image_paths.append(image_path)
    
    doc.close()
    return image_paths

# ---------------------------------------------------------------------------
# Reference table - Party List Only
# ---------------------------------------------------------------------------

def load_party_reference(party_ref_path: str) -> pd.DataFrame:
    """Load party_list.csv → DataFrame indexed by หมายเลข."""
    df = pd.read_csv(party_ref_path, dtype={"หมายเลข": int})
    return df


def match_party(ocr_num: Optional[int], ocr_name: str, party_ref_df: pd.DataFrame) -> dict:
    """
    Resolve OCR output to canonical party info (for party_list documents).

    Priority:
      1. Match by หมายเลข (most reliable)
      2. Fuzzy match by พรรคการเมือง (fallback when number unreadable)
      3. Return OCR values as-is if no match found
    """
    # 1. Match by number
    if ocr_num is not None:
        row = party_ref_df[party_ref_df["หมายเลข"] == ocr_num]
        if not row.empty:
            r = row.iloc[0]
            return {
                "หมายเลข":      int(r["หมายเลข"]),
                "พรรคการเมือง": r["พรรคการเมือง"],
                "match_method": "number",
                "match_score":  100,
            }

    # 2. Fuzzy match by party name
    if ocr_name:
        result = process.extractOne(
            ocr_name,
            party_ref_df["พรรคการเมือง"].tolist(),
            scorer=fuzz.token_sort_ratio,
            score_cutoff=65,
        )
        if result:
            matched_name, score, idx = result
            r = party_ref_df.iloc[idx]
            return {
                "หมายเลข":      int(r["หมายเลข"]),
                "พรรคการเมือง": r["พรรคการเมือง"],
                "match_method": "fuzzy",
                "match_score":  round(score, 1),
            }

    # 3. No match — keep OCR values
    return {
        "หมายเลข":      ocr_num,
        "พรรคการเมือง": ocr_name,
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
    """
    Parse header information from OCR markdown output.
    
    Fixed for party-list documents with section numbers 2.3-2.6:
    - 2.3 = บัตรดี (good ballots)
    - 2.4 = บัตรเสีย (spoiled ballots)
    - 2.5 = บัตรที่ไม่เลือก (no-vote ballots)
    - 2.6 = บัตรคงเหลือ (remaining ballots)
    """
    # Normalize whitespace and convert Thai digits first
    t = re.sub(r"\s+", " ", markdown)
    t = t.translate(THAI_DIGITS)
    
    info = {}

    # Location info
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

    # Voter info
    m = re.search(r"1\.1[^\d]*(\d+)\s*คน", t)
    info["จำนวนผู้มีสิทธิเลือกตั้ง"] = int(m.group(1)) if m else None

    m = re.search(r"1\.2[^\d]*(\d+)\s*คน", t)
    info["จำนวนผู้มาแสดงตน"] = int(m.group(1)) if m else None

    # Ballot allocation
    m = re.search(r"2\.1[^\d]*(\d+)\s*บัตร", t)
    info["จำนวนบัตรที่ได้รับจัดสรร"] = int(m.group(1)) if m else None

    m = re.search(r"2\.2[^.\d][^\d]*(\d+)\s*บัตร", t)
    info["จำนวนบัตรที่ใช้"] = int(m.group(1)) if m else None

    # Party-list specific sections (2.3-2.6)
    # 2.3 = บัตรดี (good ballots)
    m = re.search(r"2\.3[^\d]*จำนวน\s*(\d+)\s*บัตร", t, re.DOTALL)
    info["จำนวนบัตรดี"] = int(m.group(1)) if m else None

    # 2.4 = บัตรเสีย (spoiled ballots)
    m = re.search(r"2\.4[^\d]*จำนวน\s*(\d+)\s*บัตร", t, re.DOTALL)
    info["จำนวนบัตรเสีย"] = int(m.group(1)) if m else None

    # 2.5 = บัตรที่ไม่เลือก (no-vote ballots)
    m = re.search(r"2\.5[^\d]*จำนวน\s*(\d+)\s*บัตร", t, re.DOTALL)
    info["จำนวนบัตรที่ไม่เลือกผู้สมัคร"] = int(m.group(1)) if m else None

    # 2.6 = บัตรคงเหลือ (remaining ballots)
    m = re.search(r"2\.6[^\d]*จำนวน\s*(\d+)\s*บัตร", t, re.DOTALL)
    info["จำนวนบัตรคงเหลือ"] = int(m.group(1)) if m else None

    # Calculate ballots_used if missing
    if info["จำนวนบัตรที่ใช้"] is None:
        parts = [info["จำนวนบัตรดี"], info["จำนวนบัตรเสีย"], info["จำนวนบัตรที่ไม่เลือกผู้สมัคร"]]
        if any(p is not None for p in parts):
            info["จำนวนบัตรที่ใช้"] = sum(p or 0 for p in parts)

    return info


# ---------------------------------------------------------------------------
# Table parser - Party List Only
# ---------------------------------------------------------------------------

def clean_cell_text(text: str) -> str:
    """Clean OCR noise from table cell text."""
    if not text:
        return ""
    # Remove checkbox symbols and normalize whitespace
    text = text.replace("☑", "").replace("☐", "").replace("/", "").strip()
    text = re.sub(r"\s+", " ", text)
    # Convert Thai digits to Arabic
    text = text.translate(THAI_DIGITS)
    return text


def extract_score_from_cells(cells: list[str], start_idx: int = 1) -> Optional[int]:
    """
    Extract numeric score from table cells.
    
    Searches for the first integer in cells after start_idx.
    Ignores symbols like /, ☑, whitespace.
    
    Args:
        cells: List of cell text values
        start_idx: Start searching from this index (skip party number column)
    
    Returns:
        First integer found, or None
    """
    for i in range(start_idx, len(cells)):
        cell = cells[i]
        # Look for word-boundary integer (not part of larger number)
        m = re.search(r"\b(\d+)\b", cell)
        if m:
            return int(m.group(1))
    return None


def parse_parties_from_markdown(markdown: str, party_ref_df: pd.DataFrame) -> tuple[dict, list[dict]]:
    """
    Parse party list from markdown output.
    
    Args:
        markdown: OCR output markdown
        party_ref_df: Party reference dataframe
    """
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

    # Clean header row
    header = [clean_cell_text(td.get_text(" ", strip=True))
              for td in rows[0].find_all(["th", "td"])]

    def find_col(keywords):
        for i, h in enumerate(header):
            if any(kw in h for kw in keywords):
                return i
        return -1

    idx_num   = find_col(["หมายเลข"])
    idx_party = find_col(["พรรค", "สังกัด", "พรรคการเมือง"])
    idx_score = find_col(["คะแนน"])

    # Default column positions for party list
    if idx_num   < 0: idx_num   = 0
    if idx_party < 0: idx_party = 1
    if idx_score < 0: idx_score = 2

    parties = []
    for tr in rows[1:]:
        # Clean all cells
        cells = [clean_cell_text(td.get_text(" ", strip=True))
                 for td in tr.find_all(["td", "th"])]
        
        if len(cells) < 2:
            continue

        def get(idx):
            if idx < 0 or idx >= len(cells):
                return ""
            return cells[idx]

        num_str = get(idx_num)

        # Skip summary rows or empty rows
        if "รวม" in num_str or not num_str:
            continue

        # Extract party number
        num_match = re.search(r"\b(\d+)\b", num_str)
        ocr_num = int(num_match.group(1)) if num_match else None
        
        # Extract party name
        ocr_party_name = get(idx_party)

        # Extract score - try multiple strategies
        score = None
        
        # Strategy 1: Try the expected score column
        if idx_score >= 0 and idx_score < len(cells):
            score_match = re.search(r"\b(\d+)\b", cells[idx_score])
            if score_match:
                score = int(score_match.group(1))
        
        # Strategy 2: If no score found, search all cells after party name
        if score is None:
            score = extract_score_from_cells(cells, start_idx=max(idx_party + 1, 2))

        # Match against party reference
        resolved = match_party(ocr_num, ocr_party_name, party_ref_df)
        resolved["คะแนน"] = score

        parties.append(resolved)

    return header_info, parties


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(header_info: dict, parties: list[dict]) -> tuple[bool, list[str]]:
    """
    Run 3 validation checks. Returns (is_valid, list_of_failed_checks).
    """
    issues = []
    print(header_info)

    ballots_allocated = header_info.get("จำนวนบัตรเลือกตั้งที่ได้รับจัดสรร")
    ballots_used      = header_info.get("จำนวนบัตรที่ใช้")
    ballots_remaining = header_info.get("จำนวนบัตรคงเหลือ")
    good              = header_info.get("จำนวนบัตรดี")
    spoiled           = header_info.get("จำนวนบัตรเสีย")
    no_vote           = header_info.get("จำนวนบัตรที่ไม่เลือกผู้สมัคร")

    total_score = sum(p["คะแนน"] for p in parties if p.get("คะแนน") is not None)

    # Check 1: บัตรคงเหลือ = บัตรที่ได้รับ - บัตรที่ใช้


    # Check 3: รวมคะแนนพรรค = บัตรดี
    if good is not None and parties:
        if total_score != good:
            issues.append(
                f"check3_fail: รวมคะแนน={total_score} ≠ บัตรดี={good}"
            )
    else:
        issues.append("check3_skip: ข้อมูลไม่ครบ")

    is_valid = not any("fail" in i for i in issues)
    return is_valid, issues


# ---------------------------------------------------------------------------
# Main - Batch Processing
# ---------------------------------------------------------------------------

def process_single_image(image_path: Path, party_ref_df: pd.DataFrame) -> tuple[dict, list[dict], str]:
    """
    Process a single page/image/PDF and return raw header_info and parties.
    
    For PDF files, converts pages to images first, then OCRs each page.
    
    Returns:
        (header_info, parties, status) where status is "success", "no_data", or "error"
    """
    try:
        print(f"📄 {image_path.name}", end=" ")
        
        # Check if file is PDF
        if image_path.suffix.lower() == ".pdf":
            print("(PDF)", end=" ")
            # Convert PDF to images
            image_paths = pdf_to_images(str(image_path))
            print(f"→ {len(image_paths)} pages", end=" ")
            
            # Process each page and combine results
            all_parties = []
            combined_header = {}
            
            for page_path in image_paths:
                # OCR the converted page
                markdown = ocr_document(pdf_or_image_path=str(page_path))
                
                # Parse parties and header info
                header_info, parties = parse_parties_from_markdown(markdown, party_ref_df)
                
                # Combine header info (use first non-empty header)
                if not combined_header and header_info:
                    combined_header = header_info
                elif header_info:
                    # Merge ballot counts from multiple pages
                    for key in ["จำนวนบัตรดี", "จำนวนบัตรเสีย", "จำนวนบัตรที่ไม่เลือกผู้สมัคร"]:
                        if header_info.get(key) is not None:
                            combined_header[key] = combined_header.get(key, 0) + header_info[key]
                
                # Collect all parties
                all_parties.extend(parties)
                
                # Clean up temporary image
                page_path.unlink(missing_ok=True)
            
            # Clean up temp directory
            if image_paths:
                image_paths[0].parent.rmdir()
            
            header_info = combined_header
            parties = all_parties
        else:
            # Process regular image file
            markdown = ocr_document(pdf_or_image_path=str(image_path))
            print(markdown)
            
            # Parse parties and header info
            header_info, parties = parse_parties_from_markdown(markdown, party_ref_df)
        
        if not parties:
            print("⚠️ (no parties)")
            return header_info, [], "no_data"
        
        print(f"✅ ({len(parties)} parties)")
        return header_info, parties, "success"
        
    except Exception as e:
        print(f"❌ (ERROR: {str(e)})")
        return {}, [], "error"


def combine_into_rows(header_info: dict, parties: list[dict]) -> list[dict]:
    """Merge header_info with each party record to create final rows."""
    return [{**header_info, **p} for p in parties]


def merge_polling_station_pages(pages_data: list[tuple[dict, list[dict]]]) -> tuple[dict, list[dict]]:
    """
    Merge header_info and parties from multiple pages (ideally 3) of a polling station.
    
    Args:
        pages_data: List of (header_info, parties) tuples from each page
    
    Returns:
        (merged_header_info, combined_parties)
    """
    if not pages_data:
        return {}, []
    
    # Use header from first page as base
    merged_header = pages_data[0][0].copy()
    all_parties = []
    
    # Merge ballot counts from all pages (sum them)
    total_good = 0
    total_spoiled = 0
    total_no_vote = 0
    
    for header_info, parties in pages_data:
        all_parties.extend(parties)
        
        # Sum ballot counts across pages
        if header_info.get("จำนวนบัตรดี") is not None:
            total_good += header_info.get("จำนวนบัตรดี", 0)
        if header_info.get("จำนวนบัตรเสีย") is not None:
            total_spoiled += header_info.get("จำนวนบัตรเสีย", 0)
        if header_info.get("จำนวนบัตรที่ไม่เลือกผู้สมัคร") is not None:
            total_no_vote += header_info.get("จำนวนบัตรที่ไม่เลือกผู้สมัคร", 0)
    
    # Update merged header with summed ballot counts
    if total_good > 0:
        merged_header["จำนวนบัตรดี"] = total_good
    if total_spoiled > 0:
        merged_header["จำนวนบัตรเสีย"] = total_spoiled
    if total_no_vote > 0:
        merged_header["จำนวนบัตรที่ไม่เลือกผู้สมัคร"] = total_no_vote
    
    # Recalculate used ballots from components
    if total_good > 0 or total_spoiled > 0 or total_no_vote > 0:
        merged_header["จำนวนบัตรที่ใช้"] = total_good + total_spoiled + total_no_vote
    
    return merged_header, all_parties


def process_polling_station(tambon: str, unit: int, images: list[Path], party_ref_df: pd.DataFrame) -> tuple[list[dict], dict]:
    """
    Process all pages for one polling station.
    
    Args:
        tambon: ตำบล name (from top-level folder)
        unit: หน่วยเลือกตั้งที่ number (sequentially assigned)
        images: List of image paths for this polling station
        party_ref_df: Party reference dataframe
    
    Returns:
        (rows, status_dict) where status_dict tracks success/no_data/error/incomplete
    """
    status_dict = {"success": 0, "no_data": 0, "error": 0, "incomplete": 0}
    
    print(f"\n    Processing {len(images)} pages...")
    
    # Process each page
    pages_data = []
    for image_path in images:
        header_info, parties, status = process_single_image(image_path, party_ref_df)
        status_dict[status] += 1
        
        if status == "success":
            pages_data.append((header_info, parties))
    
    # Check if we have all 3 pages
    if len(pages_data) < 3:
        print(f"    ⚠️  INCOMPLETE: Only {len(pages_data)}/3 pages found")
        status_dict["incomplete"] = 1
        
        # Create incomplete record using directly passed parameters
        incomplete_header = {
            "จังหวัด": "นครศรีธรรมราช",  # Default from config
            "เขตเลือกตั้งที่": 2,  # Default from config
            "ตำบล": tambon,
            "หน่วยเลือกตั้งที่": unit,
            "source_file": f"{len(images)}/3 pages",
            "needs_review": "YES",
            "validation_notes": "incomplete_polling_station",
        }
        
        # Combine with any parties we found
        all_parties = []
        for _, parties in pages_data:
            all_parties.extend(parties)
        
        if all_parties:
            rows = combine_into_rows(incomplete_header, all_parties)
        else:
            rows = [incomplete_header]
        
        return rows, status_dict
    
    # Merge all 3 pages
    merged_header, all_parties = merge_polling_station_pages(pages_data)
    
    # Use directly passed parameters instead of parsing from path
    merged_header["ตำบล"] = tambon
    merged_header["หน่วยเลือกตั้งที่"] = unit
    
    # Set defaults for required fields if not extracted from OCR
    merged_header.setdefault("จังหวัด", "นครศรีธรรมราช")
    merged_header.setdefault("เขตเลือกตั้งที่", 2)
    
    merged_header["source_file"] = f"{len(images)}/3 pages"
    
    # Validate on merged data
    is_valid, issues = validate(merged_header, all_parties)
    
    merged_header["needs_review"] = "YES" if not is_valid else "NO"
    merged_header["validation_notes"] = " | ".join(issues) if issues else ""
    
    if is_valid:
        print(f"    ✅ Passed validation")
    else:
        print(f"    ❌ Needs review")
        for issue in issues:
            print(f"       - {issue}")
    
    # Combine header with all parties
    rows = combine_into_rows(merged_header, all_parties)
    
    return rows, status_dict


def save_tambon_csv(tambon: str, rows: list[dict], output_dir: Path) -> None:
    """Save CSV file for a single ตำบล."""
    if not rows:
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
    party_fields = ["หมายเลข", "พรรคการเมือง", "คะแนน", "match_method", "match_score"]
    fieldnames = meta_fields + party_fields
    
    # Create safe filename from ตำบล name
    safe_tambon = re.sub(r'[\\/:*?"<>|]', "-", tambon).replace(" ", "_")
    csv_file = output_dir / f"{safe_tambon}.csv"
    
    # Write CSV
    with open(csv_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main():
    """
    Batch process party-list election documents with PDF-based sequential page processing.
    
    1. Scan directory for tambon folders and PDFs in 'บช' subfolders
    2. Treat each PDF as sequential page stream
    3. Group pages: every 3 consecutive pages = 1 polling station
    4. Assign sequential polling station IDs (1, 2, 3, ...)
    5. Process each ตำบล incrementally and save CSV immediately
    6. Clear memory after each ตำบล is saved
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Batch OCR processor for party-list election documents")
    parser.add_argument("--root", default="data/lost", help="Root directory to scan")
    parser.add_argument("--output", default="output_raw_party_list", help="Output directory")
    args = parser.parse_args()
    
    root_dir = Path(SCRIPT_DIR) / args.root
    output_dir = Path(SCRIPT_DIR) / args.output
    
    # Check API key
    api_key = os.getenv("TYPHOON_OCR_API_KEY", "")
    if not api_key:
        print("❌ ไม่พบ TYPHOON_OCR_API_KEY ใน .env")
        sys.exit(1)
    os.environ["TYPHOON_OCR_API_KEY"] = api_key
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load party reference
    party_ref_df = load_party_reference(PARTY_REF_PATH)
    print(f"📋 Loaded {len(party_ref_df)} parties from reference\n")
    
    # Discover tambon folders and their PDFs
    print(f"🔍 Scanning {root_dir} for tambon folders and party-list PDFs...\n")
    
    tambon_pdfs = discover_tambon_pdfs(root_dir)
    
    total_pdfs = sum(len(pdfs) for pdfs in tambon_pdfs.values())
    print(f"📊 Found {len(tambon_pdfs)} tambon folders with {total_pdfs} PDFs\n")
    
    if not tambon_pdfs:
        print("⚠️  No tambon folders with PDFs found. Check that:")
        print("   - Directory structure has tambon folders (e.g., 'ตำบลคลองกระบือ')")
        print("   - Each tambon has 'บช' subfolders")
        print("   - 'บช' folders contain PDF files")
        sys.exit(0)
    
    print("=" * 80)
    
    # Global statistics
    global_stats = {"success": 0, "no_data": 0, "error": 0, "incomplete": 0}
    total_rows = 0
    
    # Process each tambon incrementally
    sorted_tambons = sorted(tambon_pdfs.keys(), key=lambda x: (x is None, x or ""))
    for tambon_idx, tambon in enumerate(sorted_tambons, 1):
        print(f"\n[ตำบล {tambon_idx}/{len(tambon_pdfs)}] {tambon}")
        
        pdfs_in_tambon = tambon_pdfs[tambon]
        print(f"  📄 Found {len(pdfs_in_tambon)} PDF(s) in this tambon")
        
        tambon_rows = []
        tambon_stats = {"success": 0, "no_data": 0, "error": 0, "incomplete": 0}
        
        # Process each PDF in this tambon
        sequential_station_id = 1  # Start from 1 for each tambon
        for pdf_idx, pdf_path in enumerate(pdfs_in_tambon, 1):
            print(f"    [PDF {pdf_idx}/{len(pdfs_in_tambon)}] {pdf_path.name}")
            
            # Convert PDF to images and group by polling station
            try:
                polling_stations = group_pdf_pages_by_polling_station(pdf_path)
                print(f"      📝 Converted to {len(polling_stations)} polling stations")
            except Exception as e:
                print(f"      ❌ ERROR converting PDF: {str(e)}")
                tambon_stats["error"] += 1
                continue
            
            # Process each polling station (3 pages each)
            for station_idx, station_pages in enumerate(polling_stations, 1):
                actual_station_id = sequential_station_id
                sequential_station_id += 1
                
                print(f"      [หน่วยเลือกตั้งที่ {actual_station_id}] {len(station_pages)} pages")
                
                # Process this polling station
                rows, status_dict = process_polling_station(tambon, actual_station_id, station_pages, party_ref_df)
                
                # Update statistics
                for key in ["success", "no_data", "error", "incomplete"]:
                    tambon_stats[key] += status_dict.get(key, 0)
                    global_stats[key] += status_dict.get(key, 0)
                
                # Add rows to tambon buffer
                if rows:
                    tambon_rows.extend(rows)
                    
                    needs_review_count = sum(1 for r in rows if r.get("needs_review") == "YES")
                    
                    print(f"        📊 {len(rows)} rows | ⚠️  {needs_review_count} need review")
                    print(f"        ✅ Status: {status_dict}")
                else:
                    print(f"        ⚠️  No data extracted")
        
        # Save CSV immediately after finishing this tambon
        if tambon_rows:
            csv_path = output_dir / f"{re.sub(r'[\\/:*?\"<>|]', '-', tambon).replace(' ', '_')}.csv"
            save_tambon_csv(tambon, tambon_rows, output_dir)
            
            needs_review_count = sum(1 for r in tambon_rows if r.get("needs_review") == "YES")
            
            print(f"\n  ✅ SAVED: {csv_path}")
            print(f"     📊 {len(tambon_rows)} rows | ⚠️  {needs_review_count} need review")
            print(f"     📋 Status: {tambon_stats}")
            
            total_rows += len(tambon_rows)
        else:
            print(f"\n  ⚠️  No data for {tambon} - CSV not created")
        
        # Clear memory for this tambon
        tambon_rows.clear()
        del tambon_rows
        
        print(f"  🧹 Memory cleared for {tambon}")
    
    # Print final summary
    print("\n" + "=" * 80)
    print(f"\n📊 FINAL PROCESSING SUMMARY:")
    print(f"   � Tambon processed:      {len(tambon_pdfs)}")
    print(f"   � Total PDFs:           {total_pdfs}")
    print(f"   ✅ Success: {global_stats['success']}")
    print(f"   ⚠️  No data: {global_stats['no_data']}")
    print(f"   ❌ Errors: {global_stats['error']}")
    print(f"   📋 Incomplete: {global_stats['incomplete']}")
    print(f"   📊 Total rows:          {total_rows}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
