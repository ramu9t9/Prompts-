import sqlite3
from datetime import datetime, timedelta
import pytz
import time

from angel_login import login
from option_chain_fetcher import fetch_option_chain_data
from store_option_data import store_option_data

IST = pytz.timezone("Asia/Kolkata")

# Login
login_result = login()
if not login_result:
    print("❌ Login failed. Exiting...")
    exit()

smartapi = login_result["smartapi"]
feed_token = login_result["feed_token"]

def get_backfill_timestamps():
    now = datetime.now(IST)
    today = now.date()
    backfill_timestamps = []

    # Time boundaries
    market_start_time = datetime.strptime("09:18:00", "%H:%M:%S").time()
    market_end_time = datetime.strptime("15:30:00", "%H:%M:%S").time()

    # Always backfill yesterday
    yday = today - timedelta(days=1)
    start_yday = datetime.combine(yday, market_start_time).astimezone(IST)
    end_yday = datetime.combine(yday, market_end_time).astimezone(IST)

    curr = start_yday
    while curr <= end_yday:
        backfill_timestamps.append(curr)
        curr += timedelta(minutes=3)

    # If time is after market open, also include today up to now or market close
    if now.time() >= market_start_time:
        start_today = datetime.combine(today, market_start_time).astimezone(IST)
        end_today = min(now, datetime.combine(today, market_end_time).astimezone(IST))

        curr = start_today
        while curr <= end_today:
            backfill_timestamps.append(curr)
            curr += timedelta(minutes=3)

    return backfill_timestamps[::-1]  # Descending


def backfill_for_index(index_name):
    print(f"🔄 Starting backfill for {index_name}...")

    timestamps = get_backfill_timestamps()
    if not timestamps:
        print("⚠️ No timestamps to backfill.")
        return

    for ts in timestamps:
        print(f"📡 Fetching data for {index_name} at {ts.strftime('%Y-%m-%d %H:%M:%S')}")

        try:
            raw_data = fetch_option_chain_data(smartapi, feed_token, index_name=index_name, ts_override=ts)

            if not raw_data:
                print(f"⚠️ No data for {index_name} at {ts}")
                continue

            expiry = raw_data[0]['expiry']
            store_option_data(index_name, expiry, raw_data, override_time=ts)

            time.sleep(1.5)  # Slight delay to avoid API throttling

        except Exception as e:
            print(f"❌ Error at {ts} for {index_name}: {str(e)}")
            time.sleep(2)

    print(f"✅ Finished backfill for {index_name}.")

# Run for both indices
backfill_for_index("BANKNIFTY")
backfill_for_index("NIFTY")
