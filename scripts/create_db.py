import sqlite3
import os
from datetime import datetime

def create_database():
    """Initialize SQLite database with option_snapshots table"""
    
    # Connect to SQLite database in current directory
    conn = sqlite3.connect('option_chain.db')
    cursor = conn.cursor()
    
    # Create option_snapshots table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS option_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT,
            index_name TEXT,
            expiry TEXT,
            strike INTEGER,
            
            ce_oi REAL, ce_oi_change REAL, ce_oi_percent_change REAL,
            ce_ltp REAL, ce_ltp_change REAL, ce_ltp_percent_change REAL,
            ce_volume INTEGER, ce_iv REAL, ce_delta REAL, ce_theta REAL, ce_vega REAL, ce_gamma REAL,
            ce_vs_pe_oi_bar REAL,
            
            pe_oi REAL, pe_oi_change REAL, pe_oi_percent_change REAL,
            pe_ltp REAL, pe_ltp_change REAL, pe_ltp_percent_change REAL,
            pe_volume INTEGER, pe_iv REAL, pe_delta REAL, pe_theta REAL, pe_vega REAL, pe_gamma REAL,
            pe_vs_ce_oi_bar REAL
        )
    ''')
    
    # Create indexes for better query performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_time ON option_snapshots(time)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_index_strike ON option_snapshots(index_name, strike)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_expiry ON option_snapshots(expiry)')
    
    conn.commit()
    conn.close()
    
    print(f"✅ Database initialized successfully at {datetime.now()}")
    print("📊 Table 'option_snapshots' created with all required columns")
    print("🔍 Performance indexes added for time, index+strike, and expiry")

if __name__ == "__main__":
    create_database() 