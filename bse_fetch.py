#!/usr/bin/env python3
"""
bse_fetch.py - Download BSE daily market reports for an Indian financial year.
Standard library optimized: uses csv, Decimal, requests, zipfile. Zero C-extension dependencies.
"""
import argparse
import csv
import io
import json
import random
import sys
import time
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

IST = ZoneInfo("Asia/Kolkata")

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
API = "https://api.bseindia.com/BseIndiaAPI/api"

MONTHLY = {
    "turnover_month": {
        "urls": [
            API + "/monthdisplay/w?year={year}&month={month}",
            API + "/monthdisplay/w?year={year}&month={month:02d}",
        ],
    },
    "trading_highlights": {
        "urls": [API + "/tradinghighlight/w?fromdate={from_}&todate={to_}"],
    },
}

DATASETS = {
    "cm_bhav": {
        "ext": "csv",
        "urls": [
            "https://www.bseindia.com/download/BhavCopy/Equity/BhavCopy_BSE_CM_0_0_0_{yyyymmdd}_F_0000.CSV",
        ],
    },
    "fo_summary": {
        "ext": "csv",
        "urls": ["https://www.bseindia.com/download/BhavCopy/Derivative/MS_{yyyymmdd}-01.csv"],
    },
    "fo_bhav": {
        "ext": "csv",
        "urls": ["https://www.bseindia.com/download/Bhavcopy/Derivative/BhavCopy_BSE_FO_0_0_0_{yyyymmdd}_F_0000.CSV"],
    },
    "delivery": {
        "ext": "zip",
        "urls": ["https://www.bseindia.com/BSEDATA/gross/{yyyy}/SCBSEALL{ddmm}.zip"],
    },
}

ALL_DATASETS = list(MONTHLY) + list(DATASETS)
DEFAULT_DATASETS = ["cm_bhav", "fo_summary", "delivery"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/csv,application/zip,application/octet-stream,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.bseindia.com/",
}
API_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.bseindia.com",
    "Referer": "https://www.bseindia.com/",
}

MANIFEST_FIELDS = ["date", "dataset", "status", "url", "bytes", "fetched_at"]
MAX_CONSECUTIVE_FAILURES = 6

def today_ist() -> date:
    return datetime.now(IST).date()

def fy_start(d: date) -> date:
    return date(d.year if d.month >= 4 else d.year - 1, 4, 1)

def daterange(start: date, end: date, include_weekends: bool):
    d = start
    while d <= end:
        if include_weekends or d.weekday() < 5:
            yield d
        d += timedelta(days=1)

def month_starts(start: date, end: date):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield date(y, m, 1)
        m += 1
        if m == 13:
            y, m = y + 1, 1

def month_end(first: date) -> date:
    nxt = date(first.year + (first.month == 12), first.month % 12 + 1, 1)
    return nxt - timedelta(days=1)

def day_fields(d: date) -> dict:
    return {"yyyymmdd": d.strftime("%Y%m%d"), "yyyy": d.strftime("%Y"), "ddmm": d.strftime("%d%m")}

def looks_like_html(content: bytes) -> bool:
    head = content[:400].lstrip().lower()
    return head.startswith(b"<!doctype html") or head.startswith(b"<html") or b"<head" in head

def valid_json_table(content: bytes) -> bool:
    try:
        obj = json.loads(content)
    except ValueError:
        return False
    return isinstance(obj, dict) and isinstance(obj.get("Table"), list) and len(obj["Table"]) > 0

def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    try:
        s.get("https://www.bseindia.com/", timeout=30)
    except requests.RequestException as e:
        print(f"[warn] warm-up request failed: {e}", file=sys.stderr)
    return s

def fetch(session, url, ext, headers=None, retries=3, timeout=45):
    note = ""
    for attempt in range(1, retries + 1):
        try:
            r = session.get(url, timeout=timeout, headers=headers)
        except requests.RequestException as e:
            note = f"{type(e).__name__}: {str(e)[:100]}"
            if attempt < retries:
                time.sleep(2 ** attempt)
            continue
        ctype = r.headers.get("Content-Type", "").split(";")[0]
        snippet = r.content[:80].decode("utf-8", "replace").replace("\n", " ").replace("\r", " ")
        note = f"HTTP {r.status_code} {ctype} {snippet!r}"
        if r.status_code == 404:
            return "missing", None, note
        if r.status_code in (401, 403, 429):
            return "blocked", None, note
        if r.status_code >= 500:
            if attempt < retries:
                time.sleep(2 ** attempt)
            continue
        if r.status_code != 200:
            return "error", None, note
        content = r.content
        if not content:
            return "missing", None, note
        if ext == "json":
            if not valid_json_table(content):
                return "missing", None, note
        else:
            if looks_like_html(content):
                return "missing", None, note
            if ext == "zip" and not zipfile.is_zipfile(io.BytesIO(content)):
                return "missing", None, note
        return "ok", content, ""
    return "error", None, note

def download_day(session, dataset: str, d: date):
    cfg = DATASETS[dataset]
    fields = day_fields(d)
    last = ("missing", None, "", "")
    for tmpl in cfg["urls"]:
        url = tmpl.format(**fields)
        status, content, note = fetch(session, url, cfg["ext"])
        if status == "ok":
            return status, content, url, ""
        last = (status, None, url, note)
        if status == "blocked":
            break
    return last

def download_month(session, dataset: str, first: date, frm: date, to: date):
    fields = {
        "year": first.year,
        "month": first.month,
        "from_": frm.strftime("%Y%m%d"),
        "to_": to.strftime("%Y%m%d"),
    }
    last = ("missing", None, "", "")
    for tmpl in MONTHLY[dataset]["urls"]:
        url = tmpl.format(**fields)
        status, content, note = fetch(session, url, "json", headers=API_HEADERS)
        if status == "ok":
            return status, content, url, ""
        last = (status, None, url, note)
        if status == "blocked":
            break
    return last

def load_manifest(path: Path) -> dict:
    m = {}
    if path.exists():
        with path.open(newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                m[(row["date"], row["dataset"])] = row
    return m

def append_manifest(path: Path, row: dict):
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)

def should_fetch_day(d: date, dataset: str, manifest: dict, raw_path: Path, retry_missing: bool) -> bool:
    row = manifest.get((d.isoformat(), dataset))
    if row is None:
        return True
    if row["status"] == "ok":
        return not raw_path.exists()
    if row["status"] == "missing":
        return retry_missing or (today_ist() - d).days <= 2
    return True

def should_fetch_month(first: date, dataset: str, manifest: dict, raw_path: Path, retry_missing: bool) -> bool:
    row = manifest.get((first.isoformat(), dataset))
    last = month_end(first)
    if row is None:
        return True
    if row["status"] == "ok":
        if not raw_path.exists():
            return True
        return row["fetched_at"][:10] <= last.isoformat()
    if row["status"] == "missing":
        return retry_missing or (today_ist() - last).days <= 2
    return True

def record(manifest, manifest_path, counts, fails, ds, key: date, status, url, size):
    counts[ds][status] += 1
    fails["n"] = fails["n"] + 1 if status in ("blocked", "error") else 0
    row = {
        "date": key.isoformat(), "dataset": ds, "status": status, "url": url,
        "bytes": size, "fetched_at": datetime.now(IST).isoformat(timespec="seconds"),
    }
    append_manifest(manifest_path, row)
    manifest[(row["date"], ds)] = row

def give_up_message():
    print(
        "\nStopping: several requests in a row were refused or failed.",
        file=sys.stderr,
    )

def as_decimal(val) -> Decimal:
    if val is None:
        return Decimal(0)
    s = str(val).strip().replace(",", "")
    if not s or s.upper() in {"NA", "N/A", "NULL", "NAN", "-", "NONE"}:
        return Decimal(0)
    try:
        return Decimal(s)
    except InvalidOperation:
        return Decimal(0)

# ---------------------------------------------------------------------------
# Standard Library Summaries
# ---------------------------------------------------------------------------
def summarize_cash(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header:
            return None
        header = [c.strip() for c in header]
        try:
            val_idx = header.index("TtlTrfVal")
        except ValueError:
            return None
        vol_idx = header.index("TtlTradgVol") if "TtlTradgVol" in header else None
        tx_idx = header.index("TtlNbOfTxsExctd") if "TtlNbOfTxsExctd" in header else None
        tp_idx = header.index("FinInstrmTp") if "FinInstrmTp" in header else None

        ttl_val = Decimal(0)
        ttl_vol = Decimal(0)
        ttl_tx = Decimal(0)
        by_tp = defaultdict(Decimal)
        count = 0

        for r in reader:
            if len(r) > val_idx:
                count += 1
                v = as_decimal(r[val_idx])
                ttl_val += v
                if vol_idx is not None and len(r) > vol_idx:
                    ttl_vol += as_decimal(r[vol_idx])
                if tx_idx is not None and len(r) > tx_idx:
                    ttl_tx += as_decimal(r[tx_idx])
                if tp_idx is not None and len(r) > tp_idx:
                    tp = r[tp_idx].strip()
                    by_tp[tp] += v

    row = {
        "turnover_cr": round(float(ttl_val / Decimal(1e7)), 4),
        "volume": int(ttl_vol),
        "trades": int(ttl_tx),
        "securities": count,
    }
    for tp, v in by_tp.items():
        row[f"turnover_cr_{tp}"] = round(float(v / Decimal(1e7)), 4)
    return row

def summarize_fo_summary(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header:
            return None
        header = [c.strip() for c in header]

        def get_idx(*candidates):
            for cand in candidates:
                if cand in header:
                    return header.index(cand)
            return None

        pt_idx = get_idx("Product Type")
        ot_idx = get_idx("Option Type (Call/Put)")
        k_idx = get_idx("Strike Price")
        q_idx = get_idx("Total Traded Quantity")
        v_idx = get_idx("Total Traded Value (in Thousands)(absolute)")

        if pt_idx is None or q_idx is None or v_idx is None:
            return None

        out = {
            "fut_idx_turnover_cr": Decimal(0),
            "fut_stk_turnover_cr": Decimal(0),
            "opt_idx_call_notional_cr": Decimal(0),
            "opt_idx_call_premium_cr": Decimal(0),
            "opt_idx_put_notional_cr": Decimal(0),
            "opt_idx_put_premium_cr": Decimal(0),
            "opt_stk_call_notional_cr": Decimal(0),
            "opt_stk_call_premium_cr": Decimal(0),
            "opt_stk_put_notional_cr": Decimal(0),
            "opt_stk_put_premium_cr": Decimal(0),
        }

        for r in reader:
            if len(r) > max(pt_idx, q_idx, v_idx):
                pt = r[pt_idx].strip().upper()
                ot = r[ot_idx].strip().upper() if ot_idx is not None and len(r) > ot_idx else ""
                k = as_decimal(r[k_idx]) if k_idx is not None and len(r) > k_idx else Decimal(0)
                q = as_decimal(r[q_idx])
                # Value is in Thousands of Rupees
                v = as_decimal(r[v_idx]) * Decimal(1000)
                v_cr = v / Decimal(1e7)

                if pt == "IF":
                    out["fut_idx_turnover_cr"] += v_cr
                elif pt == "SF":
                    out["fut_stk_turnover_cr"] += v_cr
                elif pt == "IO":
                    prem_cr = (v - (k * q)) / Decimal(1e7)
                    if ot == "CE":
                        out["opt_idx_call_notional_cr"] += v_cr
                        out["opt_idx_call_premium_cr"] += prem_cr
                    elif ot == "PE":
                        out["opt_idx_put_notional_cr"] += v_cr
                        out["opt_idx_put_premium_cr"] += prem_cr
                elif pt == "SO":
                    prem_cr = (v - (k * q)) / Decimal(1e7)
                    if ot == "CE":
                        out["opt_stk_call_notional_cr"] += v_cr
                        out["opt_stk_call_premium_cr"] += prem_cr
                    elif ot == "PE":
                        out["opt_stk_put_notional_cr"] += v_cr
                        out["opt_stk_put_premium_cr"] += prem_cr

    res = {k: round(float(v), 2) for k, v in out.items()}
    res["fut_turnover_cr"] = round(res["fut_idx_turnover_cr"] + res["fut_stk_turnover_cr"], 2)
    res["opt_notional_cr"] = round(sum(res[k] for k in res if k.endswith("_notional_cr")), 2)
    res["opt_premium_cr"] = round(sum(res[k] for k in res if k.endswith("_premium_cr")), 2)
    return res

def summarize_delivery(path: Path):
    try:
        with zipfile.ZipFile(path) as z:
            raw = z.read(z.namelist()[0]).decode("latin-1")
    except Exception:
        return None

    lines = raw.splitlines()
    if not lines:
        return None
    sep = max([",", "|", "\t", ";"], key=lines[0].count)
    reader = csv.reader(io.StringIO(raw), delimiter=sep)
    header = next(reader, None)
    if not header:
        return None
    header = [h.strip().upper() for h in header]

    def col_idx(*substrings):
        for sub in substrings:
            for i, h in enumerate(header):
                if sub in h:
                    return i
        return None

    tq_i = col_idx("VOLUME", "TRADED QTY")
    dq_i = col_idx("DELIVERY QTY")
    to_i = col_idx("TURNOVER")
    dv_i = col_idx("DELIVERY VAL")

    t_qty = Decimal(0)
    d_qty = Decimal(0)
    turn = Decimal(0)
    dval = Decimal(0)

    for r in reader:
        if tq_i is not None and len(r) > tq_i:
            t_qty += as_decimal(r[tq_i])
        if dq_i is not None and len(r) > dq_i:
            d_qty += as_decimal(r[dq_i])
        if to_i is not None and len(r) > to_i:
            turn += as_decimal(r[to_i])
        if dv_i is not None and len(r) > dv_i:
            dval += as_decimal(r[dv_i])

    deliv_pct = (d_qty / t_qty * 100) if t_qty > 0 else 0
    deliv_val_pct = (dval / turn * 100) if turn > 0 else 0

    return {
        "traded_qty": int(t_qty),
        "delivery_qty": int(d_qty),
        "delivery_pct": round(float(deliv_pct), 2),
        "turnover_cr": round(float(turn / Decimal(1e7)), 4),
        "delivery_value_cr": round(float(dval / Decimal(1e7)), 4),
        "delivery_value_pct": round(float(deliv_val_pct), 2),
    }

def write_site_data(site_dir: Path, fo_rows, del_rows, cash_rows):
    days = {}
    for r in cash_rows:
        days.setdefault(r["date"], {})["c"] = r["turnover_cr"]
    for r in fo_rows:
        days.setdefault(r["date"], {}).update(
            f=r["fut_turnover_cr"], o=r["opt_premium_cr"], on=r["opt_notional_cr"]
        )
    for r in del_rows:
        dp = r.get("delivery_value_pct")
        days.setdefault(r["date"], {})["dp"] = r.get("delivery_pct") if dp is None else dp

    site_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated": datetime.now(IST).isoformat(timespec="minutes"),
        "days": [{"d": d, **v} for d, v in sorted(days.items())],
    }
    (site_dir / "bse_summary.json").write_text(json.dumps(payload), encoding="utf-8")
    print(f"wrote {site_dir / 'bse_summary.json'}  ({len(days)} days)")

def summarize(out_dir: Path, site_dir: Path = None):
    raw = out_dir / "raw"
    cash_rows, fo_rows, del_rows = [], [], []

    for p in sorted((raw / "fo_summary").glob("*.csv")):
        d = datetime.strptime(p.stem, "%Y%m%d").date().isoformat()
        r = summarize_fo_summary(p)
        if r:
            fo_rows.append({"date": d, **r})

    for p in sorted((raw / "cm_bhav").glob("*.csv")):
        d = datetime.strptime(p.stem, "%Y%m%d").date().isoformat()
        r = summarize_cash(p)
        if r:
            cash_rows.append({"date": d, **r})

    for p in sorted((raw / "delivery").glob("*.zip")):
        d = datetime.strptime(p.stem, "%Y%m%d").date().isoformat()
        r = summarize_delivery(p)
        if r:
            del_rows.append({"date": d, **r})

    def write_csv_table(path: Path, rows: list):
        if not rows:
            return
        fields = list(rows[0].keys())
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        print(f"wrote {path}  ({len(rows)} rows)")

    write_csv_table(out_dir / "daily_cash.csv", cash_rows)
    write_csv_table(out_dir / "daily_fo.csv", fo_rows)
    write_csv_table(out_dir / "daily_delivery.csv", del_rows)

    if site_dir is not None:
        write_site_data(site_dir, fo_rows, del_rows, cash_rows)

def run(args) -> int:
    out_dir = Path(args.out)
    (out_dir / "raw").mkdir(parents=True, exist_ok=True)

    if args.summarize_only:
        summarize(out_dir, Path(args.site_dir))
        return 0

    session = make_session()
    end = date.fromisoformat(args.end) if args.end else today_ist()
    start = date.fromisoformat(args.start) if args.start else fy_start(end)
    manifest_path = out_dir / "manifest.csv"
    manifest = load_manifest(manifest_path)
    selected = args.datasets or DEFAULT_DATASETS
    daily = [d for d in selected if d in DATASETS]

    print(f"Fetching {', '.join(selected)} from {start} to {end}")
    counts = {ds: {"ok": 0, "missing": 0, "blocked": 0, "error": 0, "skipped": 0} for ds in selected}
    fails = {"n": 0}

    for d in daterange(start, end, not args.skip_weekends):
        for ds in daily:
            ext = DATASETS[ds]["ext"]
            raw_path = out_dir / "raw" / ds / f"{d.strftime('%Y%m%d')}.{ext}"
            if not should_fetch_day(d, ds, manifest, raw_path, args.retry_missing):
                counts[ds]["skipped"] += 1
                continue
            status, content, url, note = download_day(session, ds, d)
            size = 0
            if status == "ok":
                raw_path.parent.mkdir(parents=True, exist_ok=True)
                raw_path.write_bytes(content)
                size = len(content)
            record(manifest, manifest_path, counts, fails, ds, d, status, url, size)
            print(f"{d}  {ds:18s} {status:8s} {size:>10,} bytes")
            if fails["n"] >= MAX_CONSECUTIVE_FAILURES:
                give_up_message()
                return 2
            time.sleep(args.delay + random.uniform(0, args.delay / 2))

    summarize(out_dir, Path(args.site_dir))
    return 0

def parse_args():
    p = argparse.ArgumentParser(description="Download BSE daily reports for a financial year.")
    p.add_argument("--start", help="YYYY-MM-DD")
    p.add_argument("--end", help="YYYY-MM-DD")
    p.add_argument("--site-dir", default="docs", help="site output dir (default: docs)")
    p.add_argument("--out", default="bse_data", help="output folder (default: bse_data)")
    p.add_argument("--datasets", nargs="+", choices=ALL_DATASETS, help="datasets to fetch")
    p.add_argument("--delay", type=float, default=1.5)
    p.add_argument("--skip-weekends", action="store_true")
    p.add_argument("--retry-missing", action="store_true")
    p.add_argument("--probe", action="store_true")
    p.add_argument("--summarize-only", action="store_true")
    return p.parse_args()

if __name__ == "__main__":
    sys.exit(run(parse_args()))
