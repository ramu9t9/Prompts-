from apscheduler.schedulers.blocking import BlockingScheduler
from angel_login import login
from option_chain_fetcher import fetch_option_chain_data
from store_option_data import store_option_data
from datetime import datetime
import pytz

# 🌐 India timezone
IST = pytz.timezone("Asia/Kolkata")

# ✅ Login once
login_result = login()
if not login_result:
    print("❌ Login failed. Exiting...")
    exit()

obj = login_result["smartapi"]
feed_token = login_result["feed_token"]

def fetch_and_store_for_index(index_name):
    try:
        print(f"\n📊 Starting fetch for {index_name}")
        raw_data = fetch_option_chain_data(obj, feed_token, index_name=index_name)

        if not raw_data:
            print(f"⚠️ No data fetched for {index_name}")
            return

        expiry = raw_data[0]['expiry'] if raw_data else "NA"
        store_option_data(index_name, expiry, raw_data)
        print(f"✅ {index_name} data stored successfully.")

    except Exception as e:
        print(f"❌ Error in fetch/store for {index_name}: {str(e)}")

def fetch_and_store_all():
    print(f"\n🕒 Running scheduled fetch at {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')}")
    fetch_and_store_for_index("NIFTY")
    fetch_and_store_for_index("BANKNIFTY")

# 🧠 Scheduler
scheduler = BlockingScheduler()
scheduler.add_job(fetch_and_store_all, "interval", minutes=3)

print("🚀 3-minute Option Chain tracker started...")
fetch_and_store_all()  # Initial call
scheduler.start()
