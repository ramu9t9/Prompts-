@echo off
echo ========================================
echo OI Tracker v2 System Test
echo ========================================
echo.

echo This will run a 10-minute test of the upgraded system.
echo Expected results:
echo - ~3 polls per minute (20-second intervals)
echo - ≤1 snapshot per 3-minute bucket
echo - All snapshots include candle close prices
echo.

set /p confirm="Continue with test? (y/N): "

if /i "%confirm%"=="y" (
    echo.
    echo Starting 10-minute test...
    cd angel_oi_tracker
    python test_upgraded_system.py
    
    if %ERRORLEVEL% EQU 0 (
        echo.
        echo ========================================
        echo Test completed successfully!
        echo ========================================
        echo.
        echo Check the results above to verify:
        echo - Polling frequency is correct
        echo - Snapshots per bucket is ≤1
        echo - OI changes were detected
        echo.
    ) else (
        echo.
        echo ========================================
        echo Test failed! Please check the errors above.
        echo ========================================
        echo.
    )
) else (
    echo Test cancelled.
)

pause 