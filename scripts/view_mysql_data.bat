@echo off
echo ========================================
echo MySQL Data Viewer
echo ========================================
echo.

echo Loading data from MySQL database...
cd ..\angel_oi_tracker
python view_data_mysql.py

echo.
echo Data viewing completed!
echo.
pause 