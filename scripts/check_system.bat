@echo off
echo ========================================
echo Angel One Options Analytics Tracker
echo System Check
echo ========================================
echo.

echo Checking Python...
python --version

echo.
echo Checking current directory...
cd

echo.
echo Checking if files exist...
if exist ..\angel_oi_tracker\angel_config.txt (
    echo [OK] angel_config.txt found
) else (
    echo [ERROR] angel_config.txt missing
)

if exist ..\angel_oi_tracker\main.py (
    echo [OK] main.py found
) else (
    echo [ERROR] main.py missing
)

if exist ..\angel_oi_tracker\option_chain_fetcher.py (
    echo [OK] option_chain_fetcher.py found
) else (
    echo [ERROR] option_chain_fetcher.py missing
)

echo.
echo Checking packages...
python -c "import pyotp; print('[OK] pyotp installed')" 2>nul || echo [ERROR] pyotp not installed
python -c "import pytz; print('[OK] pytz installed')" 2>nul || echo [ERROR] pytz not installed
python -c "import smartapi; print('[OK] smartapi installed')" 2>nul || echo [ERROR] smartapi not installed

echo.
echo ========================================
echo System check completed!
echo ========================================
echo.
echo If all checks passed, you can run:
echo   cd ..\angel_oi_tracker
echo   python main.py
echo.
pause 