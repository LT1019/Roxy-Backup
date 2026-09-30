@echo off
rem Stops the background Roxy started by start_roxy.bat (restart loop first, then the bot).
rem Prefer "rr shutdown" in Discord - it saves active sessions before stopping.
powershell -NoProfile -Command ^
  "Get-CimInstance Win32_Process | Where-Object { ($_.Name -eq 'cmd.exe' -and $_.CommandLine -like '*start_roxy.bat*') -or ($_.Name -like 'python*' -and $_.CommandLine -like '*roxy.py*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
echo Roxy stopped.
timeout /t 3 > nul
