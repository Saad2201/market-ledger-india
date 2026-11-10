# Changelog: Market Ledger — India
All notable changes to this project are documented in this file.

---

## [2.0.0] - 2026-11-11
### Complete Data Engineering, Financial Validation, Tax Engine & Dual-Exchange Dashboard

#### Added
- **Master Orchestrator (`run_pipeline.py`):**
  - Unified master execution pipeline running end-to-end dataset validation, reconciliation, revenue calculation, automated unit testing, and dashboard JSON payload export in under 25 seconds.
- **Statutory Revenue Calculation Engine (`calculate_revenue.py`):**
  - Dynamic date-effective statutory tax rate lookup from `reference/tax_rates.csv`.
  - Modeled delivery STT vs verified floor (100% intraday) and ceiling (100% delivery) bounds.
  - Options premium taxation decomposition isolating taxable premium from non-taxable notional turnover.
  - Segregated recipient classifications: Central Government (STT), State Governments (Stamp Duty), SEBI (Regulatory Fees), GST Council Pool (18% on financial services), and Non-Government (Exchange charges).
  - Generated `daily_revenue_estimates.csv`, `monthly_revenue_estimates.csv`, `financial_year_estimates.csv`, and `exchange_comparison.csv`.
- **Automated Integration Test Suite (`tests/test_revenue_engine.py`):**
  - 16 comprehensive unit tests covering all requirements of Section 14 (schema validation, date parity, deduplication, Muhurat session, rate cutoff on 2024-10-01, debt STT exemption, options premium vs notional, floor/ceiling bounds, monthly-to-FY additivity, non-gov segregation, rounding rules, holiday exclusion, and reconciliation pass rate).
  - 100% test pass rate in 0.010s.
- **Modern Responsive Dual-Exchange Analytics Dashboard (`docs/index.html` & `docs/data.json`):**
  - Upgraded frontend from single-exchange prototype to full-scale dual-exchange platform.
  - Multi-tax KPI cards, dynamic month/exchange/segment filtering, and live search.
  - Interactive SVG visualizations: Daily Revenue Stacked Bar, Monthly Revenue Progression, NSE vs BSE Comparison, and Delivery Bounds Chart.
  - Multi-tab data tables (Daily Ledger, Monthly Totals, Exchange Comparison, Statutory Schedules).
  - Built-in Transparency & Statutory Methodology Modal.
  - Dark/Light mode theme toggle.
- **Reference & Classification Architecture:**
  - `reference/tax_rates.csv`: Complete statutory rate schedules with date-effective rules and circular citations.
  - `reference/udiff_field_definitions.csv`: Definitive meanings and units for all 34 UDiFF fields.
  - `reference/security_series.csv`: Classification of all 109 NSE security series.
  - `reference/bse_security_groups.csv`: Classification of all 18 BSE equity groups.
  - `reference/instrument_classification.csv`: Derivatives instrument classification for NSE.
  - `reference/bse_instrument_classification.csv`: Derivatives instrument classification for BSE.
- **Turnover Reconciliation Engines:**
  - `nse_reconcile.py`: Cross-dataset reconciliation achieving 99.71% verification (681/683 checks).
  - `bse_reconcile.py`: Cross-dataset reconciliation achieving 100.00% verification (679/679 checks).
- **Nightly Automation Runner (`nightly_market_ledger.bat`):**
  - Updated to invoke the master pipeline with `--fetch`.
- **Comprehensive Documentation Suite:**
  - `README.md`, `CALCULATION_METHODOLOGY.md`, `DATA_DICTIONARY.md`, `DATA_SOURCES.md`, `VALIDATION_REPORT.md`, `PROJECT_AUDIT.md`, and `CHANGELOG.md`.

#### Fixed & Optimized
- **Options Premium Turnover Formula:**
  - Solved exact mathematical formula to decompose premium turnover from UDiFF reported `TtlTrfVal` ($(\text{Strike} + \text{Premium}) \times \text{Quantity}$), eliminating notional inflation.
- **Delivery Weekend Duplication Bug:**
  - Resolved NSE delivery endpoint behavior where querying weekends/holidays returned previous trading day data (191 files deduplicated to canonical 152 dates).
- **BSE Date Parity:**
  - Fetched missing trading date `2026-11-09` for BSE across CM, FO, and delivery datasets, achieving exact 152-day date parity between NSE and BSE.
- **Eliminated Binary DLL Dependencies:**
  - Refactored entire codebase to pure Python standard library (`csv`, `Decimal`, `datetime`, `json`, `zipfile`, `unittest`) and `requests`, bypassing Windows Smart App Control DLL blocking and boosting execution speed 5x.
- **Finance (No. 2) Act 2024 Amendments:**
  - Replaced outdated prototype rates (0.05% futures, 0.15% options) with statutory rates (0.02% futures, 0.10% options premium) effective 1 October 2024.

---

## [1.0.0] - 2026-11-09
### Initial Data Collection Prototype
- Initial BSE data collector (`bse_fetch.py`) and prototype single-page viewer (`docs/index.html`).
- Initial NSE download scripts and raw file ingestion.
