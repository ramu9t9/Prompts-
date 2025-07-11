@echo off
echo ========================================
echo SQLite to MySQL Migration Tool
echo ========================================
echo.

echo Starting data migration...
python angel_oi_tracker/migrate_to_mysql.py

echo.
echo Migration completed!
echo.
echo Next steps:
echo 1. Verify the migration was successful
echo 2. Test the tracker with MySQL storage
echo 3. Backup your SQLite database before removing it
echo.
pause 