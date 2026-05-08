"""
Rename ส.ส.5.18 variant folders:
  → 5.18          (แบ่งเขต)
  → 5.18 บช       (บัญชีรายชื่อ / บช)
"""
import re
from pathlib import Path


from typing import Optional

def classify(name: str) -> Optional[str]:
    """Return '5.18' or '5.18 บช' based on folder name, or None if not a target."""
    # Normalize: strip whitespace
    n = name.strip()

    # บช / บัญชีรายชื่อ patterns
    if re.search(r"บช|บัญชีรายชื่อ", n):
        return "5.18 บช"

    # แบ่งเขต or plain ส.ส.5.18 (with optional spaces/dots)
    if re.search(r"ส\.?ส\.?\s*5\.18|แบ่งเขต", n):
        return "5.18"

    return None


def rename_all(root: str = "data/raw_jpg", dry_run: bool = False):
    root_path = Path(root)
    renamed = 0
    skipped = 0

    # Collect all target dirs first (avoid modifying while iterating)
    targets = []
    for d in sorted(root_path.rglob("*")):
        if not d.is_dir():
            continue
        new_name = classify(d.name)
        if new_name and d.name != new_name:
            targets.append((d, new_name))

    for old_path, new_name in targets:
        new_path = old_path.parent / new_name

        if new_path.exists():
            print(f"  [skip] already exists: {new_path}")
            skipped += 1
            continue

        print(f"  {'[dry]' if dry_run else '[rename]'} {old_path}  →  {new_path}")
        if not dry_run:
            old_path.rename(new_path)
        renamed += 1

    print(f"\nDone: {renamed} renamed, {skipped} skipped")


if __name__ == "__main__":
    import sys
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("=== DRY RUN (no changes) ===\n")
    rename_all(dry_run=dry_run)
