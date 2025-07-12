@echo off
echo ========================================
echo OI Tracker v3 Adaptive System Test
echo ========================================
echo.

echo This will run a 5-minute test of the adaptive polling system.
echo Expected results:
echo - ~3 polls per minute (20-second intervals)
echo - ≤1 snapshot per 3-minute bucket
echo - Uses index LTP as close price (simplified)
echo.

set /p confirm="Continue with test? (y/N): "

if /i "%confirm%"=="y" (
    echo.
    echo Starting 5-minute test...
    cd angel_oi_tracker
    python test_adaptive_system.py
    
    if %ERRORLEVEL% EQU 0 (
        echo.
        echo ========================================
        echo Test completed successfully!
        echo ========================================
        echo.
        echo Check the results above to verify:
        echo - Polling frequency is correct
        echo - Snapshots per bucket is ≤1
        echo - System works without rate limiting issues
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