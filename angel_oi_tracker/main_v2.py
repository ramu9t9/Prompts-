"""
Upgraded Angel One Options Analytics Tracker - Main Scheduler

This module implements the new adaptive polling system with:
- 20-second polling loop
- OI change detection
- 3-minute bucket snapshots
- getCandleData integration

Key Features:
- Adaptive polling based on OI changes
- 3-minute bucket alignment
- Live insert and backfill logic
- Uniform analytics with candle close prices

Always refer to official documentation: https://smartapi.angelone.in/docs
"""

import os
import sys
import time
import threading
from datetime import datetime, timedelta
import pytz
from angel_login import angel_login
from option_chain_fetcher_v2 import AdaptiveOptionChainFetcher
from store_option_data_mysql_v2 import UpgradedMySQLOptionDataStore

class AdaptiveOptionsTracker:
    def __init__(self):
        self.ist_tz = pytz.timezone('Asia/Kolkata')
        self.is_running = False
        self.polling_thread = None
        self.stop_event = threading.Event()
        
        # Initialize components
        self.fetcher = None
        self.store = UpgradedMySQLOptionDataStore()
        
        # Configuration
        self.polling_interval = 20  # seconds
        self.indices = ['NIFTY', 'BANKNIFTY']
        self.range_strikes = 5
        
    def is_market_open(self):
        """Check if market is currently open"""
        now = datetime.now(self.ist_tz)
        
        # Check if it's a weekday (Monday = 0, Sunday = 6)
        if now.weekday() >= 5:  # Saturday or Sunday
            return False
        
        # Check market hours (9:18 AM to 3:30 PM IST)
        market_start = now.replace(hour=9, minute=18, second=0, microsecond=0)
        market_end = now.replace(hour=15, minute=30, second=0, microsecond=0)
        
        return market_start <= now <= market_end
    
    def get_backfill_timestamps(self):
        """Generate timestamps for backfill from yesterday and today's missed data"""
        timestamps = []
        
        # Get yesterday's date
        yesterday = datetime.now(self.ist_tz) - timedelta(days=1)
        yesterday_start = yesterday.replace(hour=9, minute=18, second=0, microsecond=0)
        yesterday_end = yesterday.replace(hour=15, minute=30, second=0, microsecond=0)
        
        # Generate yesterday's timestamps (every 3 minutes)
        current_time = yesterday_start
        while current_time <= yesterday_end:
            timestamps.append(current_time.strftime('%Y-%m-%d %H:%M:%S'))
            current_time += timedelta(minutes=3)
        
        # Get today's missed data (from market start to current time)
        today_start = datetime.now(self.ist_tz).replace(hour=9, minute=18, second=0, microsecond=0)
        current_time = datetime.now(self.ist_tz)
        today_end = datetime.now(self.ist_tz).replace(hour=15, minute=30, second=0, microsecond=0)
        
        # Only add today's data if market is open or was open today
        if current_time >= today_start:
            # Use current time as the end point, not market end
            today_end = current_time
            current_time = today_start
            
            while current_time <= today_end:
                timestamps.append(current_time.strftime('%Y-%m-%d %H:%M:%S'))
                current_time += timedelta(minutes=3)
        
        return timestamps
    
    def check_existing_data(self, timestamp):
        """Check if data already exists for the given timestamp"""
        try:
            import mysql.connector
            from mysql.connector import Error
            
            # Get MySQL connection details from environment or use defaults
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
            
            cursor.execute('''
                SELECT COUNT(*) FROM option_snapshots 
                WHERE time = %s
            ''', (timestamp,))
            
            result = cursor.fetchone()
            connection.close()
            
            try:
                if result and len(result) > 0:
                    # MySQL COUNT(*) returns an integer, but let's be safe
                    # Use tuple unpacking to avoid linter issues
                    count_value, = result
                    if isinstance(count_value, (int, float)):
                        return int(count_value) > 0
                    elif isinstance(count_value, str):
                        return int(count_value) > 0
                    else:
                        return False
                return False
            except (ValueError, TypeError, IndexError):
                return False
            
        except Exception as e:
            print(f"⚠️  Error checking existing data: {str(e)}")
            return False
    
    def run_startup_backfill(self):
        """Run backfill on startup to fetch historical data"""
        print("🔄 Running startup backfill to fetch historical data...")
        
        try:
            smart_api = angel_login.get_smart_api()
            fetcher = AdaptiveOptionChainFetcher(smart_api)
            
            # Get backfill timestamps
            timestamps = self.get_backfill_timestamps()
            print(f"📅 Generated {len(timestamps)} timestamps for backfill")
            
            # Filter out timestamps that already have data
            missing_timestamps = []
            for ts in timestamps:
                if not self.check_existing_data(ts):
                    missing_timestamps.append(ts)
            
            print(f"📊 Found {len(missing_timestamps)} missing timestamps")
            
            if not missing_timestamps:
                print("✅ No missing data found. Historical data is up to date.")
                return True
            
            # Process each missing timestamp (limit to last 50 to avoid overwhelming)
            max_backfill = 50
            if len(missing_timestamps) > max_backfill:
                print(f"⚠️  Limiting backfill to last {max_backfill} timestamps to avoid overwhelming the system")
                missing_timestamps = missing_timestamps[-max_backfill:]
            
            success_count = 0
            for i, timestamp in enumerate(missing_timestamps, 1):
                print(f"🔄 Processing {i}/{len(missing_timestamps)}: {timestamp}")
                
                try:
                    # Parse timestamp
                    ts_obj = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                    ts_obj = self.ist_tz.localize(ts_obj)
                    
                    # Fetch data for each index
                    all_data = []
                    for index_name in self.indices:
                        expiry_date = fetcher.get_expiry_date(index_name)
                        if expiry_date:
                            data = fetcher.fetch_complete_option_data(index_name, expiry_date, self.range_strikes)
                            if data:
                                # Override bucket time for backfill
                                data['bucket_time'] = ts_obj
                                data['should_save'] = True
                                all_data.append(data)
                    
                    if all_data:
                        # Store data with the specific timestamp
                        if self.store.process_and_store_option_data(all_data):
                            success_count += 1
                            print(f"✅ Successfully backfilled data for {timestamp}")
                        else:
                            print(f"❌ Failed to store data for {timestamp}")
                    else:
                        print(f"⚠️  No data fetched for {timestamp}")
                    
                    # Small delay between requests
                    time.sleep(2)
                    
                except Exception as e:
                    print(f"❌ Error processing {timestamp}: {str(e)}")
                    continue
            
            print(f"🎉 Startup backfill completed! {success_count}/{len(missing_timestamps)} timestamps processed successfully")
            return success_count > 0
            
        except Exception as e:
            print(f"❌ Startup backfill error: {str(e)}")
            return False
    
    def polling_loop(self):
        """Main polling loop with 20-second intervals"""
        print(f"🔄 Starting adaptive polling loop (20-second intervals)")
        
        while not self.stop_event.is_set():
            try:
                # Check if market is open
                if not self.is_market_open():
                    print("⏰ Market is closed. Waiting for next check...")
                    time.sleep(60)  # Wait 1 minute before checking again
                    continue
                
                current_time = datetime.now(self.ist_tz)
                print(f"\n🔄 Polling at {current_time.strftime('%H:%M:%S')}")
                
                # Fetch data for each index
                all_data = []
                for index_name in self.indices:
                    try:
                        expiry_date = self.fetcher.get_expiry_date(index_name)
                        if expiry_date:
                            data = self.fetcher.fetch_complete_option_data(index_name, expiry_date, self.range_strikes)
                            if data and data.get('should_save', False):
                                all_data.append(data)
                                print(f"📈 Data ready for storage: {index_name}")
                            else:
                                print(f"⏳ No changes detected: {index_name}")
                    except Exception as e:
                        print(f"❌ Error fetching data for {index_name}: {str(e)}")
                
                # Store data if any changes detected
                if all_data:
                    if self.store.process_and_store_option_data(all_data):
                        print("✅ Data stored successfully")
                    else:
                        print("❌ Failed to store data")
                
                # Wait for next polling interval
                self.stop_event.wait(self.polling_interval)
                
            except Exception as e:
                print(f"❌ Error in polling loop: {str(e)}")
                time.sleep(5)  # Short delay on error
    
    def start_polling(self):
        """Start the adaptive polling system"""
        try:
            print("🚀 Starting Adaptive Angel One Options Analytics Tracker")
            print("=" * 60)
            
            # Initial login
            print("🔐 Logging in to Angel One...")
            if not angel_login.login():
                print("❌ Failed to login. Exiting.")
                sys.exit(1)
            
            # Initialize fetcher
            smart_api = angel_login.get_smart_api()
            self.fetcher = AdaptiveOptionChainFetcher(smart_api)
            
            # Run startup backfill to fetch historical data
            print("\n📊 Running startup backfill...")
            self.run_startup_backfill()
            print("✅ Startup backfill completed")
            
            # Start polling loop in a separate thread
            self.is_running = True
            self.polling_thread = threading.Thread(target=self.polling_loop)
            self.polling_thread.daemon = True
            self.polling_thread.start()
            
            print("\n⏰ Adaptive polling started (20-second intervals)")
            print("📊 Real-time data collection will start automatically")
            print("🛑 Press Ctrl+C to stop the tracker")
            print("=" * 60)
            
            # Keep main thread alive
            try:
                while self.is_running:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n🛑 Stopping Adaptive Options Tracker...")
                self.stop_polling()
            
        except Exception as e:
            print(f"❌ Scheduler error: {str(e)}")
            self.stop_polling()
    
    def stop_polling(self):
        """Stop the polling system and cleanup"""
        try:
            if self.is_running:
                self.is_running = False
                self.stop_event.set()
                
                if self.polling_thread and self.polling_thread.is_alive():
                    self.polling_thread.join(timeout=5)
            
            # Logout from Angel One
            if angel_login.is_authenticated():
                angel_login.logout()
            
            print("✅ Adaptive Options Tracker stopped successfully")
            
        except Exception as e:
            print(f"⚠️  Error stopping polling: {str(e)}")

def main():
    """Main function"""
    tracker = AdaptiveOptionsTracker()
    tracker.start_polling()

if __name__ == "__main__":
    main() 