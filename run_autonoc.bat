@echo off
REM ============================================================
REM  AutoNOC — Windows Launcher
REM  Usage (from Command Prompt or PowerShell):
REM    run_autonoc.bat           -> production run (opens browser)
REM    run_autonoc.bat --test    -> test run using local dummy CSV
REM    run_autonoc.bat --all     -> test run, all report types
REM    run_autonoc.bat --help    -> show help
REM ============================================================

setlocal EnableDelayedExpansion

REM Change to the directory where this .bat file lives
cd /d "%~dp0"

REM ── Help ─────────────────────────────────────────────────────
if /i "%~1"=="--help" goto :show_help
if /i "%~1"=="-h"     goto :show_help
goto :start

:show_help
echo.
echo   AutoNOC — Automated NOC Report Generator
echo.
echo   Usage: run_autonoc.bat [OPTIONS]
echo.
echo   Options:
echo     (none)          Production mode — opens browser for portal login
echo     --test          Test mode — uses local dummy CSV, no browser needed
echo     --test --all    Test mode — generates all 4 report types
echo     --help          Show this help
echo.
echo   First run: creates a virtual environment and installs
echo   all Python dependencies automatically.
echo.
goto :eof

REM ── Main ─────────────────────────────────────────────────────
:start
echo.
echo   ╔══════════════════════════════════════╗
echo   ║           AutoNOC v1.0               ║
echo   ║         Windows Launcher             ║
echo   ╚══════════════════════════════════════╝
echo.

REM ── Step 1: Find Python (3.9 or higher required) ─────────────
REM Try py launcher first (installed by official Python installer),
REM then fall back to python / python3 on PATH.

set PYTHON_CMD=
set PYTHON_OK=0

REM Try: py -3.12, py -3.11, py -3.10, py -3.9
for %%V in (3.12 3.11 3.10 3.9) do (
    if "!PYTHON_OK!"=="0" (
        py -%%V --version >nul 2>&1
        if !errorlevel! equ 0 (
            set PYTHON_CMD=py -%%V
            set PYTHON_OK=1
        )
    )
)

REM Try: python3, python
if "!PYTHON_OK!"=="0" (
    python3 --version >nul 2>&1
    if !errorlevel! equ 0 (
        set PYTHON_CMD=python3
        set PYTHON_OK=1
    )
)
if "!PYTHON_OK!"=="0" (
    python --version >nul 2>&1
    if !errorlevel! equ 0 (
        REM Verify it is actually Python 3, not Python 2
        for /f "tokens=2" %%V in ('python --version 2^>^&1') do (
            set PYVER_MAJOR=%%V
        )
        if "!PYVER_MAJOR:~0,1!"=="3" (
            set PYTHON_CMD=python
            set PYTHON_OK=1
        )
    )
)

if "!PYTHON_OK!"=="0" (
    echo.
    echo   [ERROR] Python 3.9 or higher was not found.
    echo.
    echo   Please install Python from https://www.python.org/downloads/
    echo   Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

echo   Python found: !PYTHON_CMD!
for /f "tokens=*" %%V in ('!PYTHON_CMD! --version 2^>^&1') do echo   Version: %%V

REM ── Step 2: Create virtual environment if needed ──────────────
set VENV_DIR=.venv

if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo.
    echo   Creating virtual environment...
    !PYTHON_CMD! -m venv "%VENV_DIR%"
    if !errorlevel! neq 0 (
        echo   [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo   Virtual environment created.
)

REM Activate the virtual environment
call "%VENV_DIR%\Scripts\activate.bat"

REM ── Step 3: Install or upgrade dependencies ───────────────────
set MARKER=%VENV_DIR%\.deps_installed

REM Check if requirements.txt is newer than the marker file
set NEED_INSTALL=0
if not exist "%MARKER%" set NEED_INSTALL=1

REM Simple check: if marker missing, always install
if "!NEED_INSTALL!"=="1" (
    echo.
    echo   Installing dependencies from requirements.txt...
    pip install --upgrade pip --quiet
    pip install -r requirements.txt --quiet
    if !errorlevel! neq 0 (
        echo   [ERROR] Dependency installation failed.
        echo   Check your internet connection and try again.
        pause
        exit /b 1
    )
    echo . > "%MARKER%"
    echo   Dependencies installed successfully.
) else (
    echo   Dependencies already installed.
)

REM ── Step 4: Generate dummy CSV if running in test mode ────────
if /i "%~1"=="--test" (
    if not exist "downloads\dummy_traffic_report.csv" (
        echo.
        echo   Generating test data...
        python generate_dummy_csv.py
    )
)

REM ── Step 5: Launch AutoNOC ────────────────────────────────────
echo.
echo   Starting AutoNOC...
echo.

python main.py %*
set EXIT_CODE=!errorlevel!

echo.
if !EXIT_CODE! equ 0 (
    echo   AutoNOC completed successfully.
    echo   Output: %CD%\output\AutoNOC_Report.xlsx
) else (
    echo   AutoNOC exited with code !EXIT_CODE! — check logs\autonoc.log
)
echo.

REM Keep the window open so the user can read the output
if /i "%~1"=="" (
    echo   Press any key to close this window...
    pause >nul
)

exit /b !EXIT_CODE!
