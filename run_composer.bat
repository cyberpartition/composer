@echo off
setlocal
cd /d "%~dp0"
set "ROOT=%~dp0"
set "PY=%ROOT%.venv\Scripts\python.exe"
set "PYW=%ROOT%.venv\Scripts\pythonw.exe"
if not exist "%PY%" (
  echo Setting up Composer. This can take a few minutes the first time.
  python -m venv "%ROOT%.venv"
  if errorlevel 1 goto fail
  "%PY%" -m pip install --upgrade pip
  "%PY%" -m pip install -r "%ROOT%requirements.txt"
  if errorlevel 1 goto fail
)
if exist "%PYW%" (
  start "" "%PYW%" "%ROOT%composer.pyw"
) else (
  "%PY%" "%ROOT%composer.pyw"
)
exit /b 0

:fail
echo.
echo Composer could not finish setup. Install Python 3, then run this file again.
pause
exit /b 1
