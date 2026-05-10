#!/usr/bin/env python3
"""
Merge multiple CSV files from a folder into a single CSV file.
"""

import os
import csv
import argparse
from pathlib import Path
from typing import List


def merge_csv_files(input_folder: str, output_file: str) -> None:
    """
    Merge all CSV files from input_folder into a single output_file.
    
    Args:
        input_folder: Path to folder containing CSV files
        output_file: Path to output merged CSV file
    """
    input_path = Path(input_folder)
    output_path = Path(output_file)
    
    if not input_path.exists():
        print(f"❌ Input folder does not exist: {input_folder}")
        return
    
    # Find all CSV files
    csv_files = sorted(input_path.glob("*.csv"))
    
    if not csv_files:
        print(f"⚠️  No CSV files found in {input_folder}")
        return
    
    print(f"📊 Found {len(csv_files)} CSV files to merge")
    
    # Collect all rows and determine all columns
    all_rows = []
    all_columns = set()
    source_files = {}
    
    for csv_file in csv_files:
        print(f"📄 Reading: {csv_file.name}")
        
        try:
            with open(csv_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                
                # Track columns from this file
                if reader.fieldnames:
                    all_columns.update(reader.fieldnames)
                
                # Read rows and add source file info
                for row in reader:
                    row['_source_file'] = csv_file.name
                    all_rows.append(row)
                    source_files[csv_file.name] = source_files.get(csv_file.name, 0) + 1
                    
        except Exception as e:
            print(f"   ❌ Error reading {csv_file.name}: {str(e)}")
            continue
    
    if not all_rows:
        print("⚠️  No data found in CSV files")
        return
    
    # Use specific column order for Thai election data
    column_order = [
        "จังหวัด", "เขตเลือกตั้งที่", "ตำบล", "อำเภอ",
        "หน่วยเลือกตั้งที่", "หมู่ที่",
        "จำนวนผู้มีสิทธิเลือกตั้ง", "จำนวนผู้มาแสดงตน",
        "จำนวนบัตรที่ได้รับจัดสรร", "จำนวนบัตรที่ใช้",
        "จำนวนบัตรดี", "จำนวนบัตรเสีย",
        "จำนวนบัตรที่ไม่เลือกผู้สมัคร", "จำนวนบัตรคงเหลือ",
        "source_file", "needs_review", "validation_notes",
        "หมายเลข", "พรรคการเมือง", "คะแนน", "match_method", "match_score"
    ]
    
    # Add any additional columns that aren't in the standard order
    sorted_columns = []
    for col in column_order:
        if col in all_columns:
            sorted_columns.append(col)
    
    # Add any remaining columns not in the standard order
    for col in sorted(all_columns):
        if col not in sorted_columns:
            sorted_columns.append(col)
    
    print(f"📋 Total columns: {len(sorted_columns)}")
    print(f"📝 Total rows: {len(all_rows)}")
    print(f"\n📊 Files processed:")
    for filename, count in sorted(source_files.items()):
        print(f"   - {filename}: {count} rows")
    
    # Write merged CSV
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=sorted_columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(all_rows)
    
    print(f"\n✅ Merged CSV saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Merge CSV files from a folder")
    parser.add_argument("--input", default="clean", help="Input folder containing CSV files")
    parser.add_argument("--output", default="party_list.csv", help="Output merged CSV file")
    args = parser.parse_args()
    
    merge_csv_files(args.input, args.output)


if __name__ == "__main__":
    main()
