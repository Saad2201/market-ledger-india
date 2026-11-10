# Data Dictionary: Market Ledger — India
## Schema Specifications, Field Definitions, Instrument Classifications, and Dataset Layouts

---

## 1. Unified Data Interchange Format (UDiFF) Field Specifications

The National Stock Exchange (NSE) and Bombay Stock Exchange (BSE) publish daily market BhavCopy reports using the SEBI-mandated **UDiFF standard**.

| Field Name | Data Type | Units / Meaning | Description & Financial Significance |
|---|---|---|---|
| `TradDt` | Date (`YYYY-MM-DD`) | Calendar Date | The actual trading date on which trades were executed. |
| `BizDt` | Date (`YYYY-MM-DD`) | Calendar Date | The clearing and settlement business date. |
| `Sgmt` | String (e.g. `CASH`, `FO`) | Segment Identifier | `CASH` indicates Capital Market; `FO` indicates Equity Derivatives. |
| `Src` | String (e.g. `NSE`, `BSE`) | Source Identifier | Primary reporting exchange code. |
| `FinInstrmTp` | String | Instrument Code | Capital Market: `STK` (Stock).<br>Derivatives: `IDO` (Index Options), `STO` (Stock Options), `IDF` (Index Futures), `STF` (Stock Futures). |
| `FinInstrmId` | Integer / String | Identifier | Unique numeric security or contract identifier. |
| `ISIN` | String (12 chars) | Global Standard | International Securities Identification Number (e.g. `INE002A01018`). |
| `TckrSymb` | String | Exchange Symbol | Standard trading ticker (e.g. `RELIANCE`, `TCS`, `NIFTY`). |
| `SctySrs` | String | Security Series | Capital Market trading series (e.g. `EQ`, `BE`, `SM`, `ST`, `IV`, `N0`). Blank in F&O. |
| `XpryDt` | Date (`YYYY-MM-DD`) | Expiry Date | Contract expiration date for derivative instruments. |
| `FininstrmActlXpryDt` | Date (`YYYY-MM-DD`) | Actual Expiry | Actual settlement expiration date if holiday adjustment applies. |
| `StrkPric` | Decimal (2 places) | Rupees | Strike price for option contracts. Zero for futures and cash equities. |
| `OptnTp` | String (`CE` / `PE`) | Option Type | `CE` indicates European Call Option; `PE` indicates European Put Option. |
| `FinInstrmNm` | String | Description | Full descriptive instrument or contract name. |
| `OpnPric` | Decimal (2 places) | Rupees | Session opening execution price. |
| `HghPric` | Decimal (2 places) | Rupees | Highest execution price during the session. |
| `LwPric` | Decimal (2 places) | Rupees | Lowest execution price during the session. |
| `ClsPric` | Decimal (2 places) | Rupees | Official weighted average closing price of the session. |
| `LastPric` | Decimal (2 places) | Rupees | Last traded execution price before session close. |
| `PrvsClsgPric` | Decimal (2 places) | Rupees | Closing price of the immediately preceding trading session. |
| `UndrlygPric` | Decimal (2 places) | Rupees | Closing spot price of the underlying index or stock. |
| `SttlmPric` | Decimal (2 places) | Rupees | Daily mark-to-market settlement price for derivatives. |
| `OpnIntrst` | Integer | Contracts / Lots | Total open interest outstanding at the end of the session. |
| `ChngInOpnIntrst` | Integer | Contracts / Lots | Net daily change in open interest contracts. |
| `TtlTradgVol` | Integer / Decimal | Shares / Contracts | Total executed trading volume in number of shares or derivative contracts. |
| `TtlTrfVal` | Decimal (2 places) | **Whole Rupees** | **Total Notional Traded Value**. For options, includes strike value: $(\text{Strike} + \text{Premium}) \times \text{Quantity}$. |
| `TtlNbOfTxsExctd` | Integer | Trade Count | Total number of individual executed trade transactions. |
| `SsnId` | Integer / String | Session Code | Trading session identifier (`1` = Normal, `2` = Block deal window). |
| `NewBrdLotQty` | Integer | Lot Size | Contract market lot multiplier (e.g. 25, 50, 75). |

---

## 2. NSE Cash Market Security Series Classification

Based on scan of 534,112 rows across 152 historical trading sessions:

| Series | Meaning | Instrument Category | Include in Ordinary Equity Turnover? | Tax Treatment |
|---|---|---|---|---|
| `EQ` | Standard Rolling Settlement Equity | Ordinary Equity | **YES** (99.08% of CM value) | Delivery: 0.20% STT; Intraday: 0.025% STT |
| `BE` | Trade-for-Trade Rolling Settlement | Mandatory Delivery Equity | **YES** | Mandatory Delivery: 0.20% STT (No intraday squaring off) |
| `BZ` | Surveillance Measures Equities | Surveillance Equity | **YES** | Mandatory Delivery: 0.20% STT |
| `SM` | SME Platform Equities | SME Ordinary Equity | **YES** | Delivery: 0.20% STT; Intraday: 0.025% STT |
| `ST` | SME Trade-for-Trade Equities | SME Mandatory Delivery | **YES** | Mandatory Delivery: 0.20% STT |
| `BL` | Block Deal Trading Window | Large Block Equity | **YES** (Special Session) | Delivery: 0.20% STT |
| `RR` | Rights Entitlements (RE) | Tradable Rights | **NO** (Segregated) | 0.125% STT on sale side |
| `IV` | Infrastructure Investment Trusts / REITs | Business Trust Units | **NO** (Segregated) | 0.20% STT on delivery value |
| `E1` | Equity Exchange Traded Funds (ETF) | Equity ETF Units | **NO** (Segregated) | 0.001% STT on sale side |
| `GB` | Sovereign Gold Bonds (SGB) | Government Debt | **NO** (Debt) | **0.00% STT (Exempt)**; 0.00% Stamp Duty |
| `GS` | Government of India Securities | Central Govt Debt | **NO** (Debt) | **0.00% STT (Exempt)**; 0.00% Stamp Duty |
| `SG` | State Development Loans (SDL) | State Govt Debt | **NO** (Debt) | **0.00% STT (Exempt)**; 0.00% Stamp Duty |
| `TB` | Treasury Bills | Short-term Money Market | **NO** (Debt) | **0.00% STT (Exempt)**; 0.00% Stamp Duty |
| `N0`-`NZ` | Non-Convertible Debentures (NCDs) | Corporate Debt | **NO** (Debt) | **0.00% STT (Exempt)**; 0.0001% Stamp Duty |

---

## 3. BSE Security Group Classification

| Group Code | Segment Name | Category | Equity Turnover? | Tax Treatment |
|---|---|---|---|---|
| `A` | Group A — High Liquidity Blue-Chips | Blue-chip Equity | **YES** (74% of BSE cash) | Delivery: 0.20% STT; Intraday: 0.025% STT |
| `B` | Group B — Mid & Small Cap Liquid Equities | Standard Rolling Equity | **YES** | Delivery: 0.20% STT; Intraday: 0.025% STT |
| `X` | Group X — Small-Cap Listed Equities | Small-cap Equity | **YES** | Delivery: 0.20% STT; Intraday: 0.025% STT |
| `XT` | Group XT — Trade-for-Trade Small Caps | Mandatory Delivery | **YES** | Mandatory Delivery: 0.20% STT |
| `T` | Group T — Main Board Trade-for-Trade | Mandatory Delivery | **YES** | Mandatory Delivery: 0.20% STT |
| `M` | BSE SME Platform Growth Equities | SME Equity | **YES** | Delivery: 0.20% STT; Intraday: 0.025% STT |
| `MT` | BSE SME Trade-for-Trade | SME Mandatory Delivery | **YES** | Mandatory Delivery: 0.20% STT |
| `Z` | Group Z — Non-Compliant Companies | Surveillance Equity | **YES** | Mandatory Delivery: 0.20% STT |
| `IF` | InvITs and REITs | Business Trust Units | **NO** (Segregated) | 0.20% STT on delivery |
| `E` | Exchange Traded Funds (ETFs) | Mutual Fund / ETF | **NO** (Segregated) | 0.001% STT on sale |
| `G` | Government Debt & SGBs | Sovereign Debt | **NO** (Debt) | **0.00% STT (Exempt)** |
| `F` | Corporate Debt & Debentures | Debt Securities | **NO** (Debt) | **0.00% STT (Exempt)** |

---

## 4. Processed Central Revenue Dataset Schema

File: `data/processed/revenue/daily_revenue_estimates.csv` (152 rows, date-indexed):

| Column Name | Data Type | Meaning / Calculation |
|---|---|---|
| `trade_date` | `YYYY-MM-DD` | Canonical trading session date. |
| `nse_cash_turnover_cr` | Decimal (Cr) | NSE total cash market turnover (₹ Cr). |
| `nse_futures_turnover_cr` | Decimal (Cr) | NSE total traded futures turnover (₹ Cr). |
| `nse_options_premium_cr` | Decimal (Cr) | NSE actual traded options premium turnover (₹ Cr). |
| `nse_options_notional_cr` | Decimal (Cr) | NSE reported options notional value (₹ Cr). |
| `bse_cash_turnover_cr` | Decimal (Cr) | BSE total cash market turnover (₹ Cr). |
| `bse_futures_turnover_cr` | Decimal (Cr) | BSE total traded futures turnover (₹ Cr). |
| `bse_options_premium_cr` | Decimal (Cr) | BSE actual traded options premium turnover (₹ Cr). |
| `bse_options_notional_cr` | Decimal (Cr) | BSE reported options notional value (₹ Cr). |
| `total_cash_turnover_cr` | Decimal (Cr) | Combined NSE + BSE cash turnover. |
| `total_futures_turnover_cr` | Decimal (Cr) | Combined NSE + BSE futures turnover. |
| `total_options_premium_cr` | Decimal (Cr) | Combined NSE + BSE options premium turnover. |
| `total_options_notional_cr` | Decimal (Cr) | Combined options notional turnover. |
| `total_market_turnover_cr` | Decimal (Cr) | Total cash + futures + options premium. |
| `delivery_value_cr` | Decimal (Cr) | Combined gross deliverable equity value. |
| `intraday_value_cr` | Decimal (Cr) | Combined squared-off non-delivery equity value. |
| `stt_equity_delivery_cr` | Decimal (Cr) | Estimated delivery STT (0.20% on delivery value). |
| `stt_equity_intraday_cr` | Decimal (Cr) | Estimated intraday STT (0.025% on intraday sale value). |
| `stt_equity_total_cr` | Decimal (Cr) | Modeled cash equity STT subtotal. |
| `stt_equity_floor_cr` | Decimal (Cr) | Verified Floor: STT if 100% of trades were intraday. |
| `stt_equity_ceiling_cr` | Decimal (Cr) | Verified Ceiling: STT if 100% of trades were delivery. |
| `stt_futures_cr` | Decimal (Cr) | Estimated futures STT (0.02% from 1 Oct 2024). |
| `stt_options_cr` | Decimal (Cr) | Estimated options STT (0.10% on premium from 1 Oct 2024). |
| `stt_nse_cr` | Decimal (Cr) | Total STT generated on NSE. |
| `stt_bse_cr` | Decimal (Cr) | Total STT generated on BSE. |
| `stt_total_cr` | Decimal (Cr) | Central Government Total STT. |
| `stamp_duty_total_cr` | Decimal (Cr) | State Governments Total Stamp Duty (Buy side). |
| `sebi_fee_total_cr` | Decimal (Cr) | SEBI Regulatory Turnover Fees (₹10 / Cr). |
| `exchange_fee_total_cr` | Decimal (Cr) | Combined exchange transaction charges (Non-Gov). |
| `gst_known_total_cr` | Decimal (Cr) | GST (18%) on Exchange fees + SEBI fees. |
| `central_gov_revenue_cr` | Decimal (Cr) | Central Government Revenue (= `stt_total_cr`). |
| `state_gov_revenue_cr` | Decimal (Cr) | State Government Revenue (= `stamp_duty_total_cr`). |
| `gst_revenue_cr` | Decimal (Cr) | GST Revenue (= `gst_known_total_cr`). |
| `total_government_tax_revenue_cr` | Decimal (Cr) | Central STT + State Stamp Duty + GST. |
| `total_statutory_revenue_cr` | Decimal (Cr) | Total Government Tax + SEBI Regulatory Fees. |
| `non_government_charges_cr` | Decimal (Cr) | Retained Exchange Operating Charges. |
| `status` | String | Verification status (`VERIFIED`). |
| `notes` | String | Trading session annotations (e.g. Muhurat session). |
