# Reference Data Directory

## Purpose
This directory contains reference data files used for matching and validating OCR results.

## Required File: candidates_ref.csv

### Format
```csv
หมายเลข,ชื่อสกุล,พรรค
1,นามสกุล ก,พรรคก
2,นามสกุล ข,พรรคข
3,นามสกุล ค,พรรคค
```

### Column Descriptions

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| หมายเลข | Integer | Candidate number (unique identifier) | 1, 2, 3 |
| ชื่อสกุล | String | Candidate surname or full name | "สมชาย ใจดี" |
| พรรค | String | Political party name | "พรรคเพื่อไทย" |

### Data Requirements

1. **หมายเลข (Number)**
   - Must be unique
   - Must be integer
   - Should match official candidate numbers
   - Used as primary matching key

2. **ชื่อสกุล (Name)**
   - Can be surname only or full name
   - Used for fuzzy matching when number fails
   - Should match format in election documents
   - Thai characters only

3. **พรรค (Party)**
   - Official party name
   - Used to fill missing OCR data
   - Should be consistent across all candidates
   - Thai characters only

### Creating Your Reference File

**Step 1:** Copy the template
```bash
cp candidates_ref_TEMPLATE.csv candidates_ref.csv
```

**Step 2:** Edit with your actual candidate data
```bash
# Use any text editor or spreadsheet software
# Make sure to save as UTF-8 CSV
```

**Step 3:** Validate the file
```python
import pandas as pd

# Load and check
df = pd.read_csv('reference/candidates_ref.csv')
print(f"Loaded {len(df)} candidates")
print(df.head())

# Check for duplicates
duplicates = df[df.duplicated('หมายเลข')]
if not duplicates.empty:
    print("WARNING: Duplicate numbers found!")
    print(duplicates)
```

### Data Sources

Candidate reference data can be obtained from:
1. Official Election Commission (ECT) candidate lists
2. Party registration documents
3. Previous election records
4. Official announcement documents

### Updating Reference Data

When you discover corrections during manual review:

1. **Update the CSV file**
   ```csv
   # Add new candidates or fix existing ones
   ```

2. **Delete affected output files**
   ```bash
   rm output_raw/constituency/affected_folder.csv
   ```

3. **Reprocess**
   ```bash
   python ocr_typhoon_worker.py
   ```

### Best Practices

1. **Keep it updated** - Add new candidates as discovered
2. **Use official names** - Match exactly as they appear in documents
3. **Consistent formatting** - Use same name format throughout
4. **Backup regularly** - Keep versions of the reference file
5. **Document sources** - Note where data came from

### Example: Complete Reference File

```csv
หมายเลข,ชื่อสกุล,พรรค
1,สมชาย ใจดี,พรรคเพื่อไทย
2,สมหญิง รักชาติ,พรรคประชาธิปัตย์
3,สมศักดิ์ เพื่อประชา,พรรคก้าวไกล
4,สมใจ พัฒนา,พรรคภูมิใจไทย
5,สมหวัง เจริญ,พรรคชาติไทยพัฒนา
6,สมบูรณ์ มั่นคง,พรรคเพื่อชาติ
7,สมพร สุขใจ,พรรคไทยสร้างไทย
8,สมศรี เจริญรุ่ง,พรรคพลังประชารัฐ
9,สมนึก ดีงาม,พรรคเสรีรวมไทย
10,สมคิด ก้าวหน้า,พรรคประชาชาติ
```

### Troubleshooting

**Problem:** "Reference file not found"
```bash
# Check file exists
ls -la reference/candidates_ref.csv

# Check file name (must be exact)
# Should be: candidates_ref.csv
# Not: candidates_ref_TEMPLATE.csv
```

**Problem:** "Invalid encoding"
```bash
# Convert to UTF-8
iconv -f ISO-8859-1 -t UTF-8 candidates_ref.csv > candidates_ref_utf8.csv
mv candidates_ref_utf8.csv candidates_ref.csv
```

**Problem:** "Duplicate หมายเลข"
```python
import pandas as pd
df = pd.read_csv('reference/candidates_ref.csv')
duplicates = df[df.duplicated('หมายเลข', keep=False)]
print(duplicates)
# Fix duplicates in the file
```

**Problem:** "Low match scores"
```python
# Check name format matches OCR output
import pandas as pd

ref = pd.read_csv('reference/candidates_ref.csv')
ocr = pd.read_csv('output_raw/constituency/some_file.csv')

print("Reference names:", ref['ชื่อสกุล'].head())
print("OCR names:", ocr['ชื่อสกุล'].head())
# Adjust reference names to match OCR format
```

### Template Files

- `candidates_ref_TEMPLATE.csv` - Example template (DO NOT EDIT)
- `candidates_ref.csv` - Your actual data (CREATE THIS)

### Notes

- The template file is for reference only
- Create your own `candidates_ref.csv` with actual candidate data
- The OCR worker looks for `candidates_ref.csv` (not the template)
- UTF-8 encoding is required for Thai characters
- Excel users: Save as "CSV UTF-8 (Comma delimited)"

### Support

For questions about reference data:
1. Check the main documentation: [ENHANCED_OCR_FEATURES.md](../ENHANCED_OCR_FEATURES.md)
2. Review examples in the template file
3. Validate your file format with the Python script above
