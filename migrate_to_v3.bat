@echo off
echo ========================================
echo OI Tracker v3 Database Migration
echo ========================================
echo.

echo This will migrate your database to the new v3 schema.
echo Features:
echo - Simplified structure with essential data
echo - bucket_ts for 3-minute bucket timestamps
echo - trading_symbol for easy identification
echo - ce_price_close and pe_price_close from getCandleData
echo.

echo Starting database migration...
cd scripts
python migrate_to_v3_schema.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo Migration completed successfully!
    echo ========================================
    echo.
    echo Next steps:
    echo 1. Test the new system: cd angel_oi_tracker ^& python test_adaptive_system.py
    echo 2. Start live tracking: cd angel_oi_tracker ^& python main.py
    echo.
) else (
    echo.
    echo ========================================
    echo Migration failed! Please check the errors above.
    echo ========================================
    echo.
)

pause 