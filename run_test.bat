@echo off
REM Test runner for Windows
REM Runs all test suites and generates validation logs

setlocal enabledelayedexpansion

echo ===================================================
echo Pagination Normalization System - Test Suite
echo ===================================================
echo.

REM Check if virtual environment exists, if so activate it
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

REM Create logs directory
if not exist "logs" mkdir logs

REM Generate log filename with timestamp
for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c%%a%%b)
for /f "tokens=1-2 delims=/:" %%a in ('time /t') do (set mytime=%%a%%b)
set LOG_FILE=logs\test_results_%mydate%_%mytime%.log

echo Running pagination normalization unit tests...
python -m unittest test_pagination_consistency -v > "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo Unit tests had issues - see log file
)

echo.
echo ===================================================
echo Running mock gateway demonstration...
echo ===================================================
echo.
python mock_gateway.py >> "%LOG_FILE%" 2>&1

echo.
echo ===================================================
echo Test suite complete!
echo ===================================================
echo.
echo Test results saved to: %LOG_FILE%
