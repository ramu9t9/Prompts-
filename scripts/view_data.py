#!/usr/bin/env python3
"""
View and analyze collected option data from SQLite database
"""

import sqlite3
import pandas as pd
from datetime import datetime
import pytz

def safe_int(val):
    try:
        if isinstance(val, (int, float)):
            return int(val)
        if isinstance(val, str):
            return int(float(val))
        if hasattr(val, '__int__'):
            return int(val)
    except Exception:
        pass
    return 0

def view_latest_data():
    """View the most recent option data"""
    conn = sqlite3.connect('option_chain.db')
    
    # Get latest timestamp
    cursor = conn.cursor()
    cursor.execute('SELECT MAX(time) FROM option_snapshots')
    result = cursor.fetchone()
    latest_time = result[0] if result is not None else None
    
    print(f"📊 Latest Data Timestamp: {latest_time}")
    print("=" * 80)
    
    # Get latest data
    query = '''
    SELECT * FROM option_snapshots 
    WHERE time = ? 
    ORDER BY index_name, strike
    '''
    
    df = pd.read_sql_query(query, conn, params=(latest_time,))
    
    if not df.empty:
        print(f"📈 Found {len(df)} records")
        print("\n📋 Latest Option Data:")
        print(df[['index_name', 'strike', 'ce_ltp', 'ce_volume', 'pe_ltp', 'pe_volume']].to_string(index=False))
    else:
        print("❌ No data found")
    
    conn.close()

def view_summary_stats():
    """View summary statistics"""
    conn = sqlite3.connect('option_chain.db')
    
    print("📊 Database Summary Statistics")
    print("=" * 50)
    
    # Total records
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM option_snapshots')
    result = cursor.fetchone()
    total_records = result[0] if result is not None else 0
    print(f"📈 Total Records: {total_records}")
    
    # Unique timestamps
    cursor.execute('SELECT COUNT(DISTINCT time) FROM option_snapshots')
    result = cursor.fetchone()
    unique_times = result[0] if result is not None else 0
    print(f"🕐 Unique Timestamps: {unique_times}")
    
    # Data by index
    cursor.execute('SELECT index_name, COUNT(*) FROM option_snapshots GROUP BY index_name')
    index_counts = cursor.fetchall()
    print("\n📊 Records by Index:")
    for index_name, count in index_counts:
        print(f"  {index_name}: {count} records")
    
    # Date range
    cursor.execute('SELECT MIN(time), MAX(time) FROM option_snapshots')
    result = cursor.fetchone()
    if result is not None:
        min_time, max_time = result
    else:
        min_time, max_time = None, None
    print(f"\n📅 Date Range: {min_time} to {max_time}")
    
    conn.close()

def view_nifty_data():
    """View NIFTY specific data"""
    conn = sqlite3.connect('option_chain.db')
    
    print("📊 NIFTY Option Data Analysis")
    print("=" * 50)
    
    # Get latest NIFTY data
    query = '''
    SELECT * FROM option_snapshots 
    WHERE index_name = 'NIFTY' 
    ORDER BY time DESC, strike 
    LIMIT 22
    '''
    
    df = pd.read_sql_query(query, conn)
    
    if not df.empty:
        print(f"📈 Latest NIFTY Data ({df['time'].iloc[0]}):")
        print("\n🎯 ATM Strikes Analysis:")
        
        # Group by strike
        for strike in sorted(df['strike'].unique()):
            strike_data = df[df['strike'] == strike].iloc[0]
            print(f"\n  Strike {strike}:")
            print(f"    CE: LTP={strike_data['ce_ltp']:.2f}, Volume={strike_data['ce_volume']}")
            print(f"    PE: LTP={strike_data['pe_ltp']:.2f}, Volume={strike_data['pe_volume']}")
    else:
        print("❌ No NIFTY data found")
    
    conn.close()

def view_banknifty_data():
    """View BANKNIFTY specific data"""
    conn = sqlite3.connect('option_chain.db')
    
    print("📊 BANKNIFTY Option Data Analysis")
    print("=" * 50)
    
    # Get latest BANKNIFTY data
    query = '''
    SELECT * FROM option_snapshots 
    WHERE index_name = 'BANKNIFTY' 
    ORDER BY time DESC, strike 
    LIMIT 22
    '''
    
    df = pd.read_sql_query(query, conn)
    
    if not df.empty:
        print(f"📈 Latest BANKNIFTY Data ({df['time'].iloc[0]}):")
        print("\n🎯 ATM Strikes Analysis:")
        
        # Group by strike
        for strike in sorted(df['strike'].unique()):
            strike_data = df[df['strike'] == strike].iloc[0]
            print(f"\n  Strike {strike}:")
            print(f"    CE: LTP={strike_data['ce_ltp']:.2f}, Volume={strike_data['ce_volume']}")
            print(f"    PE: LTP={strike_data['pe_ltp']:.2f}, Volume={strike_data['pe_volume']}")
    else:
        print("❌ No BANKNIFTY data found")
    
    conn.close()

def view_high_volume_options():
    """View options with high volume"""
    conn = sqlite3.connect('option_chain.db')
    
    print("📊 High Volume Options Analysis")
    print("=" * 50)
    
    # Get latest data with high volume
    query = '''
    SELECT time, index_name, strike, ce_ltp, ce_volume, pe_ltp, pe_volume
    FROM option_snapshots 
    WHERE (ce_volume > 100 OR pe_volume > 100)
    ORDER BY time DESC, (ce_volume + pe_volume) DESC
    LIMIT 20
    '''
    
    df = pd.read_sql_query(query, conn)
    
    if not df.empty:
        print("🔥 High Volume Options (>100 volume):")
        print(df.to_string(index=False))
    else:
        print("❌ No high volume options found")
    
    conn.close()

def main():
    print("🔍 Angel One Options Data Viewer")
    print("=" * 50)
    
    try:
        # Check if database exists
        conn = sqlite3.connect('option_chain.db')
        conn.close()
        
        print("\n1️⃣ Database Summary:")
        view_summary_stats()
        
        print("\n2️⃣ Latest Data:")
        view_latest_data()
        
        print("\n3️⃣ NIFTY Analysis:")
        view_nifty_data()
        
        print("\n4️⃣ BANKNIFTY Analysis:")
        view_banknifty_data()
        
        print("\n5️⃣ High Volume Options:")
        view_high_volume_options()
        
    except sqlite3.OperationalError:
        print("❌ Database not found. Run the tracker first to collect data.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main() 