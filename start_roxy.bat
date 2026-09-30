@echo off
rem Runs Roxy and restarts her if she crashes. Output goes to logs\roxy.log.
rem Stops for good on: rr shutdown (0), missing/invalid token (2), already running (3).
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
if not exist logs mkdir logs

rem Keep the log from growing forever: start a new one past ~5 MB
for %%F in (logs\roxy.log) do if %%~zF GTR 5000000 move /y logs\roxy.log logs\roxy.old.log > nul

:loop
echo [%date% %time%] Starting Roxy >> logs\roxy.log
"roxy_env\Scripts\python.exe" roxy.py >> logs\roxy.log 2>&1
set CODE=%errorlevel%
echo [%date% %time%] Roxy exited with code %CODE% >> logs\roxy.log

if "%CODE%"=="0" goto end
if "%CODE%"=="2" goto end
if "%CODE%"=="3" goto end

rem Crash: wait a bit, then start again
timeout /t 15 /nobreak > nul
goto loop

:end
