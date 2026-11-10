import csv
import glob
import os
from collections import Counter
from decimal import Decimal, InvalidOperation

ROOT = os.path.dirname(os.path.abspath(__file__))
DATASETS = {
    "CM cash": os.path.join(ROOT, "nse_data", "extracted", "cm_udiff"),
    "FO derivatives": os.path.join(ROOT, "nse_data", "extracted", "fo_udiff"),
}
DATES_TO_CHECK = ("20261109", "20261108")
VALUE_COLUMNS = ("TtlTradgVol", "TtlTrfVal", "TtlNbOfTxsExctd")
CATEGORY_COLUMNS = ("FinInstrmTp", "SctySrs", "FinInstrmNm")


def as_decimal(value):
    value = (value or "").strip().replace(",", "")
    if not value or value.upper() in {"NA", "N/A", "NULL", "NAN", "-"}:
        return Decimal(0)
    try:
        return Decimal(value)
    except InvalidOperation:
        return Decimal(0)


def find_csv(folder, date_token):
    candidates = glob.glob(os.path.join(folder, f"*{date_token}*.csv"))
    if not candidates:
        candidates = glob.glob(os.path.join(folder, "*.csv"))
        candidates.sort(key=os.path.getmtime, reverse=True)
        return candidates[0] if candidates else None
    candidates.sort(key=os.path.getmtime, reverse=True)
    return candidates[0]


def inspect(label, folder, date_token):
    path = find_csv(folder, date_token)
    print("\n" + "=" * 72)
    print(f"{label} | requested date: {date_token}")
    if not path:
        print(f"No extracted CSV found in: {folder}")
        return

    print("File:", os.path.relpath(path, ROOT))
    counts = {column: Counter() for column in CATEGORY_COLUMNS}
    totals = {column: Decimal(0) for column in VALUE_COLUMNS}
    row_count = 0
    trade_dates = Counter()
    business_dates = Counter()
    missing_columns = set()

    with open(path, "r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        print("Columns present:", len(headers))
        for required in (*CATEGORY_COLUMNS, *VALUE_COLUMNS, "TradDt", "BizDt"):
            if required not in headers:
                missing_columns.add(required)

        for row in reader:
            row_count += 1
            if row.get("TradDt"):
                trade_dates[row["TradDt"].strip()] += 1
            if row.get("BizDt"):
                business_dates[row["BizDt"].strip()] += 1
            for column in CATEGORY_COLUMNS:
                value = (row.get(column) or "").strip() or "(blank)"
                counts[column][value] += 1
            for column in VALUE_COLUMNS:
                totals[column] += as_decimal(row.get(column))

    print("Rows:", row_count)
    print("TradDt:", dict(trade_dates))
    print("BizDt:", dict(business_dates))
    if missing_columns:
        print("Missing expected columns:", ", ".join(sorted(missing_columns)))

    for column in CATEGORY_COLUMNS:
        print(f"\n{column} values (top 20):")
        for value, count in counts[column].most_common(20):
            print(f"  {value}: {count}")

    print("\nRaw column totals (NOT YET VERIFIED AS TURNOVER):")
    for column, total in totals.items():
        print(f"  {column}: {total:,.4f}")


def main():
    print("NSE UDiFF field inspection")
    print("This is a field/schema audit only; it does not calculate taxes or revenue.")
    for label, folder in DATASETS.items():
        for date_token in DATES_TO_CHECK:
            inspect(label, folder, date_token)


if __name__ == "__main__":
    main()
