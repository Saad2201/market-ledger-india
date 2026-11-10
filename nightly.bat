@echo off
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% -u bse_fetch.py --datasets cm_bhav fo_summary delivery --site-dir docs >> nightly.log 2>&1
