# backfill.py
from angel_login import login
from option_chain_fetcher import fetch_option_chain_data
from utils import get_past_tokens
from datetime import datetime, timedelta

def run_backfill():
    print("🔄 Running backfill for Friday–Sunday...")

    obj, feed_token, _ = login()

    # Fetch past 3 days' tokens
    tokens_by_date = get_past_tokens(days_back=3)

    for date_str, tokens in tokens_by_date.items():
        print(f"📆 Backfilling for {date_str}...")
        fetch_option_chain_data(obj, feed_token, tokens, timestamp_override=date_str)

if __name__ == "__main__":
    run_backfill()
