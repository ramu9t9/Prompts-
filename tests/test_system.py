#!/usr/bin/env python3
"""
Test script for Angel One Options Analytics Tracker
This script tests individual components without requiring actual API credentials
"""

import os
import sys
from datetime import datetime
import pytz

# Add parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'angel_oi_tracker'))

def test_imports():
    """Test if all required modules can be imported"""
    print("🧪 Testing imports...")
    
    try:
        from utils.symbols import get_index_token, INDEX_TOKENS
        from utils.atm_utils import find_atm_strike, get_strike_range
        from utils.strike_range import get_filtered_strikes
        print("✅ All utility modules imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_atm_calculation():
    """Test ATM calculation logic"""
    print("\n🧪 Testing ATM calculation...")
    
    try:
        from utils.atm_utils import find_atm_strike, get_strike_range
        
        # Test NIFTY ATM calculation
        nifty_ltp = 19500.50
        atm_strike = find_atm_strike(nifty_ltp, 'NIFTY')
        expected_strike = 19500  # Should round to nearest 50
        assert atm_strike == expected_strike, f"Expected {expected_strike}, got {atm_strike}"
        
        # Test BANKNIFTY ATM calculation
        banknifty_ltp = 44500.75
        atm_strike = find_atm_strike(banknifty_ltp, 'BANKNIFTY')
        expected_strike = 44500  # Should round to nearest 100
        assert atm_strike == expected_strike, f"Expected {expected_strike}, got {atm_strike}"
        
        print("✅ ATM calculation tests passed")
        return True
        
    except Exception as e:
        print(f"❌ ATM calculation test failed: {e}")
        return False

def test_strike_filtering():
    """Test strike filtering logic"""
    print("\n🧪 Testing strike filtering...")
    
    try:
        from utils.strike_range import get_filtered_strikes
        
        # Test NIFTY strike filtering
        nifty_ltp = 19500
        strike_info = get_filtered_strikes(nifty_ltp, 'NIFTY', range_strikes=2)
        
        expected_strikes = [19400, 19450, 19500, 19550, 19600]  # ATM ± 2 strikes
        assert strike_info['strikes'] == expected_strikes, f"Expected {expected_strikes}, got {strike_info['strikes']}"
        assert strike_info['atm_strike'] == 19500
        
        print("✅ Strike filtering tests passed")
        return True
        
    except Exception as e:
        print(f"❌ Strike filtering test failed: {e}")
        return False

def test_database_creation():
    """Test database creation"""
    print("\n🧪 Testing database creation...")
    
    try:
        # Import and run database creation
        from create_db import create_database
        create_database()
        
        # Check if database file exists
        if os.path.exists('angel_oi_tracker/option_chain.db'):
            print("✅ Database created successfully")
            return True
        else:
            print("❌ Database file not found")
            return False
            
    except Exception as e:
        print(f"❌ Database creation test failed: {e}")
        return False

def test_symbols():
    """Test symbol utilities"""
    print("\n🧪 Testing symbol utilities...")
    
    try:
        from utils.symbols import get_index_token, is_valid_index
        
        # Test valid indices
        assert get_index_token('NIFTY') == 26009
        assert get_index_token('BANKNIFTY') == 26017
        assert is_valid_index('NIFTY') == True
        assert is_valid_index('BANKNIFTY') == True
        
        # Test invalid index
        assert get_index_token('INVALID') == None
        assert is_valid_index('INVALID') == False
        
        print("✅ Symbol utility tests passed")
        return True
        
    except Exception as e:
        print(f"❌ Symbol utility test failed: {e}")
        return False

def test_configuration():
    """Test configuration setup"""
    print("\n🧪 Testing configuration...")
    
    # Check if example config exists
    if os.path.exists('angel_config.txt.example'):
        print("✅ Example configuration file found")
        config_ok = True
    else:
        print("⚠️  Example configuration file not found")
        config_ok = False
    
    # Check if actual config exists
    if os.path.exists('angel_config.txt'):
        print("✅ Actual configuration file found")
        config_ok = config_ok and True
    else:
        print("⚠️  Actual configuration file not found (create angel_config.txt with your credentials)")
        config_ok = False
    
    return config_ok

def main():
    """Run all tests"""
    print("🚀 Angel One Options Analytics Tracker - System Test")
    print("=" * 60)
    
    tests = [
        ("Import Test", test_imports),
        ("ATM Calculation", test_atm_calculation),
        ("Strike Filtering", test_strike_filtering),
        ("Database Creation", test_database_creation),
        ("Symbol Utilities", test_symbols),
        ("Configuration", test_configuration)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! System is ready to use.")
        print("\n📋 Next steps:")
        print("1. Create angel_config.txt with your Angel One credentials")
        print("2. Run: python startup_backfill.py (optional)")
        print("3. Run: python main.py (to start real-time tracking)")
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main() 