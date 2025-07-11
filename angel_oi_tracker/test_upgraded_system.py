#!/usr/bin/env python3
"""
Test script for the upgraded OI tracking system

This script tests the new adaptive polling system with:
- 20-second polling intervals
- OI change detection
- 3-minute bucket snapshots
- getCandleData integration

Run this for 10 minutes to verify exactly one row per 3-min bucket.
"""

import time
import sys
from datetime import datetime, timedelta
import pytz
from angel_login import angel_login
from option_chain_fetcher_v2 import AdaptiveOptionChainFetcher
from store_option_data_mysql_v2 import UpgradedMySQLOptionDataStore
import os

class UpgradedSystemTester:
    def __init__(self):
        self.ist_tz = pytz.timezone('Asia/Kolkata')
        self.test_duration = 10 * 60  # 10 minutes
        self.polling_interval = 20  # 20 seconds
        self.start_time = None
        self.end_time = None
        
        # Initialize components
        self.fetcher = None
        self.store = UpgradedMySQLOptionDataStore()
        
        # Test configuration
        self.indices = ['NIFTY', 'BANKNIFTY']
        self.range_strikes = 5
        
        # Statistics
        self.total_polls = 0
        self.snapshots_saved = 0
        self.oi_changes_detected = 0
        self.bucket_changes = 0
        
    def floor_to_3min(self, timestamp):
        """Floor timestamp to the nearest 3-minute bucket"""
        minutes_since_midnight = timestamp.hour * 60 + timestamp.minute
        floored_minutes = (minutes_since_midnight // 3) * 3
        floored_time = timestamp.replace(minute=floored_minutes, second=0, microsecond=0)
        return floored_time
    
    def verify_candle_data(self, candle_data, index_name):
        """Verify that candle data is properly fetched"""
        if not candle_data:
            print(f"❌ No candle data received for {index_name}")
            return False
        
        required_fields = ['open', 'high', 'low', 'close', 'volume']
        for field in required_fields:
            if field not in candle_data:
                print(f"❌ Missing field '{field}' in candle data for {index_name}")
                return False
        
        # Verify close price is reasonable
        close_price = candle_data['close']
        if close_price <= 0:
            print(f"❌ Invalid close price {close_price} for {index_name}")
            return False
        
        print(f"✅ Candle data verified for {index_name}: close={close_price}")
        return True
    
    def check_database_entries(self, bucket_time):
        """Check if database entries exist for the given bucket time"""
        try:
            import mysql.connector
            from mysql.connector import Error
            
            # Get MySQL connection details
            host = os.getenv('MYSQL_HOST', 'localhost')
            user = os.getenv('MYSQL_USER', 'root')
            password = os.getenv('MYSQL_PASSWORD', 'YourNewPassword')
            database = os.getenv('MYSQL_DATABASE', 'options_analytics')
            
            connection = mysql.connector.connect(
                host=host,
                user=user,
                password=password,
                database=database
            )
            
            cursor = connection.cursor()
            
            # Check entries for this bucket time
            cursor.execute('''
                SELECT COUNT(*) FROM option_snapshots 
                WHERE time = %s
            ''', (bucket_time,))
            
            result = cursor.fetchone()
            connection.close()
            
            if result and len(result) > 0:
                count_value, = result
                return int(count_value)
            return 0
            
        except Exception as e:
            print(f"⚠️  Error checking database entries: {str(e)}")
            return 0
    
    def run_test(self):
        """Run the complete test for 10 minutes"""
        print("🧪 Starting Upgraded OI Tracking System Test")
        print("=" * 60)
        print(f"⏰ Test Duration: {self.test_duration // 60} minutes")
        print(f"🔄 Polling Interval: {self.polling_interval} seconds")
        print(f"📊 Expected 3-minute buckets: {self.test_duration // 180}")
        print("=" * 60)
        
        try:
            # Login to Angel One
            print("🔐 Logging in to Angel One...")
            if not angel_login.login():
                print("❌ Failed to login. Cannot run test.")
                return False
            
            # Initialize fetcher
            smart_api = angel_login.get_smart_api()
            self.fetcher = AdaptiveOptionChainFetcher(smart_api)
            
            # Start test
            self.start_time = datetime.now(self.ist_tz)
            print(f"🚀 Test started at: {self.start_time.strftime('%H:%M:%S')}")
            
            # Run polling loop for test duration
            while datetime.now(self.ist_tz) - self.start_time < timedelta(seconds=self.test_duration):
                current_time = datetime.now(self.ist_tz)
                bucket_time = self.floor_to_3min(current_time)
                
                print(f"\n🔄 Poll #{self.total_polls + 1} at {current_time.strftime('%H:%M:%S')} (bucket: {bucket_time.strftime('%H:%M:%S')})")
                
                # Fetch data for each index
                all_data = []
                for index_name in self.indices:
                    try:
                        expiry_date = self.fetcher.get_expiry_date(index_name)
                        if expiry_date:
                            data = self.fetcher.fetch_complete_option_data(index_name, expiry_date, self.range_strikes)
                            if data:
                                # Verify candle data
                                if data.get('candle_data'):
                                    self.verify_candle_data(data['candle_data'], index_name)
                                
                                # Count OI changes
                                oi_changes = data.get('oi_changes', [])
                                if oi_changes:
                                    self.oi_changes_detected += len(oi_changes)
                                    print(f"📈 {len(oi_changes)} OI changes detected for {index_name}")
                                
                                if data.get('should_save', False):
                                    all_data.append(data)
                                    print(f"💾 Data ready for storage: {index_name}")
                                else:
                                    print(f"⏳ No storage needed: {index_name}")
                    except Exception as e:
                        print(f"❌ Error fetching data for {index_name}: {str(e)}")
                
                # Store data if any changes detected
                if all_data:
                    if self.store.process_and_store_option_data(all_data):
                        self.snapshots_saved += 1
                        print("✅ Data stored successfully")
                        
                        # Check database entries for this bucket
                        entries_count = self.check_database_entries(bucket_time)
                        print(f"📊 Database entries for bucket {bucket_time.strftime('%H:%M:%S')}: {entries_count}")
                    else:
                        print("❌ Failed to store data")
                
                self.total_polls += 1
                
                # Wait for next polling interval
                time.sleep(self.polling_interval)
            
            # Test completed
            self.end_time = datetime.now(self.ist_tz)
            self.print_test_results()
            
            return True
            
        except Exception as e:
            print(f"❌ Test error: {str(e)}")
            return False
        
        finally:
            # Logout
            if angel_login.is_authenticated():
                angel_login.logout()
    
    def print_test_results(self):
        """Print comprehensive test results"""
        print("\n" + "=" * 60)
        print("🧪 TEST RESULTS")
        print("=" * 60)
        
        test_duration = self.end_time - self.start_time
        expected_buckets = int(test_duration.total_seconds() // 180)  # 3 minutes = 180 seconds
        
        print(f"⏰ Test Duration: {test_duration}")
        print(f"🔄 Total Polls: {self.total_polls}")
        print(f"📊 Snapshots Saved: {self.snapshots_saved}")
        print(f"📈 OI Changes Detected: {self.oi_changes_detected}")
        print(f"🕐 Expected 3-min Buckets: {expected_buckets}")
        
        # Calculate statistics
        avg_polls_per_minute = self.total_polls / (test_duration.total_seconds() / 60)
        snapshots_per_bucket = self.snapshots_saved / max(expected_buckets, 1)
        
        print(f"\n📊 Statistics:")
        print(f"   Average polls per minute: {avg_polls_per_minute:.2f}")
        print(f"   Snapshots per 3-min bucket: {snapshots_per_bucket:.2f}")
        
        # Verify results
        print(f"\n✅ Verification:")
        
        if abs(avg_polls_per_minute - 3.0) <= 0.5:  # Allow some tolerance
            print("   ✅ Polling frequency is correct (~3 polls per minute)")
        else:
            print(f"   ❌ Polling frequency is incorrect: {avg_polls_per_minute:.2f} polls/min (expected ~3)")
        
        if snapshots_per_bucket <= 1.0:
            print("   ✅ Snapshots per bucket is within limits (≤1 per bucket)")
        else:
            print(f"   ❌ Too many snapshots per bucket: {snapshots_per_bucket:.2f}")
        
        if self.oi_changes_detected > 0:
            print("   ✅ OI changes were detected and processed")
        else:
            print("   ⚠️  No OI changes detected (this might be normal during low activity)")
        
        print("\n🎉 Test completed!")

def main():
    """Main test function"""
    tester = UpgradedSystemTester()
    success = tester.run_test()
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main() 