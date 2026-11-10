# Deployment & Automated Daily Updates Guide
## Market Ledger — India

This guide provides step-by-step instructions to:
1. Deploy the dashboard to the public internet for free via **GitHub Pages** (accessible to anyone globally with automatic HTTPS).
2. Configure **fully automated daily data fetching** so future trading days are ingested, reconciled, calculated, and published without manual intervention.

---

## 1. Quick Overview of the Architecture

- **Frontend:** Built into the [`docs/`](file:///D:/bse-tracker/bse-tracker/docs) directory (`index.html` + `data.json`).
- **Web Host:** GitHub Pages natively serves out of the `/docs` folder of your GitHub repository at zero cost on a global CDN.
- **Automated Cloud Updates:** GitHub Actions workflow ([`.github/workflows/market_ledger_daily.yml`](file:///D:/bse-tracker/bse-tracker/.github/workflows/market_ledger_daily.yml)) runs every Monday–Friday at 19:30 IST and 22:30 IST, downloads the day's BhavCopy, recalculates taxes, and updates the website.
- **Automated Local Updates (Geo-blocking Safeguard):** A Windows Task Scheduler job running [`nightly_market_ledger.bat`](file:///D:/bse-tracker/bse-tracker/nightly_market_ledger.bat) from your Indian residential connection, ensuring 100% reliability if exchange firewalls block overseas cloud IPs.

---

## 2. Step-by-Step: Deploy to GitHub Pages (5 Minutes)

### Step 2.1: Initialize Git and Commit the Platform
Open Windows PowerShell in the project directory:

```powershell
cd D:\bse-tracker\bse-tracker

# Initialize git repository
git init
git branch -M main

# Add all files and make initial commit
git add .
git commit -m "Deploy Market Ledger India v2.0 with complete dual-exchange data"
```

### Step 2.2: Create a New Repository on GitHub
1. Open your browser and log into your GitHub account ([https://github.com/new](https://github.com/new)).
2. Repository name: `market-ledger-india` (or any name you prefer).
3. Set visibility to **Public** (required for free GitHub Pages).
4. Do **NOT** initialize with a README, .gitignore, or license (we already have them).
5. Click **Create repository**.

### Step 2.3: Push Code to GitHub
Copy and paste these commands into PowerShell:

```powershell
git remote set-url origin https://github.com/Saad2201/market-ledger-india.git
git push -u origin main
```

*(If prompted to authenticate, sign in via your browser or paste a GitHub Personal Access Token).*

### Step 2.4: Turn On GitHub Pages
1. On GitHub, navigate to your repository: `https://github.com/Saad2201/market-ledger-india`
2. Click **Settings** (top right tab).
3. In the left sidebar, click **Pages** (under "Code and automation").
4. Under **Build and deployment**:
   - Source: **Deploy from a branch**
   - Branch: select `main`
   - Folder: select `/docs` (IMPORTANT: do not select `/root`)
5. Click **Save**.

**Congratulations!** Within 60 seconds, your site will be live at:
```text
https://Saad2201.github.io/market-ledger-india/
```
Anyone in the world can now access your dashboard from mobile or desktop!

---

## 3. How Automated Daily Updates Work

Once pushed to GitHub, future trading sessions will be fetched and updated automatically via two complementary systems:

### Method A: Cloud Automation via GitHub Actions (Zero-Touch)
The workflow file [`.github/workflows/market_ledger_daily.yml`](file:///D:/bse-tracker/bse-tracker/.github/workflows/market_ledger_daily.yml) is already configured in the repository.

1. **Schedule:** Runs every weekday (Monday through Friday) at:
   - **19:30 IST (14:00 UTC):** Shortly after the NSE & BSE evening BhavCopy releases.
   - **22:30 IST (17:00 UTC):** Catch-up / reconciliation retry run.
2. **What it does:**
   - Spins up a virtual Ubuntu environment.
   - Executes `python run_pipeline.py --fetch`.
   - Downloads the day's reports from NSE & BSE.
   - Runs validation and turnover reconciliation.
   - Computes statutory taxes (STT, Stamp Duty, GST, SEBI fee).
   - Runs the unit test suite (`tests/test_revenue_engine.py`).
   - Updates `docs/data.json` and processed CSVs.
   - Commits and pushes changes back to `main`.
   - GitHub Pages immediately redeploys the website with the latest numbers!

#### Manual Cloud Trigger:
To trigger an update anytime from your phone or browser:
1. Go to your repository on GitHub.
2. Click the **Actions** tab.
3. Click **Daily Market Ledger Ingestion & Deployment** on the left.
4. Click **Run workflow** > **Run workflow**.

---

### Method B: Local Automation via Windows Scheduler (Indian IP Safeguard)

Exchange servers (especially NSE) occasionally block requests originating from overseas cloud data centers (e.g. GitHub's Azure runners). To ensure 100% uninterrupted daily updates regardless of cloud firewall policies, we provide a Windows Task Scheduler job.

To activate the automated daily scheduler on your PC:

1. Open PowerShell as Administrator.
2. Run:
```powershell
cd D:\bse-tracker\bse-tracker
powershell -ExecutionPolicy Bypass -File scripts\setup_windows_scheduler.ps1
```

3. **What this does:**
   - Registers a Windows Scheduled Task named `MarketLedgerDailyUpdate`.
   - Fires automatically every weekday (Monday–Friday) at **19:45 IST**.
   - Executes `nightly_market_ledger.bat` from your local Indian ISP IP.
   - Downloads the day's data, validates, recalculates, commits to git, and pushes to GitHub.
   - Your GitHub Pages website updates within minutes!

---

## 4. Alternative Hosting Options (Optional)

If you prefer custom hosting services with instant global CDNs:

### Deploying to Vercel (Free)
1. Go to [vercel.com](https://vercel.com) and log in with GitHub.
2. Click **Add New...** > **Project** and import `market-ledger-india`.
3. In **Build and Output Settings**:
   - Set **Root Directory** to `docs`.
4. Click **Deploy**. Your site will be live instantly with a free `.vercel.app` domain.

### Deploying to Netlify (Free)
1. Go to [netlify.com](https://netlify.com) and import your GitHub repo.
2. Set **Publish directory** to `docs`.
3. Click **Deploy Site**.

---

## 5. Verification Checklist

- [x] Dashboard source files compiled in `docs/` (`index.html` & `data.json`).
- [x] GitHub Actions automated workflow created at `.github/workflows/market_ledger_daily.yml`.
- [x] Local Windows Task Scheduler setup script created at `scripts/setup_windows_scheduler.ps1`.
- [x] Automated batch runner updated at `nightly_market_ledger.bat`.
- [x] Unit test suite verified (16/16 tests passing).
- [x] Git configuration verified for user `Saad2201`.
