@echo off
REM Psy Observer Web — Beta 3.1 launcher (Windows Explorer double-clickable).
REM Resolves %%~dp0 as project root. First launch may create .venv_psy_web.
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "PSY_OBSERVER_PROJECT_ROOT=%ROOT%"
set "PYTHONPATH=%ROOT%;%PYTHONPATH%"
set "LOG_DIR=%ROOT%\.psy_observer"
set "LOG_FILE=%LOG_DIR%\launcher.log"
set "BOOTSTRAP=%ROOT%\scripts\bootstrap_psy_observer_env.py"
set "VENV_PY=%ROOT%\.venv_psy_web\Scripts\python.exe"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

if not exist "%ROOT%\mechanistic_mind\ui\psy_observer_web\web_dist\index.html" goto :no_spa
if not exist "%BOOTSTRAP%" goto :no_bootstrap

REM Prefer explicit override, else ready venv, else bootstrap with system Python.
set "PY="
if defined PSY_OBSERVER_PYTHON if exist "%PSY_OBSERVER_PYTHON%" set "PY=%PSY_OBSERVER_PYTHON%"

if not defined PY if exist "%VENV_PY%" (
  "%VENV_PY%" "%BOOTSTRAP%" --root "%ROOT%" --check-only >nul 2>nul
  if not errorlevel 1 set "PY=%VENV_PY%"
)

if defined PY goto :launch

echo Preparing Psy Observer environment
echo Creating Python environment and installing dependencies if needed.
echo This may take a few minutes on first launch (network required).
echo.

set "SYS_PY="
if defined PSY_OBSERVER_PYTHON if exist "%PSY_OBSERVER_PYTHON%" set "SYS_PY=%PSY_OBSERVER_PYTHON%"

if not defined SYS_PY (
  where py >nul 2>nul
  if not errorlevel 1 (
    for /f "delims=" %%I in ('py -3.11 -c "import sys; print(sys.executable)" 2^>nul') do set "SYS_PY=%%I"
  )
)
if not defined SYS_PY (
  where py >nul 2>nul
  if not errorlevel 1 (
    for /f "delims=" %%I in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "SYS_PY=%%I"
  )
)
if not defined SYS_PY (
  where python >nul 2>nul
  if not errorlevel 1 (
    for /f "delims=" %%I in ('where python') do (
      if not defined SYS_PY set "SYS_PY=%%I"
    )
  )
)
if not defined SYS_PY (
  where python3 >nul 2>nul
  if not errorlevel 1 (
    for /f "delims=" %%I in ('where python3') do (
      if not defined SYS_PY set "SYS_PY=%%I"
    )
  )
)

if not defined SYS_PY goto :no_python

"%SYS_PY%" -c "import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 11) else 1)" >nul 2>nul
if errorlevel 1 goto :old_python

echo Using system Python: %SYS_PY%
"%SYS_PY%" "%BOOTSTRAP%" --root "%ROOT%"
if errorlevel 1 goto :bootstrap_fail

if not exist "%VENV_PY%" goto :bootstrap_fail
set "PY=%VENV_PY%"

:launch
cd /d "%ROOT%"
echo Starting Psy Observer
"%PY%" -m mechanistic_mind.ui.psy_observer_web.launcher %*
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" goto :fail
exit /b 0

:no_python
echo Psy Observer Web could not start.
echo.
echo Python 3.11 or newer is required.
echo Download Python from https://www.python.org/downloads/
echo During install, enable "Add python.exe to PATH".
echo You do not need to create .venv_psy_web by hand.
echo.
echo Log: %LOG_FILE%
echo %DATE% %TIME% ERROR missing Python>> "%LOG_FILE%"
echo.
pause
exit /b 1

:old_python
echo Psy Observer Web could not start.
echo.
echo Python 3.11 or newer is required.
echo The Python found on PATH is too old.
echo Download a current Python from https://www.python.org/downloads/
echo.
echo Log: %LOG_FILE%
echo %DATE% %TIME% ERROR Python too old>> "%LOG_FILE%"
echo.
pause
exit /b 1

:no_spa
echo Psy Observer Web could not start.
echo.
echo Missing production web_dist. Re-download the Beta 3.1 archive.
echo.
echo Log: %LOG_FILE%
echo %DATE% %TIME% ERROR missing web_dist>> "%LOG_FILE%"
echo.
pause
exit /b 1

:no_bootstrap
echo Psy Observer Web could not start.
echo.
echo Missing scripts\bootstrap_psy_observer_env.py
echo.
pause
exit /b 1

:bootstrap_fail
echo.
echo Psy Observer Web could not prepare its Python environment.
echo First-run setup failed. See %LOG_FILE% for details.
echo Typical causes: no network, blocked pip, or incomplete Python install.
echo Fix the cause and run Psy Observer again.
echo.
echo %DATE% %TIME% ERROR bootstrap failed>> "%LOG_FILE%"
echo.
pause
exit /b 1

:fail
echo.
echo Psy Observer Web could not start.
echo Python reported exit code %ERR%.
echo See README.md and %LOG_FILE% for details.
echo.
pause
exit /b %ERR%
