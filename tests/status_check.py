#!/usr/bin/env python3
"""
Status check script for Angel One Options Analytics Tracker
"""

import os
import sys
from datetime import datetime
import pytz

def check_python():
    """Check Python version and environment"""
    print("🐍 Python Environment:")
    print(f"   Version: {sys.version}")
    print(f"   Executable: {sys.executable}")
    print(f"   Platform: {sys.platform}")
    return True

def check_directory():
    """Check current directory and files"""
    print("\n📁 Directory & Files:")
    current_dir = os.getcwd()
    print(f"   Current Directory: {current_dir}")
    
    required_files = [
        'angel_config.txt',
        'main.py',
        'option_chain_fetcher.py',
        'store_option_data.py',
        'angel_login.py',
        'requirements.txt'
    ]
    
    for file in required_files:
        if os.path.exists(file):
            print(f"   ✅ {file}")
        else:
            print(f"   ❌ {file} (missing)")
    
    return True

def check_database():
    """Check database status"""
    print("\n🗄️ Database Status:")
    db_file = 'option_chain.db'
    
    if os.path.exists(db_file):
        size = os.path.getsize(db_file)
        print(f"   ✅ Database exists ({size} bytes)")
        
        try:
            import sqlite3
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            conn.close()
            
            if tables:
                print(f"   ✅ Tables found: {[table[0] for table in tables]}")
            else:
                print("   ⚠️  No tables found")
                
        except Exception as e:
            print(f"   ❌ Database error: {e}")
    else:
        print("   ⚠️  Database not found (will be created on first run)")
    
    return True

def check_packages():
    """Check required packages"""
    print("\n📦 Required Packages:")
    
    packages = [
        'smartapi',
        'pyotp',
        'apscheduler',
        'pytz'
    ]
    
    for package in packages:
        try:
            __import__(package)
            print(f"   ✅ {package}")
        except ImportError:
            print(f"   ❌ {package} (not installed)")
    
    return True

def check_credentials():
    """Check credentials configuration"""
    print("\n🔐 Credentials Status:")
    
    config_file = 'angel_config.txt'
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                content = f.read()
                
            required_keys = ['API_KEY', 'CLIENT_ID', 'PASSWORD', 'TOTP_KEY']
            for key in required_keys:
                if key in content:
                    print(f"   ✅ {key} configured")
                else:
                    print(f"   ❌ {key} missing")
        except Exception as e:
            print(f"   ❌ Error reading config: {e}")
    else:
        print("   ❌ Config file not found")
    
    return True

def check_market_hours():
    """Check if market is currently open"""
    print("\n⏰ Market Hours Check:")
    
    ist_tz = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist_tz)
    
    print(f"   Current Time (IST): {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Day of Week: {now.strftime('%A')}")
    
    # Check if it's a weekday
    if now.weekday() >= 5:  # Saturday or Sunday
        print("   ❌ Market closed (weekend)")
        return False
    
    # Check market hours (9:18 AM to 3:30 PM IST)
    market_start = now.replace(hour=9, minute=18, second=0, microsecond=0)
    market_end = now.replace(hour=15, minute=30, second=0, microsecond=0)
    
    if market_start <= now <= market_end:
        print("   ✅ Market is open")
        return True
    else:
        print("   ❌ Market is closed")
        return False

def main():
    """Main status check function"""
    print("🚀 Angel One Options Analytics Tracker - Status Check")
    print("=" * 60)
    print(f"Check Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Run all checks
    check_python()
    check_directory()
    check_database()
    check_packages()
    check_credentials()
    market_open = check_market_hours()
    
    print("\n" + "=" * 60)
    print("📊 STATUS SUMMARY:")
    
    if market_open:
        print("✅ System is ready for real-time tracking!")
        print("\n🚀 To start tracking:")
        print("   python main.py")
        print("   OR double-click: run_tracker.bat")
    else:
        print("⚠️  Market is closed, but system is ready")
        print("\n📋 Available options:")
        print("   1. Test system: python simple_test.py")
        print("   2. Backfill data: python startup_backfill.py")
        print("   3. Wait for market to open (9:18 AM - 3:30 PM IST)")
    
    print("\n📖 For more information, see README.md")

if __name__ == "__main__":
    main() 