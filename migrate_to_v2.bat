@echo off
echo ========================================
echo OI Tracker v2 Database Migration
echo ========================================
echo.

echo Starting database migration...
cd scripts
python migrate_to_new_schema.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo Migration completed successfully!
    echo ========================================
    echo.
    echo Next steps:
    echo 1. Test the new system: cd angel_oi_tracker ^& python test_upgraded_system.py
    echo 2. Start live tracking: cd angel_oi_tracker ^& python main_v2.py
    echo.
) else (
    echo.
    echo ========================================
    echo Migration failed! Please check the errors above.
    echo ========================================
    echo.
)

pause 