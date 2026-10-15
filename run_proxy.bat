@echo off
chcp 65001 >nul
cd /d "%~dp0"
py proxy_gui.py
if errorlevel 1 python proxy_gui.py
if errorlevel 1 pause
