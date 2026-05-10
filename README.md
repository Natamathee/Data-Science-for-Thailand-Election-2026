# Thai Election Data Science Project

## Overview

This project processes Thai election documents using OCR (Optical Character Recognition) to extract structured data from scanned PDFs and images. It focuses on party-list election documents (บช) and constituency election data.

## Project Structure

```
Data-Science-for-Thailand-Election-2026/
├── data/                          # Raw input data
│   ├── raw_pdf/                   # Scanned PDF documents
│   └── raw_jpg/                   # Scanned image documents
├── reference/                     # Reference data files
│   ├── party_list.csv            # Party reference data
│   └── candidates_ref.csv        # Candidate reference data
├── output_raw_party_list/        # OCR output for party-list data
├── merge_csv.py                   # Merge CSV files from folder
├── ocr_partylist.py              # OCR worker for party-list documents
└── requirements.txt               # Python dependencies
```

## Setup

### Prerequisites

- Python 3.8+
- Typhoon OCR API key

### Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
cp .env_example .env
# Edit .env and add your TYPHOON_OCR_API_KEY
```

### Typhoon OCR Setup

See `reference/README.md` for detailed OCR setup instructions.

## Workflow

### Party-List Document Processing

The OCR worker processes party-list election documents with the following workflow:

```
┌─────────────────────────────────────────────────────────┐
│                    INPUT                                  │
│  • PDF files in tambon folders containing "บช"          │
│  • Each PDF contains multiple polling stations          │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│              PDF PROCESSING                              │
│  • Convert PDF to images (300 DPI)                       │
│  • Group pages: 3 consecutive pages = 1 polling station│
│  • Assign sequential polling station IDs (1, 2, 3...)   │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│              OCR EXTRACTION                              │
│  • Send images to Typhoon OCR API                        │
│  • Extract table data and header information              │
│  • Parse Thai numerals and text                          │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│              DATA PARSING                                │
│  • Extract header info (ballot counts, location)         │
│  • Parse party table (number, name, score)                │
│  • Match party names with reference data                 │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│              VALIDATION                                  │
│  • Check ballot allocation math                          │
│  • Verify vote totals match good ballots                 │
│  • Flag records needing review                           │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│              OUTPUT                                      │
│  • Save CSV per tambon (incremental)                     │
│  • Column order: Thai election schema                    │
│  • UTF-8 encoding with BOM                               │
└─────────────────────────────────────────────────────────┘
```

## Key Features

### PDF-Based Sequential Page Processing

- **Treats PDF as sequential page stream**: Each PDF contains multiple polling stations mixed together
- **3-page grouping**: Every 3 consecutive pages = 1 polling station
- **Sequential IDs**: Assigns polling station IDs sequentially (1, 2, 3...)
- **Tambon from folder**: Uses top-level folder name for tambon identification
- **No folder name inference**: Page order is the single source of truth

### Data Validation

- **Ballot Allocation Check**: บัตรคงเหลือ = บัตรที่ได้รับ - บัตรที่ใช้
- **Ballot Breakdown Check**: บัตรดี + บัตรเสีย + ไม่เลือก = บัตรที่ใช้
- **Vote Accuracy Check**: รวมคะแนน = บัตรดี
- **Review Flags**: Marks records needing manual review

### Party Matching

- **Reference matching**: Uses party_list.csv for fuzzy name matching
- **Match scoring**: Provides match_method and match_score
- **Thai character support**: Handles Thai numerals and text

## Usage

### Process Party-List Documents

```bash
python ocr_partylist.py --root data/raw_pdf --output output_raw_party_list
```

Arguments:
- `--root`: Input directory (default: `data/raw_pdf`)
- `--output`: Output directory (default: `output_raw_party_list`)

### Merge CSV Files

```bash
python merge_csv.py --input output_raw_party_list --output merged_output.csv
```

Arguments:
- `--input`: Input folder containing CSV files (default: `output_raw_party_list`)
- `--output`: Output merged CSV file (default: `merged_output.csv`)

## Output Schema

### Column Order

The merged CSV uses this specific column order:

1. จังหวัด (Province)
2. เขตเลือกตั้งที่ (Constituency Number)
3. ตำบล (Subdistrict)
4. อำเภอ (District)
5. หน่วยเลือกตั้งที่ (Polling Station Number)
6. หมู่ที่ (Village Number)
7. จำนวนผู้มีสิทธิเลือกตั้ง (Eligible Voters)
8. จำนวนผู้มาแสดงตน (Voters Who Showed Up)
9. จำนวนบัตรที่ได้รับจัดสรร (Ballots Allocated)
10. จำนวนบัตรที่ใช้ (Ballots Used)
11. จำนวนบัตรดี (Good Ballots)
12. จำนวนบัตรเสีย (Spoiled Ballots)
13. จำนวนบัตรที่ไม่เลือกผู้สมัคร (No-Vote Ballots)
14. จำนวนบัตรคงเหลือ (Remaining Ballots)
15. source_file (Source File Name)
16. needs_review (Review Flag)
17. validation_notes (Validation Issues)
18. หมายเลข (Party Number)
19. พรรคการเมือง (Party Name)
20. คะแนน (Score)
21. match_method (Matching Method)
22. match_score (Match Score)

## Directory Structure for Processing

### Input Structure

```
data/raw_pdf/
├── ตำบลคลองกระบือ/
│   └── บช/
│       └── election_data.pdf
├── ตำบลกำแพงเซา/
│   └── บช/
│       └── election_data.pdf
└── ...
```

**Rules:**
- Tambon folders must start with "ตำบล"
- Party-list data must be in subfolders containing "บช"
- Each PDF contains multiple polling stations
- Page order determines polling station grouping

### Output Structure

```
output_raw_party_list/
├── ตำบลคลองกระบือ.csv
├── ตำบลกำแพงเซา.csv
└── ...
```

- One CSV per tambon
- Incremental saving (memory efficient)
- UTF-8 with BOM encoding

## Dependencies

```
pandas
typhoon-ocr
rapidfuzz
PyMuPDF (fitz)
python-dotenv
```

## Troubleshooting

### OCR Quality Issues

If OCR results are poor:
- Ensure PDF resolution is at least 300 DPI
- Check image quality and clarity
- Verify Thai text is properly formatted
- Review Typhoon OCR API key is valid

### Matching Issues

If party matching fails:
- Check reference/party_list.csv format
- Verify Thai character encoding (UTF-8)
- Ensure party names match OCR output format
- Review match scores in output CSV

### Validation Failures

If validation checks fail:
- Review validation_notes column in output
- Check ballot arithmetic
- Verify vote totals
- Manually review flagged records

## Reference Files

- `reference/README.md` - Detailed reference data setup
- `reference/party_list.csv` - Party reference data
- `reference/candidates_ref.csv` - Candidate reference data

## License

This project is for Thai election data processing and analysis.
