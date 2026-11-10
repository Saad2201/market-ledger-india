#!/usr/bin/env python3
"""
nse_validate_datasets.py - Deterministic NSE Field & Instrument Validation Pipeline

Audits, normalizes, and aggregates all 152 historical NSE trading dates (2026-04-01 to 2026-11-09).
- Separates CM series using reference/security_series.csv
- Calculates exact Options Premium Turnover from UDiFF: TtlTrfVal - (StrkPric * Vol * Lot)
- Deduplicates cm_security_delivery strictly by embedded DATE1
- Uses Decimal for financial precision. Zero third-party dependencies required.
"""
from __future__ import annotations

import csv
import glob
import os
import zipfile
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NSE_DATA = ROOT / "nse_data"
REFERENCE = ROOT / "reference"
PROCESSED_NSE = ROOT / "data" / "processed" / "nse"

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

def parse_date_str(val: str) -> str:
    val = (val or "").strip()
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%m-%Y", "%d/%m/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(val, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return val

def load_security_series_map() -> dict:
    series_map = {}
    path = REFERENCE / "security_series.csv"
    if path.exists():
        with path.open("r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                series_map[row["series"].strip()] = {
                    "include_in_equity": row.get("include_in_equity_turnover", "FALSE").upper() == "TRUE",
                    "stt_applicable": row.get("stt_applicable", "FALSE").upper() == "TRUE",
                    "category": row.get("instrument_category", "Other"),
                }
    return series_map

def process_cm_delivery_files():
    """
    Deduplicate delivery files by embedded DATE1 and return map:
    date_iso -> dict(traded_qty, deliv_qty, deliv_pct, turnover_lacs, deliv_value_cr)
    """
    pattern = str(NSE_DATA / "extracted" / "cm_security_delivery" / "*.csv")
    files = sorted(glob.glob(pattern))
    delivery_by_date = {}
    seen_dates_source = defaultdict(list)

    for path in files:
        with open(path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                continue
            header = [h.strip().upper() for h in header]
            try:
                date_idx = header.index("DATE1")
                qty_idx = header.index("TTL_TRD_QNTY")
                deliv_qty_idx = header.index("DELIV_QTY")
                turnover_lacs_idx = header.index("TURNOVER_LACS")
                avg_price_idx = header.index("AVG_PRICE")
            except ValueError:
                continue

            first_row = next(reader, None)
            if not first_row:
                continue
            embedded_date = parse_date_str(first_row[date_idx])
            seen_dates_source[embedded_date].append(os.path.basename(path))

            # If we haven't processed this actual date yet, compute aggregates
            if embedded_date not in delivery_by_date:
                # Reset and read full file
                f.seek(0)
                r_all = csv.reader(f)
                next(r_all)
                ttl_qty = Decimal(0)
                deliv_qty = Decimal(0)
                turnover_lacs = Decimal(0)
                deliv_val_rupees = Decimal(0)

                for r in r_all:
                    if len(r) > max(date_idx, qty_idx, deliv_qty_idx, turnover_lacs_idx, avg_price_idx):
                        q = as_decimal(r[qty_idx])
                        dq = as_decimal(r[deliv_qty_idx])
                        tl = as_decimal(r[turnover_lacs_idx])
                        ap = as_decimal(r[avg_price_idx])
                        ttl_qty += q
                        deliv_qty += dq
                        turnover_lacs += tl
                        deliv_val_rupees += ap * dq

                deliv_pct = (deliv_qty / ttl_qty * 100) if ttl_qty > 0 else Decimal(0)
                deliv_val_cr = deliv_val_rupees / Decimal(1e7)
                turnover_cr = turnover_lacs / Decimal(100)
                deliv_val_pct = (deliv_val_cr / turnover_cr * 100) if turnover_cr > 0 else Decimal(0)

                delivery_by_date[embedded_date] = {
                    "date": embedded_date,
                    "canonical_file": os.path.basename(path),
                    "traded_qty": int(ttl_qty),
                    "deliv_qty": int(deliv_qty),
                    "deliv_pct": round(float(deliv_pct), 2),
                    "turnover_cr": round(float(turnover_cr), 4),
                    "deliv_val_cr": round(float(deliv_val_cr), 4),
                    "deliv_val_pct": round(float(deliv_val_pct), 2),
                }

    print(f"Delivery files audited: {len(files)}, Unique canonical trade dates: {len(delivery_by_date)}")
    return delivery_by_date, seen_dates_source

def ensure_extracted(dataset: str):
    ext_dir = NSE_DATA / "extracted" / dataset
    raw_dir = NSE_DATA / "raw" / dataset
    ext_dir.mkdir(parents=True, exist_ok=True)
    if not list(ext_dir.glob("*.csv")) and raw_dir.exists():
        zips = list(raw_dir.glob("*.zip"))
        print(f"Extracting {len(zips)} raw archives for {dataset}...")
        for zpath in zips:
            try:
                with zipfile.ZipFile(zpath) as z:
                    for member in z.namelist():
                        if member.lower().endswith(".csv"):
                            target = ext_dir / f"{zpath.stem[:8]}_{member}"
                            if not target.exists():
                                target.write_bytes(z.read(member))
            except Exception as e:
                print(f"Error extracting {zpath.name}: {e}")

def process_all_dates():
    PROCESSED_NSE.mkdir(parents=True, exist_ok=True)
    series_map = load_security_series_map()
    delivery_map, duplicate_sources = process_cm_delivery_files()

    ensure_extracted("cm_udiff")
    ensure_extracted("fo_udiff")

    cm_files = sorted(glob.glob(str(NSE_DATA / "extracted" / "cm_udiff" / "*.csv")))
    fo_files = sorted(glob.glob(str(NSE_DATA / "extracted" / "fo_udiff" / "*.csv")))

    fo_by_date = {}
    for f in fo_files:
        d = os.path.basename(f)[:8]
        iso_d = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
        fo_by_date[iso_d] = f

    daily_summary_rows = []
    fo_breakdown_rows = []
    cm_series_rows = []

    print(f"Processing {len(cm_files)} CM files and {len(fo_files)} FO files...")

    for cm_path in cm_files:
        cm_base = os.path.basename(cm_path)
        d_str = cm_base[:8]
        trade_date = f"{d_str[:4]}-{d_str[4:6]}-{d_str[6:8]}"

        # 1. Process CM UDiFF
        cm_records = 0
        cm_trades = Decimal(0)
        cm_volume = Decimal(0)
        cm_total_val = Decimal(0)
        cm_equity_val = Decimal(0)
        cm_debt_val = Decimal(0)
        cm_etf_val = Decimal(0)
        cm_trust_val = Decimal(0)

        series_aggregates = defaultdict(lambda: {"count": 0, "volume": Decimal(0), "value": Decimal(0), "trades": Decimal(0)})

        with open(cm_path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if header:
                h_map = {name.strip(): i for i, name in enumerate(header)}
                srs_idx = h_map.get("SctySrs")
                vol_idx = h_map.get("TtlTradgVol")
                val_idx = h_map.get("TtlTrfVal")
                tx_idx = h_map.get("TtlNbOfTxsExctd")

                for r in reader:
                    if len(r) > max(srs_idx, vol_idx, val_idx, tx_idx):
                        cm_records += 1
                        srs = r[srs_idx].strip()
                        vol = as_decimal(r[vol_idx])
                        val = as_decimal(r[val_idx])
                        tx = as_decimal(r[tx_idx])

                        cm_volume += vol
                        cm_total_val += val
                        cm_trades += tx

                        series_aggregates[srs]["count"] += 1
                        series_aggregates[srs]["volume"] += vol
                        series_aggregates[srs]["value"] += val
                        series_aggregates[srs]["trades"] += tx

                        meta = series_map.get(srs, {})
                        cat = meta.get("category", "")
                        if meta.get("include_in_equity", False):
                            cm_equity_val += val
                        elif cat == "Units of Business Trust":
                            cm_trust_val += val
                        elif cat == "ETF":
                            cm_etf_val += val
                        else:
                            cm_debt_val += val

        for srs, s_data in series_aggregates.items():
            cm_series_rows.append({
                "trade_date": trade_date,
                "series": srs,
                "records": s_data["count"],
                "traded_shares": int(s_data["volume"]),
                "turnover_rupees": str(s_data["value"]),
                "turnover_crore": round(float(s_data["value"] / Decimal(1e7)), 4),
                "trades": int(s_data["trades"]),
            })

        # 2. Process FO UDiFF
        fo_path = fo_by_date.get(trade_date)
        fo_types = {
            "IDF": {"records": 0, "trades": Decimal(0), "vol": Decimal(0), "notional": Decimal(0), "premium": Decimal(0)},
            "STF": {"records": 0, "trades": Decimal(0), "vol": Decimal(0), "notional": Decimal(0), "premium": Decimal(0)},
            "IDO": {"records": 0, "trades": Decimal(0), "vol": Decimal(0), "notional": Decimal(0), "premium": Decimal(0), "call_prem": Decimal(0), "put_prem": Decimal(0)},
            "STO": {"records": 0, "trades": Decimal(0), "vol": Decimal(0), "notional": Decimal(0), "premium": Decimal(0), "call_prem": Decimal(0), "put_prem": Decimal(0)},
        }

        if fo_path:
            with open(fo_path, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if header:
                    h_map = {name.strip(): i for i, name in enumerate(header)}
                    tp_idx = h_map.get("FinInstrmTp")
                    vol_idx = h_map.get("TtlTradgVol")
                    val_idx = h_map.get("TtlTrfVal")
                    tx_idx = h_map.get("TtlNbOfTxsExctd")
                    strk_idx = h_map.get("StrkPric")
                    lot_idx = h_map.get("NewBrdLotQty")
                    opt_tp_idx = h_map.get("OptnTp")

                    for r in reader:
                        if len(r) > max(tp_idx, vol_idx, val_idx, tx_idx):
                            tp = r[tp_idx].strip()
                            if tp in fo_types:
                                vol = as_decimal(r[vol_idx])
                                trf_val = as_decimal(r[val_idx])
                                tx = as_decimal(r[tx_idx])
                                entry = fo_types[tp]
                                entry["records"] += 1
                                entry["trades"] += tx
                                entry["vol"] += vol
                                entry["notional"] += trf_val

                                if tp in ("IDO", "STO"):
                                    strike = as_decimal(r[strk_idx])
                                    lot = as_decimal(r[lot_idx])
                                    opt_tp = r[opt_tp_idx].strip()
                                    strike_val = strike * vol * lot
                                    prem_val = trf_val - strike_val
                                    entry["premium"] += prem_val
                                    if opt_tp == "CE":
                                        entry["call_prem"] += prem_val
                                    elif opt_tp == "PE":
                                        entry["put_prem"] += prem_val
                                else:
                                    # For Futures, turnover equals TtlTrfVal
                                    entry["premium"] += trf_val

        for tp, data in fo_types.items():
            fo_breakdown_rows.append({
                "trade_date": trade_date,
                "instrument_type": tp,
                "records": data["records"],
                "trades": int(data["trades"]),
                "contracts": int(data["vol"]),
                "notional_crore": round(float(data["notional"] / Decimal(1e7)), 4),
                "premium_or_turnover_crore": round(float(data["premium"] / Decimal(1e7)), 4),
                "call_premium_crore": round(float(data.get("call_prem", Decimal(0)) / Decimal(1e7)), 4),
                "put_premium_crore": round(float(data.get("put_prem", Decimal(0)) / Decimal(1e7)), 4),
            })

        # 3. Delivery Data Alignment
        deliv_entry = delivery_map.get(trade_date, {})

        # 4. Master Daily Row
        daily_summary_rows.append({
            "trade_date": trade_date,
            "cm_records": cm_records,
            "cm_trades": int(cm_trades),
            "cm_traded_shares": int(cm_volume),
            "cm_total_turnover_cr": round(float(cm_total_val / Decimal(1e7)), 4),
            "cm_ordinary_equity_cr": round(float(cm_equity_val / Decimal(1e7)), 4),
            "cm_business_trust_cr": round(float(cm_trust_val / Decimal(1e7)), 4),
            "cm_etf_cr": round(float(cm_etf_val / Decimal(1e7)), 4),
            "cm_debt_cr": round(float(cm_debt_val / Decimal(1e7)), 4),
            "fut_index_turnover_cr": round(float(fo_types["IDF"]["premium"] / Decimal(1e7)), 4),
            "fut_stock_turnover_cr": round(float(fo_types["STF"]["premium"] / Decimal(1e7)), 4),
            "opt_index_premium_cr": round(float(fo_types["IDO"]["premium"] / Decimal(1e7)), 4),
            "opt_index_notional_cr": round(float(fo_types["IDO"]["notional"] / Decimal(1e7)), 4),
            "opt_stock_premium_cr": round(float(fo_types["STO"]["premium"] / Decimal(1e7)), 4),
            "opt_stock_notional_cr": round(float(fo_types["STO"]["notional"] / Decimal(1e7)), 4),
            "delivery_traded_qty": deliv_entry.get("traded_qty", ""),
            "delivery_deliv_qty": deliv_entry.get("deliv_qty", ""),
            "delivery_qty_pct": deliv_entry.get("deliv_pct", ""),
            "delivery_value_cr": deliv_entry.get("deliv_val_cr", ""),
            "delivery_value_pct": deliv_entry.get("deliv_val_pct", ""),
        })

    # Write output CSVs
    def write_csv(path: Path, rows: list, fields: list):
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)

    summary_fields = list(daily_summary_rows[0].keys())
    write_csv(PROCESSED_NSE / "nse_daily_summary.csv", daily_summary_rows, summary_fields)
    print(f"Created: {PROCESSED_NSE / 'nse_daily_summary.csv'} ({len(daily_summary_rows)} days)")

    fo_fields = list(fo_breakdown_rows[0].keys())
    write_csv(PROCESSED_NSE / "nse_fo_breakdown.csv", fo_breakdown_rows, fo_fields)
    print(f"Created: {PROCESSED_NSE / 'nse_fo_breakdown.csv'} ({len(fo_breakdown_rows)} rows)")

    cm_fields = list(cm_series_rows[0].keys())
    write_csv(PROCESSED_NSE / "nse_cm_series_breakdown.csv", cm_series_rows, cm_fields)
    print(f"Created: {PROCESSED_NSE / 'nse_cm_series_breakdown.csv'} ({len(cm_series_rows)} rows)")

    # Write delivery deduplicated table
    deliv_rows = sorted(delivery_map.values(), key=lambda x: x["date"])
    deliv_fields = ["date", "canonical_file", "traded_qty", "deliv_qty", "deliv_pct", "turnover_cr", "deliv_val_cr", "deliv_val_pct"]
    write_csv(PROCESSED_NSE / "nse_delivery_deduplicated.csv", deliv_rows, deliv_fields)
    print(f"Created: {PROCESSED_NSE / 'nse_delivery_deduplicated.csv'} ({len(deliv_rows)} days)")

if __name__ == "__main__":
    process_all_dates()
