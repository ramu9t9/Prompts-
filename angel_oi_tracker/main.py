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
from option_chain_fetcher import fetch_option_chain_data, OptionChainFetcher, AdaptivePollingEngine
from store_option_data_mysql import store_option_chain_data, MySQLOptionDataStore
from utils.expiry_manager import get_current_expiry, get_all_expiries
from utils.market_calendar import MarketCalendar
from oi_analysis_engine import OIAnalysisEngine
from ai_trade_engine import AITradeEngine

# --- Begin BackfillSystem class (moved from backup_old_files/backfill_system.py) ---
import time
from store_option_data_mysql import MySQLOptionDataStore

class BackfillSystem:
    def __init__(self):
        self.ist_tz = pytz.timezone('Asia/Kolkata')
        self.store = MySQLOptionDataStore()
    def is_market_open(self):
        now = datetime.now(self.ist_tz)
        if now.weekday() >= 5:
            return False
        market_start = now.replace(hour=9, minute=18, second=0, microsecond=0)
        market_end = now.replace(hour=15, minute=30, second=0, microsecond=0)
        return market_start <= now <= market_end
    def get_market_hours(self, date=None):
        if date is None:
            date = datetime.now(self.ist_tz)
        market_start = date.replace(hour=9, minute=18, second=0, microsecond=0)
        market_end = date.replace(hour=15, minute=30, second=0, microsecond=0)
        return market_start, market_end
    def get_last_market_day(self):
        now = datetime.now(self.ist_tz)
        current_day = now
        while current_day.weekday() >= 5:
            current_day -= timedelta(days=1)
        return current_day
    def generate_backfill_timestamps(self, start_time, end_time):
        timestamps = []
        current_time = start_time
        while current_time <= end_time:
            timestamps.append(current_time)
            current_time += timedelta(minutes=3)
        return timestamps
    def check_existing_data(self, bucket_time, trading_symbol):
        try:
            connection = self.store.get_connection()
            if connection is None:
                return False
            cursor = connection.cursor()
            cursor.execute('''SELECT COUNT(*) FROM option_snapshots WHERE bucket_ts = %s AND trading_symbol = %s''', (bucket_time, trading_symbol))
            result = cursor.fetchone()
            connection.close()
            if result and len(result) > 0:
                (count_value,) = result
                return safe_int(count_value) > 0
            return False
        except Exception as e:
            print(f"⚠️  Error checking existing data: {str(e)}")
            return False
    def backfill_mid_market(self):
        print("🔄 Starting mid-market backfill...")
        try:
            today = datetime.now(self.ist_tz)
            market_start, market_end = self.get_market_hours(today)
            current_time = datetime.now(self.ist_tz)
            if current_time < market_start:
                print("✅ Market hasn't started yet. No backfill needed.")
                return True
            end_time = min(current_time, market_end)
            timestamps = self.generate_backfill_timestamps(market_start, end_time)
            print(f"📅 Backfilling {len(timestamps)} timestamps from {market_start.strftime('%H:%M')} to {end_time.strftime('%H:%M')}")
            return self._execute_backfill(timestamps, "mid-market")
        except Exception as e:
            print(f"❌ Error in mid-market backfill: {str(e)}")
            return False
    def backfill_complete_day(self, target_date=None):
        print("🔄 Starting complete day backfill...")
        try:
            if target_date is None:
                target_date = datetime.now(self.ist_tz)
            market_start, market_end = self.get_market_hours(target_date)
            timestamps = self.generate_backfill_timestamps(market_start, market_end)
            print(f"📅 Backfilling complete day: {target_date.strftime('%Y-%m-%d')}")
            print(f"📊 {len(timestamps)} timestamps from {market_start.strftime('%H:%M')} to {market_end.strftime('%H:%M')}")
            return self._execute_backfill(timestamps, "complete-day")
        except Exception as e:
            print(f"❌ Error in complete day backfill: {str(e)}")
            return False
    def backfill_last_market_day(self):
        print("🔄 Starting last market day backfill...")
        try:
            last_market_day = self.get_last_market_day()
            return self.backfill_complete_day(last_market_day)
        except Exception as e:
            print(f"❌ Error in last market day backfill: {str(e)}")
            return False
    def _execute_backfill(self, timestamps, backfill_type):
        try:
            if not angel_login.is_authenticated():
                print("🔐 Logging in to Angel One...")
                if not angel_login.login():
                    print("❌ Failed to login. Cannot perform backfill.")
                    return False
            smart_api = angel_login.get_smart_api()
            fetcher = OptionChainFetcher(smart_api)
            self.store.create_new_schema()
            success_count = 0
            total_processed = 0
            for i, timestamp in enumerate(timestamps, 1):
                print(f"🔄 Processing {i}/{len(timestamps)}: {timestamp.strftime('%H:%M:%S')}")
                try:
                    all_data = fetcher.fetch_all_indices_data(range_strikes=5)
                    if all_data:
                        for index_data in all_data:
                            index_name = index_data['index_name']
                            index_ltp = index_data['index_ltp']
                            options = index_data['options']
                            strikes_data = {}
                            for option in options:
                                strike = option['strike']
                                option_type = option['type']
                                if strike not in strikes_data:
                                    strikes_data[strike] = {'CE': {}, 'PE': {}}
                                strikes_data[strike][option_type] = {
                                    'oi': option.get('oi', 0),
                                    'ltp': option.get('ltp', 0)
                                }
                            for strike, strike_data in strikes_data.items():
                                trading_symbol = f"{index_name}{strike}"
                                if self.check_existing_data(timestamp, trading_symbol):
                                    continue
                                snapshot_data = {
                                    'bucket_ts': timestamp,
                                    'trading_symbol': trading_symbol,
                                    'option_type': 'XX',
                                    'strike': strike,
                                    'ce_oi': strike_data.get('CE', {}).get('oi', 0),
                                    'ce_price_close': index_ltp,
                                    'pe_oi': strike_data.get('PE', {}).get('oi', 0),
                                    'pe_price_close': index_ltp
                                }
                                ce_snapshot = snapshot_data.copy()
                                ce_snapshot['option_type'] = 'CE'
                                if self.store.insert_single_snapshot(ce_snapshot):
                                    success_count += 1
                                pe_snapshot = snapshot_data.copy()
                                pe_snapshot['option_type'] = 'PE'
                                if self.store.insert_single_snapshot(pe_snapshot):
                                    success_count += 1
                                total_processed += 2
                    time.sleep(1)
                except Exception as e:
                    print(f"❌ Error processing {timestamp}: {str(e)}")
                    continue
            print(f"🎉 {backfill_type} backfill completed!")
            print(f"✅ Successfully processed {success_count}/{total_processed} snapshots")
            return success_count > 0
        except Exception as e:
            print(f"❌ Error in backfill execution: {str(e)}")
            return False
    def run_smart_backfill(self):
        print("🧠 Running smart backfill analysis...")
        current_time = datetime.now(self.ist_tz)
        is_weekend = current_time.weekday() >= 5
        market_open = self.is_market_open()
        print(f"📅 Current time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📊 Weekend: {is_weekend}")
        print(f"📊 Market open: {market_open}")
        if is_weekend:
            print("🔄 Weekend detected - backfilling last market day...")
            return self.backfill_last_market_day()
        elif market_open:
            print("🔄 Market is open - backfilling from market start...")
            return self.backfill_mid_market()
        else:
            print("🔄 Market is closed - backfilling complete day...")
            return self.backfill_complete_day()
# --- End BackfillSystem class ---

def safe_int(val):
    try:
        if isinstance(val, (int, float)):
            return int(val)
        if isinstance(val, str):
            return int(float(val))
        # For Decimal, date, datetime, etc.
        if hasattr(val, '__int__'):
            return int(val)
    except Exception:
        pass
    return 0

class OptionsTracker:
    def __init__(self):
        self.ist_tz = pytz.timezone('Asia/Kolkata')
        self.scheduler = BlockingScheduler(timezone=self.ist_tz)
        self.calendar = MarketCalendar()
        self.datastore = MySQLOptionDataStore()
        self.analysis_engine = OIAnalysisEngine(self.datastore)
        self.ai_trade_engine = AITradeEngine(self.datastore)
        self.adaptive_polling_engine = None
        
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
            
            if result and len(result) > 0:
                count_value = result[0]
                if isinstance(count_value, (int, float, str)):
                    try:
                        return int(count_value) > 0
                    except Exception:
                        return False
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
        """Fetch and store data for all indices"""
        try:
            # Fetch complete snapshot
            fetcher = OptionChainFetcher(angel_login.get_smart_api())
            complete_snapshot = fetcher.fetch_complete_snapshot(range_strikes=5)
            
            if complete_snapshot:
                # Store data using Phase 1 schema
                store_option_chain_data(complete_snapshot, datetime.now(self.ist_tz).strftime('%Y-%m-%d %H:%M:%S'))
                
                # Generate AI trade insights for each index
                bucket_ts = datetime.now(self.ist_tz)
                for index_name in ['NIFTY', 'BANKNIFTY']:
                    try:
                        self.ai_trade_engine.generate_trade_insights(bucket_ts, index_name)
                    except Exception as e:
                        print(f"⚠️  AI trade insight generation failed for {index_name}: {str(e)}")
                
                return True
            return False
        except Exception as e:
            print(f"❌ Error in fetch_and_store_all: {str(e)}")
            return False
    
    def start_adaptive_polling(self):
        """Start the adaptive polling system with 20-second intervals"""
        try:
            print("🔄 Starting adaptive polling system...")
            
            # Check if logged in, if not, login
            if not angel_login.is_authenticated():
                print("🔐 Logging in to Angel One...")
                if not angel_login.login():
                    print("❌ Failed to login. Cannot start polling.")
                    return False
            
            # Get SmartAPI instance
            smart_api = angel_login.get_smart_api()
            
            # Create fetcher instance
            fetcher = OptionChainFetcher(smart_api)
            
            # Start the adaptive polling loop
            fetcher.start_live_poll()
                
        except Exception as e:
            print(f"❌ Error in adaptive polling: {str(e)}")
            return False
    
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
        """Start the APScheduler with adaptive polling and backfill"""
        try:
            print("🚀 Starting Angel One Options Analytics Tracker v3")
            print("=" * 60)
            
            # Initial login
            print("🔐 Logging in to Angel One...")
            if not angel_login.login():
                print("❌ Failed to login. Exiting.")
                sys.exit(1)
            
            # Initialize the new v3 schema
            print("\n📊 Initializing v3 schema...")
            from store_option_data_mysql import MySQLOptionDataStore
            store = MySQLOptionDataStore()
            store.create_new_schema()
            print("✅ v3 schema initialized")
            
            # Run smart backfill based on current situation
            print("\n🔄 Running smart backfill...")
            backfill_system = BackfillSystem()
            backfill_system.run_smart_backfill()
            print("✅ Backfill completed")
            
            # Add job to run adaptive polling every second on market days
            self.scheduler.add_job(
                func=self.start_adaptive_polling,
                trigger=CronTrigger(second='*/1'),  # Every second
                id='adaptive_polling',
                name='Adaptive Polling (20-second intervals)',
                max_instances=1,
                coalesce=True
            )
            
            print("\n⏰ Scheduler configured with:")
            print("   - Adaptive polling: Every second (20-second intervals)")
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
    """Main function with Phase 2-5 integration"""
    print("🚀 Starting Angel One Options Analytics Tracker - Phase 5")
    print("=" * 60)
    
    try:
        # Initialize components
        print("🔧 Initializing Phase 2-5 components...")
        
        # Initialize market calendar
        calendar = MarketCalendar()
        market_status = calendar.get_market_status()
        
        print(f"📅 Market Status:")
        print(f"   - Current Time: {market_status['current_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   - Day: {market_status['weekday_name']}")
        print(f"   - Market Live: {market_status['is_live']}")
        print(f"   - Market Hours: {market_status['market_start'].strftime('%H:%M')} - {market_status['market_end'].strftime('%H:%M')}")
        
        # Initialize data store
        datastore = MySQLOptionDataStore()
        datastore.create_new_schema()
        print("✅ Phase 1 schema initialized")
        
        # Initialize Phase 3 analysis engine
        analysis_engine = OIAnalysisEngine(datastore)
        print("✅ Phase 3 analysis engine initialized")
        
        # Initialize Phase 4 AI trade engine
        ai_engine = AITradeEngine(datastore)
        print("✅ Phase 4 AI trade engine initialized")
        
        # Initialize Phase 5 dashboard API
        print("🌐 Initializing Phase 5 dashboard API...")
        from dashboard_api import DashboardAPI
        dashboard_api = DashboardAPI()
        print("✅ Phase 5 dashboard API initialized")
        
        # Login to Angel One
        print("🔐 Logging in to Angel One...")
        if not angel_login.login():
            print("❌ Failed to login. Exiting.")
            return
        
        smart_api = angel_login.get_smart_api()
        if not smart_api:
            print("❌ Failed to get SmartAPI instance. Exiting.")
            return
        
        print("✅ Angel One authentication successful")
        
        # Initialize adaptive polling engine with analysis engine
        poller = AdaptivePollingEngine(smart_api, calendar, datastore, analysis_engine)
        
        # Phase 2 Logic: Market-aware startup
        if calendar.is_market_live_now():
            print("\n📈 Market is LIVE - Starting adaptive polling...")
            
            # Check if new market day and clear live table if needed
            if datastore.is_new_market_day():
                print("📅 New market day detected - clearing live tracking table")
                datastore.clear_live_tracking()
            
            # Check if we need to backfill from market start
            current_time = datetime.now(calendar.ist_tz)
            market_start, _ = calendar.get_market_hours()
            
            if current_time > market_start:
                print(f"🔄 Mid-market start detected - backfilling from {market_start.strftime('%H:%M')} to {current_time.strftime('%H:%M')}")
                
                # Backfill missing buckets from market start to now
                success = datastore.backfill_missing_buckets(
                    start_dt=market_start,
                    end_dt=current_time,
                    fetcher=poller.fetcher
                )
                
                if success:
                    print("✅ Mid-market backfill completed")
                else:
                    print("⚠️  Mid-market backfill had issues")
            
            # Start adaptive polling
            print("🚀 Starting adaptive live polling...")
            poller.start_live_poll()
            
        else:
            print("\n📉 Market is CLOSED - Running backfill operations...")
            
            # Check if it's weekend
            if market_status['is_weekend']:
                print("🔄 Weekend detected - backfilling last market day...")
                last_market_day = calendar.get_last_market_day()
                market_start, market_end = calendar.get_market_hours(last_market_day)
                
                success = datastore.backfill_missing_buckets(
                    start_dt=market_start,
                    end_dt=market_end,
                    fetcher=poller.fetcher
                )
                
                if success:
                    print("✅ Weekend backfill completed")
                else:
                    print("⚠️  Weekend backfill had issues")
                    
            else:
                # Market closed but weekday - backfill today's market hours
                print("🔄 Market closed - backfilling today's market hours...")
                market_start, market_end = calendar.get_market_hours()
                
                success = datastore.backfill_missing_buckets(
                    start_dt=market_start,
                    end_dt=market_end,
                    fetcher=poller.fetcher
                )
                
                if success:
                    print("✅ Closed market backfill completed")
                else:
                    print("⚠️  Closed market backfill had issues")
            
            print(f"⏰ Next market open: {calendar.next_open_datetime().strftime('%Y-%m-%d %H:%M')}")
        
        # Phase 5: Start Dashboard API
        print("\n🌐 Starting Phase 5 Dashboard API...")
        print("   - API Server: http://localhost:8000")
        print("   - Dashboard: Open dashboard_frontend.html in browser")
        print("   - WebSocket: ws://localhost:8000/ws")
        print("   - API Docs: http://localhost:8000/docs")
        
        # Start dashboard API in a separate thread
        import threading
        api_thread = threading.Thread(target=dashboard_api.run, daemon=True)
        api_thread.start()
        
        print("✅ Phase 5 dashboard API started successfully")
        
        print("\n🎉 All phases (1-5) startup completed successfully!")
        print("=" * 60)
        print("📊 System Status:")
        print("   ✅ Phase 1: Data Collection & Storage")
        print("   ✅ Phase 2: Market Calendar & Backfill")
        print("   ✅ Phase 3: Real-time Analytics")
        print("   ✅ Phase 4: AI Trade Intelligence")
        print("   ✅ Phase 5: Dashboard & API")
        print("=" * 60)
        
        # Keep main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Shutting down...")
        
    except KeyboardInterrupt:
        print("\n🛑 Stopping Options Tracker...")
    except Exception as e:
        print(f"❌ Error in main: {str(e)}")
    finally:
        # Cleanup
        if angel_login.is_authenticated():
            angel_login.logout()
        print("✅ Options Tracker stopped")

if __name__ == "__main__":
    main() 