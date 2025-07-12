@echo off
echo Starting Complete System Test for OI Tracker v3...
echo.

cd angel_oi_tracker
python test_complete_system.py

echo.
echo Test completed. Press any key to exit...
pause >nul 