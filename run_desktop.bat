@echo off
title LOCUS Desktop App
cd /d "%~dp0"
echo =======================================================
echo   LOCUS Desktop Launcher (pywebview / Web Interface)
echo   Target: http://127.0.0.1:8000
echo =======================================================
python desktop_launcher.py
pause
