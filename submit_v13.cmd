@echo off
REM One-shot: put the goose_target=0 build (v13) on both ladder slots once the
REM daily submission quota resets at 00:00 UTC. Registered as a scheduled task
REM so it runs whether or not a session is open; it deletes that task on the way
REM out so it cannot fire twice.
REM
REM The artefact was built from the commit it ships and preflighted: 12/12 model
REM checks, 108,754 against the starter, 7.7 ms/turn against a 1,000 ms limit.

REM A scheduled task runs with a bare environment, so the CLI is pinned by full
REM path rather than trusted to be on PATH.
set "KAGGLE=C:\Users\thegr\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\LocalCache\local-packages\Python313\Scripts\kaggle.exe"

cd /d "C:\Users\thegr\kaggriculture"
echo ==== submit v13 %DATE% %TIME% ==== >> data\submit-v13.log

if not exist "%KAGGLE%" (
  echo ERROR: kaggle CLI not found at %KAGGLE% >> data\submit-v13.log
  goto cleanup
)

if not exist submission.tar.gz (
  echo ERROR: submission.tar.gz missing, nothing sent >> data\submit-v13.log
  goto cleanup
)

"%KAGGLE%" competitions submit kaggriculture -f submission.tar.gz -m "v13: no coops (goose_target=0). Measured +4,078 mirror, CI [+1,766, +6,390], 14/16; panel worst case +4,078, beats every member. We were buying geese we never placed - three sat in the shed from day 12 to the end of the season." >> data\submit-v13.log 2>&1

"%KAGGLE%" competitions submit kaggriculture -f submission.tar.gz -m "v13b: same build as v13, second slot, so both slots run the current best agent and episode accrual stays high for the win-rate estimate." >> data\submit-v13.log 2>&1

"%KAGGLE%" competitions submissions kaggriculture >> data\submit-v13.log 2>&1

:cleanup
schtasks /delete /tn KaggricultureSubmitV13 /f >> data\submit-v13.log 2>&1
echo ==== done ==== >> data\submit-v13.log
