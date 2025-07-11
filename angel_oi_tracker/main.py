"""
Angel One Options Analytics Tracker - Main Scheduler

This module runs the real-time options data collection scheduler.
Always refer to official documentation: https://smartapi.angelone.in/docs

API Compliance:
- Rate Limits: https://smartapi.angelone.in/docs/rate-limits
- Session Management: Handle session expiry and re-authentication
- Terms of Service: Follow Angel One's terms and conditions
"""

import os
import sys
import time
from datetime import datetime, timedelta
import pytz
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from angel_login import angel_login
from option_chain_fetcher import fetch_option_chain_data
from store_option_data_mysql import store_option_chain_data

class OptionsTracker:
    def __init__(self):
        self.ist_tz = pytz.timezone('Asia/Kolkata')
        self.scheduler = BlockingScheduler(timezone='Asia/Kolkata')
        self.is_running = False
        
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
                    # Fetch data with timestamp override
                    option_data = fetch_option_chain_data(smart_api, ts_override=timestamp)
                    
                    if option_data:
                        # Store data with the specific timestamp
                        if store_option_chain_data(option_data, timestamp):
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
        
    def fetch_and_store_all(self):
        """Main function to fetch and store option chain data"""
        try:
            print(f"\n🔄 Fetching option chain data at {datetime.now(self.ist_tz).strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Check if logged in, if not, login
            if not angel_login.is_authenticated():
                print("🔐 Re-authenticating with Angel One...")
                if not angel_login.login():
                    print("❌ Failed to login. Skipping this cycle.")
                    return
            
            # Get SmartAPI instance
            smart_api = angel_login.get_smart_api()
            
            # Fetch option chain data
            option_data = fetch_option_chain_data(smart_api)
            
            if option_data:
                # Store the data
                if store_option_chain_data(option_data):
                    print("✅ Data fetch and store completed successfully")
                else:
                    print("❌ Failed to store data")
            else:
                print("⚠️  No data fetched")
                
        except Exception as e:
            print(f"❌ Error in fetch_and_store_all: {str(e)}")
    
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
    
    def start_scheduler(self):
        """Start the APScheduler with 3-minute intervals"""
        try:
            print("🚀 Starting Angel One Options Analytics Tracker")
            print("=" * 60)
            
            # Initial login
            print("🔐 Logging in to Angel One...")
            if not angel_login.login():
                print("❌ Failed to login. Exiting.")
                sys.exit(1)
            
            # Run startup backfill to fetch historical data
            print("\n📊 Running startup backfill...")
            self.run_startup_backfill()
            print("✅ Startup backfill completed")
            
            # Add job to run every 3 minutes during market hours
            self.scheduler.add_job(
                func=self.fetch_and_store_all,
                trigger=CronTrigger(minute='*/3'),  # Every 3 minutes
                id='option_chain_fetch',
                name='Fetch Option Chain Data',
                max_instances=1,
                coalesce=True
            )
            
            print("\n⏰ Scheduler configured to run every 3 minutes")
            print("📊 Real-time data collection will start automatically")
            print("🛑 Press Ctrl+C to stop the tracker")
            print("=" * 60)
            
            # Start the scheduler
            self.is_running = True
            self.scheduler.start()
            
        except KeyboardInterrupt:
            print("\n🛑 Stopping Options Tracker...")
            self.stop_scheduler()
        except Exception as e:
            print(f"❌ Scheduler error: {str(e)}")
            self.stop_scheduler()
    
    def stop_scheduler(self):
        """Stop the scheduler and cleanup"""
        try:
            if self.is_running:
                self.scheduler.shutdown()
                self.is_running = False
            
            # Logout from Angel One
            if angel_login.is_authenticated():
                angel_login.logout()
            
            print("✅ Options Tracker stopped successfully")
            
        except Exception as e:
            print(f"⚠️  Error stopping scheduler: {str(e)}")

def main():
    """Main function"""
    tracker = OptionsTracker()
    tracker.start_scheduler()

if __name__ == "__main__":
    main() 