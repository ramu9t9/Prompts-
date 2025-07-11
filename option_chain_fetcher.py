import math
from utils.atm_utils import get_atm_strike
from utils.strike_range import get_strike_range
from utils.symbols import get_exchange_tokens
from datetime import datetime

def fetch_option_chain_data(obj, feed_token, index_name="BANKNIFTY", ts_override=None):
    try:
        # 1. Get ATM dynamically
        atm_strike = get_atm_strike(obj, feed_token, index_name)
        strike_list = get_strike_range(atm_strike, range_size=5)

        # 2. Get tokens
        exchange_tokens = get_exchange_tokens(index_name, strike_list)

        # 3. Fetch market data
        print(f"📡 Fetching data for {index_name} at {ts_override or datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        result = obj.getMarketData("FULL", exchange_tokens)

        # 4. Parse fetched data
        formatted_data = []
        if result["status"]:
            for item in result["data"]["fetched"]:
                ts = item["tradingSymbol"]
                strike = extract_strike(ts)
                expiry = extract_expiry(ts)
                option_type = "CE" if "CE" in ts else "PE"

                # Convert timestamp override
                now = ts_override if ts_override else datetime.now()

                formatted_data.append({
                    "timestamp": now,
                    "index_name": index_name,
                    "expiry": expiry,
                    "strike": strike,
                    "type": option_type,
                    "ltp": item.get("ltp", 0),
                    "iv": item.get("iv", 0),
                    "delta": item.get("greeks", {}).get("delta", 0),
                    "theta": item.get("greeks", {}).get("theta", 0),
                    "vega": item.get("greeks", {}).get("vega", 0),
                    "gamma": item.get("greeks", {}).get("gamma", 0),
                    "openInterest": item.get("openInterest", 0),
                    "volume": item.get("volume", 0),
                })

        return formatted_data

    except Exception as e:
        print(f"❌ Error fetching {index_name}:", str(e))
        return []

def extract_strike(symbol):
    # Extract numerical strike from symbol
    digits = ''.join(filter(str.isdigit, symbol))
    return int(digits[-5:]) if digits else 0

def extract_expiry(symbol):
    # Extract expiry from symbol (e.g., BANKNIFTY11JUL243800CE → 11JUL24)
    try:
        return ''.join([c for c in symbol if c.isalnum()])[len("BANKNIFTY"):len("BANKNIFTY")+7]
    except:
        return "NA"
