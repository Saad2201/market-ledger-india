#!/usr/bin/env python3
"""
NSE historical data collector for Market Ledger India.

Downloads official NSE daily reports and preserves the original responses.
It deliberately does NOT calculate tax collections yet: UDiFF field meanings,
segment coverage, buy/sell sides and taxable bases must be validated before
any figure is presented as government revenue.

Install:
    py -m pip install -r requirements.txt

Probe endpoints:
    py nse_fetch.py --probe

Download the project history:
    py nse_fetch.py --start 2026-04-01 --end 2026-11-09

Resume later (already downloaded files are skipped):
    py nse_fetch.py

Retry previously missing reports:
    py nse_fetch.py --retry-missing

Output:
    nse_data/raw/<dataset>/...
    nse_data/extracted/<dataset>/...
    nse_data/manifest.csv
    nse_data/schema_inventory.csv
    nse_data/collection_summary.json

The collection summary distinguishes activity in the current run from the
latest known status for every date/dataset in the requested historical range.
The manifest remains append-only; earlier failed attempts are not deleted.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import random
import re
import time
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

IST = ZoneInfo("Asia/Kolkata")
BASE = "https://nsearchives.nseindia.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "text/csv,application/zip,application/octet-stream,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

DATASETS = {
    "cm_udiff": {
        "kind": "zip",
        "url": BASE + "/content/cm/BhavCopy_NSE_CM_0_0_0_{ymd}_F_0000.csv.zip",
    },
    "fo_udiff": {
        "kind": "zip",
        "url": BASE + "/content/fo/BhavCopy_NSE_FO_0_0_0_{ymd}_F_0000.csv.zip",
    },
    # Security-wise traded and deliverable quantities. This does not by itself
    # classify every trade's tax treatment or provide client-level settlement data.
    "cm_security_delivery": {
        "kind": "csv",
        "url": BASE + "/products/content/sec_bhavdata_full_{ddmmyyyy}.csv",
    },
}

MANIFEST_FIELDS = [
    "trade_date", "dataset", "status", "url", "bytes", "sha256",
    "saved_file", "fetched_at_ist", "note"
]
STATUS_NAMES = ("ok", "missing", "blocked", "error")


def ist_now() -> str:
    return datetime.now(IST).isoformat(timespec="seconds")


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def date_range(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name)


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    try:
        s.get("https://www.nseindia.com/", timeout=10)
    except requests.RequestException:
        pass
    return s


def fetch(session: requests.Session, url: str, kind: str, retries: int = 3):
    last_note = ""
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, timeout=15)
            content = response.content
            ctype = response.headers.get("Content-Type", "")
            if response.status_code == 404:
                return "missing", None, f"HTTP 404 ({ctype})"
            if response.status_code in (401, 403, 429):
                return "blocked", None, f"HTTP {response.status_code} ({ctype})"
            if response.status_code != 200:
                last_note = f"HTTP {response.status_code} ({ctype})"
                if response.status_code >= 500 and attempt < retries:
                    time.sleep(attempt * 2)
                    continue
                return "error", None, last_note
            if not content:
                return "missing", None, "HTTP 200 but empty response"
            if content.lstrip().lower().startswith((b"<!doctype html", b"<html")):
                return "blocked", None, "NSE returned an HTML page instead of the report"
            if kind == "zip" and not zipfile.is_zipfile(io.BytesIO(content)):
                return "error", None, f"HTTP 200 but response is not a ZIP ({ctype})"
            if kind == "csv" and len(content.splitlines()) < 2:
                return "missing", None, "CSV has fewer than two lines"
            return "ok", content, ""
        except requests.RequestException as exc:
            last_note = f"{type(exc).__name__}: {str(exc)[:180]}"
            if attempt < retries:
                time.sleep(attempt * 2 + random.random())
    return "error", None, last_note


def read_manifest(path: Path):
    """Return the latest manifest row for each (date, dataset) key."""
    result = {}
    if path.exists():
        with path.open("r", newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                result[(row["trade_date"], row["dataset"])] = row
    return result


def append_csv(path: Path, fields, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def inspect_csv_bytes(content: bytes, dataset: str, trade_day: date,
                      root: Path, member_name: str):
    target_dir = root / "extracted" / dataset
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{trade_day:%Y%m%d}_{safe_name(Path(member_name).name)}"
    target.write_bytes(content)

    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        header = []
    row_count = sum(1 for _ in reader)
    return target, [h.strip() for h in header], row_count


def inspect_and_extract(content: bytes, dataset: str, trade_day: date, root: Path):
    if dataset.endswith("_udiff"):
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            candidates = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            if not candidates:
                raise ValueError("ZIP contains no CSV member")
            member = max(candidates, key=lambda n: zf.getinfo(n).file_size)
            csv_bytes = zf.read(member)
            return inspect_csv_bytes(csv_bytes, dataset, trade_day, root, member)
    return inspect_csv_bytes(content, dataset, trade_day, root, f"{dataset}.csv")


def build_historical_status(manifest: dict, start: date, end: date, datasets):
    """
    Count the latest known status for every calendar date/dataset.
    Non-trading days and dates without a manifest entry remain visible as
    missing/not_recorded; they are never converted to zero turnover.
    """
    result = {
        ds: {**{status: 0 for status in STATUS_NAMES}, "not_recorded": 0}
        for ds in datasets
    }

    for d in date_range(start, end):
        day = d.isoformat()
        for ds in datasets:
            row = manifest.get((day, ds))
            if row is None:
                result[ds]["not_recorded"] += 1
                continue
            status = row.get("status", "")
            if status in STATUS_NAMES:
                result[ds][status] += 1
            else:
                result[ds]["error"] += 1
    return result


def main():
    ap = argparse.ArgumentParser(
        description="Download official NSE daily reports for Market Ledger India."
    )
    ap.add_argument("--start", default="2026-04-01")
    ap.add_argument("--end", default=datetime.now(IST).date().isoformat())
    ap.add_argument("--out", default="nse_data")
    ap.add_argument("--datasets", nargs="+", choices=list(DATASETS),
                    default=list(DATASETS))
    ap.add_argument("--delay", type=float, default=0.8)
    ap.add_argument("--retry-missing", action="store_true")
    ap.add_argument("--probe", action="store_true")
    args = ap.parse_args()

    root = Path(args.out)
    raw_root = root / "raw"
    raw_root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "manifest.csv"
    schema_path = root / "schema_inventory.csv"
    manifest = read_manifest(manifest_path)
    session = make_session()

    if args.probe:
        print("NSE endpoint probe: checking recent calendar days (latest report may lag).")
        end = parse_date(args.end)
        days = [end - timedelta(days=i) for i in range(14)]
        for ds in args.datasets:
            found = False
            for d in days:
                ymd = d.strftime("%Y%m%d")
                url = DATASETS[ds]["url"].format(
                    ymd=ymd, ddmmyyyy=d.strftime("%d%m%Y")
                )
                status, content, note = fetch(session, url, DATASETS[ds]["kind"])
                if status == "ok":
                    print(f"[OK] {ds} {d}: {len(content):,} bytes | {url}")
                    try:
                        target, cols, rows = inspect_and_extract(content, ds, d, root)
                        print(f"     CSV rows={rows}; columns={len(cols)}; saved={target}")
                        print("     Header:", ", ".join(cols[:24]))
                    except Exception as exc:
                        print(f"     [SCHEMA ERROR] {exc}")
                    found = True
                    break
                time.sleep(args.delay)
            if not found:
                print(f"[NOT FOUND] {ds}: no usable report in the last 14 calendar days")
        return

    start, end = parse_date(args.start), parse_date(args.end)
    if end < start:
        ap.error("--end must be on or after --start")

    totals = {
        ds: {**{status: 0 for status in STATUS_NAMES}, "skipped": 0}
        for ds in args.datasets
    }

    for d in date_range(start, end):
        ymd = d.strftime("%Y%m%d")
        for ds in args.datasets:
            prior = manifest.get((d.isoformat(), ds))

            if prior and prior["status"] == "ok":
                saved = Path(prior["saved_file"]) if prior.get("saved_file") else None
                if saved and saved.exists():
                    totals[ds]["skipped"] += 1
                    continue

            if prior and prior["status"] == "missing" and not args.retry_missing:
                # Recheck recent dates because NSE reports can be published late.
                if (end - d).days > 3:
                    totals[ds]["skipped"] += 1
                    continue

            url = DATASETS[ds]["url"].format(
                ymd=ymd, ddmmyyyy=d.strftime("%d%m%Y")
            )
            status, content, note = fetch(session, url, DATASETS[ds]["kind"])
            saved_path = ""
            digest = ""
            size = 0

            if status == "ok":
                try:
                    digest = hashlib.sha256(content).hexdigest()
                    size = len(content)
                    raw_dir = raw_root / ds
                    raw_dir.mkdir(parents=True, exist_ok=True)
                    suffix = ".zip" if DATASETS[ds]["kind"] == "zip" else ".csv"
                    raw_path = raw_dir / f"{ymd}{suffix}"
                    raw_path.write_bytes(content)
                    saved_path = str(raw_path)

                    extracted, columns, rows = inspect_and_extract(
                        content, ds, d, root
                    )
                    append_csv(
                        schema_path,
                        ["trade_date", "dataset", "csv_file", "row_count",
                         "column_count", "columns"],
                        {
                            "trade_date": d.isoformat(),
                            "dataset": ds,
                            "csv_file": str(extracted),
                            "row_count": rows,
                            "column_count": len(columns),
                            "columns": "|".join(columns),
                        },
                    )
                    note = (
                        f"CSV rows={rows}; columns={len(columns)}; "
                        f"member={extracted.name}"
                    )
                except Exception as exc:
                    status = "error"
                    note = (
                        f"Saved response but extraction/schema inspection failed: "
                        f"{type(exc).__name__}: {exc}"
                    )

            row = {
                "trade_date": d.isoformat(),
                "dataset": ds,
                "status": status,
                "url": url,
                "bytes": size,
                "sha256": digest,
                "saved_file": saved_path,
                "fetched_at_ist": ist_now(),
                "note": note,
            }
            append_csv(manifest_path, MANIFEST_FIELDS, row)
            manifest[(d.isoformat(), ds)] = row
            totals[ds][status] += 1
            print(f"[{status.upper():7}] {d} {ds}" +
                  (f" — {note}" if note else ""))
            time.sleep(max(0.0, args.delay))

    historical = build_historical_status(
        manifest, start, end, args.datasets
    )

    summary = {
        "generated_at_ist": ist_now(),
        "date_range": {
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
        "this_run": totals,
        "latest_historical_status": historical,
        "important_note": (
            "Historical status uses the latest manifest entry for each "
            "date and dataset. The manifest remains an append-only attempt "
            "log. Missing reports and non-trading days are not assumed to "
            "mean zero turnover. This is a raw-data collection report, not "
            "a government-revenue estimate. Tax calculations are withheld "
            "until source fields and taxable bases are reconciled and validated."
        ),
    }

    (root / "collection_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print("\nCollection summary:")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
