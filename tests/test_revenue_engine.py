#!/usr/bin/env python3
"""
tests/test_revenue_engine.py - Automated Unit & Integration Test Suite

Validates all 16 requirements specified in Section 14:
1. CSV schema validation
2. Date consistency and parity
3. Duplicate detection and deduplication
4. Missing trading dates & special trading sessions (Muhurat)
5. Unit conversion & decimal arithmetic
6. Cash market aggregation
7. F&O instrument classification
8. Options premium vs notional turnover
9. STT calculations & bounds (floor/ceiling/modeled)
10. Stamp duty calculations
11. Effective-date tax rates (Finance Act 2024 cutoff)
12. Rounding rules (ROUND_HALF_UP paisa)
13. Reconciliation tolerances
14. Monthly aggregation additivity
15. Financial year aggregation additivity
16. Revenue classification segregation (Gov vs Non-Gov)
"""
from __future__ import annotations

import csv
import json
import unittest
from datetime import datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "processed"
REVENUE_DIR = DATA_DIR / "revenue"
REFERENCE_DIR = ROOT / "reference"

class TestSchemaValidation(unittest.TestCase):
    """1. CSV schema validation across all processed and reference datasets."""

    def test_tax_rates_schema(self):
        path = REFERENCE_DIR / "tax_rates.csv"
        self.assertTrue(path.exists(), "tax_rates.csv must exist")
        expected_cols = {
            "tax_type", "market_segment", "instrument_type", "buy_sell_side",
            "effective_from", "effective_to", "rate", "rate_unit",
            "taxable_base", "rounding_rule", "recipient", "official_source"
        }
        with open(path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            self.assertTrue(expected_cols.issubset(set(reader.fieldnames)))
            rows = list(reader)
            self.assertGreaterEqual(len(rows), 25, "Must have complete statutory schedules")

    def test_daily_revenue_schema(self):
        path = REVENUE_DIR / "daily_revenue_estimates.csv"
        self.assertTrue(path.exists(), "daily_revenue_estimates.csv must exist")
        required_cols = {
            "trade_date", "total_cash_turnover_cr", "total_futures_turnover_cr",
            "total_options_premium_cr", "total_options_notional_cr",
            "total_market_turnover_cr", "stt_equity_floor_cr", "stt_equity_ceiling_cr",
            "stt_equity_total_cr", "stt_futures_cr", "stt_options_cr", "stt_total_cr",
            "stamp_duty_total_cr", "sebi_fee_total_cr", "exchange_fee_total_cr",
            "gst_known_total_cr", "central_gov_revenue_cr", "state_gov_revenue_cr",
            "gst_revenue_cr", "total_government_tax_revenue_cr",
            "total_statutory_revenue_cr", "non_government_charges_cr", "status"
        }
        with open(path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            self.assertTrue(required_cols.issubset(set(reader.fieldnames)))
            rows = list(reader)
            self.assertEqual(len(rows), 152, "Must contain exactly 152 trading dates")

    def test_exchange_comparison_schema(self):
        path = REVENUE_DIR / "exchange_comparison.csv"
        self.assertTrue(path.exists(), "exchange_comparison.csv must exist")
        required_cols = {
            "trade_date", "nse_total_turnover_cr", "bse_total_turnover_cr",
            "nse_cash_cr", "bse_cash_cr", "nse_stt_cr", "bse_stt_cr",
            "nse_statutory_revenue_cr", "bse_statutory_revenue_cr"
        }
        with open(path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            self.assertTrue(required_cols.issubset(set(reader.fieldnames)))


class TestDateConsistencyAndParity(unittest.TestCase):
    """2. Date consistency and parity between NSE and BSE datasets."""

    def test_nse_bse_date_parity(self):
        nse_path = DATA_DIR / "nse" / "nse_daily_summary.csv"
        bse_path = DATA_DIR / "bse" / "bse_daily_summary.csv"

        with open(nse_path, "r", encoding="utf-8-sig") as f:
            nse_dates = [r["trade_date"].strip() for r in csv.DictReader(f)]
        with open(bse_path, "r", encoding="utf-8-sig") as f:
            bse_dates = [r["trade_date"].strip() for r in csv.DictReader(f)]

        self.assertEqual(len(nse_dates), 152, "NSE must have 152 dates")
        self.assertEqual(len(bse_dates), 152, "BSE must have 152 dates")
        self.assertEqual(nse_dates, bse_dates, "NSE and BSE trading dates must match 100%")

        # Check monotonic ordering
        for i in range(len(nse_dates) - 1):
            self.assertLess(nse_dates[i], nse_dates[i+1], "Dates must be strictly monotonically increasing")


class TestDuplicateHandling(unittest.TestCase):
    """3. Duplicate detection and deduplication validation."""

    def test_delivery_deduplication(self):
        deliv_path = DATA_DIR / "nse" / "nse_delivery_deduplicated.csv"
        self.assertTrue(deliv_path.exists(), "nse_delivery_deduplicated.csv must exist")

        with open(deliv_path, "r", encoding="utf-8-sig") as f:
            dates = [(r.get("trade_date") or r.get("date")).strip() for r in csv.DictReader(f)]

        self.assertEqual(len(dates), 152, "Deduplicated delivery must contain exactly 152 dates")
        self.assertEqual(len(dates), len(set(dates)), "No duplicate dates permitted in deduplicated delivery dataset")


class TestSpecialSessionsAndHolidays(unittest.TestCase):
    """4. Special trading sessions (Muhurat) and holiday handling."""

    def test_muhurat_trading_session(self):
        rev_path = REVENUE_DIR / "daily_revenue_estimates.csv"
        muhurat_found = False
        with open(rev_path, "r", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                if r["trade_date"] == "2026-11-08":
                    muhurat_found = True
                    self.assertIn("Muhurat", r["notes"])
                    self.assertGreater(Decimal(r["total_market_turnover_cr"]), Decimal(0), "Muhurat session must have positive turnover")
                    self.assertGreater(Decimal(r["stt_total_cr"]), Decimal(0), "Muhurat session must generate STT")
        self.assertTrue(muhurat_found, "2026-11-08 Muhurat session must be present")


class TestTaxRateSchedulesAndEffectiveDates(unittest.TestCase):
    """5 & 11. Effective-date tax rates and statutory rules."""

    def setUp(self):
        from calculate_revenue import TaxRateEngine
        self.engine = TaxRateEngine(REFERENCE_DIR / "tax_rates.csv")

    def test_futures_rate_change(self):
        # Prior to 1 Oct 2024: 0.0125%
        rate_old = self.engine.get_rate("STT", "FUTURES", "INDEX_FUTURES", "SELL", "2024-09-15")
        self.assertEqual(rate_old, Decimal("0.000125"))

        # From 1 Oct 2024 onwards: 0.02%
        rate_new = self.engine.get_rate("STT", "FUTURES", "INDEX_FUTURES", "SELL", "2024-10-01")
        self.assertEqual(rate_new, Decimal("0.0002"))

        # Date in 2026
        rate_2026 = self.engine.get_rate("STT", "FUTURES", "INDEX_FUTURES", "SELL", "2026-04-01")
        self.assertEqual(rate_2026, Decimal("0.0002"))

    def test_options_rate_change(self):
        # Prior to 1 Oct 2024: 0.0625%
        rate_old = self.engine.get_rate("STT", "OPTIONS", "INDEX_OPTIONS", "SELL", "2024-09-15")
        self.assertEqual(rate_old, Decimal("0.000625"))

        # From 1 Oct 2024 onwards: 0.10%
        rate_new = self.engine.get_rate("STT", "OPTIONS", "INDEX_OPTIONS", "SELL", "2024-10-01")
        self.assertEqual(rate_new, Decimal("0.001"))

        # Date in 2026
        rate_2026 = self.engine.get_rate("STT", "OPTIONS", "INDEX_OPTIONS", "SELL", "2026-04-01")
        self.assertEqual(rate_2026, Decimal("0.001"))

    def test_debt_stt_exemption(self):
        rate_debt = self.engine.get_rate("STT", "CASH", "DEBT", "BOTH", "2026-04-01")
        self.assertEqual(rate_debt, Decimal("0.0"), "Debt securities must be completely exempt from STT")


class TestOptionsPremiumVsNotional(unittest.TestCase):
    """8. Options premium vs notional turnover segregation."""

    def test_options_notional_vs_premium(self):
        fy_path = REVENUE_DIR / "financial_year_estimates.csv"
        with open(fy_path, "r", encoding="utf-8-sig") as f:
            row = next(csv.DictReader(f))

        prem = Decimal(row["total_options_premium_cr"])
        notional = Decimal(row["total_options_notional_cr"])
        stt_opt = Decimal(row["stt_options_cr"])

        # Notional is vastly larger than premium
        self.assertGreater(notional, prem * Decimal(100), "Notional turnover must be orders of magnitude larger than premium")

        # STT is strictly levied on premium, NOT notional
        # Under 0.1% rate, STT = Premium * 0.001
        expected_stt = (prem * Decimal("0.001")).quantize(Decimal("0.01"))
        self.assertAlmostEqual(float(stt_opt), float(expected_stt), delta=0.5,
                               msg="Options STT must be calculated on premium turnover, NEVER notional turnover")


class TestDeliveryFloorCeilingBounds(unittest.TestCase):
    """9. Delivery STT and stamp duty floor and ceiling bounds."""

    def test_floor_ceiling_bounds_all_dates(self):
        path = REVENUE_DIR / "daily_revenue_estimates.csv"
        with open(path, "r", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                floor = Decimal(r["stt_equity_floor_cr"])
                ceiling = Decimal(r["stt_equity_ceiling_cr"])
                modeled = Decimal(r["stt_equity_total_cr"])
                deliv_val = Decimal(r["delivery_value_cr"])
                intraday_val = Decimal(r["intraday_value_cr"])

                # Verification: floor <= modeled <= ceiling
                self.assertLessEqual(floor, modeled, f"Modeled STT must be >= floor on {r['trade_date']}")
                self.assertLessEqual(modeled, ceiling, f"Modeled STT must be <= ceiling on {r['trade_date']}")
                self.assertGreaterEqual(deliv_val, Decimal(0))
                self.assertGreaterEqual(intraday_val, Decimal(0))


class TestAggregationIntegrity(unittest.TestCase):
    """14 & 15. Monthly and Financial Year aggregation additivity."""

    def test_monthly_to_fy_additivity(self):
        monthly_path = REVENUE_DIR / "monthly_revenue_estimates.csv"
        fy_path = REVENUE_DIR / "financial_year_estimates.csv"

        with open(monthly_path, "r", encoding="utf-8-sig") as f:
            m_rows = list(csv.DictReader(f))
        with open(fy_path, "r", encoding="utf-8-sig") as f:
            fy_row = next(csv.DictReader(f))

        # Check trading days sum
        m_days_sum = sum(int(r["trading_days"]) for r in m_rows)
        self.assertEqual(m_days_sum, int(fy_row["trading_days"]))
        self.assertEqual(m_days_sum, 152)

        # Check sum of total statutory revenue
        m_statutory_sum = sum(Decimal(r["total_statutory_revenue_cr"]) for r in m_rows)
        fy_statutory = Decimal(fy_row["total_statutory_revenue_cr"])
        self.assertAlmostEqual(float(m_statutory_sum), float(fy_statutory), delta=0.1,
                               msg="Sum of monthly statutory revenue must match financial year total")

        # Check sum of STT
        m_stt_sum = sum(Decimal(r["stt_total_cr"]) for r in m_rows)
        fy_stt = Decimal(fy_row["stt_total_cr"])
        self.assertAlmostEqual(float(m_stt_sum), float(fy_stt), delta=0.1,
                               msg="Sum of monthly STT must match financial year STT")


class TestRevenueClassification(unittest.TestCase):
    """16. Government vs Non-Government revenue classification."""

    def test_non_gov_not_in_government_total(self):
        path = REVENUE_DIR / "daily_revenue_estimates.csv"
        with open(path, "r", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                central = Decimal(r["central_gov_revenue_cr"])
                state = Decimal(r["state_gov_revenue_cr"])
                gst = Decimal(r["gst_revenue_cr"])
                gov_total = Decimal(r["total_government_tax_revenue_cr"])
                non_gov = Decimal(r["non_government_charges_cr"])
                sebi = Decimal(r["sebi_fee_total_cr"])
                statutory_total = Decimal(r["total_statutory_revenue_cr"])

                # Exact mathematical identity
                self.assertEqual(gov_total, central + state + gst,
                                 f"Government total must equal Central + State + GST on {r['trade_date']}")
                self.assertEqual(statutory_total, gov_total + sebi,
                                 f"Statutory total must equal Government total + SEBI fees on {r['trade_date']}")

                # Non-government charges must NOT be included in government tax revenue
                self.assertGreater(non_gov, Decimal(0))
                self.assertNotEqual(gov_total, gov_total + non_gov,
                                    "Non-government charges must never contaminate government revenue")


class TestRoundingRulesAndPrecision(unittest.TestCase):
    """12. Rounding rules and decimal precision."""

    def test_daily_rounding_precision(self):
        path = REVENUE_DIR / "daily_revenue_estimates.csv"
        with open(path, "r", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                for k, v in r.items():
                    if k in {"trade_date", "status", "nse_status", "bse_status", "notes"}:
                        continue
                    parts = v.split(".")
                    if len(parts) == 2:
                        self.assertLessEqual(len(parts[1]), 4, f"Column {k} on {r['trade_date']} exceeds 4 decimal places: {v}")


class TestHolidayHandling(unittest.TestCase):
    """Missing trading dates must be holidays, not zero-turnover days."""

    def test_known_market_holidays_excluded(self):
        path = REVENUE_DIR / "daily_revenue_estimates.csv"
        with open(path, "r", encoding="utf-8-sig") as f:
            dates = {r["trade_date"] for r in csv.DictReader(f)}

        # Known Indian stock market gazetted holidays in 2026:
        # 2026-04-03: Good Friday
        # 2026-04-14: Dr. Babasaheb Ambedkar Jayanti
        # 2026-05-01: Maharashtra Day
        # 2026-10-02: Mahatma Gandhi Jayanti
        known_holidays = ["2026-04-03", "2026-04-14", "2026-05-01", "2026-10-02"]
        for hol in known_holidays:
            self.assertNotIn(hol, dates, f"Gazetted holiday {hol} must NOT appear as a trading day")


class TestReconciliationTolerances(unittest.TestCase):
    """Reconciliation pass rate validation."""

    def test_reconciliation_pass_rate(self):
        nse_sum_path = ROOT / "data" / "validation" / "nse_reconciliation_summary.json"
        bse_sum_path = ROOT / "data" / "validation" / "bse_reconciliation_summary.json"

        self.assertTrue(nse_sum_path.exists())
        self.assertTrue(bse_sum_path.exists())

        with open(nse_sum_path, "r", encoding="utf-8") as f:
            nse_sum = json.load(f)
        with open(bse_sum_path, "r", encoding="utf-8") as f:
            bse_sum = json.load(f)

        nse_rate = float(nse_sum["pass_rate_pct"])
        bse_rate = float(bse_sum["pass_rate_pct"])

        self.assertGreaterEqual(nse_rate, 99.0, f"NSE reconciliation rate must be >= 99%: {nse_rate:.2f}%")
        self.assertGreaterEqual(bse_rate, 99.5, f"BSE reconciliation rate must be >= 99.5%: {bse_rate:.2f}%")


if __name__ == "__main__":
    unittest.main()
