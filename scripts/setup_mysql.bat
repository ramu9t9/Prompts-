@echo off
echo ========================================
echo MySQL Setup for Options Analytics Tracker
echo ========================================
echo.

echo Installing MySQL dependencies...
pip install mysql-connector-python==8.2.0 pandas==2.1.4

echo.
echo Setting up MySQL database...
python angel_oi_tracker/mysql_setup.py

echo.
echo MySQL setup completed!
echo.
echo Next steps:
echo 1. Make sure MySQL server is running
echo 2. Update your MySQL credentials if needed
echo 3. Run the migration script to transfer data
echo 4. Start the tracker with MySQL storage
echo.
pause 