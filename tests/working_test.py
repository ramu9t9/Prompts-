#!/usr/bin/env python3
"""
Working test script that doesn't depend on smartapi
"""

import os
import sys
from datetime import datetime
import pytz

# Add parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'angel_oi_tracker'))

def main():
    print("🚀 Angel One Options Analytics Tracker - Working Test")
    print("=" * 50)
    
    # Test 1: Python environment
    print(f"✅ Python version: {sys.version}")
    print(f"✅ Current directory: {os.getcwd()}")
    
    # Test 2: Check files
    print("\n📁 File Check:")
    files_to_check = [
        'angel_config.txt',
        'main.py',
        'option_chain_fetcher.py',
        'store_option_data.py',
        'angel_login.py',
        'requirements.txt',
        'utils/symbols.py',
        'utils/atm_utils.py',
        'utils/strike_range.py'
    ]
    
    all_files_exist = True
    for file in files_to_check:
        if os.path.exists(file):
            print(f"   ✅ {file}")
        else:
            print(f"   ❌ {file}")
            all_files_exist = False
    
    # Test 3: Check credentials
    print("\n🔐 Credentials Check:")
    if os.path.exists('angel_config.txt'):
        with open('angel_config.txt', 'r') as f:
            content = f.read()
            if 'API_KEY=P9ErUZG0' in content:
                print("   ✅ API Key configured")
            else:
                print("   ❌ API Key not found")
            
            if 'CLIENT_ID=R117172' in content:
                print("   ✅ Client ID configured")
            else:
                print("   ❌ Client ID not found")
    else:
        print("   ❌ Config file not found")
    
    # Test 4: Check market hours
    print("\n⏰ Market Hours Check:")
    try:
        import pytz
        ist_tz = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist_tz)
        print(f"   Current Time (IST): {now.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Day: {now.strftime('%A')}")
    except Exception as e:
        print(f"   ❌ Error getting IST time: {e}")
        now = datetime.now()  # fallback to local time
    # Check if it's a weekday
    if now.weekday() >= 5:  # Saturday or Sunday
        print("   ❌ Market closed (weekend)")
        market_open = False
    else:
        # Check market hours (9:18 AM to 3:30 PM IST)
        market_start = now.replace(hour=9, minute=18, second=0, microsecond=0)
        market_end = now.replace(hour=15, minute=30, second=0, microsecond=0)
        
        if market_start <= now <= market_end:
            print("   ✅ Market is open")
            market_open = True
        else:
            print("   ❌ Market is closed")
            market_open = False
    
    # Test 5: Try to import basic modules
    print("\n📦 Module Import Check:")
    try:
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'angel_oi_tracker'))
        from utils.symbols import get_index_token
        print("   ✅ Utils module imported")
    except Exception as e:
        print(f"   ❌ Utils import failed: {e}")
    
    try:
        import pyotp
        print("   ✅ pyotp imported")
    except Exception as e:
        print(f"   ❌ pyotp import failed: {e}")
    
    try:
        import pytz
        print("   ✅ pytz imported")
    except Exception as e:
        print(f"   ❌ pytz import failed: {e}")
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY:")
    
    if all_files_exist:
        print("✅ All files are present")
    else:
        print("❌ Some files are missing")
    
    if market_open:
        print("✅ Market is open - ready for real-time tracking")
        print("\n🚀 To start tracking:")
        print("   python main.py")
    else:
        print("⚠️  Market is closed, but system is ready")
        print("\n📋 Available options:")
        print("   1. Test with credentials: python test_with_credentials.py")
        print("   2. Backfill data: python startup_backfill.py")
        print("   3. Wait for market hours (9:18 AM - 3:30 PM IST)")
    
    print("\n💡 Note: smartapi package needs to be installed for API calls")
    print("   Run: pip install smartapi-python")

if __name__ == "__main__":
    main() 