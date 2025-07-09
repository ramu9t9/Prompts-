from datetime import datetime
import pytz

def now_ist():
    return datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S")

def log(msg):
    print(f"[{now_ist()}] {msg}")
