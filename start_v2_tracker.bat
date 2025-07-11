@echo off
echo ========================================
echo OI Tracker v2 - Adaptive Polling System
echo ========================================
echo.

echo Starting the upgraded OI tracking system...
echo.
echo Features:
echo - 20-second adaptive polling
echo - OI change detection
echo - 3-minute bucket snapshots
echo - Candle close price integration
echo.

cd angel_oi_tracker
python main_v2.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo Tracker stopped normally.
    echo ========================================
    echo.
) else (
    echo.
    echo ========================================
    echo Tracker stopped with errors.
    echo ========================================
    echo.
    echo Check the logs above for details.
    echo.
)

pause 