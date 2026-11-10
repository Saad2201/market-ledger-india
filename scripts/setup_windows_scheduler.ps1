# setup_windows_scheduler.ps1 - Registers an automated daily update task in Windows Task Scheduler
#
# Runs every Monday through Friday at 19:45 IST (7:45 PM), after market hours and BhavCopy release.
# Executes nightly_market_ledger.bat which fetches data, recalculates revenues, and pushes to GitHub.

$TaskName = "MarketLedgerDailyUpdate"
$ScriptDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$BatchFile = Join-Path $ScriptDir "nightly_market_ledger.bat"

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "Market Ledger — India: Automated Windows Scheduler Setup" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "Target Script : $BatchFile" -ForegroundColor Yellow

if (-not (Test-Path $BatchFile)) {
    Write-Error "Could not locate nightly_market_ledger.bat at: $BatchFile"
    exit 1
}

# Define the action
$Action = New-ScheduledTaskAction -Execute $BatchFile -WorkingDirectory $ScriptDir

# Define the trigger: Mon-Fri at 19:45 (7:45 PM)
$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At "19:45"

# Define task settings
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)

# Unregister previous task if exists
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

# Register new scheduled task
try {
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Fetches daily stock market data from NSE & BSE, recalculates revenues, and updates the Market Ledger dashboard." -ErrorAction Stop
    Write-Host "`n[SUCCESS] Scheduled task '$TaskName' registered successfully!" -ForegroundColor Green
    Write-Host "Schedule: Every weekday (Monday-Friday) at 19:45 IST."
    Write-Host "Task will automatically fetch new daily reports and update your website."
} catch {
    Write-Warning "Could not register task via PowerShell cmdlet: $_"
    Write-Host "Attempting fallback via schtasks.exe..."
    schtasks /create /tn $TaskName /tr "`"$BatchFile`"" /sc weekly /d MON,TUE,WED,THU,FRI /st 19:45 /f
    Write-Host "[SUCCESS] Task created via schtasks.exe." -ForegroundColor Green
}
