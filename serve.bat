@echo off
cd /d "%~dp0docs"
echo Site running at http://localhost:8000  (close this window to stop)
python -m http.server 8000
