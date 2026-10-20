@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "STEEL_PY="
set "STEEL_BASE="
set "STEEL_ENV=%~dp0.venv"

echo Checking existing Python environments...
call :try_ready "%STEEL_ENV%\Scripts\python.exe"
for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do call :try_ready "%%P"
for /f "delims=" %%P in ('where python.exe 2^>nul') do call :try_ready "%%P"
if defined STEEL_PY goto run
if /i "%~1"=="--check" exit /b 2

echo No compatible environment found. Preparing dependencies...
if exist "%STEEL_ENV%\Scripts\python.exe" (
    "%STEEL_ENV%\Scripts\python.exe" -c "import sys; assert sys.version_info >= (3,10)" >nul 2>&1
    if not errorlevel 1 (
        set "STEEL_PY=%STEEL_ENV%\Scripts\python.exe"
        goto install
    )
)
for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do call :try_base "%%P"
for /f "delims=" %%P in ('where python.exe 2^>nul') do call :try_base "%%P"
if not defined STEEL_BASE (
    echo Python 3.10 or newer was not found.
    pause
    exit /b 1
)
"%STEEL_BASE%" -m venv "%STEEL_ENV%"
if errorlevel 1 (
    echo Could not prepare the Python environment.
    pause
    exit /b 1
)
set "STEEL_PY=%STEEL_ENV%\Scripts\python.exe"
:install
"%STEEL_PY%" -m pip install --disable-pip-version-check --retries 1 --timeout 20 -r requirements.txt
if errorlevel 1 (
    echo Dependency download failed. Check network access to PyPI.
    echo Existing environments were checked before this download.
    pause
    exit /b 1
)

:run
echo Using: %STEEL_PY%
"%STEEL_PY%" --version
if /i "%~1"=="--check" (
    "%STEEL_PY%" start.py --check
    exit /b
)
"%STEEL_PY%" start.py
if errorlevel 1 (
    echo Startup failed. See .logs\streamlit.log for details.
    pause
    exit /b 1
)
exit /b 0

:try_ready
if defined STEEL_PY exit /b 0
if not exist "%~1" exit /b 0
echo(%~1| findstr /i /c:"\Microsoft\WindowsApps\" >nul
if not errorlevel 1 exit /b 0
"%~1" -c "import sys,streamlit,pandas,openpyxl; assert sys.version_info >= (3,10); assert callable(getattr(streamlit,'iframe',None))" >nul 2>&1
if not errorlevel 1 set "STEEL_PY=%~1"
exit /b 0

:try_base
if defined STEEL_BASE exit /b 0
if not exist "%~1" exit /b 0
echo(%~1| findstr /i /c:"\Microsoft\WindowsApps\" >nul
if not errorlevel 1 exit /b 0
"%~1" -c "import sys; assert sys.version_info >= (3,10)" >nul 2>&1
if not errorlevel 1 set "STEEL_BASE=%~1"
exit /b 0
