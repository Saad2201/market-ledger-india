#!/usr/bin/env python3
"""
run_pipeline.py - Unified Master Orchestrator for Market Ledger India

Executes the complete end-to-end data engineering, validation, reconciliation,
calculation, testing, and dashboard update workflow:
1. (Optional) Ingestion of latest trading day from NSE & BSE (--fetch)
2. NSE dataset validation & deduplication (nse_validate_datasets.py)
3. NSE turnover reconciliation (nse_reconcile.py)
4. BSE dataset validation & normalization (bse_validate_datasets.py)
5. BSE turnover reconciliation (bse_reconcile.py)
6. Statutory Revenue Calculation (calculate_revenue.py)
7. Automated Verification & Unit Tests (tests/test_revenue_engine.py)
8. Dashboard Data Payload Export (build_dashboard_data.py)

Usage:
  python run_pipeline.py                  # Rebuild & recalculate from collected data
  python run_pipeline.py --run-tests      # Run full pipeline and execute unit test suite
  python run_pipeline.py --fetch          # Attempt daily download before processing
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
IST = ZoneInfo("Asia/Kolkata")

def log(msg: str):
    ts = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")
    print(f"[{ts}] {msg}", flush=True)

def run_step(step_name: str, script_name: str, args: list[str] = None) -> bool:
    log(f"--- Starting: {step_name} ({script_name}) ---")
    script_path = ROOT / script_name
    if not script_path.exists():
        log(f"ERROR: Script not found: {script_path}")
        return False

    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)

    t0 = time.time()
    process = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    if process.stdout:
        for line in iter(process.stdout.readline, ''):
            line_str = line.rstrip()
            if line_str:
                print(f"   | {line_str}", flush=True)
        process.stdout.close()
    returncode = process.wait()
    elapsed = time.time() - t0

    if returncode == 0:
        log(f"PASSED: {step_name} in {elapsed:.2f}s")
        return True
    else:
        log(f"FAILED: {step_name} (exit code {returncode}) in {elapsed:.2f}s")
        return False

def main():
    parser = argparse.ArgumentParser(description="Market Ledger India - Master Orchestrator")
    parser.add_argument("--fetch", action="store_true", help="Fetch latest trading data from NSE and BSE")
    parser.add_argument("--skip-tests", action="store_true", help="Skip test suite execution")
    args = parser.parse_args()

    start_time = datetime.now(IST)
    log("================================================================================")
    log("MARKET LEDGER — INDIA: MASTER PIPELINE EXECUTION")
    log("================================================================================")

    steps = []

    if args.fetch:
        lookback_date = (datetime.now(IST).date() - timedelta(days=5)).isoformat()
        steps.append(("Fetch BSE Daily Data", "bse_fetch.py", ["--start", lookback_date, "--datasets", "cm_bhav", "fo_summary", "delivery"]))
        steps.append(("Fetch NSE Daily Data", "nse_fetch.py", ["--start", lookback_date]))

    steps.extend([
        ("Validate NSE Datasets", "nse_validate_datasets.py", []),
        ("Reconcile NSE Turnover", "nse_reconcile.py", []),
        ("Validate BSE Datasets", "bse_validate_datasets.py", []),
        ("Reconcile BSE Turnover", "bse_reconcile.py", []),
        ("Calculate Statutory Revenue", "calculate_revenue.py", []),
    ])

    if not args.skip_tests:
        steps.append(("Run Automated Unit Tests", "-m unittest tests/test_revenue_engine.py", []))

    steps.append(("Export Dashboard JSON Payload", "build_dashboard_data.py", []))

    all_passed = True
    for step_desc, script, script_args in steps:
        if step_desc.startswith("Fetch"):
            # Live exchange download step: log warnings gracefully on cloud IP blocking
            success = run_step(step_desc, script, script_args)
            if not success:
                log(f"WARNING: {step_desc} encountered network issues (e.g. cloud runner IP rate-limiting). Continuing pipeline with existing verified data.")
            continue

        if script.startswith("-m "):
            # Python module invocation
            cmd = [sys.executable] + script.split()
            log(f"--- Starting: {step_desc} ---")
            t0 = time.time()
            res = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
            elapsed = time.time() - t0
            if res.returncode == 0:
                log(f"PASSED: {step_desc} in {elapsed:.2f}s")
                if res.stderr.strip():
                    for line in res.stderr.strip().splitlines()[-4:]:
                        print(f"   | {line}", flush=True)
            else:
                log(f"FAILED: {step_desc} (exit code {res.returncode})")
                print(res.stderr, flush=True)
                all_passed = False
                break
        else:
            success = run_step(step_desc, script, script_args)
            if not success:
                all_passed = False
                break

    total_elapsed = (datetime.now(IST) - start_time).total_seconds()
    log("================================================================================")
    if all_passed:
        log(f"MASTER PIPELINE COMPLETED SUCCESSFULLY in {total_elapsed:.2f}s.")
        
        # Read FY total for executive summary
        fy_path = ROOT / "data" / "processed" / "revenue" / "financial_year_estimates.csv"
        if fy_path.exists():
            with open(fy_path, "r", encoding="utf-8-sig") as f:
                row = next(csv.DictReader(f))
                days_count = row.get("trading_days", "153")
                log(f"EXECUTIVE SUMMARY ({days_count} Trading Days):")
                log(f"  • Total Market Turnover:     ₹{float(row['total_market_turnover_cr']):,.2f} Cr")
                log(f"  • Central Gov STT:           ₹{float(row['central_gov_revenue_cr']):,.2f} Cr")
                log(f"  • State Gov Stamp Duty:      ₹{float(row['state_gov_revenue_cr']):,.2f} Cr")
                log(f"  • GST on Financial Services: ₹{float(row['gst_revenue_cr']):,.2f} Cr")
                log(f"  • Total Government Tax:      ₹{float(row['total_government_tax_revenue_cr']):,.2f} Cr")
                log(f"  • SEBI Regulatory Fees:      ₹{float(row['sebi_fee_total_cr']):,.2f} Cr")
                log(f"  • Total Statutory Revenue:   ₹{float(row['total_statutory_revenue_cr']):,.2f} Cr")
                log(f"  • Non-Gov Exchange Fees:     ₹{float(row['non_government_charges_cr']):,.2f} Cr")
        return 0
    else:
        log(f"MASTER PIPELINE HALTED WITH ERRORS in {total_elapsed:.2f}s.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
