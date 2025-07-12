"""
Phase 1 Test Script

This script tests the Phase 1 implementation:
1. Creates the new schema
2. Fetches a complete snapshot
3. Stores data in all three tables
4. Verifies the data was stored correctly

Always refer to official documentation: https://smartapi.angelone.in/docs

API Compliance:
- Data Usage: Use data only for authorized purposes
- Terms of Service: Follow Angel One's terms and conditions
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from angel_login import AngelOneLogin
from option_chain_fetcher import OptionChainFetcher
from store_option_data_mysql import (
    create_phase1_schema,
    store_phase1_complete_snapshot,
    insert_phase1_raw_data,
    insert_phase1_historical_data,
    insert_phase1_live_data
)
import mysql.connector
from mysql.connector import Error

def test_phase1_implementation():
    """Test the complete Phase 1 implementation"""
    print("🧪 Testing Phase 1 Implementation")
    print("=" * 50)
    
    # Step 1: Create schema
    print("\n📋 Step 1: Creating Phase 1 schema...")
    if create_phase1_schema():
        print("✅ Schema created successfully")
    else:
        print("❌ Failed to create schema")
        return False
    
    # Step 2: Initialize Angel One connection
    print("\n🔐 Step 2: Initializing Angel One connection...")
    try:
        angel_login = AngelOneLogin()
        if not angel_login.login():
            print("❌ Angel One login failed")
            return False
        smart_api = angel_login.get_smart_api()
        if not smart_api:
            print("❌ Failed to initialize Angel One connection")
            return False
        print("✅ Angel One connection established")
    except Exception as e:
        print(f"❌ Error initializing Angel One: {e}")
        return False
    
    # Step 3: Initialize fetcher and get complete snapshot
    print("\n📊 Step 3: Fetching complete snapshot...")
    try:
        fetcher = OptionChainFetcher(smart_api)
        complete_snapshot = fetcher.fetch_complete_snapshot(range_strikes=3)  # Reduced for testing
        
        if not complete_snapshot:
            print("❌ Failed to fetch complete snapshot")
            return False
        
        print(f"✅ Complete snapshot fetched:")
        print(f"   - Raw data: {len(complete_snapshot['raw_data'])} records")
        print(f"   - Historical data: {len(complete_snapshot['historical_data'])} records")
        print(f"   - Live data: {len(complete_snapshot['live_data'])} records")
        
    except Exception as e:
        print(f"❌ Error fetching snapshot: {e}")
        return False
    
    # Step 4: Store data in all tables
    print("\n💾 Step 4: Storing data in Phase 1 tables...")
    if store_phase1_complete_snapshot(complete_snapshot):
        print("✅ Data stored successfully in all tables")
    else:
        print("❌ Failed to store data")
        return False
    
    # Step 5: Verify data was stored
    print("\n🔍 Step 5: Verifying stored data...")
    if verify_stored_data():
        print("✅ Data verification successful")
    else:
        print("❌ Data verification failed")
        return False
    
    print("\n🎉 Phase 1 implementation test completed successfully!")
    return True

def verify_stored_data():
    """Verify that data was stored correctly in all tables"""
    try:
        from store_option_data_mysql import MySQLOptionDataStore
        store = MySQLOptionDataStore()
        connection = store.get_connection()
        
        if not connection:
            return False
        
        cursor = connection.cursor()
        
        # Check raw data table
        cursor.execute("SELECT COUNT(*) FROM options_raw_data")
        raw_result = cursor.fetchone()
        raw_count = 0
        if raw_result and len(raw_result) > 0:
            try:
                raw_count = int(str(raw_result[0]))
            except (ValueError, TypeError):
                raw_count = 0
        
        # Check historical data table
        cursor.execute("SELECT COUNT(*) FROM historical_oi_tracking")
        historical_result = cursor.fetchone()
        historical_count = 0
        if historical_result and len(historical_result) > 0:
            try:
                historical_count = int(str(historical_result[0]))
            except (ValueError, TypeError):
                historical_count = 0
        
        # Check live data table
        cursor.execute("SELECT COUNT(*) FROM live_oi_tracking")
        live_result = cursor.fetchone()
        live_count = 0
        if live_result and len(live_result) > 0:
            try:
                live_count = int(str(live_result[0]))
            except (ValueError, TypeError):
                live_count = 0
        
        connection.close()
        
        print(f"   - Raw data records: {raw_count}")
        print(f"   - Historical data records: {historical_count}")
        print(f"   - Live data records: {live_count}")
        
        # Basic validation - should have some data
        if raw_count > 0 and historical_count > 0 and live_count > 0:
            return True
        else:
            return False
            
    except Error as e:
        print(f"❌ Error verifying data: {e}")
        return False

def test_individual_functions():
    """Test individual Phase 1 functions"""
    print("\n🧪 Testing Individual Phase 1 Functions")
    print("=" * 50)
    
    # Test schema creation
    print("\n📋 Testing schema creation...")
    if create_phase1_schema():
        print("✅ Schema creation function works")
    else:
        print("❌ Schema creation function failed")
    
    # Test with sample data
    print("\n📊 Testing with sample data...")
    
    sample_raw_data = [{
        'bucket_ts': '2024-01-01 09:15:00',
        'trading_symbol': 'NIFTY24JAN19000CE',
        'strike': 19000,
        'option_type': 'CE',
        'ltp': 150.50,
        'volume': 1000,
        'oi': 5000,
        'price_change': 5.50,
        'change_percent': 3.78,
        'open_price': 145.00,
        'high_price': 155.00,
        'low_price': 144.00,
        'close_price': 145.00,
        'delta': 0.65,
        'gamma': 0.02,
        'theta': -0.15,
        'vega': 0.08,
        'iv': 18.50,
        'index_name': 'NIFTY',
        'expiry_date': '2024-01-25'
    }]
    
    sample_historical_data = [{
        'bucket_ts': '2024-01-01 09:15:00',
        'trading_symbol': 'NIFTY19000',
        'strike': 19000,
        'ce_oi': 5000,
        'pe_oi': 3000,
        'total_oi': 8000,
        'ce_oi_change': 100,
        'pe_oi_change': 50,
        'ce_oi_pct_change': 2.0,
        'pe_oi_pct_change': 1.7,
        'ce_ltp': 150.50,
        'pe_ltp': 120.30,
        'ce_ltp_change_pct': 3.78,
        'pe_ltp_change_pct': 2.15,
        'index_ltp': 19250.00,
        'ce_volume': 1000,
        'pe_volume': 800,
        'ce_volume_change': 50,
        'pe_volume_change': 30,
        'pcr': 0.60,
        'ce_pe_ratio': 1.67,
        'oi_quadrant': 'NEUTRAL',
        'confidence_score': 0,
        'strike_rank': None,
        'delta_band': 'ATM',
        'index_name': 'NIFTY',
        'expiry_date': '2024-01-25'
    }]
    
    sample_live_data = [{
        'bucket_ts': '2024-01-01 09:15:00',
        'trading_symbol': 'NIFTY19000',
        'strike': 19000,
        'ce_oi': 5000,
        'pe_oi': 3000,
        'ce_oi_change': 100,
        'pe_oi_change': 50,
        'pcr': 0.60,
        'oi_quadrant': 'NEUTRAL',
        'index_name': 'NIFTY'
    }]
    
    # Test individual insert functions
    if insert_phase1_raw_data(sample_raw_data):
        print("✅ Raw data insert function works")
    else:
        print("❌ Raw data insert function failed")
    
    if insert_phase1_historical_data(sample_historical_data):
        print("✅ Historical data insert function works")
    else:
        print("❌ Historical data insert function failed")
    
    if insert_phase1_live_data(sample_live_data):
        print("✅ Live data insert function works")
    else:
        print("❌ Live data insert function failed")

if __name__ == "__main__":
    print("🚀 Phase 1 Test Script")
    print("=" * 50)
    
    # Test individual functions first
    test_individual_functions()
    
    # Test complete implementation
    print("\n" + "=" * 50)
    test_phase1_implementation() 