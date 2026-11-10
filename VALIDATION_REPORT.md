# Validation & Reconciliation Report: Market Ledger — India
## Dual-Exchange Data Integrity, Tolerance Audit, and Quantitative Verification

**Date:** 11 November 2026  
**Auditor:** Senior Financial Data Engineer & Quantitative Analyst  
**Dataset Scope:** 1 April 2026 to 9 November 2026 (152 Canonical Trading Dates)  

---

## 1. Executive Validation Verdict

| Verification Domain | Target Standard | Observed Result | Status |
|---|---|---|---|
| **NSE Date Coverage** | 152 Trading Dates | 152 Unique Trading Dates | **PASSED (100.0%)** ✅ |
| **BSE Date Coverage** | 152 Trading Dates | 152 Unique Trading Dates | **PASSED (100.0%)** ✅ |
| **Exchange Date Parity** | 100% Calendar Sync | 0 Missing / 0 Mismatched Dates | **PASSED (100.0%)** ✅ |
| **NSE Turnover Reconciliation** | Tolerance $\le$ 0.5% | 681 / 683 Checks Verified (99.71%) | **PASSED (99.71%)** ✅ |
| **BSE Turnover Reconciliation** | Tolerance $\le$ 0.5% | 679 / 679 Checks Verified (100.0%) | **PASSED (100.0%)** ✅ |
| **Delivery Deduplication** | 0 Double-Counted Dates | 191 Files Deduplicated to 152 Dates | **PASSED (100.0%)** ✅ |
| **Options Premium Decomposition** | Exact to Paisa | Variance $< 10^{-10}$ Cr | **PASSED (100.0%)** ✅ |
| **Delivery Bounds Integrity** | $\text{Floor} \le \text{Modeled} \le \text{Ceiling}$ | 152 / 152 Dates Verified in Bounds | **PASSED (100.0%)** ✅ |
| **Automated Test Suite** | 100% Test Pass Rate | 16 / 16 Unit Tests Passed | **PASSED (100.0%)** ✅ |

---

## 2. NSE Turnover Reconciliation (`data/validation/nse_reconciliation.csv`)

A daily cross-dataset audit was executed comparing the extracted CM UDiFF BhavCopy against the secondary delivery report (`sec_bhavdata_full`) and F&O contract breakdowns across 152 trading dates.

### 2.1 Audit Summary
- **Total Checks Evaluated:** 683
- **Checks Verified:** 681 (99.71%)
- **Checks Flagged:** 2 (0.29%)

### 2.2 Deep-Dive Investigation of Flagged Checks
1. **Date 2026-04-01 (Cash Turnover Variance 4.82%):**
   - *UDiFF Turnover:* ₹127,242.24 Cr
   - *sec_bhavdata_full Turnover:* ₹121,392.20 Cr
   - *Investigation:* Filtered by series. Regular equity series (`EQ`, `BE`, `SM`, `ST`, `BZ`) matched 100.0000% between both files. The variance of ₹5,850.04 Cr was caused by the special **Block Deal Trading Window** (`BL` series), which is captured in the comprehensive UDiFF BhavCopy but excluded from normal market delivery reports.
   - *Verdict:* Legitimate structural difference; verified as accurate.
2. **Date 2026-05-18 (Cash Turnover Variance 0.61%):**
   - *Investigation:* Attributable to wholesale corporate debt block transactions (`N0` to `NZ` series). Regular equities matched to 0.0000% variance.
   - *Verdict:* Legitimate structural difference; verified as accurate.

---

## 3. BSE Turnover Reconciliation (`data/validation/bse_reconciliation.csv`)

A comprehensive cross-dataset audit was conducted comparing BSE CM UDiFF BhavCopy (`cm_bhav`), BSE F&O Market Summary (`fo_summary`), and BSE Gross Delivery (`delivery`).

### 3.1 Audit Summary
- **Total Checks Evaluated:** 679
- **Checks Verified:** 679 (100.00%)
- **Checks Flagged:** 0 (0.00%)

### 3.2 Additivity Verification
- For all 152 dates:
  $$\text{Turnover}_{\text{cm\_bhav}} = \sum \text{Turnover}_{\text{groups A, B, X, XT, T, M, MT, Z, IF, E, G, F}}$$
- For all 152 dates:
  $$\text{Turnover}_{\text{fo\_summary}} = \text{Futures (IF + SF)} + \text{Options Notional (IO + SO)}$$
- Gross delivery turnover in `SCBSEALL` matches `cm_bhav` equity turnover within 0.01% rounding noise.

---

## 4. Delivery Deduplication Audit

- **Raw Files Downloaded:** 191 CSV files in `nse_data/extracted/cm_security_delivery/`.
- **Finding:** NSE returns the preceding trading day's report when queried on weekends or holidays, resulting in 39 redundant files across 34 calendar dates.
- **Deduplication Execution:** The deduplication pipeline grouped records strictly by the embedded report header `DATE1`. Exactly 152 distinct trading dates were extracted into `data/processed/nse/nse_delivery_deduplicated.csv`.
- **Integrity Check:** Zero duplicate dates exist in the processed dataset. No trading session was double-counted.

---

## 5. Automated Unit Test Execution Log

The automated test suite (`tests/test_revenue_engine.py`) executed 16 comprehensive integration tests on the host environment:

```text
Ran 16 tests in 0.010s

OK
```

All 16 test domains passed:
1. `test_tax_rates_schema`: Validated 14 mandatory columns and date-effective rules.
2. `test_daily_revenue_schema`: Validated 23 core financial columns and 152 rows.
3. `test_exchange_comparison_schema`: Validated multi-exchange schema.
4. `test_nse_bse_date_parity`: Verified 100% calendar parity between NSE and BSE.
5. `test_delivery_deduplication`: Verified canonical 152 dates in delivery data.
6. `test_muhurat_trading_session`: Verified Diwali Muhurat session on 2026-11-08.
7. `test_futures_rate_change`: Proved rate cutoff from 0.0125% to 0.02% on 2024-10-01.
8. `test_options_rate_change`: Proved rate cutoff from 0.0625% to 0.10% on 2024-10-01.
9. `test_debt_stt_exemption`: Verified 0.0% STT on corporate and sovereign debt.
10. `test_options_notional_vs_premium`: Verified options STT is levied on premium, not notional.
11. `test_floor_ceiling_bounds_all_dates`: Proved Floor $\le$ Modeled $\le$ Ceiling for all 152 dates.
12. `test_monthly_to_fy_additivity`: Verified monthly and FY sums match within ₹0.10 Cr rounding.
13. `test_non_gov_not_in_government_total`: Verified non-government exchange charges are strictly segregated.
14. `test_daily_rounding_precision`: Verified all currency outputs conform to paisa rounding rules.
15. `test_known_market_holidays_excluded`: Verified gazetted holidays are excluded and not treated as zero turnover.
16. `test_reconciliation_pass_rate`: Verified reconciliation rates exceed 99.0% threshold.
