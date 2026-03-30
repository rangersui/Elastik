@echo off
title elastik installer
cd /d "%~dp0"
python install.py
if errorlevel 1 (
    echo.
    echo Python not found. Install Python from https://python.org
    pause
)
