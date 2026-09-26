@echo off
REM Psy Observer Web — Beta 1 launcher (Windows Explorer double-clickable).
REM Resolves %%~dp0 as project root. Targets psy_observer_web only (not Legacy Observer).
setlocal EnableExtensions

set "ROOT=%~dp0"
REM strip trailing backslash for PYTHONPATH consistency
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "PSY_OBSERVER_PROJECT_ROOT=%ROOT%"
set "PYTHONPATH=%ROOT%;%PYTHONPATH%"
set "LOG_DIR=%ROOT%\.psy_observer"
set "LOG_FILE=%LOG_DIR%\launcher.log"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

set "PY="
if defined PSY_OBSERVER_PYTHON if exist "%PSY_OBSERVER_PYTHON%" set "PY=%PSY_OBSERVER_PYTHON%"

if not defined PY if exist "%ROOT%\.venv_psy_web\Scripts\python.exe" set "PY=%ROOT%\.venv_psy_web\Scripts\python.exe"
if not defined PY if exist "%ROOT%\.venv\Scripts\python.exe" set "PY=%ROOT%\.venv\Scripts\python.exe"

if not defined PY (
  where py >nul 2>nul
  if not errorlevel 1 (
    for /f "delims=" %%I in ('where py') do (
      if not defined PY set "PY=%%I"
    )
  )
)

if not defined PY (
  where python >nul 2>nul
  if not errorlevel 1 (
    for /f "delims=" %%I in ('where python') do (
      if not defined PY set "PY=%%I"
    )
  )
)

if not defined PY goto :no_python

if not exist "%ROOT%\mechanistic_mind\ui\psy_observer_web\web_dist\index.html" goto :no_spa

cd /d "%ROOT%"
echo Starting Psy Observer Web ^(Beta 1^)...
"%PY%" -m mechanistic_mind.ui.psy_observer_web.launcher %*
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" goto :fail
exit /b 0

:no_python
echo Psy Observer Web could not start.
echo.
echo Python/dependency missing: no project venv ^(.venv_psy_web\Scripts\python.exe^)
echo and neither "py" nor "python" was found on PATH.
echo.
echo See README installation instructions.
echo Log: %LOG_FILE%
echo %DATE% %TIME% ERROR missing Python>> "%LOG_FILE%"
echo.
pause
exit /b 1

:no_spa
echo Psy Observer Web could not start.
echo.
echo The Observer interface is not built yet ^(missing production web_dist files^).
echo Rebuild with: cd web\psy-observer ^&^& npm run build
echo.
echo See README installation instructions.
echo Log: %LOG_FILE%
echo %DATE% %TIME% ERROR missing web_dist>> "%LOG_FILE%"
echo.
pause
exit /b 1

:fail
echo.
echo Psy Observer Web could not start.
echo Python reported exit code %ERR%.
echo See README installation instructions and %LOG_FILE% for details.
echo.
pause
exit /b %ERR%
