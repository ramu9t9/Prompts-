#!/usr/bin/env python3
"""
Check database schema
"""

import sqlite3

def check_db_schema():
    conn = sqlite3.connect('option_chain.db')
    cursor = conn.cursor()
    
    # Get table info
    cursor.execute('PRAGMA table_info(option_snapshots)')
    columns = cursor.fetchall()
    
    print("Database schema:")
    for col in columns:
        print(f"  {col[1]} ({col[2]})")
    
    print(f"\nTotal columns: {len(columns)}")
    
    conn.close()

if __name__ == "__main__":
    check_db_schema() 