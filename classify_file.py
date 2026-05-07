# classify_files.py
import os
import re
import pandas as pd
from pathlib import Path

ROOT = Path("/Users/chavaponsuu/Downloads/Data-Science-for-Thailand-Election-2026/data/test")

def classify_folder(folder_name: str) -> str:
    name = folder_name.strip()

    if re.search(r"อ\.ส\.", name):
        return "referendum"

    elif re.search(r"ส\.ส\.", name) and (
        "(บช)" in name or "(บัญชีรายชื่อ" in name
    ):
        return "party_list"

    elif re.search(r"ส\.ส\.", name):
        return "constituency"

    else:
        return "unknown"

def classify_form_type(folder_name: str) -> str:
    """Classify election form type (5.17, 5.18, or unknown).
    
    Supports multiple naming variations:
    - 5.17, 5-17, 5_17
    - ส.ส.5.17, ส.ส.5-17, ส.ส.5_17
    - สส 5.17, สส 5-17, สส 5_17
    """
    name = folder_name.strip()
    
    # Match 5.17 patterns: 5.17, 5-17, 5_17, ส.ส.5.17, ส.ส.5-17, ส.ส.5_17, สส 5.17, etc.
    if re.search(r"(?:ส\.ส\.|สส\s+)?5[.\-_]17", name):
        return "5.17"
    
    # Match 5.18 patterns
    elif re.search(r"(?:ส\.ส\.|สส\s+)?5[.\-_]18", name):
        return "5.18"
    
    else:
        return "unknown"

def get_files(folder: Path):
    """คืน list ของ JPG + PDF ในโฟลเดอร์นั้น"""
    jpgs = sorted(folder.glob("*.jpg")) + sorted(folder.glob("*.jpeg"))
    pdfs = sorted(folder.glob("*.pdf"))
    return jpgs, pdfs

records = []

for dirpath, dirnames, filenames in os.walk(ROOT):
    p = Path(dirpath)
    jpgs, pdfs = get_files(p)
    
    # leaf folder = มีไฟล์ภาพหรือ PDF และไม่มี subfolder
    has_content = (jpgs or pdfs) and not dirnames
    if not has_content:
        continue

    parts = p.relative_to(ROOT).parts
    print(parts)
    tambon     = parts[0] if len(parts) > 0 else ""
    unit       = parts[1] if len(parts) > 1 else ""
    doc_folder = parts[-1]
    doc_type   = classify_folder(doc_folder)
    voted_type  = classify_form_type(doc_folder)

    records.append({
        "path":       str(p),
        "tambon":     tambon,
        "unit":       unit,
        "doc_folder": doc_folder,
        "doc_type":   doc_type,
        "voted_type":  voted_type,
        "n_jpg":      len(jpgs),
        "n_pdf":      len(pdfs),
    })

df = pd.DataFrame(records)

print("=== สรุปประเภท ===")
print(df.groupby("doc_type")[["n_jpg", "n_pdf"]].sum())
print(f"\nTotal folders: {len(df)}")

print("\n=== unknown (ต้องแก้ classify_folder) ===")
print(df[df["doc_type"] == "unknown"][["tambon", "unit", "doc_folder"]])

print("\n=== Form Type Cross-tabulation (doc_type vs voted_type) ===")
print(pd.crosstab(df["doc_type"], df["voted_type"]))

df.to_csv("test_manifest.csv", index=False, encoding="utf-8-sig")
print("\nบันทึก file_manifest.csv แล้ว — ตรวจ unknown ก่อนรัน OCR")