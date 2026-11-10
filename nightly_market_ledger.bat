@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py) || (set PY=python)

echo [%date% %time%] ====================================================== >> market_ledger_nightly.log
echo [%date% %time%] Starting Market Ledger Master Pipeline Execution >> market_ledger_nightly.log
echo [%date% %time%] ====================================================== >> market_ledger_nightly.log

%PY% -u run_pipeline.py --fetch >> market_ledger_nightly.log 2>&1

where git >nul 2>nul
if %errorlevel% equ 0 (
    git rev-parse --is-inside-work-tree >nul 2>nul
    if %errorlevel% equ 0 (
        echo [%date% %time%] Committing and pushing updated data to GitHub... >> market_ledger_nightly.log
        git add data docs reference bse_data nse_data >> market_ledger_nightly.log 2>&1
        git diff --cached --quiet
        if %errorlevel% neq 0 (
            git commit -m "Auto-update market data: %date% [automated]" >> market_ledger_nightly.log 2>&1
            git push >> market_ledger_nightly.log 2>&1
            echo [%date% %time%] Successfully pushed updates to GitHub repository >> market_ledger_nightly.log
        ) else (
            echo [%date% %time%] No new data changes to commit >> market_ledger_nightly.log
        )
    )
)

echo [%date% %time%] Master Pipeline Completed >> market_ledger_nightly.log
endlocal
