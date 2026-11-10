#!/usr/bin/env python3
"""
audit_nse_dates.py - Audit embedded trade dates vs filename dates in extracted CSVs.
Zero third-party dependencies; uses Python standard library csv and datetime.
"""
import csv
import glob
import os
from datetime import datetime

folders = {
    "cm_udiff": ("nse_data/extracted/cm_udiff/*.csv", "TradDt"),
    "fo_udiff": ("nse_data/extracted/fo_udiff/*.csv", "TradDt"),
    "cm_security_delivery": (
        "nse_data/extracted/cm_security_delivery/*.csv", "DATE1"
    ),
}

def parse_date(value):
    value = str(value).strip()
    for fmt in (
        "%Y-%m-%d",
        "%d-%b-%Y",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y%m%d",
    ):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return None

for dataset, (pattern, expected_column) in folders.items():
    print(f"\n===== {dataset} =====")
    files = sorted(glob.glob(pattern))
    checked = 0
    mismatches = 0
    errors = 0

    for path in files:
        filename_date = os.path.basename(path)[:8]
        try:
            requested = datetime.strptime(filename_date, "%Y%m%d").date()
        except ValueError:
            continue

        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if not header:
                    errors += 1
                    continue
                header = [c.replace("\ufeff", "").strip().upper() for c in header]
                try:
                    col_idx = header.index(expected_column.upper())
                except ValueError:
                    errors += 1
                    print(f"HEADER ERROR: {os.path.basename(path)}")
                    continue

                dates = set()
                # Inspect dates across rows (first 100 rows is sufficient to check date consistency)
                row_count = 0
                for row in reader:
                    if len(row) > col_idx:
                        val = row[col_idx].strip()
                        if val:
                            dates.add(val)
                    row_count += 1
                    if row_count >= 100:
                        break

                parsed_dates = {parse_date(v) for v in dates}
                parsed_dates.discard(None)
                checked += 1

                if len(parsed_dates) != 1:
                    mismatches += 1
                    print(f"DATE CHECK: {os.path.basename(path)} | values={list(dates)[:5]}")
                    continue

                actual = next(iter(parsed_dates))
                if actual != requested:
                    mismatches += 1
                    # Expected for delivery files where non-trading dates return previous trading day
                    if dataset != "cm_security_delivery":
                        print(f"MISMATCH: {os.path.basename(path)} | embedded={actual}")

        except Exception as e:
            errors += 1
            print(f"ERROR: {path} | {e}")

    print(f"Files found: {len(files)}")
    print(f"Files checked: {checked}")
    print(f"Date mismatches/checks: {mismatches}")
    print(f"Errors: {errors}")
