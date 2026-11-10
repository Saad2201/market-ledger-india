#!/usr/bin/env python3
"""
bse_validate_datasets.py - Deterministic BSE Field & Instrument Validation Pipeline

Audits, normalizes, and aggregates all 152 historical BSE trading dates (2026-04-01 to 2026-11-09).
- Separates CM groups using reference/bse_security_groups.csv
- Calculates exact Options Premium Turnover from MS_<date>-01.csv: Traded Value - (Strike * Qty)
- Computes Gross Delivery volume, value, and percentages
- Uses Decimal for financial precision. Zero third-party dependencies.
"""
from __future__ import annotations

import csv
import glob
import io
import json
import os
import zipfile
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BSE_DATA = ROOT / "bse_data"
REFERENCE = ROOT / "reference"
PROCESSED_BSE = ROOT / "data" / "processed" / "bse"

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

def load_bse_group_map() -> dict:
    group_map = {}
    path = REFERENCE / "bse_security_groups.csv"
    if path.exists():
        with path.open("r", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                group_map[row["group_code"].strip()] = {
                    "include_in_equity": row.get("include_in_equity_turnover", "FALSE").upper() == "TRUE",
                    "stt_applicable": row.get("stt_applicable", "FALSE").upper() == "TRUE",
                    "category": row.get("instrument_category", "Other"),
                }
    return group_map

def summarize_bse_delivery_file(path: Path) -> dict:
    try:
        with zipfile.ZipFile(path) as z:
            name = z.namelist()[0]
            raw = z.read(name).decode("latin-1")
    except Exception as exc:
        print(f"[warn] Delivery read failed for {path.name}: {exc}")
        return {}

    lines = raw.splitlines()
    if not lines:
        return {}
    first_line = lines[0]
    sep = max([",", "|", "\t", ";"], key=first_line.count)
    reader = csv.reader(io.StringIO(raw), delimiter=sep)
    header = next(reader, None)
    if not header:
        return {}
    header = [h.strip().upper() for h in header]

    def find_col(*substrings):
        for sub in substrings:
            for i, h in enumerate(header):
                if sub in h:
                    return i
        return None

    tq_idx = find_col("VOLUME", "TRADED QTY", "QTY TRADED")
    dq_idx = find_col("DELIVERY QTY", "DELIVERABLE QTY")
    turn_idx = find_col("TURNOVER")
    dval_idx = find_col("DELIVERY VAL", "DELIVERABLE VAL")

    ttl_qty = Decimal(0)
    deliv_qty = Decimal(0)
    turnover_rupees = Decimal(0)
    deliv_val_rupees = Decimal(0)

    for row in reader:
        if tq_idx is not None and len(row) > tq_idx:
            ttl_qty += as_decimal(row[tq_idx])
        if dq_idx is not None and len(row) > dq_idx:
            deliv_qty += as_decimal(row[dq_idx])
        if turn_idx is not None and len(row) > turn_idx:
            turnover_rupees += as_decimal(row[turn_idx])
        if dval_idx is not None and len(row) > dval_idx:
            deliv_val_rupees += as_decimal(row[dval_idx])

    deliv_pct = (deliv_qty / ttl_qty * 100) if ttl_qty > 0 else Decimal(0)
    turnover_cr = turnover_rupees / Decimal(1e7)
    deliv_val_cr = deliv_val_rupees / Decimal(1e7)
    deliv_val_pct = (deliv_val_cr / turnover_cr * 100) if turnover_cr > 0 else Decimal(0)

    return {
        "traded_qty": int(ttl_qty),
        "deliv_qty": int(deliv_qty),
        "deliv_pct": round(float(deliv_pct), 2),
        "turnover_cr": round(float(turnover_cr), 4),
        "deliv_val_cr": round(float(deliv_val_cr), 4),
        "deliv_val_pct": round(float(deliv_val_pct), 2),
    }

def process_all_bse_dates():
    PROCESSED_BSE.mkdir(parents=True, exist_ok=True)
    group_map = load_bse_group_map()

    raw_cm = sorted(glob.glob(str(BSE_DATA / "raw" / "cm_bhav" / "*.csv")))
    raw_fo = sorted(glob.glob(str(BSE_DATA / "raw" / "fo_summary" / "*.csv")))
    raw_del = sorted(glob.glob(str(BSE_DATA / "raw" / "delivery" / "*.zip")))

    fo_by_date = {}
    for f in raw_fo:
        d = os.path.basename(f)[3:11] if os.path.basename(f).startswith("MS_") else os.path.basename(f)[:8]
        iso_d = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
        fo_by_date[iso_d] = f

    del_by_date = {}
    for f in raw_del:
        d = os.path.basename(f)[:8]
        iso_d = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
        del_by_date[iso_d] = f

    daily_summary_rows = []
    fo_breakdown_rows = []
    cm_group_rows = []
    delivery_summary_rows = []
    fo_types_map = {}

    print(f"Processing {len(raw_cm)} BSE CM files and {len(raw_fo)} BSE FO files...")

    for cm_path in raw_cm:
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

        group_aggregates = defaultdict(lambda: {"count": 0, "volume": Decimal(0), "value": Decimal(0), "trades": Decimal(0)})

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

                        group_aggregates[srs]["count"] += 1
                        group_aggregates[srs]["volume"] += vol
                        group_aggregates[srs]["value"] += val
                        group_aggregates[srs]["trades"] += tx

                        meta = group_map.get(srs, {})
                        cat = meta.get("category", "")
                        if meta.get("include_in_equity", False):
                            cm_equity_val += val
                        elif cat == "Units of Business Trust":
                            cm_trust_val += val
                        elif cat == "ETF":
                            cm_etf_val += val
                        else:
                            cm_debt_val += val

        for grp, g_data in group_aggregates.items():
            cm_group_rows.append({
                "trade_date": trade_date,
                "group_code": grp,
                "records": g_data["count"],
                "traded_shares": int(g_data["volume"]),
                "turnover_rupees": str(g_data["value"]),
                "turnover_crore": round(float(g_data["value"] / Decimal(1e7)), 4),
                "trades": int(g_data["trades"]),
            })

        # 2. Process FO Summary
        fo_path = fo_by_date.get(trade_date)
        fo_types = {
            "IF": {"records": 0, "trades": Decimal(0), "qty": Decimal(0), "notional": Decimal(0), "premium": Decimal(0)},
            "SF": {"records": 0, "trades": Decimal(0), "qty": Decimal(0), "notional": Decimal(0), "premium": Decimal(0)},
            "IO": {"records": 0, "trades": Decimal(0), "qty": Decimal(0), "notional": Decimal(0), "premium": Decimal(0), "call_prem": Decimal(0), "put_prem": Decimal(0), "call_notional": Decimal(0), "put_notional": Decimal(0)},
            "SO": {"records": 0, "trades": Decimal(0), "qty": Decimal(0), "notional": Decimal(0), "premium": Decimal(0), "call_prem": Decimal(0), "put_prem": Decimal(0), "call_notional": Decimal(0), "put_notional": Decimal(0)},
        }

        if fo_path:
            with open(fo_path, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if header:
                    h_map = {name.strip(): i for i, name in enumerate(header)}
                    pt_idx = h_map.get("Product Type")
                    ot_idx = h_map.get("Option Type (Call/Put)")
                    strk_idx = h_map.get("Strike Price")
                    qty_idx = h_map.get("Total Traded Quantity")
                    val_idx = h_map.get("Total Traded Value (in Thousands)(absolute)")
                    tx_idx = h_map.get("Total Trades")

                    for r in reader:
                        if len(r) > max(pt_idx, qty_idx, val_idx):
                            pt = r[pt_idx].strip().upper()
                            if pt in fo_types:
                                ot = r[ot_idx].strip().upper() if ot_idx is not None and len(r) > ot_idx else ""
                                strike = as_decimal(r[strk_idx]) if strk_idx is not None and len(r) > strk_idx else Decimal(0)
                                qty = as_decimal(r[qty_idx])
                                # Total Traded Value is in Thousands of Rupees
                                val_rupees = as_decimal(r[val_idx]) * Decimal(1000)
                                tx = as_decimal(r[tx_idx]) if tx_idx is not None and len(r) > tx_idx else Decimal(0)

                                entry = fo_types[pt]
                                entry["records"] += 1
                                entry["trades"] += tx
                                entry["qty"] += qty
                                entry["notional"] += val_rupees

                                if pt in ("IO", "SO"):
                                    strike_val = strike * qty
                                    prem_val = val_rupees - strike_val
                                    entry["premium"] += prem_val
                                    if ot == "CE":
                                        entry["call_prem"] += prem_val
                                        entry["call_notional"] += val_rupees
                                    elif ot == "PE":
                                        entry["put_prem"] += prem_val
                                        entry["put_notional"] += val_rupees
                                else:
                                    entry["premium"] += val_rupees

        fo_types_map[trade_date] = fo_types

        for pt, data in fo_types.items():
            fo_breakdown_rows.append({
                "trade_date": trade_date,
                "product_type": pt,
                "records": data["records"],
                "trades": int(data["trades"]),
                "quantity": int(data["qty"]),
                "notional_crore": round(float(data["notional"] / Decimal(1e7)), 4),
                "premium_or_turnover_crore": round(float(data["premium"] / Decimal(1e7)), 4),
                "call_premium_crore": round(float(data.get("call_prem", Decimal(0)) / Decimal(1e7)), 4),
                "put_premium_crore": round(float(data.get("put_prem", Decimal(0)) / Decimal(1e7)), 4),
            })

        # 3. Delivery Data Alignment
        del_path = del_by_date.get(trade_date)
        del_data = summarize_bse_delivery_file(Path(del_path)) if del_path else {}
        if del_data:
            delivery_summary_rows.append({
                "trade_date": trade_date,
                "file_name": os.path.basename(del_path),
                **del_data
            })

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
            "fut_index_turnover_cr": round(float(fo_types["IF"]["premium"] / Decimal(1e7)), 4),
            "fut_stock_turnover_cr": round(float(fo_types["SF"]["premium"] / Decimal(1e7)), 4),
            "opt_index_premium_cr": round(float(fo_types["IO"]["premium"] / Decimal(1e7)), 4),
            "opt_index_notional_cr": round(float(fo_types["IO"]["notional"] / Decimal(1e7)), 4),
            "opt_stock_premium_cr": round(float(fo_types["SO"]["premium"] / Decimal(1e7)), 4),
            "opt_stock_notional_cr": round(float(fo_types["SO"]["notional"] / Decimal(1e7)), 4),
            "delivery_traded_qty": del_data.get("traded_qty", ""),
            "delivery_deliv_qty": del_data.get("deliv_qty", ""),
            "delivery_qty_pct": del_data.get("deliv_pct", ""),
            "delivery_value_cr": del_data.get("deliv_val_cr", ""),
            "delivery_value_pct": del_data.get("deliv_val_pct", ""),
        })

    def write_csv(path: Path, rows: list, fields: list):
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)

    summary_fields = list(daily_summary_rows[0].keys())
    write_csv(PROCESSED_BSE / "bse_daily_summary.csv", daily_summary_rows, summary_fields)
    print(f"Created: {PROCESSED_BSE / 'bse_daily_summary.csv'} ({len(daily_summary_rows)} days)")

    fo_fields = list(fo_breakdown_rows[0].keys())
    write_csv(PROCESSED_BSE / "bse_fo_breakdown.csv", fo_breakdown_rows, fo_fields)
    print(f"Created: {PROCESSED_BSE / 'bse_fo_breakdown.csv'} ({len(fo_breakdown_rows)} rows)")

    cm_fields = list(cm_group_rows[0].keys())
    write_csv(PROCESSED_BSE / "bse_cm_group_breakdown.csv", cm_group_rows, cm_fields)
    print(f"Created: {PROCESSED_BSE / 'bse_cm_group_breakdown.csv'} ({len(cm_group_rows)} rows)")

    del_fields = list(delivery_summary_rows[0].keys())
    write_csv(PROCESSED_BSE / "bse_delivery_summary.csv", delivery_summary_rows, del_fields)
    print(f"Created: {PROCESSED_BSE / 'bse_delivery_summary.csv'} ({len(delivery_summary_rows)} days)")

    # Also update bse_data/daily_cash.csv, daily_fo.csv, daily_delivery.csv, docs/data.json
    bse_cash_rows = [
        {
            "date": r["trade_date"],
            "turnover_cr": r["cm_total_turnover_cr"],
            "volume": r["cm_traded_shares"],
            "trades": r["cm_trades"],
            "securities": r["cm_records"],
            "turnover_cr_STK": r["cm_ordinary_equity_cr"],
        }
        for r in daily_summary_rows
    ]
    write_csv(BSE_DATA / "daily_cash.csv", bse_cash_rows, list(bse_cash_rows[0].keys()))

    bse_fo_rows = [
        {
            "date": r["trade_date"],
            "fut_idx_turnover_cr": r["fut_index_turnover_cr"],
            "fut_stk_turnover_cr": r["fut_stock_turnover_cr"],
            "opt_idx_call_notional_cr": round(float(fo_types_map[r["trade_date"]]["IO"]["call_notional"] / Decimal(1e7)), 2),
            "opt_idx_call_premium_cr": round(float(fo_types_map[r["trade_date"]]["IO"]["call_prem"] / Decimal(1e7)), 2),
            "opt_idx_put_notional_cr": round(float(fo_types_map[r["trade_date"]]["IO"]["put_notional"] / Decimal(1e7)), 2),
            "opt_idx_put_premium_cr": round(float(fo_types_map[r["trade_date"]]["IO"]["put_prem"] / Decimal(1e7)), 2),
            "opt_stk_call_notional_cr": round(float(fo_types_map[r["trade_date"]]["SO"]["call_notional"] / Decimal(1e7)), 2),
            "opt_stk_call_premium_cr": round(float(fo_types_map[r["trade_date"]]["SO"]["call_prem"] / Decimal(1e7)), 2),
            "opt_stk_put_notional_cr": round(float(fo_types_map[r["trade_date"]]["SO"]["put_notional"] / Decimal(1e7)), 2),
            "opt_stk_put_premium_cr": round(float(fo_types_map[r["trade_date"]]["SO"]["put_prem"] / Decimal(1e7)), 2),
            "fut_turnover_cr": round(float(r["fut_index_turnover_cr"] + r["fut_stock_turnover_cr"]), 2),
            "opt_notional_cr": round(float(r["opt_index_notional_cr"] + r["opt_stock_notional_cr"]), 2),
            "opt_premium_cr": round(float(r["opt_index_premium_cr"] + r["opt_stock_premium_cr"]), 2),
        }
        for r in daily_summary_rows
    ]
    write_csv(BSE_DATA / "daily_fo.csv", bse_fo_rows, list(bse_fo_rows[0].keys()))

    # Update docs/data.json
    days_payload = []
    del_map = {r["trade_date"]: r for r in delivery_summary_rows}
    for r in daily_summary_rows:
        t_d = r["trade_date"]
        d_item = del_map.get(t_d, {})
        dp = d_item.get("deliv_val_pct") or d_item.get("deliv_pct")
        days_payload.append({
            "d": t_d,
            "c": r["cm_total_turnover_cr"],
            "f": round(float(r["fut_index_turnover_cr"] + r["fut_stock_turnover_cr"]), 2),
            "o": round(float(r["opt_index_premium_cr"] + r["opt_stock_premium_cr"]), 2),
            "on": round(float(r["opt_index_notional_cr"] + r["opt_stock_notional_cr"]), 2),
            "dp": dp if dp else None,
        })
    site_payload = {
        "updated": datetime.now().strftime("%Y-%m-%dT%H:%M+05:30"),
        "days": days_payload,
    }
    (ROOT / "docs" / "data.json").write_text(json.dumps(site_payload), encoding="utf-8")
    print(f"Updated: {ROOT / 'docs' / 'data.json'} ({len(days_payload)} days)")

if __name__ == "__main__":
    process_all_bse_dates()
