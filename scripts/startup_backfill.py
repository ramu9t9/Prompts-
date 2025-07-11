import os
import sys
from datetime import datetime, timedelta
import pytz
import time

# Add parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'angel_oi_tracker'))

from angel_login import angel_login
from option_chain_fetcher import fetch_option_chain_data
from store_option_data import store_option_chain_data

class BackfillEngine:
    def __init__(self):
        self.ist_tz = pytz.timezone('Asia/Kolkata')
        self.market_start = datetime.now(self.ist_tz).replace(hour=9, minute=18, second=0, microsecond=0)
        self.market_end = datetime.now(self.ist_tz).replace(hour=15, minute=30, second=0, microsecond=0)
        
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
        today_start = self.market_start
        current_time = datetime.now(self.ist_tz)
        
        # Only add today's data if market is open or was open today
        if current_time >= today_start:
            today_end = min(current_time, self.market_end)
            current_time = today_start
            
            while current_time <= today_end:
                timestamps.append(current_time.strftime('%Y-%m-%d %H:%M:%S'))
                current_time += timedelta(minutes=3)
        
        return timestamps
    
    def check_existing_data(self, timestamp):
        """Check if data already exists for the given timestamp"""
        try:
            import sqlite3
            conn = sqlite3.connect('angel_oi_tracker/option_chain.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT COUNT(*) FROM option_snapshots 
                WHERE time = ?
            ''', (timestamp,))
            
            count = cursor.fetchone()[0]
            conn.close()
            
            return count > 0
            
        except Exception as e:
            print(f"⚠️  Error checking existing data: {str(e)}")
            return False
    
    def run_backfill(self):
        """Run the backfill process"""
        print("🔄 Starting backfill process...")
        
        # Login to Angel One
        if not angel_login.login():
            print("❌ Failed to login. Cannot proceed with backfill.")
            return False
        
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
                print("✅ No missing data found. Backfill not needed.")
                return True
            
            # Process each missing timestamp
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
            
            print(f"🎉 Backfill completed! {success_count}/{len(missing_timestamps)} timestamps processed successfully")
            return success_count > 0
            
        except Exception as e:
            print(f"❌ Backfill error: {str(e)}")
            return False
        
        finally:
            # Logout
            angel_login.logout()

def main():
    """Main function to run backfill"""
    print("🚀 Angel One Options Analytics Tracker - Backfill Engine")
    print("=" * 60)
    
    backfill = BackfillEngine()
    success = backfill.run_backfill()
    
    if success:
        print("✅ Backfill process completed successfully")
    else:
        print("❌ Backfill process failed")
        sys.exit(1)

if __name__ == "__main__":
    main() 