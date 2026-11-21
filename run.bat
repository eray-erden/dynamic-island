@echo off
cd /d "%~dp0"
if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" dynamic_island.py %*
) else if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" dynamic_island.py %*
) else (
    python dynamic_island.py %*
)
