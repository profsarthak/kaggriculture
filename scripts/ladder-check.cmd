@echo off
REM Scheduled ladder pull. Registered with Task Scheduler as "KaggricultureLadder".
REM Appends a timestamped run to data\ladder-runs.log; ladder.py itself keeps the
REM structured history in data\ladder-log.jsonl.

cd /d "%~dp0.."
echo. >> data\ladder-runs.log
echo ================ %DATE% %TIME% ================ >> data\ladder-runs.log
python ladder.py >> data\ladder-runs.log 2>&1
exit /b 0
