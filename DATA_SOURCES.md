# Data Sources: Market Ledger — India
## Official Endpoints, Access Protocols, Data Formats, and Ingestion Caveats

---

## 1. National Stock Exchange (NSE) Sources

### 1.1 Capital Market UDiFF BhavCopy
- **Endpoint Pattern:**
  `https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.csv.zip`
- **Format:** ZIP archive containing a single CSV file.
- **Fields:** 34 standardized UDiFF columns.
- **Content:** Complete security-level trade summary for equities, SMEs, debt, business trusts, and ETFs.
- **Turnover Field:** `TtlTrfVal` represents whole Rupees.
- **Storage Location:** `nse_data/raw/cm_udiff/` and `nse_data/extracted/cm_udiff/`.

### 1.2 Equity Derivatives (F&O) UDiFF BhavCopy
- **Endpoint Pattern:**
  `https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_YYYYMMDD_F_0000.csv.zip`
- **Format:** ZIP archive containing a single CSV file.
- **Fields:** 34 standardized UDiFF columns.
- **Content:** Contract-level records for Index Futures (`IDF`), Stock Futures (`STF`), Index Options (`IDO`), and Stock Options (`STO`).
- **Critical Ingestion Caveat:** `TtlTrfVal` represents **Notional Contract Value** for options ($(\text{Strike} + \text{Premium}) \times \text{Quantity}$). Premium turnover must be decomposed using:
  $$\text{Premium Turnover} = \text{TtlTrfVal} - (\text{StrkPric} \times \text{TtlTradgVol} \times \text{NewBrdLotQty})$$
- **Storage Location:** `nse_data/raw/fo_udiff/` and `nse_data/extracted/fo_udiff/`.

### 1.3 Security-Wise Delivery Position (`sec_bhavdata_full`)
- **Endpoint Pattern:**
  `https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_DDMMYYYY.csv`
- **Format:** Raw CSV file.
- **Columns:** `SYMBOL`, `SERIES`, `DATE1`, `PREV_CLOSE`, `OPEN_PRICE`, `HIGH_PRICE`, `LOW_PRICE`, `LAST_PRICE`, `CLOSE_PRICE`, `AVG_PRICE`, `TTL_TRD_QNTY`, `TURNOVER_LACS`, `NO_OF_TRADES`, `DELIV_QTY`, `DELIV_PER`.
- **Critical Endpoint Caveat (Weekend & Holiday Duplication):**
  When queried on a non-trading date (Saturday, Sunday, or gazetted holiday), the NSE web server returns the immediately preceding trading session's report rather than an HTTP 404 error. Querying 223 calendar dates yielded 191 downloaded files.
  **Data Safeguard:** Ingestion scripts must read the embedded `DATE1` column, group by canonical date, detect byte-identical duplicate files, and preserve exactly one canonical record per trading date (152 total).
- **Storage Location:** `nse_data/raw/cm_security_delivery/` and `nse_data/extracted/cm_security_delivery/`.

---

## 2. Bombay Stock Exchange (BSE) Sources

### 2.1 BSE Capital Market BhavCopy
- **Endpoint Pattern:**
  `https://www.bseindia.com/download/BhavCopy/Equity/BhavCopy_BSE_CM_0_0_0_YYYYMMDD_F_0000.CSV`
- **Format:** Raw uncompressed CSV file.
- **Fields:** 34 standardized UDiFF columns (with UTF-8 BOM `\ufeff`).
- **Content:** Security-level records with security groups stored in `SctySrs` (`A`, `B`, `X`, `XT`, `T`, `M`, `MT`, `Z`, `IF`, `E`, `G`, `F`).
- **Storage Location:** `bse_data/raw/cm_bhav/`.

### 2.2 BSE Derivatives Market Summary
- **Endpoint Pattern:**
  `https://www.bseindia.com/download/BhavCopy/Derivative/MS_YYYYMMDD-01.csv`
- **Format:** Raw CSV file.
- **Columns:** `Product Type` (`IF`, `SF`, `IO`, `SO`), `Option Type` (`CE`, `PE`), `Strike Price`, `Total Traded Quantity`, `Total Traded Value (in Thousands)(absolute)`, `Total Trades`.
- **Unit Caveat:** Total Traded Value is reported in **Thousands of Rupees**. Multiply by 1,000 to convert to whole Rupees.
- **Storage Location:** `bse_data/raw/fo_summary/`.

### 2.3 BSE Gross Delivery Position
- **Endpoint Pattern:**
  `https://www.bseindia.com/BSEDATA/gross/YYYY/SCBSEALLDDMM.zip`
- **Format:** ZIP archive containing a pipe-delimited text/CSV file (`SCBSEALLDDMM.TXT`).
- **Columns:** `SCRIP CODE`, `SCRIP NAME`, `DELIVERY QTY`, `DELIVERY VAL`, `TURNOVER`, `VOLUME`.
- **Units:** `DELIVERY VAL` and `TURNOVER` are in whole Rupees.
- **Storage Location:** `bse_data/raw/delivery/`.

---

## 3. Special Trading Sessions & Calendar Anomalies

1. **Diwali Muhurat Trading Session (8 November 2026):**
   - Falls on a Sunday. Both NSE and BSE conducted a 1-hour special evening trading session.
   - Valid session: NSE generated ₹23,274.86 Cr cash turnover and ₹71.19 Cr STT; BSE generated ₹2,685.12 Cr cash turnover and ₹7.02 Cr STT.
   - Preserved and verified in both exchange datasets.
2. **7 November 2026 (Saturday):**
   - Saturday preceding Diwali. Confirmed non-trading holiday (HTTP 404 returned correctly).

---

## 4. Archival and Preservation Policy

- **Permanent Raw Storage:** All original ZIP and CSV downloads are preserved permanently in `nse_data/raw/` and `bse_data/raw/`. They are never overwritten or deleted.
- **Audit Manifest:** Every HTTP fetch attempt, HTTP response code, response size in bytes, and timestamp is logged in `nse_data/manifest.csv` and `bse_data/manifest.csv`.
