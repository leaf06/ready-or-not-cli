@echo off
rem Windows launcher: ron [--seed N] [--no-color] [--scenario ID]
setlocal
if defined PYTHONPATH (set "PYTHONPATH=%~dp0;%PYTHONPATH%") else (set "PYTHONPATH=%~dp0")
where py >nul 2>nul
if %ERRORLEVEL%==0 (
    py -3 -m readyornot %*
) else (
    python -m readyornot %*
)
exit /b %ERRORLEVEL%
