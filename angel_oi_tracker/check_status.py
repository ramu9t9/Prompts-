"""
Status Check Script for OI Tracker v3

This script checks the status of the OI tracking system and shows recent data.
"""

import sys
import os
from datetime import datetime, timedelta
import pytz
from store_option_data_mysql import MySQLOptionDataStore

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

def check_system_status():
    """Check the overall system status"""
    print("🔍 OI Tracker v3 System Status Check")
    print("=" * 50)
    
    try:
        # Initialize database connection
        store = MySQLOptionDataStore()
        connection = store.get_connection()
        
        if connection is None:
            print("❌ Database connection failed")
            return False
        
        cursor = connection.cursor()
        
        # Check if table exists
        cursor.execute("SHOW TABLES LIKE 'option_snapshots'")
        table_exists = cursor.fetchone()
        
        if not table_exists:
            print("❌ option_snapshots table not found")
            return False
        
        # Get total record count
        cursor.execute("SELECT COUNT(*) FROM option_snapshots")
        result = cursor.fetchone()
        total_records = result[0] if result is not None else 0
        
        # Get latest record
        cursor.execute("SELECT MAX(time) FROM option_snapshots")
        result = cursor.fetchone()
        latest_time = result[0] if result is not None else None
        
        # Get recent records (last hour)
        one_hour_ago = datetime.now() - timedelta(hours=1)
        cursor.execute("SELECT COUNT(*) FROM option_snapshots WHERE bucket_ts >= %s", (one_hour_ago,))
        result = cursor.fetchone()
        recent_records = result[0] if result is not None else 0
        
        # Get unique trading symbols
        cursor.execute("SELECT COUNT(DISTINCT trading_symbol) FROM option_snapshots")
        result = cursor.fetchone()
        unique_symbols = result[0] if result is not None else 0
        
        connection.close()
        
        print(f"✅ Database connection: OK")
        print(f"📊 Total records: {total_records:,}")
        print(f"🕒 Latest record: {latest_time}")
        print(f"📈 Records in last hour: {recent_records}")
        print(f"📋 Unique trading symbols: {unique_symbols}")
        
        if latest_time:
            time_diff = datetime.now(pytz.timezone('Asia/Kolkata')) - latest_time.replace(tzinfo=pytz.timezone('Asia/Kolkata'))
            if time_diff.total_seconds() < 300:  # 5 minutes
                print("🟢 System Status: ACTIVE (Recent data found)")
            else:
                print("🟡 System Status: WARNING (No recent data)")
        else:
            print("🔴 System Status: INACTIVE (No data found)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking system status: {str(e)}")
        return False

def show_recent_data(limit=10):
    """Show recent data from the database"""
    print(f"\n📊 Recent Data (Last {limit} records):")
    print("-" * 50)
    
    try:
        store = MySQLOptionDataStore()
        connection = store.get_connection()
        
        if connection is None:
            print("❌ Database connection failed")
            return
        
        cursor = connection.cursor()
        
        # Get recent data
        cursor.execute("""
            SELECT bucket_ts, trading_symbol, option_type, strike, 
                   ce_oi, ce_price_close, pe_oi, pe_price_close
            FROM option_snapshots 
            ORDER BY bucket_ts DESC 
            LIMIT %s
        """, (limit,))
        
        records = cursor.fetchall()
        connection.close()
        
        if not records:
            print("❌ No data found")
            return
        
        # Display data
        print(f"{'Time':<12} {'Symbol':<15} {'Type':<4} {'Strike':<8} {'CE_OI':<10} {'CE_Price':<10} {'PE_OI':<10} {'PE_Price':<10}")
        print("-" * 90)
        
        for record in records:
            bucket_ts, trading_symbol, option_type, strike, ce_oi, ce_price_close, pe_oi, pe_price_close = record
            time_str = bucket_ts.strftime('%H:%M:%S') if bucket_ts else 'N/A'
            print(f"{time_str:<12} {trading_symbol:<15} {option_type:<4} {strike:<8} {ce_oi:<10} {ce_price_close:<10.2f} {pe_oi:<10} {pe_price_close:<10.2f}")
        
    except Exception as e:
        print(f"❌ Error showing recent data: {str(e)}")

def main():
    """Main function"""
    print("OI Tracker v3 Status Check")
    print("=" * 30)
    
    # Check system status
    status_ok = check_system_status()
    
    if status_ok:
        # Show recent data
        show_recent_data(10)
        
        print("\n" + "=" * 30)
        print("✅ Status check completed")
    else:
        print("\n❌ System status check failed")

if __name__ == "__main__":
    main() 