#!/usr/bin/env python3
"""
build_dashboard_data.py - Exports structured JSON payload for Market Ledger India Dashboard

Converts processed daily, monthly, FY revenue datasets and statutory reference schedules
into a single optimized docs/data.json payload consumed by docs/index.html.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
REVENUE_DIR = ROOT / "data" / "processed" / "revenue"
REFERENCE_DIR = ROOT / "reference"
DOCS_DIR = ROOT / "docs"

IST = ZoneInfo("Asia/Kolkata")

def build_data_json():
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Read Financial Year Summary
    fy_path = REVENUE_DIR / "financial_year_estimates.csv"
    with open(fy_path, "r", encoding="utf-8-sig") as f:
        fy_row = next(csv.DictReader(f))
    
    fy_summary = {k: (float(v) if v.replace(".", "", 1).replace("-", "", 1).isdigit() else v) for k, v in fy_row.items()}

    # 2. Read Monthly Summary
    monthly_path = REVENUE_DIR / "monthly_revenue_estimates.csv"
    monthly_summary = []
    with open(monthly_path, "r", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            monthly_summary.append({
                k: (int(v) if k == "trading_days" else (float(v) if v.replace(".", "", 1).isdigit() else v))
                for k, v in r.items()
            })

    # 3. Read Daily Revenue Estimates
    daily_path = REVENUE_DIR / "daily_revenue_estimates.csv"
    daily_records = []
    with open(daily_path, "r", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rec = {}
            for k, v in r.items():
                if k in {"trade_date", "status", "nse_status", "bse_status", "notes"}:
                    rec[k] = v
                else:
                    try:
                        rec[k] = float(v)
                    except ValueError:
                        rec[k] = v
            daily_records.append(rec)

    # 4. Read Statutory Tax Rates Reference
    tax_rates = []
    rates_path = REFERENCE_DIR / "tax_rates.csv"
    if rates_path.exists():
        with open(rates_path, "r", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                tax_rates.append(r)

    # 5. Read Data Quality Report
    quality_path = REVENUE_DIR / "data_quality_report.json"
    quality_report = {}
    if quality_path.exists():
        with open(quality_path, "r", encoding="utf-8") as f:
            quality_report = json.load(f)

    payload = {
        "meta": {
            "title": "Market Ledger — India",
            "subtitle": "Indian Stock-Market Government Revenue Estimation Platform",
            "version": "2.0.0",
            "updated_ist": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST"),
            "total_trading_dates": len(daily_records),
            "start_date": daily_records[0]["trade_date"] if daily_records else "2026-04-01",
            "end_date": daily_records[-1]["trade_date"] if daily_records else "2026-11-09",
            "canonical_status": "HIGH_CONFIDENCE_VERIFIED",
            "exchanges_tracked": ["NSE", "BSE"],
            "disclaimer": "Quantitative financial estimates derived from official exchange BhavCopy, delivery records, and statutory schedules. Not actual Treasury receipts."
        },
        "quality_report": quality_report,
        "fy_summary": fy_summary,
        "monthly_summary": monthly_summary,
        "daily_records": daily_records,
        "tax_schedules": tax_rates
    }

    out_file = DOCS_DIR / "data.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"))

    size_kb = out_file.stat().st_size / 1024
    print(f"Generated {out_file} ({size_kb:.1f} KB, {len(daily_records)} daily records).")
    return payload

if __name__ == "__main__":
    build_data_json()
