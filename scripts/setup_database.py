#!/usr/bin/env python3
"""
Database setup script for Angel One Options Analytics Tracker
"""

import sqlite3
import os

def create_database():
    """Create the SQLite database and tables"""
    try:
        # Create database directory if it doesn't exist
        os.makedirs('angel_oi_tracker', exist_ok=True)
        
        # Connect to database (this will create it if it doesn't exist)
        conn = sqlite3.connect('angel_oi_tracker/option_chain.db')
        cursor = conn.cursor()
        
        # Create option_snapshots table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS option_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time TEXT NOT NULL,
                index_name TEXT NOT NULL,
                expiry TEXT NOT NULL,
                strike REAL NOT NULL,
                
                -- CE (Call) data
                ce_oi INTEGER DEFAULT 0,
                ce_oi_change INTEGER DEFAULT 0,
                ce_oi_percent_change REAL DEFAULT 0,
                ce_ltp REAL DEFAULT 0,
                ce_ltp_change REAL DEFAULT 0,
                ce_ltp_percent_change REAL DEFAULT 0,
                ce_volume INTEGER DEFAULT 0,
                ce_iv REAL DEFAULT 0,
                ce_delta REAL DEFAULT 0,
                ce_theta REAL DEFAULT 0,
                ce_vega REAL DEFAULT 0,
                ce_gamma REAL DEFAULT 0,
                ce_vs_pe_oi_bar REAL DEFAULT 0,
                
                -- PE (Put) data
                pe_oi INTEGER DEFAULT 0,
                pe_oi_change INTEGER DEFAULT 0,
                pe_oi_percent_change REAL DEFAULT 0,
                pe_ltp REAL DEFAULT 0,
                pe_ltp_change REAL DEFAULT 0,
                pe_ltp_percent_change REAL DEFAULT 0,
                pe_volume INTEGER DEFAULT 0,
                pe_iv REAL DEFAULT 0,
                pe_delta REAL DEFAULT 0,
                pe_theta REAL DEFAULT 0,
                pe_vega REAL DEFAULT 0,
                pe_gamma REAL DEFAULT 0,
                pe_vs_ce_oi_bar REAL DEFAULT 0,
                
                -- Metadata
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes for better performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_time ON option_snapshots(time)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_index_name ON option_snapshots(index_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_expiry ON option_snapshots(expiry)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_strike ON option_snapshots(strike)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_time_index ON option_snapshots(time, index_name)')
        
        conn.commit()
        conn.close()
        
        print("✅ Database created successfully!")
        print("📊 Table: option_snapshots")
        print("📁 Location: angel_oi_tracker/option_chain.db")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating database: {str(e)}")
        return False

def check_database():
    """Check if database exists and has the correct structure"""
    try:
        conn = sqlite3.connect('angel_oi_tracker/option_chain.db')
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='option_snapshots'")
        table_exists = cursor.fetchone() is not None
        
        if table_exists:
            # Check table structure
            cursor.execute("PRAGMA table_info(option_snapshots)")
            columns = cursor.fetchall()
            
            print("✅ Database exists and is properly configured")
            print(f"📊 Found {len(columns)} columns in option_snapshots table")
            
            # Show column names
            column_names = [col[1] for col in columns]
            print("📋 Columns:", ", ".join(column_names))
            
        else:
            print("❌ option_snapshots table not found")
            return False
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error checking database: {str(e)}")
        return False

def main():
    """Main function"""
    print("🚀 Angel One Options Analytics Tracker - Database Setup")
    print("=" * 60)
    
    # Check if database already exists
    if check_database():
        print("\n✅ Database is ready!")
        return
    
    # Create database if it doesn't exist
    print("\n🔧 Creating database...")
    if create_database():
        print("\n✅ Database setup completed successfully!")
    else:
        print("\n❌ Database setup failed!")
        return
    
    # Verify the setup
    print("\n🔍 Verifying database setup...")
    check_database()

if __name__ == "__main__":
    main() 