@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "STEEL_PY="
set "STEEL_BASE="
for %%D in ("%~dp0..\..\..\..\..") do set "STEEL_WORKSPACE=%%~fD"
set "STEEL_ENV=%STEEL_WORKSPACE%\.venv"

if exist "%STEEL_ENV%\Scripts\python.exe" (
    "%STEEL_ENV%\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
    if not errorlevel 1 set "STEEL_PY=%STEEL_ENV%\Scripts\python.exe"
)
if defined STEEL_PY goto ready

echo Searching for Python 3.10 or newer...
for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do call :try_python "%%P"
for /f "delims=" %%P in ('where python.exe 2^>nul') do call :try_python "%%P"
call :try_python "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if not defined STEEL_BASE (
    echo Python 3.10 or newer was not found. Python 3.9 cannot run this version.
    echo Install Python 3.10 or newer, then run this file again.
    pause
    exit /b 1
)

"%STEEL_BASE%" -m venv "%STEEL_ENV%"
if errorlevel 1 (
    echo Could not create the local Python environment.
    pause
    exit /b 1
)
set "STEEL_PY=%STEEL_ENV%\Scripts\python.exe"

:ready
echo Using: %STEEL_PY%
"%STEEL_PY%" --version
"%STEEL_PY%" -c "import streamlit, plotly, pandas, numpy, openpyxl, xlrd" >nul 2>&1
if errorlevel 1 (
    "%STEEL_PY%" -m pip install -r requirements.txt
)

if errorlevel 1 (
    echo Dependency installation failed.
    pause
    exit /b 1
)

"%STEEL_PY%" start_app.py
if errorlevel 1 (
    echo Startup failed. See .logs\streamlit.log for details.
    pause
    exit /b 1
)
exit /b 0

:try_python
if defined STEEL_BASE exit /b 0
if not exist "%~1" exit /b 0
echo(%~1| findstr /i /c:"\Microsoft\WindowsApps\" >nul
if not errorlevel 1 exit /b 0
"%~1" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 set "STEEL_BASE=%~1"
exit /b 0
