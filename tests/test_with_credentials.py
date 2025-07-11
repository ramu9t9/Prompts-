#!/usr/bin/env python3
"""
Test script for Angel One Options Analytics Tracker with actual credentials
This script tests the complete system with real API calls
"""

import os
import sys
from datetime import datetime
import pytz

# Add parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'angel_oi_tracker'))

def test_login():
    """Test Angel One login with actual credentials"""
    print("🔐 Testing Angel One login...")
    
    try:
        from angel_login import angel_login
        
        if angel_login.login():
            print("✅ Login successful!")
            return True
        else:
            print("❌ Login failed")
            return False
            
    except Exception as e:
        print(f"❌ Login test failed: {e}")
        return False

def test_index_ltp():
    """Test getting index LTP"""
    print("\n📈 Testing index LTP fetching...")
    
    try:
        from angel_login import angel_login
        from option_chain_fetcher import OptionChainFetcher
        
        if not angel_login.is_authenticated():
            print("❌ Not logged in. Cannot test LTP.")
            return False
        
        smart_api = angel_login.get_smart_api()
        fetcher = OptionChainFetcher(smart_api)
        
        # Test NIFTY LTP
        nifty_ltp = fetcher.get_index_ltp('NIFTY')
        if nifty_ltp:
            print(f"✅ NIFTY LTP: {nifty_ltp}")
        else:
            print("❌ Failed to get NIFTY LTP")
            return False
        
        # Test BANKNIFTY LTP
        banknifty_ltp = fetcher.get_index_ltp('BANKNIFTY')
        if banknifty_ltp:
            print(f"✅ BANKNIFTY LTP: {banknifty_ltp}")
        else:
            print("❌ Failed to get BANKNIFTY LTP")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ LTP test failed: {e}")
        return False

def test_expiry_dates():
    """Test getting expiry dates"""
    print("\n📅 Testing expiry date fetching...")
    
    try:
        from angel_login import angel_login
        from option_chain_fetcher import OptionChainFetcher
        
        if not angel_login.is_authenticated():
            print("❌ Not logged in. Cannot test expiry dates.")
            return False
        
        smart_api = angel_login.get_smart_api()
        fetcher = OptionChainFetcher(smart_api)
        
        # Test NIFTY expiry
        nifty_expiry = fetcher.get_current_expiry('NIFTY')
        if nifty_expiry:
            print(f"✅ NIFTY Expiry: {nifty_expiry}")
        else:
            print("❌ Failed to get NIFTY expiry")
            return False
        
        # Test BANKNIFTY expiry
        banknifty_expiry = fetcher.get_current_expiry('BANKNIFTY')
        if banknifty_expiry:
            print(f"✅ BANKNIFTY Expiry: {banknifty_expiry}")
        else:
            print("❌ Failed to get BANKNIFTY expiry")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Expiry test failed: {e}")
        return False

def test_option_chain():
    """Test option chain fetching"""
    print("\n📊 Testing option chain fetching...")
    
    try:
        from angel_login import angel_login
        from option_chain_fetcher import OptionChainFetcher
        
        if not angel_login.is_authenticated():
            print("❌ Not logged in. Cannot test option chain.")
            return False
        
        smart_api = angel_login.get_smart_api()
        fetcher = OptionChainFetcher(smart_api)
        
        # Test NIFTY option chain
        nifty_data = fetcher.fetch_and_filter_option_data('NIFTY', range_strikes=2)
        if nifty_data:
            print(f"✅ NIFTY: Found {len(nifty_data['option_data'])} options")
            print(f"   ATM Strike: {nifty_data['atm_strike']}")
            print(f"   Target Strikes: {nifty_data['target_strikes']}")
        else:
            print("❌ Failed to get NIFTY option chain")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Option chain test failed: {e}")
        return False

def test_database_storage():
    """Test database storage"""
    print("\n🗄️ Testing database storage...")
    
    try:
        from angel_login import angel_login
        from option_chain_fetcher import fetch_option_chain_data
        from store_option_data import store_option_chain_data
        
        if not angel_login.is_authenticated():
            print("❌ Not logged in. Cannot test storage.")
            return False
        
        smart_api = angel_login.get_smart_api()
        
        # Fetch data
        option_data = fetch_option_chain_data(smart_api)
        if not option_data:
            print("❌ No data to store")
            return False
        
        # Store data
        if store_option_chain_data(option_data):
            print("✅ Data stored successfully")
            return True
        else:
            print("❌ Failed to store data")
            return False
        
    except Exception as e:
        print(f"❌ Storage test failed: {e}")
        return False

def main():
    """Run all tests with actual credentials"""
    print("🚀 Angel One Options Analytics Tracker - Credential Test")
    print("=" * 60)
    
    tests = [
        ("Login Test", test_login),
        ("Index LTP Test", test_index_ltp),
        ("Expiry Date Test", test_expiry_dates),
        ("Option Chain Test", test_option_chain),
        ("Database Storage Test", test_database_storage)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                print(f"❌ {test_name} failed")
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! System is working perfectly.")
        print("\n🚀 You can now run:")
        print("1. python startup_backfill.py (for historical data)")
        print("2. python main.py (for real-time tracking)")
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        print("💡 Make sure:")
        print("   - Market is open (9:18 AM - 3:30 PM IST)")
        print("   - Your credentials are correct")
        print("   - You have API access enabled")
    
    # Cleanup
    try:
        from angel_login import angel_login
        if angel_login.is_authenticated():
            angel_login.logout()
    except:
        pass

if __name__ == "__main__":
    main() 