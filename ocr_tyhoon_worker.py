import pandas as pd
import time, random, re, argparse, base64, json, os, requests
from pathlib import Path
from dotenv import load_dotenv
import numpy as np

load_dotenv()

TYPHOON_API_KEY = os.getenv("TYPHOON_OCR_API_KEY")
TYPHOON_API_URL = "https://api.opentyphoon.ai/v1/chat/completions"
EXTRACT_RULES = """
- Output: valid JSON array only. No markdown, no explanation.
- Extract ONLY rows inside the table. Ignore all other text.
- If no clear table exists → return []
- Preserve Thai text exactly
- Convert Thai numerals to Arabic (๑๒๓ → 123)
- Use "" for missing values
- Output MUST start with [ and end with ]
"""

PROMPTS = {
    "constituency": """
Extract the candidate result table from the text below.

Each row → one JSON object:
{"จังหวัด": "...", "เขต": "...", "หมายเลข": "...", "ชื่อผู้สมัคร": "...", "พรรค": "...", "คะแนน": "..."}

Rules:
""" + EXTRACT_RULES,

    "party_list": """
Extract the party result table from the text below.

Each row → one JSON object:
{"จังหวัด": "...", "เขต": "...", "หมายเลข": "...", "พรรค": "...", "คะแนน": "..."}

Rules:
""" + EXTRACT_RULES,
}
# ---- Helpers ----
THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")


import requests
import json
import time
import random
model = "typhoon-ocr"
def call_typhoon_ocr(image_path, api_key, task_type, max_tokens=16384,
                     temperature=0.1, top_p=0.6, repetition_penalty=1.2,
                     pages=None, retries=5):

    url = "https://api.opentyphoon.ai/v1/ocr"


    for attempt in range(retries):
        try:

            with open(image_path, "rb") as file:
                files = {"file": file}

                data = {
                    "model": model,
                    "task_type": task_type,
                    "max_tokens": str(max_tokens),
                    "temperature": str(temperature),
                    "top_p": str(top_p),
                    "repetition_penalty": str(repetition_penalty)
                }

                if pages:
                    data["pages"] = json.dumps(pages)

                headers = {
                    "Authorization": f"Bearer {api_key}"
                }
                response = requests.post(
                    url,
                    files=files,
                    data=data,
                    headers=headers,
                    timeout=120
                )

            if response.status_code == 200:
                result = response.json()
                print(result)
                extracted_pages = []

                for page_result in result.get("results", []):

                    if page_result.get("success") and page_result.get("message"):

                        content = page_result["message"]["choices"][0]["message"]["content"]
                        content = extract_table_only(content, task_type)
                        # debug
                        print("\n=== RAW RESPONSE ===\n", content[:], "\n===")

                        extracted_pages.append(content)

                    else:
                        print("page error:", page_result.get("error"))

                return "\n".join(extracted_pages)

            elif response.status_code == 429:
                wait = 2 ** attempt + random.uniform(0, 1)
                print(f"rate limit → wait {wait:.1f}s")
                time.sleep(wait)

            else:
                print("Typhoon error:", response.status_code, response.text[:200])
                return ""

        except Exception as e:
            wait = 2 ** attempt + random.uniform(0, 1)
            print(f"exception: {e} → retry {wait:.1f}s")
            time.sleep(wait)

    return ""

def extract_table_only(text, doc_type):
    """Extract table content based on doc_type using relevant header keywords."""
    
    # Define header keywords for each document type
    header_keywords = {
        "constituency": ["หมายเลขประจำตัว ผู้สมัคร", "ผู้สมัครรับเลือกตั้ง", "พรรคการเมือง", "คะแนน"],
        "party_list": ["หมายเลข", "พรรคการเมือง", "คะแนน"]
    }
    
    keywords = header_keywords.get(doc_type, [])
    
    # case 1: real HTML table
    match = re.search(r"<table.*?>.*?</table>", text, re.DOTALL)
    if match:
        return match.group(0)

    # case 2: fallback → detect table-like block using doc_type specific keywords
    lines = text.split("\n")
    table_lines = []
    in_table = False

    for line in lines:
        if any(kw in line for kw in keywords):
            in_table = True

        if in_table:
            table_lines.append(line)

        # stop when narrative ends (optional heuristic)
        if in_table and line.strip() == "":
            break

    return "\n".join(table_lines)

def process_folder(row: pd.Series, output_dir: Path):
    doc_type = row["doc_type"]

    if doc_type == "referendum":
        print(f"  [skip referendum] {row['doc_folder']}")
        return
    if doc_type not in PROMPTS:
        print(f"  [skip unknown] {row['doc_folder']}")
        return

    folder   = Path(row["path"])
    safe     = re.sub(r'[\\/:*?"<>|]', "-",
                   f"{row['tambon']}__{row['unit']}__{row['doc_folder']}"
               ).replace(" ", "_")
    type_dir = output_dir / doc_type
    type_dir.mkdir(exist_ok=True)
    out_csv  = type_dir / f"{safe}.csv"

    if out_csv.exists():
        print(f"  [skip done] {safe}")
        return

    jpgs = sorted(folder.glob("*.jpg")) + sorted(folder.glob("*.jpeg"))
    if not jpgs:
        print(f"  [warn] ไม่มี JPG ใน {folder}")
        return

    print(f"  [start] {safe} | {doc_type} | {len(jpgs)} pages")

    all_dfs = []
    for i, jpg in enumerate(jpgs, 1):
        print(f"    {i}/{len(jpgs)} {jpg.name}")
        # Call Typhoon OCR with correct parameters
        json_text = call_typhoon_ocr(str(jpg), TYPHOON_API_KEY, doc_type)
        # Clean up JSON array
        df= table_html_to_df(json_text)
        
        if df.empty:
            print(f"    [warn] empty dataframe from OCR")
            continue
        
        meta = {
            "ตำบล":              row["tambon"],
            "หน่วยเลือกตั้ง":    row["unit"],
            "ประเภทของเอกสาร":   doc_type,
            "ประเภทการเลือกตั้ง": row.get("voted_type", ""),
            "แหล่งที่มา":         row["path"],
        }
        for k, v in meta.items():
            df[k] = v
        
        # df = json_to_df(json_text, doc_type, meta)
        df.columns = df.columns.str.replace("\n", "").str.strip()
        # df = df.rename(columns={"ได้คะแนน(ให้กรอกทั้งตัวเลขและตัวอักษร)": "คะแนน"})
        
        # # Check if คะแนน column exists, if not try to find it
        # if "คะแนน" not in df.columns:
        #     # Try alternative column names for score
        #     score_cols = [col for col in df.columns if "คะแนน" in col or "score" in col.lower()]
        #     if score_cols:
        #         print(f"    [warn] renaming {score_cols[0]} → คะแนน")
        #         df = df.rename(columns={score_cols[0]: "คะแนน"})
        #     else:
        #         print(f"    [warn] no score column found. Available: {list(df.columns)}")
        #         continue

        df["ได้คะแนน(ให้กรอกทั้งตัวเลขและตัวอักษร)"] = df["ได้คะแนน(ให้กรอกทั้งตัวเลขและตัวอักษร)"].apply(clean_score)
        if not df.empty:
            all_dfs.append(df)
        time.sleep(1.5)

    if all_dfs:
        result = pd.concat(all_dfs, ignore_index=True)
        result.to_csv(out_csv, index=False, encoding="utf-8-sig")
        print(f"  [done] {len(result)} rows → {out_csv.name}")
    else:
        print(f"  [warn] no data — {safe}")
        with open("logs/failed.txt", "a", encoding="utf-8") as f:
            f.write(str(folder) + "\n")

import pandas as pd
from bs4 import BeautifulSoup
import re

def thai_to_arabic(text):
    """Convert Thai numerals to Arabic numerals"""
    thai_digits = "๐๑๒๓๔๕๖๗๘๙"
    arabic_digits = "0123456789"
    trans = str.maketrans(thai_digits, arabic_digits)
    return str(text).translate(trans)

def clean_cell(text):
    """Clean OCR noise inside cell"""
    if text is None:
        return ""
    text = text.replace("\n", " ").strip()
    text = thai_to_arabic(text)

    # remove checkbox symbols
    text = text.replace("☑", "").replace("☐", "").strip()

    # normalize spaces
    text = re.sub(r"\s+", " ", text)
    return text
def clean_score(x):
    if x is None:
        return np.nan

    x = str(x).strip()

    # O → 0
    if x == "O":
        return 0

    # extract numeric only
    match = re.search(r"\d+", x)
    if match:
        return int(match.group())

    return np.nan
def table_html_to_df(html):
    """
    Convert HTML table (OCR output) → pandas DataFrame
    """

    soup = BeautifulSoup(html, "html.parser")

    rows = []
    for tr in soup.find_all("tr"):
        cols = []
        for cell in tr.find_all(["td", "th"]):
            cols.append(clean_cell(cell.get_text()))
        if cols:
            rows.append(cols)

    if not rows:
        return pd.DataFrame()

    # detect header row
    header = rows[0]
    data = rows[1:]

    # remove footer rows (e.g. "รวมคะแนน")
    cleaned_data = []
    for r in data:
        if len(r) < 2:
            continue
        if "รวม" in r[0]:
            continue
        cleaned_data.append(r)

    # normalize row length
    max_len = max(len(r) for r in cleaned_data + [header])
    header = header + [""] * (max_len - len(header))

    normalized = []
    for r in cleaned_data:
        r = r + [""] * (max_len - len(r))
        normalized.append(r)

    df = pd.DataFrame(normalized, columns=header)

    return df
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--doc_type", default="all",
                        choices=["all", "constituency", "party_list"])
    parser.add_argument("--manifest", default="file_manifest.csv")
    parser.add_argument("--output",   default="output_raw")
    args = parser.parse_args()

    Path("logs").mkdir(exist_ok=True)
    out = Path(args.output)
    out.mkdir(exist_ok=True)

    manifest = pd.read_csv(args.manifest)
    manifest = manifest[manifest["doc_type"].isin(["constituency", "party_list"])]
    if args.doc_type != "all":
        manifest = manifest[manifest["doc_type"] == args.doc_type]

    print(f"Processing {len(manifest)} folders  [doc_type={args.doc_type}]")
    print(manifest.groupby("doc_type")["path"].count())
    print()

    for _, row in manifest.iterrows():
        process_folder(row, out)