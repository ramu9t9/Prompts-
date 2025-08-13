import os
# Enhanced OI Monitor v2.1 — NIFTY (WS LTP + AI Coach + Paper Trade DB)
# Full script with:
# - Direct API Authentication (session + feed token)
# - SmartWebSocketV2 for ultra-low-latency ticks (spot + ATM±2 options)
# - 3-4 min OI/Greeks snapshot cycle for context (PCR/MaxPain/S-R)
# - Realtime Coach (ENTER/HOLD/EXIT/WAIT) every second using WS ticks
# - AI nudge via OpenRouterClient (optional)
# - SQLite signal logging (paper trading)

import time
import pandas as pd
import numpy as np
import hashlib
import requests
import io
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from datetime import datetime, timedelta
from dateutil import parser
from SmartApi import SmartConnect
import pyotp
import warnings
from collections import Counter, deque
import sqlite3
import re
import threading
import json
from collections import defaultdict, deque


sws = None  # global SmartWebSocketV2 instance

# Suppress pandas warnings
warnings.filterwarnings('ignore', category=pd.errors.SettingWithCopyWarning)

# === CONFIGURATION ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_IDS = [
    "1022980118", # Admin Bro
    "1585910202", # Ram Bro
    # "6905413717" # Charan Bro
]

ACTIVE_STRATEGY = "scalping"  # or "expert_spike"
# How many strikes on each side of ATM to watch via WS
ATM_WINDOW = 2  # watch ATM ±2 by default

# ====== API Authentication ======
obj = SmartConnect(api_key="IF0vWmnY")
user_id = "r117172"
pin = 9029
totp = pyotp.TOTP("Y4GDOA6SL5VOCKQPFLR5EM3HOY").now()
data = obj.generateSession(user_id, pin, totp)

# Feed token for WebSocket v2
try:
    FEED_TOKEN = obj.getfeedToken()
except Exception as e:
    print(f"⚠️ Could not fetch feed token: {e}")
    FEED_TOKEN = None

# ====== AI COACH — Inline OpenRouterClient (no external import) ======
USE_AI_COACH = True
_ai_client = None  # Will be initialized after OpenRouterClient class is defined

# Forward declarations to prevent "not defined" errors
def _db_conn(): pass
def start_ws_feed(initial=None): pass
def ws_stop(): pass
def ai_trade_coach(context: dict) -> dict: pass



# === Load & Filter Instruments ===
def fetch_instruments():
    response = requests.get("https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json")
    if response.ok:
        try:
            df = pd.DataFrame(response.json())
            print(f"Fetched and stored {len(df)} instruments")
            required_columns = ['name', 'instrumenttype', 'exch_seg', 'token', 'symbol', 'expiry']
            if not all(col in df.columns for col in required_columns):
                print(f"Warning: Missing columns in instrument_list. Available columns: {df.columns.tolist()}")
            return df
        except ValueError as e:
            print(f"Error parsing JSON response: {e}")
            return pd.DataFrame()
    print(f"Failed to fetch instruments. Status code: {response.status_code}, Response: {response.text}")
    return pd.DataFrame()

instrument_list = fetch_instruments()

# NEW: Add NIFTY index token with error handling
nifty_index_df = instrument_list[
    (instrument_list['name'] == 'NIFTY 50') &
    (instrument_list['instrumenttype'] == 'INDEX') &
    (instrument_list['exch_seg'] == 'NSE')
]
nifty_index_token = nifty_index_df['token'].iloc[0] if not nifty_index_df.empty else '99926000' # Hardcode fallback
if nifty_index_token == '99926000':
    print("Used hardcoded NIFTY index token: 99926000")

# Auto detect current expiry
def get_current_expiry(index_name='NIFTY'):
    current_time = datetime.now()
    options_df = instrument_list[(instrument_list['name'] == index_name) & (instrument_list['instrumenttype'] == 'OPTIDX')]
    unique_expiries = sorted(options_df['expiry'].unique())
    expiry_dates = []
    for exp in unique_expiries:
        try:
            date = datetime.strptime(exp, '%d%b%Y')
            expiry_dates.append(date)
        except ValueError:
            continue
    expiry_dates.sort()
    current_expiry = None
    for date in expiry_dates:
        if date > current_time and date.weekday() == 3: # Thursday
            current_expiry = date
            break
    if not current_expiry:
        for date in expiry_dates:
            if date > current_time:
                current_expiry = date
                break
    if not current_expiry and expiry_dates:
        current_expiry = max(expiry_dates)
    if not current_expiry:
        current_expiry = current_time
    current_expiry_str = current_expiry.strftime('%d%b%Y').upper()
    current_expiry_short = current_expiry.strftime('%d%b%y').upper()
    print(f"Detected current expiry: {current_expiry_str} (short: {current_expiry_short})")
    return current_expiry_str, current_expiry_short

current_expiry, current_expiry_short = get_current_expiry('NIFTY')

# === Dynamic symbol map builder based on ATM ± MAP_WINDOW ===
STRIKE_STEP = 50  # NIFTY strike step
MAP_WINDOW = int(os.getenv("MAP_WINDOW", "8"))  # how many strikes on each side for token map (WS + snapshots)

def _guess_spot_for_mapping():
    """
    Try to obtain a current spot for building ATM-centered maps.
    Order: WS cache -> FULL/LTP API -> median of available strikes -> hard fallback.
    """
    # 1) WS cache
    try:
        with WS_LOCK:
            cache_spot = TICKS_CACHE.get("NIFTY_SPOT", {}).get("ltp", None)
        if cache_spot and float(cache_spot) > 0:
            return float(cache_spot)
    except Exception:
        pass
    # 2) API (best-effort)
    try:
        # Using FULL market data with only the index token may return LTP
        data = obj.getMarketData("FULL", {"NSE": [nifty_index_token]})
        fetched = data.get("data", {}).get("fetched", [])
        if fetched:
            ltp = float(fetched[0].get("ltp") or fetched[0].get("last_traded_price") or 0.0)
            if ltp > 0:
                return ltp
    except Exception:
        try:
            # fallback to ltpData if available in environment
            ltpr = obj.ltpData("NSE", "NIFTY 50", str(nifty_index_token))
            ltp = float(ltpr.get("data", {}).get("ltp", 0.0))
            if ltp > 0:
                return ltp
        except Exception:
            pass
    # 3) Median of available strikes for current expiry
    try:
        strikes = instrument_list[(instrument_list['name']=="NIFTY") & (instrument_list['expiry']==current_expiry)]['strike'].dropna().astype(float)
        if not strikes.empty:
            return float(strikes.median())
    except Exception:
        pass
    # 4) Last known WS spot before hard fallback
    try:
        with WS_LOCK:
            last_spot = TICKS_CACHE.get("NIFTY_SPOT", {}).get("ltp", None)
        if last_spot and float(last_spot) > 0:
            print(f"📊 Using last known WS spot: {last_spot}")
            return float(last_spot)
    except Exception:
        pass
    # 5) Hard fallback (rare)
    return 24650.0

def build_symbol_token_maps():
    """
    Returns: filtered_oi, SYMBOL_TO_TOKEN, TOKEN_TO_SYMBOL, exchange_tokens, expected_strikes
    """
    spot_guess = _guess_spot_for_mapping()
    atm = int(round(spot_guess / STRIKE_STEP) * STRIKE_STEP)
    lower = atm - MAP_WINDOW * STRIKE_STEP
    upper = atm + MAP_WINDOW * STRIKE_STEP

    _base = instrument_list[
        (instrument_list['name'] == 'NIFTY') &
        (instrument_list['expiry'] == current_expiry) &
        (instrument_list['symbol'].str.endswith(('CE','PE')))
    ].copy()

    filtered = _base[(_base['strike'] >= lower) & (_base['strike'] <= upper)].copy()
    if filtered.empty:
        # As a fallback build a minimal window around the nearest available strike
        try:
            nearest = _base.iloc[(abs(_base['strike'] - atm)).argsort()[:1]]['strike'].iloc[0]
            lower = nearest - MAP_WINDOW * STRIKE_STEP
            upper = nearest + MAP_WINDOW * STRIKE_STEP
            filtered = _base[(_base['strike'] >= lower) & (_base['strike'] <= upper)].copy()
        except Exception:
            filtered = _base.head(0).copy()

    symbol_to_token = dict(zip(filtered['symbol'], filtered['token'].astype(str)))
    token_to_symbol = dict(zip(filtered['token'].astype(str), filtered['symbol']))

    expected = set()
    for strike in sorted(filtered['strike'].unique()):
        expected.add(f"NIFTY{current_expiry_short}{int(strike):05d}CE")
        expected.add(f"NIFTY{current_expiry_short}{int(strike):05d}PE")

    exch_tokens = {
        "NSE": [nifty_index_token] if nifty_index_token else [],
        "NFO": filtered['token'].astype(str).tolist()
    }
    return filtered, symbol_to_token, token_to_symbol, exch_tokens, expected

# FIXED: Updated strike range and expiry format
instrument_list['strike'] = instrument_list['symbol'].str.extract(r'NIFTY' + re.escape(current_expiry_short) + r'(\d{5})[CP]E').astype(float)

# You can widen/narrow these ranges as needed
filtered_oi, SYMBOL_TO_TOKEN, TOKEN_TO_SYMBOL, exchange_tokens, expected_strikes = build_symbol_token_maps()
symbol_to_strike = filtered_oi.set_index('symbol')['strike'].to_dict()
exchange_tokens = {
    "NSE": [nifty_index_token] if nifty_index_token else [],
    "NFO": filtered_oi['token'].tolist()
}

# Expected strikes CE+PE for selected band
expected_strikes = set()
for strike in filtered_oi['strike'].unique():
    expected_strikes.add(f"NIFTY{current_expiry_short}{int(strike):05d}CE")
    expected_strikes.add(f"NIFTY{current_expiry_short}{int(strike):05d}PE")
EXPECTED_STRIKE_COUNT = len(expected_strikes)
print(f"📊 Monitoring {EXPECTED_STRIKE_COUNT} option contracts across {len(filtered_oi['strike'].unique())} strike prices")

# Build symbol <-> token maps for WS lookups
# (built by build_symbol_token_maps())
# === ENHANCED CONFIGURATION ===
class OIAnalysisConfig:
    """Enhanced configuration for better trading signals"""
    # Minimum thresholds for signal detection
    MIN_OI_CHANGE_WEAK = 2.0
    MIN_OI_CHANGE_MODERATE = 5.0
    MIN_OI_CHANGE_STRONG = 10.0
    MIN_OI_CHANGE_EXTREME = 20.0

    MIN_PRICE_CHANGE_WEAK = 1.0
    MIN_PRICE_CHANGE_MODERATE = 2.5
    MIN_PRICE_CHANGE_STRONG = 5.0
    MIN_PRICE_CHANGE_EXTREME = 10.0

    # Volume-based filters (in lakhs)
    MIN_ABSOLUTE_OI_CHANGE = 50
    MIN_SIGNIFICANT_OI = 100
    MIN_MASSIVE_OI = 500

    # Signal weights
    LONG_BUILDUP_WEIGHT = 1.5
    SHORT_BUILDUP_WEIGHT = 2.0
    UNWINDING_WEIGHT = 1.0
    COVERING_WEIGHT = 2.5

# Enhanced monitoring configuration
ENHANCED_MONITORING = True
MINIMUM_SIGNAL_CONFIDENCE = 60
POSITION_SIZE_MULTIPLIER = {
    'HIGH': 1.0,
    'MODERATE': 0.6,
    'LOW': 0.3
}

# === Telegram Functions ===
def send_telegram_message(message, parse_mode='Markdown'):
    success_count = 0
    for chat_id in TELEGRAM_CHAT_IDS:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                'chat_id': chat_id,
                'text': message,
                'parse_mode': parse_mode,
                'disable_web_page_preview': True
            }
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                success_count += 1
            else:
                print(f"❌ Failed to send to {chat_id}: {response.status_code}")
        except Exception as e:
            print(f"❌ Error sending to {chat_id}: {e}")
    if success_count > 0:
        print(f"✅ Message sent to {success_count}/{len(TELEGRAM_CHAT_IDS)} chats")
        return True
    else:
        print(f"❌ Failed to send to all chats")
        return False

def create_enhanced_caption(label, changed_count, market_analysis, trading_signals):
    final_emoji = "✅" if "BULLISH" in market_analysis.get('direction','') else "🔴" if "BEARISH" in market_analysis.get('direction','') else "⚪"
    confidence_level = market_analysis.get('confidence_factor',0)
    caption = f"{label[:50]}"
    if changed_count > 0:
        caption += f"\n📈 {changed_count}/{EXPECTED_STRIKE_COUNT} updated"
    caption += f"\n{final_emoji} {market_analysis.get('direction','')[:20]} ({confidence_level:.0f}%)"
    caption += f"\n📊 {market_analysis.get('dominant_side','')}: {max(market_analysis.get('bullish_pct',0), market_analysis.get('bearish_pct',0)):.1f}%"
    caption += f"\nPCR: {market_analysis.get('pcr',0):.2f} | Max Pain: {market_analysis.get('max_pain',0)}"
    if trading_signals:
        caption += "\n🚨 Signals: "
        for signal in trading_signals[:1]:
            action_emoji = "🟢" if signal['action'] == 'BUY' else "🔴"
            caption += f"{action_emoji}{signal['action']}"
    return caption[:1000]

def send_telegram_image(image_buffer, caption=""):
    success_count = 0
    for chat_id in TELEGRAM_CHAT_IDS:
        try:
            image_buffer.seek(0)
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
            files = {'photo': ('OI_Analysis.png', image_buffer, 'image/png')}
            data = {
                'chat_id': chat_id,
                'caption': caption[:1024] if len(caption) > 1024 else caption,
                'parse_mode': 'Markdown'
            }
            response = requests.post(url, files=files, data=data, timeout=30)
            if response.status_code == 200:
                success_count += 1
                print(f"✅ Photo sent successfully to {chat_id}")
            else:
                print(f"⚠️ Photo failed for {chat_id} (status: {response.status_code})")
                print(f"Response: {response.text[:200]}")
                image_buffer.seek(0)
                url_doc = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
                files_doc = {'document': ('OI_Analysis.png', image_buffer, 'image/png')}
                data_doc = {
                    'chat_id': chat_id,
                    'caption': caption[:1024] if len(caption) > 1024 else caption,
                    'parse_mode': 'Markdown'
                }
                response_doc = requests.post(url_doc, files=files_doc, data=data_doc, timeout=30)
                if response_doc.status_code == 200:
                    success_count += 1
                    print(f"✅ Document sent successfully to {chat_id}")
                else:
                    print(f"❌ Both photo and document failed for {chat_id}: {response_doc.status_code}")
                    print(f"Document response: {response_doc.text[:200]}")
        except Exception as e:
            print(f"❌ Error sending to {chat_id}: {e}")
        time.sleep(0.5)
    if success_count > 0:
        print(f"✅ Image sent to {success_count}/{len(TELEGRAM_CHAT_IDS)} chats")
        return True
    else:
        print(f"❌ Failed to send image to all chats")
        return False

def clean_caption_text(text):
    if not text:
        return ""
    cleaned = text.replace('*', '').replace('_', '').replace('`', '')
    cleaned = cleaned.replace('[', '(').replace(']', ')')
    cleaned = cleaned.replace('{', '(').replace('}', ')')
    for char in ['\\', '|', '~', '#', '+', '-', '=', '!', '.', '>']:
        cleaned = cleaned.replace(char, ' ')
    cleaned = ' '.join(cleaned.split())
    return cleaned[:1000]

def send_telegram_message_simple(message, chat_id=None):
    if chat_id:
        chat_ids = [chat_id]
    else:
        chat_ids = TELEGRAM_CHAT_IDS
    success_count = 0
    clean_message = clean_caption_text(message)
    for cid in chat_ids:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                'chat_id': cid,
                'text': clean_message[:4000],
                'disable_web_page_preview': True
            }
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                success_count += 1
            else:
                print(f"❌ Message failed for {cid}: {response.status_code}")
        except Exception as e:
            print(f"❌ Error sending message to {cid}: {e}")
    return success_count > 0

def send_telegram_image_fixed(image_buffer, caption=""):
    success_count = 0
    safe_caption = clean_caption_text(caption) if caption else ""
    for chat_id in TELEGRAM_CHAT_IDS:
        try:
            image_buffer.seek(0)
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
            files = {'photo': ('OI_Analysis.png', image_buffer, 'image/png')}
            data = {'chat_id': chat_id, 'caption': safe_caption[:1024]}
            response = requests.post(url, files=files, data=data, timeout=30)
            if response.status_code == 200:
                success_count += 1
                print(f"✅ Photo sent successfully to {chat_id}")
            else:
                print(f"⚠️ Photo failed for {chat_id} (status: {response.status_code})")
                image_buffer.seek(0)
                data_no_caption = {'chat_id': chat_id}
                response_no_caption = requests.post(url, files={'photo': ('OI_Analysis.png', image_buffer, 'image/png')}, data=data_no_caption, timeout=30)
                if response_no_caption.status_code == 200:
                    success_count += 1
                    print(f"✅ Photo sent without caption to {chat_id}")
                    if safe_caption:
                        send_telegram_message_simple(safe_caption, chat_id)
                else:
                    print(f"❌ Both photo attempts failed for {chat_id}")
        except Exception as e:
            print(f"❌ Error sending to {chat_id}: {e}")
        time.sleep(0.5)
    if success_count > 0:
        print(f"✅ Image sent to {success_count}/{len(TELEGRAM_CHAT_IDS)} chats")
        return True
    else:
        print(f"❌ Failed to send image to all chats")
        return False

# === Helper Functions (shared) ===
def format_pct(val):
    if pd.isna(val):
        return " 0.0"
    elif val > 0:
        return f"+{val:5.1f}"
    elif val < 0:
        return f"{val:6.1f}"
    else:
        return f" 0.0"

def get_strikes_with_oi_changes(current_df, previous_df):
    changed_strikes = set()
    if previous_df.empty:
        return set(current_df['tradingSymbol'].tolist()) if not current_df.empty else set()
    current_oi_map = current_df.set_index('tradingSymbol')['opnInterest'].to_dict()
    previous_oi_map = previous_df.set_index('tradingSymbol')['opnInterest'].to_dict()
    for symbol in current_oi_map:
        current_oi = pd.to_numeric(current_oi_map.get(symbol, 0), errors='coerce')
        previous_oi = pd.to_numeric(previous_oi_map.get(symbol, 0), errors='coerce')
        if current_oi != previous_oi:
            changed_strikes.add(symbol)
    return changed_strikes

def get_latest_exchange_time(df):
    try:
        times = pd.to_datetime(df['exchTradeTime'], errors='coerce')
        return times.max()
    except:
        return datetime.now()

def get_underlying_price(current_df):
    """
    Enhanced function to get underlying NIFTY price with multiple fallbacks
    """
    nifty_df = current_df[
        (current_df.get('exchange', '') == 'NSE') &
        (current_df['tradingSymbol'].str.contains('NIFTY', na=False)) &
        (~current_df['tradingSymbol'].str.contains('CE|PE', na=False))
    ]
    if not nifty_df.empty:
        underlying_price = pd.to_numeric(nifty_df['ltp'].iloc[0], errors='coerce')
        if pd.notna(underlying_price) and underlying_price > 0:
            print(f"📊 Underlying NIFTY price: {underlying_price}")
            return underlying_price
    try:
        option_df = current_df[current_df['tradingSymbol'].str.contains('CE|PE', na=False)]
        if not option_df.empty:
            option_df['strike_extracted'] = option_df['tradingSymbol'].str.extract(r'(\d{5})(?:CE|PE)').astype(float)
            option_df = option_df.dropna(subset=['strike_extracted'])
            if not option_df.empty:
                ce_options = option_df[option_df['tradingSymbol'].str.contains('CE')]
                pe_options = option_df[option_df['tradingSymbol'].str.contains('PE')]
                if not ce_options.empty and not pe_options.empty:
                    ce_avg = ce_options.groupby('strike_extracted')['ltp'].mean()
                    pe_avg = pe_options.groupby('strike_extracted')['ltp'].mean()
                    common_strikes = ce_avg.index.intersection(pe_avg.index)
                    if len(common_strikes) > 0:
                        diff = abs(ce_avg[common_strikes] - pe_avg[common_strikes])
                        atm_strike = diff.idxmin()
                        print(f"📊 Estimated underlying from ATM: {atm_strike}")
                        return atm_strike
    except Exception as e:
        print(f"⚠️ Error calculating underlying from options: {e}")
    # Prefer last known WS cache spot if available before using hardcoded fallback
    try:
        with WS_LOCK:
            cache_spot = TICKS_CACHE.get("NIFTY_SPOT", {}).get("ltp", None)
        if cache_spot and float(cache_spot) > 0:
            print(f"📊 Using cache-based underlying price: {cache_spot}")
            return float(cache_spot)
    except Exception:
        pass
    # Last known WS spot before hard fallback
    try:
        with WS_LOCK:
            last_spot = TICKS_CACHE.get("NIFTY_SPOT", {}).get("ltp", None)
        if last_spot and float(last_spot) > 0:
            print(f"📊 Using last known WS spot: {last_spot}")
            return float(last_spot)
    except Exception:
        pass
    print("📊 Using ultimate fallback underlying price: 24650")
    return 24650

def fetch_snapshot():
    try:
        oi_data = obj.getMarketData("FULL", exchange_tokens)
        fetched_data = oi_data.get('data', {}).get('fetched', [])
        if fetched_data:
            times = sorted(set(row.get('exchTradeTime') for row in fetched_data if 'exchTradeTime' in row))
            print(f"🕒 [{datetime.now().strftime('%H:%M:%S')}] Data fetched - Latest exchTradeTime: {times[-1] if times else 'None'}")
        return pd.DataFrame(fetched_data)
    except Exception as e:
        print(f"⚠️ Snapshot fetch error: {e}")
        return pd.DataFrame()

# === SMART WEBSOCKET V2 (Ultra-low-latency ticks) ===
TICKS_CACHE = {}
WS_RUNNING = False
WS_LOCK = threading.Lock()
WS_THREAD = None

try:
    from SmartApi.smartWebSocketV2 import SmartWebSocketV2
except Exception as _ws_e:
    print(f"⚠️ SmartWebSocketV2 import failed: {_ws_e}")
    SmartWebSocketV2 = None

def _ws_on_open(wsapp):
    print("🔌 WSv2 opened")

def _ws_on_error(wsapp, error):
    print(f"⚠️ WSv2 error: {error}")

def _ws_on_close(wsapp):
    global WS_RUNNING
    WS_RUNNING = False
    print("🔌 WSv2 closed")

def _ws_on_data(wsapp, msg):
    """
    Store LTP/best prices/volume in shared cache.
    """
    try:
        token = str(msg.get("token") or msg.get("symboltoken") or "")
        ltp = float(msg.get("ltp") or msg.get("lastTradedPrice") or 0)
        bid = float(msg.get("bestBidPrice") or 0)
        ask = float(msg.get("bestAskPrice") or 0)
        vol = int(msg.get("tradedVolume") or msg.get("volume") or 0)
        ts  = msg.get("lastTradeTime") or msg.get("exchFeedTime") or datetime.now().strftime("%H:%M:%S")

        with WS_LOCK:
            sym = TOKEN_TO_SYMBOL.get(token) if 'TOKEN_TO_SYMBOL' in globals() else None
            if sym:
                TICKS_CACHE[sym] = {"ltp": ltp, "bid": bid, "ask": ask, "vol": vol, "ts": ts}
            elif token == str(nifty_index_token):
                TICKS_CACHE["NIFTY_SPOT"] = {"ltp": ltp, "bid": bid, "ask": ask, "vol": vol, "ts": ts}
    except Exception:
        pass



def pick_atm_strikes_for_watch(spot: float, window: int = ATM_WINDOW):
    if not pd.notna(spot) or spot <= 0:
        return []
    atm = int(round(spot / 50.0) * 50)
    desired = set()
    for off in range(-window, window+1):
        strike = atm + off * 50
        ce = f"NIFTY{current_expiry_short}{int(strike):05d}CE"
        pe = f"NIFTY{current_expiry_short}{int(strike):05d}PE"
        if ce in SYMBOL_TO_TOKEN: desired.add(ce)
        if pe in SYMBOL_TO_TOKEN: desired.add(pe)
    return sorted(desired)

def fetch_realtime_ticks_from_ws(symbols):
    """
    Return a dict {symbol: {ltp,bid,ask,vol,ts}, "NIFTY_SPOT": {...}} using the WS cache.
    """
    out = {}
    with WS_LOCK:
        if "NIFTY_SPOT" in TICKS_CACHE:
            out["NIFTY_SPOT"] = TICKS_CACHE["NIFTY_SPOT"].copy()
        for s in symbols:
            if s in TICKS_CACHE:
                out[s] = TICKS_CACHE[s].copy()
    return out


# === ENHANCED OI ANALYSIS FUNCTIONS ===
def analyze_oi_change_pattern(oi_change_pct, price_change_pct, option_type, absolute_oi_change=0):
    """
    ENHANCED OI analysis with improved thresholds and confidence scoring
    Returns: (pattern_name, market_impact, strength, confidence)
    """
    config = OIAnalysisConfig()

    # Enhanced filtering - only consider significant moves
    if (abs(oi_change_pct) < config.MIN_OI_CHANGE_WEAK or
        abs(price_change_pct) < config.MIN_PRICE_CHANGE_WEAK or
        absolute_oi_change < config.MIN_ABSOLUTE_OI_CHANGE):
        return "Neutral", 0, 0, 0

    def get_strength_score(oi_change, price_change):
        oi_score = 0
        price_score = 0
        if abs(oi_change) >= config.MIN_OI_CHANGE_EXTREME:
            oi_score = 4
        elif abs(oi_change) >= config.MIN_OI_CHANGE_STRONG:
            oi_score = 3
        elif abs(oi_change) >= config.MIN_OI_CHANGE_MODERATE:
            oi_score = 2
        elif abs(oi_change) >= config.MIN_OI_CHANGE_WEAK:
            oi_score = 1

        if abs(price_change) >= config.MIN_PRICE_CHANGE_EXTREME:
            price_score = 4
        elif abs(price_change) >= config.MIN_PRICE_CHANGE_STRONG:
            price_score = 3
        elif abs(price_change) >= config.MIN_PRICE_CHANGE_MODERATE:
            price_score = 2
        elif abs(price_change) >= config.MIN_PRICE_CHANGE_WEAK:
            price_score = 1
        return (oi_score + price_score) / 2

    strength = get_strength_score(oi_change_pct, price_change_pct)

    # Confidence (0-100)
    confidence = min(strength * 20 + (absolute_oi_change / config.MIN_ABSOLUTE_OI_CHANGE) * 10, 100)

    # Volume multiplier
    volume_multiplier = 1.0
    if absolute_oi_change >= config.MIN_MASSIVE_OI:
        volume_multiplier = 2.0
    elif absolute_oi_change >= config.MIN_SIGNIFICANT_OI:
        volume_multiplier = 1.5

    if option_type == "CE":
        if oi_change_pct > 0 and price_change_pct > 0:
            return "Call Long Buildup", config.LONG_BUILDUP_WEIGHT * volume_multiplier, strength, confidence
        elif oi_change_pct > 0 and price_change_pct < 0:
            return "Call Short Buildup", -config.SHORT_BUILDUP_WEIGHT * volume_multiplier, strength, confidence
        elif oi_change_pct < 0 and price_change_pct > 0:
            return "Call Short Covering", config.COVERING_WEIGHT * volume_multiplier, strength, confidence
        elif oi_change_pct < 0 and price_change_pct < 0:
            return "Call Long Unwinding", -config.UNWINDING_WEIGHT * volume_multiplier, strength, confidence
    elif option_type == "PE":
        if oi_change_pct > 0 and price_change_pct > 0:
            return "Put Long Buildup", -config.LONG_BUILDUP_WEIGHT * volume_multiplier, strength, confidence
        elif oi_change_pct > 0 and price_change_pct < 0:
            return "Put Short Buildup", config.SHORT_BUILDUP_WEIGHT * volume_multiplier, strength, confidence
        elif oi_change_pct < 0 and price_change_pct > 0:
            return "Put Short Covering", -config.COVERING_WEIGHT * volume_multiplier, strength, confidence
        elif oi_change_pct < 0 and price_change_pct < 0:
            return "Put Long Unwinding", config.UNWINDING_WEIGHT * volume_multiplier, strength, confidence

    return "Neutral", 0, 0, 0

# === SUPPORT/RESISTANCE AND MAX PAIN ===
def calculate_support_resistance(merged_df, underlying_price):
    """
    Hybrid S/R: Strikes with large OI build, adjusted for distance to underlying.
    """
    supports = []
    resistances = []
    for _, row in merged_df.iterrows():
        strike = row['strike']
        call_oi = row.get('opnInterest_call', 0)
        put_oi = row.get('opnInterest_put', 0)
        dist = abs(strike - underlying_price) / underlying_price if underlying_price > 0 else 0
        if dist > 0.05:
            continue  # Ignore far OTM
        strength = max(call_oi, put_oi) * (1 / (dist + 0.01))
        if put_oi > call_oi * 1.5 and strike < underlying_price:
            supports.append((strike, strength))
        if call_oi > put_oi * 1.5 and strike > underlying_price:
            resistances.append((strike, strength))
    supports.sort(key=lambda x: x[1], reverse=True)
    resistances.sort(key=lambda x: x[1], reverse=True)
    return supports[:3], resistances[:3]

def calculate_max_pain(merged_df):
    strikes = sorted(merged_df['strike'].unique())
    min_pain = float('inf')
    max_pain_strike = None
    for S in strikes:
        total_pain = 0
        for _, row in merged_df.iterrows():
            K = row['strike']
            call_oi = row.get('opnInterest_call', 0)
            put_oi = row.get('opnInterest_put', 0)
            total_pain += max(0, S - K) * call_oi
            total_pain += max(0, K - S) * put_oi
        if total_pain < min_pain:
            min_pain = total_pain
            max_pain_strike = S
    return max_pain_strike if max_pain_strike else 0

def calculate_comprehensive_market_direction(merged_df):
    """
    ENHANCED: Calculate market direction with improved confidence weighting
    """
    total_bullish_score = 0
    total_bearish_score = 0
    total_bullish_volume = 0
    total_bearish_volume = 0
    high_confidence_signals = 0
    total_signals = 0

    for _, row in merged_df.iterrows():
        # Call analysis
        call_oi_chg = row.get('oi_chg_pct_call', 0)
        call_price_chg = row.get('cls_chg_pct_call', 0)
        call_oi_abs = abs(row.get('opnInterest_call', 0) - row.get('prev_oi_call', 0)) * 100000
        cpatt, cimp, cstr, cconf = analyze_oi_change_pattern(call_oi_chg, call_price_chg, "CE", call_oi_abs)

        # Put analysis
        put_oi_chg = row.get('oi_chg_pct_put', 0)
        put_price_chg = row.get('cls_chg_pct_put', 0)
        put_oi_abs = abs(row.get('opnInterest_put', 0) - row.get('prev_oi_put', 0)) * 100000
        ppatt, pimp, pstr, pconf = analyze_oi_change_pattern(put_oi_chg, put_price_chg, "PE", put_oi_abs)

        if cconf > 30:
            total_signals += 1
            if cconf > 60:
                high_confidence_signals += 1
            w = cimp * (cconf / 100)
            if w > 0:
                total_bullish_score += abs(w)
                total_bullish_volume += call_oi_abs / 100000
            else:
                total_bearish_score += abs(w)
                total_bearish_volume += call_oi_abs / 100000

        if pconf > 30:
            total_signals += 1
            if pconf > 60:
                high_confidence_signals += 1
            w = pimp * (pconf / 100)
            if w > 0:
                total_bullish_score += abs(w)
                total_bullish_volume += put_oi_abs / 100000
            else:
                total_bearish_score += abs(w)
                total_bearish_volume += put_oi_abs / 100000

    total_score = total_bullish_score + total_bearish_score
    if total_score > 0:
        bullish_pct = (total_bullish_score / total_score) * 100
        bearish_pct = (total_bearish_score / total_score) * 100
    else:
        bullish_pct = 50
        bearish_pct = 50

    score_diff = bullish_pct - bearish_pct
    confidence_factor = (high_confidence_signals / max(total_signals, 1)) * 100

    if total_signals < 3:
        direction = "INSUFFICIENT_DATA"
        trend = "Waiting for more data"
    elif confidence_factor < 30:
        direction = "NEUTRAL"
        trend = "Low confidence signals"
    elif abs(score_diff) < 10:
        direction = "NEUTRAL"
        trend = "Market is balanced"
    elif score_diff > 40 and confidence_factor > 60:
        direction = "STRONGLY BULLISH"
        trend = "Strong buying momentum with high confidence"
    elif score_diff > 25 and confidence_factor > 50:
        direction = "BULLISH"
        trend = "Buyers in control"
    elif score_diff > 10:
        direction = "MILDLY BULLISH"
        trend = "Slight buying bias"
    elif score_diff < -40 and confidence_factor > 60:
        direction = "STRONGLY BEARISH"
        trend = "Strong selling pressure with high confidence"
    elif score_diff < -25 and confidence_factor > 50:
        direction = "BEARISH"
        trend = "Sellers in control"
    else:
        direction = "MILDLY BEARISH"
        trend = "Slight selling bias"

    pcr = merged_df['opnInterest_put'].sum() / merged_df['opnInterest_call'].sum() if merged_df['opnInterest_call'].sum() > 0 else 0
    max_pain = calculate_max_pain(merged_df)

    return {
        'direction': direction,
        'trend': trend,
        'bullish_pct': round(bullish_pct, 1),
        'bearish_pct': round(bearish_pct, 1),
        'bullish_volume': round(total_bullish_volume, 2),
        'bearish_volume': round(total_bearish_volume, 2),
        'confidence_factor': round(confidence_factor, 1),
        'high_confidence_signals': high_confidence_signals,
        'total_signals': total_signals,
        'dominant_side': 'Buyers' if bullish_pct > bearish_pct else 'Sellers' if bearish_pct > bullish_pct else 'Balanced',
        'pcr': pcr,
        'max_pain': max_pain
    }

def calculate_strike_verdict_new(row):
    call_oi_chg = row.get('oi_chg_pct_call', 0)
    call_price_chg = row.get('cls_chg_pct_call', 0)
    put_oi_chg = row.get('oi_chg_pct_put', 0)
    put_price_chg = row.get('cls_chg_pct_put', 0)

    call_oi_abs = abs(row.get('opnInterest_call', 0) - row.get('prev_oi_call', 0)) * 100000
    put_oi_abs = abs(row.get('opnInterest_put', 0) - row.get('prev_oi_put', 0)) * 100000

    call_pattern, call_impact, call_strength, call_confidence = analyze_oi_change_pattern(
        call_oi_chg, call_price_chg, "CE", call_oi_abs
    )
    put_pattern, put_impact, put_strength, put_confidence = analyze_oi_change_pattern(
        put_oi_chg, put_price_chg, "PE", put_oi_abs
    )

    total_volume = call_oi_abs + put_oi_abs
    if total_volume > 0 and (call_confidence > 30 or put_confidence > 30):
        weighted_score = (
            (call_impact * call_confidence * call_oi_abs) +
            (put_impact * put_confidence * put_oi_abs)
        ) / (total_volume * 100)
        avg_confidence = (call_confidence + put_confidence) / 2
    else:
        weighted_score = 0
        avg_confidence = 0

    if avg_confidence < 30:
        return "Neutral (Low Confidence)"
    elif abs(weighted_score) < 0.5:
        return "Neutral"
    elif weighted_score >= 2.0:
        return f"Strong Bullish ({avg_confidence:.0f}%)"
    elif weighted_score >= 1.0:
        return f"Moderate Bullish ({avg_confidence:.0f}%)"
    elif weighted_score > 0:
        return f"Mild Bullish ({avg_confidence:.0f}%)"
    elif weighted_score <= -2.0:
        return f"Strong Bearish ({avg_confidence:.0f}%)"
    elif weighted_score <= -1.0:
        return f"Moderate Bearish ({avg_confidence:.0f}%)"
    else:
        return f"Mild Bearish ({avg_confidence:.0f}%)"

# === TRADING SIGNAL FUNCTIONS ===
def generate_trading_signal(merged_df, market_analysis):
    signals = []
    if (market_analysis['direction'] in ['STRONGLY BULLISH', 'BULLISH'] and
        market_analysis['confidence_factor'] > 60):
        signals.append({
            'action': 'BUY',
            'type': 'INDEX_LONG',
            'confidence': market_analysis['confidence_factor'],
            'reason': f"{market_analysis['direction']} with {market_analysis['confidence_factor']:.0f}% confidence"
        })
    elif (market_analysis['direction'] in ['STRONGLY BEARISH', 'BEARISH'] and
          market_analysis['confidence_factor'] > 60):
        signals.append({
            'action': 'SELL',
            'type': 'INDEX_SHORT',
            'confidence': market_analysis['confidence_factor'],
            'reason': f"{market_analysis['direction']} with {market_analysis['confidence_factor']:.0f}% confidence"
        })

    pcr = market_analysis['pcr']
    if pcr > 1.3:
        signals.append({
            'action': 'BUY',
            'type': 'PCR_OVERSOLD',
            'confidence': min((pcr - 1.0) * 50, 90),
            'reason': f"PCR {pcr:.2f} indicates oversold conditions"
        })
    elif pcr < 0.7:
        signals.append({
            'action': 'SELL',
            'type': 'PCR_OVERBOUGHT',
            'confidence': min((1.0 - pcr) * 50, 90),
            'reason': f"PCR {pcr:.2f} indicates overbought conditions"
        })
    return signals

def validate_trading_signals(trading_signals, market_analysis, risk_metrics):
    validated = []
    for signal in trading_signals:
        if signal['confidence'] < MINIMUM_SIGNAL_CONFIDENCE:
            continue
        adjusted_confidence = signal['confidence']
        if risk_metrics['risk_level'] == 'HIGH':
            adjusted_confidence *= 0.7
        elif risk_metrics['risk_level'] == 'MODERATE':
            adjusted_confidence *= 0.85
        if adjusted_confidence < 50:
            continue
        confidence_level = "HIGH" if adjusted_confidence > 75 else "MODERATE" if adjusted_confidence > 60 else "LOW"
        position_size = POSITION_SIZE_MULTIPLIER[confidence_level]
        max_position = risk_metrics['max_position_pct'] / 100
        final_position_size = min(position_size, max_position)
        v = signal.copy()
        v['adjusted_confidence'] = round(adjusted_confidence, 1)
        v['position_size'] = final_position_size
        v['risk_level'] = risk_metrics['risk_level']
        v['stop_loss_pct'] = risk_metrics['stop_loss_pct']
        validated.append(v)
    return validated

def analyze_pcr_regime(pcr_value):
    if pcr_value > 1.5:
        return {'regime': 'EXTREME_OVERSOLD','signal': 'STRONG_BUY','confidence': 90,'description': 'Extreme put accumulation, strong reversal expected'}
    elif pcr_value > 1.3:
        return {'regime': 'OVERSOLD','signal': 'BUY','confidence': 75,'description': 'Heavy put buildup, potential bounce'}
    elif pcr_value < 0.5:
        return {'regime': 'EXTREME_OVERBOUGHT','signal': 'STRONG_SELL','confidence': 90,'description': 'Extreme call accumulation, strong correction expected'}
    elif pcr_value < 0.7:
        return {'regime': 'OVERBOUGHT','signal': 'SELL','confidence': 75,'description': 'Heavy call buildup, potential pullback'}
    else:
        return {'regime': 'NEUTRAL','signal': 'HOLD','confidence': 50,'description': 'Balanced put-call ratio'}

def calculate_risk_metrics(merged_df, market_analysis):
    risk_level = "LOW"
    if (market_analysis['pcr'] > 1.5 or market_analysis['pcr'] < 0.5 or
        market_analysis['confidence_factor'] < 40):
        risk_level = "HIGH"
    elif (abs(market_analysis['bullish_pct'] - market_analysis['bearish_pct']) < 15 or
          market_analysis['confidence_factor'] < 60):
        risk_level = "MODERATE"
    max_position_pct = {'LOW': 100,'MODERATE': 60,'HIGH': 30}[risk_level]
    return {
        'risk_level': risk_level,
        'max_position_pct': max_position_pct,
        'stop_loss_pct': 2.0 if risk_level == "LOW" else 1.5 if risk_level == "MODERATE" else 1.0
    }

def log_enhanced_trading_signals(trading_signals, market_analysis):
    if trading_signals:
        risk_metrics = calculate_risk_metrics(None, market_analysis)
        validated = validate_trading_signals(trading_signals, market_analysis, risk_metrics)
        if validated:
            print(f"\n🎯 VALIDATED TRADING SIGNALS:")
            print(f"📊 Market Risk Level: {risk_metrics['risk_level']}")
            print(f"🛡️ Max Position Size: {risk_metrics['max_position_pct']}%")
            print(f"⛔ Stop Loss: {risk_metrics['stop_loss_pct']}%")
            print("-" * 80)
            for s in validated:
                confidence_emoji = "🔥" if s['adjusted_confidence'] > 80 else "⚡" if s['adjusted_confidence'] > 65 else "⚠️"
                position_pct = s['position_size'] * 100
                print(f" {confidence_emoji} {s['action']} - {s['type']}")
                print(f" Original Confidence: {s['confidence']:.0f}%")
                print(f" Adjusted Confidence: {s['adjusted_confidence']:.0f}%")
                print(f" Recommended Position: {position_pct:.0f}%")
                print(f" Stop Loss: {s['stop_loss_pct']:.1f}%")
                print(f" Reason: {s['reason']}\n")
        else:
            print(f"\n⚠️ NO SIGNALS PASSED VALIDATION - Risk filters applied")
    else:
        print(f"\n⏳ NO TRADING SIGNALS GENERATED")

# === GREEKS FUNCTIONS ===
def fetch_greeks(obj, underlying='NIFTY', expiry=current_expiry):
    greekParam = {"name": underlying, "expirydate": expiry}
    try:
        print(f"Fetching Greeks with params: {greekParam}")
        greekRes = obj.optionGreek(greekParam)
        if greekRes.get('status', False):
            data = greekRes.get('data', [])
            if data:
                print(f"Greeks data received: {len(data)} records")
                df_greeks = pd.DataFrame(data)
                df_greeks['strike'] = pd.to_numeric(df_greeks['strikePrice'], errors='coerce')
                df_greeks['optionType'] = df_greeks['optionType'].str.upper()
                for col in ['delta', 'gamma', 'vega', 'theta', 'impliedVolatility']:
                    if col in df_greeks.columns:
                        df_greeks[col] = pd.to_numeric(df_greeks[col], errors='coerce')
                if 'impliedVolatility' in df_greeks.columns:
                    df_greeks['iv'] = df_greeks['impliedVolatility']
                required_cols = ['strike', 'optionType', 'delta', 'gamma', 'vega', 'theta', 'iv']
                available_cols = [c for c in required_cols if c in df_greeks.columns]
                df_greeks = df_greeks[available_cols].copy()
                print(f"Greeks data processed: {len(df_greeks)} records")
                return df_greeks
            else:
                print("No Greeks data in API response")
        else:
            print(f"Greeks API failed: {greekRes.get('message', 'Unknown error')}")
    except Exception as e:
        print(f"Error fetching Greeks: {e}")
    return pd.DataFrame()

def enrich_with_greeks(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df['optionType'] = df['tradingSymbol'].str.extract(r'(CE|PE)')
    df['strike'] = df['tradingSymbol'].map(symbol_to_strike)
    df_greeks = fetch_greeks(obj, expiry=current_expiry)
    if not df_greeks.empty:
        print(f"Merging Greeks data...")
        df = df.merge(df_greeks, on=['strike', 'optionType'], how='left', suffixes=('', '_greeks'))
        print(f"Greeks merge completed")
    else:
        print("No Greeks data - using fallback values")
    for col in ['delta', 'gamma', 'vega', 'theta', 'iv']:
        if col not in df.columns:
            df[col] = 0.0
        else:
            df[col] = df[col].fillna(0.0)
    return df

def compute_orderbook_imbalance(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    def calc_imbalance(row):
        if 'depth' not in row or not isinstance(row['depth'], dict):
            return 0
        buy_qty = sum(b.get('quantity', 0) for b in row['depth'].get('buy', []))
        sell_qty = sum(s.get('quantity', 0) for s in row['depth'].get('sell', []))
        total = buy_qty + sell_qty
        return (buy_qty - sell_qty) / total if total > 0 else 0
    df['order_imbalance'] = df.apply(calc_imbalance, axis=1)
    return df

# === VISUALIZATION FUNCTIONS ===
def create_improved_table_image(merged_df, market_analysis, label="OI Analysis", changed_count=0):
    plt.style.use('default')
    plt.rcParams.update({
        'font.family': ['Arial', 'DejaVu Sans', 'sans-serif'],
        'font.size': 10,
        'font.weight': 'normal',
        'figure.facecolor': 'black',
        'axes.facecolor': 'black',
        'text.color': 'white',
        'axes.labelcolor': 'white',
        'xtick.color': 'white',
        'ytick.color': 'white'
    })

    CALL_COLOR = '#E53935'
    PUT_COLOR = '#43A047'
    STRIKE_COLOR = '#039BE5'
    NEUTRAL_COLOR = '#757575'

    fig = plt.figure(figsize=(22, 10))
    gs = fig.add_gridspec(3, 1, height_ratios=[1, 1, 6], hspace=0.05)

    ax_title = fig.add_subplot(gs[0])
    ax_title.axis('off')
    ax_title.set_facecolor('black')
    title = f"{label} - {datetime.now().strftime('%H:%M:%S')}"
    if changed_count > 0:
        title += f"\n{changed_count}/{EXPECTED_STRIKE_COUNT} strikes with OI changes detected"
    ax_title.text(0.5, 0.5, title, ha='center', va='center', fontsize=16, fontweight='bold',
                  transform=ax_title.transAxes, color='white')

    ax_summary = fig.add_subplot(gs[1])
    ax_summary.axis('off')
    ax_summary.set_facecolor('black')

    if "BULLISH" in market_analysis.get('direction',''):
        direction_color = '#4CAF50'; emoji = "BULL"
    elif "BEARISH" in market_analysis.get('direction',''):
        direction_color = '#F44336'; emoji = "BEAR"
    else:
        direction_color = '#FFC107'; emoji = "NEUTRAL"

    summary_text = f"{emoji} {market_analysis.get('direction','')} - {market_analysis.get('trend','')}"
    ax_summary.text(0.5, 0.7, summary_text, ha='center', va='center', fontsize=14,
                    fontweight='bold', color=direction_color, transform=ax_summary.transAxes)

    stats_text = (f"Bulls: {market_analysis.get('bullish_pct',0)}% | Bears: {market_analysis.get('bearish_pct',0)}% "
                  f"| {market_analysis.get('dominant_side','')} in Control\n"
                  f"PCR: {market_analysis.get('pcr',0):.2f} | Max Pain: {market_analysis.get('max_pain',0)}")
    ax_summary.text(0.5, 0.3, stats_text, ha='center', va='center', fontsize=12,
                    color='white', transform=ax_summary.transAxes)

    ax_table = fig.add_subplot(gs[2])
    ax_table.axis('off')
    ax_table.set_facecolor('black')

    headers = ['Cls Chg%', 'OI Chg%', 'Prev Close', 'Curr Close', 'Prev OI', 'Curr OI', 'Delta', 'Theta',
               'Strike',
               'Curr OI', 'Prev OI', 'Curr Close', 'Prev Close', 'OI Chg%', 'Cls Chg%', 'Delta', 'Theta', 'Verdict']

    table_data = []
    for _, row in merged_df.iterrows():
        verdict = row.get('verdict', 'Neutral')
        if 'Strong Bullish' in verdict:
            verdict_display = "Strong Bull"
        elif 'Moderate Bullish' in verdict:
            verdict_display = "Mod Bull"
        elif 'Mild Bullish' in verdict:
            verdict_display = "Mild Bull"
        elif 'Strong Bearish' in verdict:
            verdict_display = "Strong Bear"
        elif 'Moderate Bearish' in verdict:
            verdict_display = "Mod Bear"
        elif 'Mild Bearish' in verdict:
            verdict_display = "Mild Bear"
        else:
            verdict_display = "Neutral"

        row_data = [
            format_pct(row.get('cls_chg_pct_call', 0)),
            format_pct(row.get('oi_chg_pct_call', 0)),
            f"{row.get('prev_close_call', 0):.1f}",
            f"{row.get('close_call', 0):.1f}",
            f"{row.get('prev_oi_call', 0):.1f}",
            f"{row.get('opnInterest_call', 0):.1f}",
            f"{row.get('delta_call', 0):.2f}",
            f"{row.get('theta_call', 0):.2f}",
            f"{int(row['strike'])}",
            f"{row.get('opnInterest_put', 0):.1f}",
            f"{row.get('prev_oi_put', 0):.1f}",
            f"{row.get('close_put', 0):.1f}",
            f"{row.get('prev_close_put', 0):.1f}",
            format_pct(row.get('oi_chg_pct_put', 0)),
            format_pct(row.get('cls_chg_pct_put', 0)),
            f"{row.get('delta_put', 0):.2f}",
            f"{row.get('theta_put', 0):.2f}",
            verdict_display
        ]
        table_data.append(row_data)

    table = ax_table.table(cellText=table_data, colLabels=headers, cellLoc='center', loc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.1, 1.8)

    for i in range(len(headers)):
        cell = table[(0, i)]
        if i < 8:
            cell.set_facecolor(CALL_COLOR)
        elif i == 8:
            cell.set_facecolor(STRIKE_COLOR)
        elif i < 16:
            cell.set_facecolor(PUT_COLOR)
        else:
            cell.set_facecolor(NEUTRAL_COLOR)
        cell.set_text_props(weight='bold', color='white')

    for i in range(1, len(table_data) + 1):
        for j in range(len(headers)):
            cell = table[(i, j)]
            if j == 8:  # Strike
                cell.set_facecolor('#1976D2')
                cell.set_text_props(weight='bold', color='white', fontsize=12)
            elif j == 16:  # Verdict
                verdict = table_data[i-1][j]
                if 'Bull' in verdict:
                    cell.set_facecolor('#2E7D32')
                elif 'Bear' in verdict:
                    cell.set_facecolor('#C62828')
                else:
                    cell.set_facecolor('#616161')
                cell.set_text_props(color='white', weight='bold')
            elif j in [0, 1, 13, 14]:
                value = table_data[i-1][j]
                if isinstance(value, str) and '+' in value and value != '+0.0':
                    cell.set_facecolor('#1B5E20')
                elif isinstance(value, str) and '-' in value and value != '-0.0':
                    cell.set_facecolor('#B71C1C')
                else:
                    cell.set_facecolor('#424242')
                cell.set_text_props(color='white')
            else:
                cell.set_facecolor('#333333')
                cell.set_text_props(color='white')

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight', facecolor='black', edgecolor='none')
    buf.seek(0)
    plt.close()
    return buf

# === Spike Prediction & Sustainability Tracker ===
class SpikeTracker:
    def __init__(self):
        self.history = []  # list of (ts, oi, premium)
        self.state = 'idle'
        self.start_ts = None
        self.peak_ts = None
        self.duration = 0
        self.initial_oi = None
        self.peak_oi = None
        self.initial_premium = None
        self.peak_premium = None

    def update(self, ts, oi, premium):
        self.history.append((ts, oi, premium))
        if len(self.history) > 5:
            self.history = self.history[-5:]
        if len(self.history) < 2:
            return
        increases = 0
        for i in range(len(self.history)-1, 0, -1):
            prev_oi = self.history[i-1][1]
            curr_oi = self.history[i][1]
            prev_premium = self.history[i-1][2]
            curr_premium = self.history[i][2]
            oi_change = curr_oi - prev_oi
            premium_change = curr_premium - prev_premium
            if oi_change > 0 and premium_change > 0:
                increases += 1
            else:
                break
        if self.state == 'idle':
            if increases >= 2:
                self.state = 'forming'
                self.start_ts = self.history[-increases][0]
                self.initial_oi = self.history[-increases][1]
                self.initial_premium = self.history[-increases][2]
                self.peak_oi = oi
                self.peak_premium = premium
                self.peak_ts = ts
        elif self.state in ['forming', 'active']:
            prev_oi = self.history[-2][1]
            prev_premium = self.history[-2][2]
            oi_change = oi - prev_oi
            premium_change = premium - prev_premium
            if oi_change >= 0 and premium_change >= 0:
                self.state = 'active'
                if oi > self.peak_oi:
                    self.peak_oi = oi; self.peak_ts = ts
                if premium > self.peak_premium:
                    self.peak_premium = premium; self.peak_ts = ts
            else:
                if oi_change < 0 or premium_change < -prev_premium * 0.03:
                    self.state = 'fading'
        elif self.state == 'fading':
            prev_oi = self.history[-2][1]
            prev_premium = self.history[-2][2]
            oi_change = oi - prev_oi
            premium_change = premium - prev_premium
            if oi_change > 0 and premium_change > 0:
                self.state = 'active'
                if oi > self.peak_oi:
                    self.peak_oi = oi; self.peak_ts = ts
                if premium > self.peak_premium:
                    self.peak_premium = premium; self.peak_ts = ts
            elif oi_change < -prev_oi * 0.05 or premium_change < -prev_premium * 0.05:
                self.state = 'ended'
        if self.start_ts:
            self.duration = (ts - self.start_ts).total_seconds() / 60

    def get_state(self):
        return self.state

    def get_metrics(self):
        if self.state == 'idle':
            return 0, 0, 0
        gain = (((self.peak_oi - self.initial_oi) / self.initial_oi if self.initial_oi > 0 else 0) +
                ((self.peak_premium - self.initial_premium) / self.initial_premium if self.initial_premium > 0 else 0)) / 2 * 100
        strength = min(self.duration * 10 + gain, 100)
        return self.duration, gain, strength

spike_trackers = {}

# === Market Strength Score ===
def calculate_market_strength_score(market_analysis, num_strikes_changed, total_strikes, support_count, resistance_count):
    diff_pct = market_analysis['bullish_pct'] - market_analysis['bearish_pct']
    score = (diff_pct / 100 * 30) + (market_analysis['confidence_factor'] * 0.3)
    coverage = num_strikes_changed / total_strikes * 100 * 0.2
    score += coverage
    pcr_skew = abs(market_analysis['pcr'] - 1) * 10
    if market_analysis['pcr'] > 1:
        score -= pcr_skew
    else:
        score += pcr_skew
    sr_skew = support_count - resistance_count
    score += sr_skew * 10
    score = max(0, min(100, score))
    if score > 80:
        label = "Strong Bullish"
    elif score > 60:
        label = "Moderate Bullish"
    elif score > 40:
        label = "Neutral"
    elif score > 20:
        label = "Moderate Bearish"
    else:
        label = "Strong Bearish"
    return {"score": score, "label": label}

# === Nifty vs Strike Divergence Detection ===
previous_spot = None
def detect_nifty_strike_divergence(current_spot, previous_spot, merged_df):
    if previous_spot is None:
        return {"divergence_type": "none", "verdict_strength": 0, "notes": ""}
    spot_change = (current_spot - previous_spot) / previous_spot * 100 if previous_spot > 0 else 0
    spot_rising = spot_change >= 0.2
    spot_falling = spot_change <= -0.2
    num_bullish = len(merged_df[merged_df['verdict'].str.contains('Bullish')])
    num_bearish = len(merged_df[merged_df['verdict'].str.contains('Bearish')])
    total_verdicts = len(merged_df)
    bullish_pct = num_bullish / total_verdicts * 100 if total_verdicts else 0
    bearish_pct = num_bearish / total_verdicts * 100 if total_verdicts else 0
    if spot_rising and bearish_pct > 60:
        return {"divergence_type": "negative", "verdict_strength": bearish_pct, "notes": "Spot rising but strikes weak"}
    elif spot_falling and bullish_pct > 60:
        return {"divergence_type": "positive", "verdict_strength": bullish_pct, "notes": "Spot falling but strikes strong"}
    else:
        return {"divergence_type": "none", "verdict_strength": 0, "notes": ""}

# === Scalping Signal Generation (ATM±2 candidates) ===
def generate_scalp_signals(merged_df, underlying_price):
    atm = round(underlying_price / 50) * 50
    atm_strikes = [atm - 100, atm - 50, atm, atm + 50, atm + 100]
    candidates = {"bullish": [], "bearish": []}
    for _, row in merged_df[merged_df['strike'].isin(atm_strikes)].iterrows():
        strike = row['strike']
        # Call analysis
        call_oi_chg = row.get('oi_chg_pct_call', 0)
        call_price_chg = row.get('cls_chg_pct_call', 0)
        call_oi_abs = abs(row.get('opnInterest_call', 0) - row.get('prev_oi_call', 0)) * 100000
        call_pattern, call_impact, call_strength, call_confidence = analyze_oi_change_pattern(
            call_oi_chg, call_price_chg, "CE", call_oi_abs
        )
        # Put analysis
        put_oi_chg = row.get('oi_chg_pct_put', 0)
        put_price_chg = row.get('cls_chg_pct_put', 0)
        put_oi_abs = abs(row.get('opnInterest_put', 0) - row.get('prev_oi_put', 0)) * 100000
        put_pattern, put_impact, put_strength, put_confidence = analyze_oi_change_pattern(
            put_oi_chg, put_price_chg, "PE", put_oi_abs
        )

        total_impact = call_impact + put_impact
        total_conf = max(call_confidence, put_confidence)
        total_strength = max(call_strength, put_strength)
        reason = f"{call_pattern} on CE, {put_pattern} on PE"

        if total_conf < 60:
            continue

        if total_impact > 0:  # Bullish
            entry = row.get('close_call', 0)
            if entry <= 0: continue
            target = entry * 1.2
            sl = entry * 0.9
            candidates["bullish"].append({
                "strike": strike,
                "symbol": row.get('tradingSymbol_call', ''),
                "entry": round(entry, 1),
                "target": round(target, 1),
                "sl": round(sl, 1),
                "conf": round(total_conf),
                "reason": reason,
                "strength": total_strength,
                "dist": abs(strike - atm)
            })
        elif total_impact < 0:  # Bearish
            entry = row.get('close_put', 0)
            if entry <= 0: continue
            target = entry * 1.2
            sl = entry * 0.9
            candidates["bearish"].append({
                "strike": strike,
                "symbol": row.get('tradingSymbol_put', ''),
                "entry": round(entry, 1),
                "target": round(target, 1),
                "sl": round(sl, 1),
                "conf": round(total_conf),
                "reason": reason,
                "strength": total_strength,
                "dist": abs(strike - atm)
            })

    signals = []
    for side in ["bullish", "bearish"]:
        if candidates[side]:
            best = sorted(candidates[side], key=lambda x: (-x["conf"], -x["strength"], x["dist"]))[0]
            direction = "BUY CALL" if side == "bullish" else "BUY PUT"
            signals.append({
                "direction": direction,
                "strike": best["strike"],
                "symbol": best["symbol"],
                "entry": best["entry"],
                "target": best["target"],
                "sl": best["sl"],
                "conf": best["conf"],
                "reason": best["reason"]
            })
    return signals

# === REALTIME COACH (tick-by-tick using WS cache) ===

from collections import defaultdict, deque

TICK_INTERVAL_SECS = 1.0          # how often we read WS cache
MOM_LOOKBACK = 12                 # ~12s momentum window
ACC_LOOKBACK = 6                  # ~6s acceleration window
MAX_HISTORY = 120                 # keep ~2 minutes of tick history
SPREAD_MAX_BPS = 80               # 0.80% relative spread threshold
MIN_LTP = 5.0                     # ignore stale/micro values
COOLDOWN_AFTER_EXIT = 20          # seconds to wait after forced exit
TRAIL_RATIO = 0.5                 # trail 50% of MFE

def _rel_spread(bid, ask):
    if bid is None or ask is None or bid <= 0 or ask <= 0: return 1e9
    mid = (bid + ask) / 2
    return (ask - bid) / max(mid, 1e-9)

def _slope(xs):
    # simple slope: last - first
    if len(xs) < 2: return 0.0
    return xs[-1] - xs[0]

def _pct(a, b):
    if b == 0: return 0.0
    return (a - b) / b * 100.0

class PositionCoach:
    """
    Minimal stateful coach that:
      - reads WS ticks every second
      - suggests ENTER (one symbol), HOLD, EXIT or WAIT
      - respects spread, momentum, acceleration and a short cooldown
      - optional AI nudge via ai_trade_coach(context)
    """
    def __init__(self):
        self.hist = defaultdict(lambda: deque(maxlen=MAX_HISTORY))   # sym -> deque of (ts, ltp, bid, ask)
        self.last_decision_ts = 0.0
        self.last_exit_ts = 0.0
        self.open_memo = {}  # sym -> dict(entry, sl, target, mfe)
        self.last_ai_note = ""

    def push_tick(self, ticks: dict):
        now = time.time()
        for sym, pack in ticks.items():
            if sym == "NIFTY_SPOT":
                # store spot under special key
                self.hist[sym].append((now, float(pack.get("ltp", 0.0)), None, None))
            else:
                ltp = float(pack.get("ltp", 0.0))
                bid = float(pack.get("bid", 0.0)) if pack.get("bid") is not None else None
                ask = float(pack.get("ask", 0.0)) if pack.get("ask") is not None else None
                self.hist[sym].append((now, ltp, bid, ask))

    def _mom(self, sym, n):
        q = self.hist.get(sym, [])
        if len(q) < max(2, n): return 0.0
        return _slope([x[1] for x in list(q)[-n:]])

    def _accel(self, sym, n):
        q = self.hist.get(sym, [])
        if len(q) < 2*n: return 0.0
        a = [x[1] for x in list(q)[-2*n:-n]]
        b = [x[1] for x in list(q)[-n:]]
        return _slope(b) - _slope(a)

    def _spread_ok(self, sym):
        q = self.hist.get(sym, [])
        if not q: return False
        _, ltp, bid, ask = q[-1]
        if ltp is None or ltp < MIN_LTP: return False
        rel = _rel_spread(bid, ask)
        return rel*10000 <= SPREAD_MAX_BPS  # bps compare

    def _last_price(self, sym):
        q = self.hist.get(sym, [])
        return q[-1][1] if q else 0.0

    def _spot_dir(self):
        sym = "NIFTY_SPOT"
        m = self._mom(sym, MOM_LOOKBACK)
        a = self._accel(sym, ACC_LOOKBACK)
        return m, a

    def _best_candidate(self, watch_syms):
        """
        Pick one symbol to ENTER, preferring the option that matches spot direction and has
        strong momentum & acceptable spread.
        """
        if time.time() - self.last_exit_ts < COOLDOWN_AFTER_EXIT:
            return None, "cooldown"

        m_spot, a_spot = self._spot_dir()
        bias = "UP" if (m_spot > 0 or a_spot > 0) else "DOWN" if (m_spot < 0 or a_spot < 0) else "FLAT"
        if bias == "FLAT": return None, "no_bias"

        best = None
        best_score = -1e9
        why = ""
        for s in watch_syms:
            if not self._spread_ok(s): continue
            if "CE" in s and bias != "UP": continue
            if "PE" in s and bias != "DOWN": continue
            m = self._mom(s, MOM_LOOKBACK)
            a = self._accel(s, ACC_LOOKBACK)
            price = self._last_price(s)
            if price < MIN_LTP: continue
            score = 2.0*m + 1.0*a
            if score > best_score:
                best_score = score
                best = s
        if best is None:
            return None, "no_symbol"
        why = f"spot:{bias} | mom:{best_score:.2f}"
        return best, why

    def decide(self, market_analysis, open_positions, watch_syms, ticks):
        """
        Returns None or a dict with keys:
          coach: ENTER|HOLD|EXIT|WAIT
          symbol, entry, sl, target (for ENTER)
          why: short rationale
          ai: {advice, note} (optional)
        """
        now = time.time()
        # Basic open position model (single-leg long options)
        my_open = None
        for pos in open_positions:
            if pos.get("quantity", 0) != 0 and pos.get("symbol") in self.hist:
                my_open = pos
                break

        # If we have an open position, manage HOLD/EXIT + trailing
        if my_open:
            sym = my_open["symbol"]
            entry = float(my_open.get("entry_price", 0.0))
            sl = float(my_open.get("sl", entry*0.9)) if my_open.get("sl") else entry*0.9
            target = float(my_open.get("target", entry*1.2)) if my_open.get("target") else entry*1.2
            px = self._last_price(sym)
            # Track MFE & trail
            memo = self.open_memo.get(sym, {"mfe": 0.0, "entry": entry, "sl": sl, "target": target})
            memo["mfe"] = max(memo["mfe"], px - entry)
            trail_sl = entry + memo["mfe"]*TRAIL_RATIO
            memo["sl"] = max(sl, trail_sl)
            self.open_memo[sym] = memo

            # Exit checks
            if px <= memo["sl"] * 0.999:
                self.last_exit_ts = now
                return {"coach": "EXIT", "symbol": sym, "why": f"SL hit @ {px:.1f} (trail {memo['sl']:.1f})"}
            if px >= memo["target"] * 0.999:
                self.last_exit_ts = now
                return {"coach": "EXIT", "symbol": sym, "why": f"Target hit @ {px:.1f}"}

            # Momentum fade exit (against direction)
            m = self._mom(sym, MOM_LOOKBACK)
            a = self._accel(sym, ACC_LOOKBACK)
            spread_ok = self._spread_ok(sym)
            if not spread_ok:
                # exit if liquidity deteriorates
                self.last_exit_ts = now
                return {"coach": "EXIT", "symbol": sym, "why": "Spread widened / liquidity poor"}

            # HOLD with trail update
            why = f"HOLD {sym} @ {px:.1f} | trail {memo['sl']:.1f} | mom {m:.2f} acc {a:.2f}"
            return {"coach": "HOLD", "symbol": sym, "why": why}

        # No open position -> consider ENTER
        cand, reason = self._best_candidate(watch_syms)
        if cand:
            px = self._last_price(cand)
            # compute quick SL/target using local micro-vol (last 12s)
            recent = [x[1] for x in list(self.hist[cand])[-MOM_LOOKBACK:]]
            if len(recent) >= 2:
                r = max(0.5, np.std(recent))  # basic vol proxy in premium points
            else:
                r = 2.0
            sl = max(px - 2*r, px*0.9)
            target = px + 2.5*r
            return {
                "coach": "ENTER",
                "symbol": cand,
                "entry": round(px, 1),
                "sl": round(sl, 1),
                "target": round(target, 1),
                "why": f"{reason} | vol≈{r:.1f}"
            }

        return {"coach": "WAIT", "why": f"{reason}"}

# === OPEN POSITIONS (paper or live) ===

PAPER_TRADE = True  # Keep True for forward test; flip to False to place live orders later.

def fetch_open_positions(api) -> list:
    """
    Normalize current open single-leg option positions to:
    [{"symbol": "NIFTY...CE", "quantity": int, "entry_price": float, "sl": float, "target": float}]
    Paper mode: read from SQLite "signals" table where status='OPEN'
    Live mode : call SmartAPI getPosition()
    """
    if PAPER_TRADE:
        res = []
        try:
            db = _db_conn()
            cur = db.cursor()
            cur.execute('SELECT symbol, entry_price, target, sl FROM signals WHERE status="OPEN"')
            for sym, entry, tgt, sl in cur.fetchall():
                res.append({"symbol": sym, "quantity": 1, "entry_price": float(entry), "sl": float(sl), "target": float(tgt)})
            db.close()
        except Exception as e:
            print(f"Paper position fetch error: {e}")
        return res
    else:
        try:
            pos = api.getPosition()
            # Map SmartAPI response to our minimal schema if needed
            arr = []
            data = pos.get("data", [])
            for p in data:
                qty = int(p.get("netqty") or 0)
                if qty != 0:
                    arr.append({
                        "symbol": p.get("tradingsymbol"),
                        "quantity": qty,
                        "entry_price": float(p.get("avgnetprice") or 0.0),
                        "sl": None, "target": None
                    })
            return arr
        except Exception as e:
            print(f"Live position fetch error: {e}")
            return []

# === STARTUP BANNER ===
print("🔗 Testing enhanced Telegram connection...")
startup_msg = """🚀 **Enhanced OI Monitor v2.1 (WS + AI Coach) Started!**
✅ **New WS LTP Feed:** Sub-second ticks via SmartWebSocketV2
✅ **Realtime Coach:** ENTER / HOLD / EXIT / WAIT every second
✅ **AI Nudge:** OpenRouterClient (optional)
✅ **Context Engine:** 3–4 min OI/Greeks (PCR, MaxPain, S/R)
🛡 **Paper Mode:** Signals recorded to SQLite (no live orders)
"""
send_telegram_message(clean_caption_text(startup_msg), parse_mode=None)
print("✅ Enhanced monitoring system activated!")

# === IMPROVED FORMATTER (snapshot → merged table → Telegram + DB logging) ===

def format_table_output_improved(current_df, previous_df, label="🔄 All Strikes Updated", changed_count=0, send_to_telegram=True):
    print(f"\n{label}")
    if changed_count > 0:
        print(f"📈 {changed_count}/{EXPECTED_STRIKE_COUNT} strikes with OI changes detected\n")
    else:
        print()

    # copies
    current_df = current_df.copy()
    previous_df = previous_df.copy()

    # map strike
    current_df['strike'] = current_df['tradingSymbol'].map(symbol_to_strike)
    previous_df['strike'] = previous_df['tradingSymbol'].map(symbol_to_strike)
    current_df = current_df.dropna(subset=['strike'])
    previous_df = previous_df.dropna(subset=['strike'])

    # enrich/normalize
    for df in [current_df, previous_df]:
        df['optionType'] = df['tradingSymbol'].str.extract(r'(CE|PE)')
        df['close'] = pd.to_numeric(df.get('ltp', 0), errors='coerce')
        df['opnInterest'] = pd.to_numeric(df['opnInterest'], errors='coerce')

    # Underlying
    global previous_spot
    current_spot = get_underlying_price(current_df)
    spot_change = (current_spot - previous_spot) / previous_spot * 100 if previous_spot is not None and previous_spot>0 else 0

    # Greeks + orderbook
    current_df = enrich_with_greeks(current_df)
    current_df = compute_orderbook_imbalance(current_df)

    # Spike trackers
    ts = get_latest_exchange_time(current_df)
    for _, row in current_df.iterrows():
        symbol = row['tradingSymbol']
        oi_abs = row['opnInterest'] * 1e5  # absolute
        premium = row['close']
        tracker = spike_trackers.get(symbol, SpikeTracker())
        tracker.update(ts, oi_abs, premium)
        spike_trackers[symbol] = tracker

    # prev maps
    prev_map = previous_df.set_index('tradingSymbol')
    current_df['prev_oi'] = current_df['tradingSymbol'].map(prev_map['opnInterest'])
    current_df['prev_close'] = current_df['tradingSymbol'].map(prev_map['close'])

    # % changes
    current_df['oi_chg_pct'] = np.where(
        current_df['prev_oi'] > 0,
        ((current_df['opnInterest'] - current_df['prev_oi']) / current_df['prev_oi']) * 100,
        np.nan
    ).round(2)
    current_df['cls_chg_pct'] = np.where(
        current_df['prev_close'] > 0,
        ((current_df['close'] - current_df['prev_close']) / current_df['prev_close']) * 100,
        np.nan
    ).round(2)

    # to lakhs
    current_df['opnInterest'] = (current_df['opnInterest'] / 1e5).round(2)
    current_df['prev_oi'] = (current_df['prev_oi'] / 1e5).round(2)

    # calls/puts by strike
    calls = current_df[current_df['optionType'] == 'CE'].groupby('strike').first().reset_index()
    puts = current_df[current_df['optionType'] == 'PE'].groupby('strike').first().reset_index()

    # ensure cols
    required_columns = ['cls_chg_pct', 'oi_chg_pct', 'prev_close', 'close', 'prev_oi', 'opnInterest', 'order_imbalance']
    for col in required_columns:
        if col not in calls.columns: calls[col] = 0
        if col not in puts.columns: puts[col] = 0

    merged = pd.merge(
        calls[required_columns + ['strike','tradingSymbol'] + ['delta','gamma','vega','theta','iv']],
        puts[required_columns + ['strike','tradingSymbol'] + ['delta','gamma','vega','theta','iv']],
        on='strike', how='outer', suffixes=('_call', '_put')
    ).sort_values(by='strike')

    # rename quick aliases for readability
    merged = merged.rename(columns={
        'tradingSymbol_call': 'tradingSymbol_call',
        'tradingSymbol_put' : 'tradingSymbol_put',
        'close_call': 'close_call',
        'close_put':  'close_put',
        'prev_close_call':'prev_close_call',
        'prev_close_put':'prev_close_put',
        'opnInterest_call':'opnInterest_call',
        'opnInterest_put':'opnInterest_put',
        'prev_oi_call':'prev_oi_call',
        'prev_oi_put':'prev_oi_put',
        'oi_chg_pct_call':'oi_chg_pct_call',
        'oi_chg_pct_put':'oi_chg_pct_put',
        'cls_chg_pct_call':'cls_chg_pct_call',
        'cls_chg_pct_put':'cls_chg_pct_put',
        'delta_call':'delta_call',
        'delta_put':'delta_put',
        'theta_call':'theta_call',
        'theta_put':'theta_put',
    })

    # verdicts & market analysis
    merged["verdict"] = merged.apply(calculate_strike_verdict_new, axis=1)
    market_analysis = calculate_comprehensive_market_direction(merged)

    # trading signals (contextual)
    trading_signals = generate_trading_signal(merged, market_analysis)

    # S/R & divergence
    supports, resistances = calculate_support_resistance(merged, current_spot)
    divergence = detect_nifty_strike_divergence(current_spot, previous_spot, merged)
    previous_spot = current_spot

    total_strikes = EXPECTED_STRIKE_COUNT // 2
    strength_score = calculate_market_strength_score(market_analysis, changed_count // 2, total_strikes, len(supports), len(resistances))

    # spike summary
    all_states = [spike_trackers.get(s, SpikeTracker()).get_state() for s in expected_strikes if s in spike_trackers]
    state_counts = Counter(all_states)
    forming = state_counts['forming']; active = state_counts['active']; fading = state_counts['fading']
    momentum = 'building' if active > fading else 'weakening' if fading > active else 'stable'
    spike_summary = f"🚀 {forming} forming, {active} active, {fading} fading — momentum {momentum}"

    # === PRINT SUMMARY ===
    print("=" * 250)
    print(f"🎯 ENHANCED MARKET ANALYSIS SUMMARY:")
    emoji = "🟢" if "BULLISH" in market_analysis['direction'] else "🔴" if "BEARISH" in market_analysis['direction'] else "⚪"
    print(f"{emoji} Market: {market_analysis['direction']} - {market_analysis['trend']}")
    print(f"📊 Confidence: {market_analysis['confidence_factor']:.1f}% "
          f"({market_analysis['high_confidence_signals']}/{market_analysis['total_signals']} high-confidence)")
    print(f"💪 {market_analysis['dominant_side']} Control: {max(market_analysis['bullish_pct'], market_analysis['bearish_pct']):.1f}%")
    print(f" • Bullish: {market_analysis['bullish_pct']:.1f}% (Vol: {market_analysis['bullish_volume']:.2f}L)")
    print(f" • Bearish: {market_analysis['bearish_pct']:.1f}% (Vol: {market_analysis['bearish_volume']:.2f}L)")
    print(f" • PCR: {market_analysis['pcr']:.2f} | Max Pain: {market_analysis['max_pain']}")
    print(f"🧠 Strength Score: {strength_score['score']:.1f}/100 ({strength_score['label']})")
    print(spike_summary)
    print(f"📈 NIFTY Spot: {current_spot:.2f} ({spot_change:+.2f}%)")
    if divergence['divergence_type'] != "none":
        print(f"📈 Divergence: {divergence['divergence_type'].capitalize()} ({divergence['verdict_strength']:.1f}%) - {divergence['notes']}")

    log_enhanced_trading_signals(trading_signals, market_analysis)
    print("=" * 250)

    # console table
    print("=" * 250)
    print(f"{'CALLS':<60}{changed_count}/{EXPECTED_STRIKE_COUNT} strikes with OI changes detected{'PUTS':>60}")
    header = (f"{'Cls Chg%':>8} | {'OI Chg%':>8} | {'Prev Close':>12} | {'Curr Close':>12} | {'Prev OI':>10} | "
              f"{'Curr OI':>10} | {'Delta':>6} | {'Theta':>6} || {'Strike':^7} || "
              f"{'Curr OI':>10} | {'Prev OI':>10} | {'Curr Close':>12} | {'Prev Close':>12} | "
              f"{'OI Chg%':>8} | {'Cls Chg%':>8} | {'Delta':>6} | {'Theta':>6} | {'Verdict':>25}")
    print(header)
    print("-" * 250)
    for _, row in merged.iterrows():
        verdict_display = row.get('verdict', 'Neutral')
        print(f"{format_pct(row.get('cls_chg_pct_call')):>8} | {format_pct(row.get('oi_chg_pct_call')):>8} | "
              f"{row.get('prev_close_call', 0):>12.2f} | {row.get('close_call', 0):>12.2f} | "
              f"{row.get('prev_oi_call', 0):>10,.2f} | {row.get('opnInterest_call', 0):>10,.2f} | "
              f"{row.get('delta_call', 0):>6.2f} | {row.get('theta_call', 0):>6.2f} || "
              f"{int(row['strike']):^7} || "
              f"{row.get('opnInterest_put', 0):>10,.2f} | {row.get('prev_oi_put', 0):>10,.2f} | "
              f"{row.get('close_put', 0):>12.2f} | {row.get('prev_close_put', 0):>12.2f} | "
              f"{format_pct(row.get('oi_chg_pct_put')):>8} | {format_pct(row.get('cls_chg_pct_put')):>8} | "
              f"{row.get('delta_put', 0):>6.2f} | {row.get('theta_put', 0):>6.2f} | {verdict_display:>25}")
    print("=" * 250)

    # final verdict
    confidence_level = market_analysis['confidence_factor']
    if confidence_level > 75:
        confidence_text = "🎯 HIGH CONFIDENCE"
    elif confidence_level > 50:
        confidence_text = "⚠️ MODERATE CONFIDENCE"
    elif confidence_level > 30:
        confidence_text = "⚪ LOW CONFIDENCE"
    else:
        confidence_text = "❌ INSUFFICIENT DATA"
    final_emoji = "✅" if "BULLISH" in market_analysis['direction'] else "🔴" if "BEARISH" in market_analysis['direction'] else "⚪"
    final_msg = (f"{final_emoji} Final Verdict: {market_analysis['direction']} — {market_analysis['dominant_side']} "
                 f"dominating by {max(market_analysis['bullish_pct'], market_analysis['bearish_pct']):.1f}% | "
                 f"{confidence_text} ({confidence_level:.0f}%)")
    print(f"\n{final_msg}\n")

    # SR message
    sr_message = "🔑 Key Levels:\n"
    if supports:
        sr_message += "🔵 Support: " + ", ".join([f"{int(s[0])} (strength: {s[1]:.1f})" for s in supports]) + "\n"
    if resistances:
        sr_message += "🔴 Resistance: " + ", ".join([f"{int(r[0])} (strength: {r[1]:.1f})" for r in resistances])

    # Telegram image + messages
    if send_to_telegram and TELEGRAM_BOT_TOKEN != "YOUR_BOT_TOKEN_HERE":
        try:
            print("📸 Creating enhanced table image for Telegram...")
            image_buffer = create_improved_table_image(merged.copy(), market_analysis, label, changed_count)
            # simple safe caption
            cap = create_enhanced_caption(label, changed_count, market_analysis, trading_signals)
            _ = send_telegram_image_fixed(image_buffer, cap)

            if trading_signals:
                signal_text = "Trading Signals:\n"
                for s in trading_signals:
                    action_emoji = "🟢" if s['action'] == 'BUY' else "🔴"
                    signal_text += f"{action_emoji} {s['action']} - {s['type']}\n"
                    signal_text += f"Confidence: {s['confidence']:.0f}%\n"
                    signal_text += f"Reason: {s['reason']}\n\n"
                send_telegram_message_simple(signal_text)

            if sr_message.strip() != "🔑 Key Levels:":
                send_telegram_message_simple(sr_message)
        except Exception as e:
            print(f"❌ Telegram section failed: {e}")
            try:
                send_telegram_message_simple("OI Analysis completed - check console for details")
            except:
                print("❌ Even fallback message failed")

    # === PAPER SIGNALS: open & close tracking ===
    db = _db_conn()
    cur = db.cursor()
    now_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # A) Record new scalp signals (ATM±2) as OPEN if not already there
    scalp_signals = generate_scalp_signals(merged, current_spot)
    for sig in scalp_signals:
        cur.execute('''
            SELECT 1 FROM signals
            WHERE symbol=? AND direction=? AND entry_price=? AND status='OPEN'
        ''', (sig['symbol'], sig['direction'], sig['entry']))
        if cur.fetchone() is None:
            cur.execute('''
                INSERT INTO signals
                (timestamp, symbol, direction, entry_price, target, sl, confidence, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN')
            ''', (now_ts, sig['symbol'], sig['direction'], sig['entry'], sig['target'], sig['sl'], sig['conf']))

    db.commit()

    # B) Check OPEN signals for TARGET/SL hit with current tick LTP if available
    cur.execute('SELECT id, symbol, target, sl FROM signals WHERE status="OPEN"')
    open_rows = cur.fetchall()
    # We can use WS cache for LTP
    sym_to_ltp = {}
    with WS_LOCK:
        for s in SYMBOL_TO_TOKEN.keys():
            if s in TICKS_CACHE:
                sym_to_ltp[s] = float(TICKS_CACHE[s].get("ltp", 0.0))

    for sid, sym, tgt, stop in open_rows:
        ltp = sym_to_ltp.get(sym, None)
        if ltp is None:
            # fallback to dataframe
            row = current_df[current_df['tradingSymbol'] == sym]
            if row.empty:
                continue
            ltp = float(row.iloc[0]['close'])

        if ltp >= float(tgt):
            reason = 'TARGET'
        elif ltp <= float(stop):
            reason = 'SL'
        else:
            continue

        exit_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cur.execute('''
            UPDATE signals
            SET status='CLOSED', exit_time=?, exit_price=?, exit_reason=?
            WHERE id=?
        ''', (exit_ts, ltp, reason, sid))
        db.commit()

        send_telegram_message_simple(f"🚪 Signal {sym} {reason}\nExit: ₹{ltp:.2f}")

    db.close()

    return merged, market_analysis, trading_signals


# === DB: SQLite (paper trading logs) ===
db = _db_conn()
cur = db.cursor()
cur.execute('''
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY,
    symbol TEXT,
    entry_time TEXT,
    entry_price REAL,
    exit_time TEXT,
    exit_price REAL,
    pnl REAL,
    reason TEXT
)
''')
cur.execute('''
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY,
    timestamp TEXT,
    symbol TEXT,
    direction TEXT,
    entry_price REAL,
    target REAL,
    sl REAL,
    confidence INTEGER,
    status TEXT, -- 'OPEN' or 'CLOSED'
    exit_time TEXT,
    exit_price REAL,
    exit_reason TEXT -- 'TARGET' or 'SL'
)
''')
db.commit()
db.close()

# === INITIAL SNAPSHOT (for OI context) ===
reference_oi_data = fetch_snapshot()
if not reference_oi_data.empty:
    format_table_output_improved(
        reference_oi_data.copy(),
        reference_oi_data.copy(),
        label="📦 Initial OI Data Snapshot",
        send_to_telegram=False
    )

# === MONITORING LOOP VARIABLES ===
collection_start_time = None
strikes_with_changes = set()
latest_complete_data = None
iteration_count = 0
update_cycle = 0
COLLECTION_WINDOW = timedelta(minutes=4)
past_snapshots = deque(maxlen=5)

# === WS BOOTSTRAP ===
start_ws_feed()  # background thread
time.sleep(1.0)  # small delay before first subscription

# Subscribe initial ATM±2 around current spot (from reference snapshot if present)
def _initial_ws_subscribe():
    spot_guess = None
    if not reference_oi_data.empty:
        try:
            spot_guess = get_underlying_price(reference_oi_data)
        except Exception:
            spot_guess = None
    if spot_guess is None:
        # fallback to last known in cache or a typical level
        with WS_LOCK:
            spot_guess = TICKS_CACHE.get("NIFTY_SPOT", {}).get("ltp", None)
        if not spot_guess:
            try:
                spot_guess = _guess_spot_for_mapping()
            except Exception:
                # Try last known WS spot before hard fallback
                try:
                    with WS_LOCK:
                        last_spot = TICKS_CACHE.get("NIFTY_SPOT", {}).get("ltp", None)
                    if last_spot and float(last_spot) > 0:
                        spot_guess = float(last_spot)
                    else:
                        spot_guess = 24650.0
                except Exception:
                    spot_guess = 24650.0
    syms = pick_atm_strikes_for_watch(spot_guess, ATM_WINDOW)
    if syms:
        ws_refresh_subscription(syms)
        print(f"📡 WS subscribed to {len(syms)} NIFTY option symbols around {spot_guess:.1f}")

_initial_ws_subscribe()

# === REALTIME COACH INSTANCE ===
coach = PositionCoach()

# === OPEN-ROUTER AI COACH WRAPPER FOR PERIODIC HINTS (optional) ===
AI_HINT_INTERVAL = 15  # seconds between AI hints at most
_last_ai_hint_ts = 0.0

def maybe_ai_hint(context):
    global _last_ai_hint_ts
    if not USE_AI_COACH:
        return {}
    now = time.time()
    if now - _last_ai_hint_ts < AI_HINT_INTERVAL:
        return {}
    _last_ai_hint_ts = now
    return ai_trade_coach(context)

# === SMALL HELPERS ===
def _fetch_open_positions_for_coach():
    """
    Returns normalized open positions for coach (paper or live).
    """
    return fetch_open_positions(obj)

def _coach_watch_list_from_spot():
    """
    Dynamically re-pick ATM±2 from current WS spot, and refresh WS subscription
    occasionally (every ~30s) or when ATM moved by >= 50.
    """
    with WS_LOCK:
        spot = TICKS_CACHE.get("NIFTY_SPOT", {}).get("ltp", None)
    if not spot:
        return []
    desired = pick_atm_strikes_for_watch(spot, ATM_WINDOW)
    return desired

_last_resub_time = 0.0
_last_atm = None

def _maybe_resubscribe_ws():
    """
    If ATM has shifted by >= 50 from last subscription or every ~30 seconds,
    refresh the subscription to keep only ATM±2 strikes streaming.
    """
    global _last_resub_time, _last_atm
    now = time.time()
    need = False

    with WS_LOCK:
        spot = TICKS_CACHE.get("NIFTY_SPOT", {}).get("ltp", None)
    if spot:
        atm = int(round(spot / 50.0) * 50)
        if _last_atm is None or abs(atm - (_last_atm or atm)) >= 50:
            _last_atm = atm
            need = True

    if now - _last_resub_time > 30.0:
        need = True

    if need:
        _last_resub_time = now
        syms = _coach_watch_list_from_spot()
        if syms:
            ws_refresh_subscription(syms)
            print(f"🔁 WS re-subscribed to {len(syms)} option symbols (ATM±{ATM_WINDOW})")


# === MAIN LOOP ===
try:
    print("🚀 Starting scalper coach loop (Ctrl+C to stop)...")
    collection_start_time = datetime.now()

    while True:
        now = datetime.now()

        # Every ~3–4 min: refresh OI context snapshot
        if now - collection_start_time >= COLLECTION_WINDOW:
            new_snapshot = fetch_snapshot()
            if not new_snapshot.empty:
                format_table_output_improved(
                    reference_oi_data.copy(),
                    new_snapshot.copy(),
                    label="📊 OI Data Update",
                    send_to_telegram=False
                )
                reference_oi_data = new_snapshot
                past_snapshots.append(new_snapshot)
            collection_start_time = now

        # WS LTP tick-based: update watchlist if needed
        _maybe_resubscribe_ws()

        # Build context for coach
        with WS_LOCK:
            ticks_copy = dict(TICKS_CACHE)

        positions = _fetch_open_positions_for_coach()
        ai_hint = maybe_ai_hint({
            "spot": ticks_copy.get("NIFTY_SPOT"),
            "ticks": ticks_copy,
            "positions": positions,
            "oi_context": reference_oi_data.to_dict() if not reference_oi_data.empty else {}
        })

        advice, note = coach.analyze(
            spot=ticks_copy.get("NIFTY_SPOT"),
            ticks=ticks_copy,
            positions=positions,
            ai_hint=ai_hint
        )

        # Handle advice
        if advice in ("ENTER", "EXIT"):
            # Paper trade execution: insert into SQLite
            db = _db_conn()
            cur = db.cursor()
            ts_str = datetime.now().isoformat()
            if advice == "ENTER":
                entry_price = coach.last_signal_price
                cur.execute('''
                    INSERT INTO signals (timestamp, symbol, direction, entry_price, target, sl, confidence, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    ts_str,
                    "NIFTY",
                    coach.last_signal_dir,
                    entry_price,
                    coach.last_signal_target,
                    coach.last_signal_sl,
                    coach.last_signal_conf,
                    "OPEN"
                ))
                db.commit()
                msg = f"📈 PAPER ENTER {coach.last_signal_dir} at {entry_price} | SL {coach.last_signal_sl} | TG {coach.last_signal_target} | Conf {coach.last_signal_conf}%"
                send_telegram_message(msg)
            elif advice == "EXIT":
                exit_price = coach.last_exit_price
                cur.execute('''
                    UPDATE signals
                    SET status=?, exit_time=?, exit_price=?, exit_reason=?
                    WHERE status='OPEN'
                ''', ("CLOSED", ts_str, exit_price, coach.last_exit_reason))
                db.commit()
                msg = f"📉 PAPER EXIT at {exit_price} | Reason: {coach.last_exit_reason}"
                send_telegram_message(msg)
            db.close()

        # Send HOLD/WAIT hints periodically
        elif advice in ("HOLD", "WAIT") and ai_hint.get("note"):
            send_telegram_message(f"🤖 {advice}: {ai_hint['note']}")

        time.sleep(1.0)

except KeyboardInterrupt:
    print("👋 Interrupted by user. Closing WebSocket...")
    ws_stop()
except Exception as e:
    print(f"💥 Fatal error in main loop: {e}")
    ws_stop()


# =========================
# AI PAYLOAD UPGRADE — PART A
# Rolling tick & OI/Greeks history + auto-detect FUT/VIX + samplers
# =========================

# --- Config for AI payload depth ---
HIST_WINDOW_SECS = 30 * 60       # 30 minutes of history
AI_ATM_WINDOW = 3                # ATM ±3 strikes for AI payload depth
HIST_SAMPLE_SECS = 1.0           # tick sampler reads WS cache every 1s
OI_MAX_POINTS = 24               # 24 * 3-4min ~= last 72-96 minutes (cap)
MAX_TICK_POINTS = HIST_WINDOW_SECS  # sample every second -> ~1800 points

# --- Rolling stores ---
from collections import defaultdict, deque

class RollingTicks:
    """Keeps per-symbol last ~30min of (ts, ltp, bid, ask, vol?)."""
    def __init__(self, max_points=MAX_TICK_POINTS):
        self.buf = defaultdict(lambda: deque(maxlen=max_points))

    def push(self, sym, ts, ltp, bid=None, ask=None, vol=None):
        self.buf[sym].append({
            "ts": float(ts),
            "ltp": float(ltp) if ltp is not None else None,
            "bid": float(bid) if bid is not None else None,
            "ask": float(ask) if ask is not None else None,
            "vol": float(vol) if vol is not None else None,
        })

    def series(self, sym, last_n=None):
        q = self.buf.get(sym, deque())
        if not q:
            return []
        if last_n is None or last_n >= len(q):
            return list(q)
        return list(q)[-last_n:]

    def latest(self, sym):
        q = self.buf.get(sym, deque())
        return q[-1] if q else None

    def vwap(self, sym, last_secs=300):
        """Approx VWAP proxy using last 'last_secs' with LTP only (if no per-tick volume)."""
        now = time.time()
        xs = [x for x in self.buf.get(sym, []) if now - x["ts"] <= last_secs and x["ltp"]]
        if not xs:
            return None
        # no true volume here; use time-weighted mean as proxy
        return sum(x["ltp"] for x in xs) / len(xs)

    def spread_bps(self, sym):
        x = self.latest(sym)
        if not x or not x["bid"] or not x["ask"]:
            return None
        mid = (x["bid"] + x["ask"]) / 2.0
        if mid <= 0:
            return None
        return (x["ask"] - x["bid"]) / mid * 10000.0  # bps

    def momentum(self, sym, secs=12):
        now = time.time()
        xs = [x["ltp"] for x in self.buf.get(sym, []) if x["ltp"] is not None and now - x["ts"] <= secs]
        if len(xs) < 2:
            return 0.0
        return xs[-1] - xs[0]

    def accel(self, sym, secs=12):
        now = time.time()
        xs = [x["ltp"] for x in self.buf.get(sym, []) if x["ltp"] is not None and now - x["ts"] <= 2*secs]
        if len(xs) < 4:
            return 0.0
        half = len(xs)//2
        return (xs[-1] - xs[half]) - (xs[half-1] - xs[0])

TICK_HISTORY = RollingTicks()

class OIHistory:
    """Keeps per-strike last N OI/Greeks snapshots (3–4 min cadence)."""
    def __init__(self, max_points=OI_MAX_POINTS):
        self.buf = defaultdict(lambda: deque(maxlen=max_points))  # key: tradingSymbol

    def push_row(self, row, ts=None):
        sym_call = row.get('tradingSymbol_call')
        sym_put  = row.get('tradingSymbol_put')
        snap_ts = ts or time.time()

        def pack(prefix):
            return {
                "ts": snap_ts,
                "strike": float(row.get('strike', 0)),
                "oi": float(row.get(f'opnInterest_{prefix}', 0)),
                "prev_oi": float(row.get(f'prev_oi_{prefix}', 0)),
                "close": float(row.get(f'close_{prefix}', 0)),
                "prev_close": float(row.get(f'prev_close_{prefix}', 0)),
                "oi_chg_pct": float(row.get(f'oi_chg_pct_{prefix}', 0) or 0),
                "cls_chg_pct": float(row.get(f'cls_chg_pct_{prefix}', 0) or 0),
                "delta": float(row.get(f'delta_{prefix}', 0) or 0),
                "theta": float(row.get(f'theta_{prefix}', 0) or 0),
            }

        if sym_call:
            self.buf[sym_call].append(pack("call"))
        if sym_put:
            self.buf[sym_put].append(pack("put"))

    def last(self, sym, n=3):
        q = self.buf.get(sym, deque())
        if not q:
            return []
        return list(q)[-n:]

OI_HISTORY = OIHistory()

# --- Detect NIFTY FUT (current month) and INDIA VIX token from instrument_list ---
def detect_nifty_current_month_future(instruments: pd.DataFrame):
    try:
        now = datetime.now()
        # NIFTY futures rows (FUTIDX) / NFO
        futs = instruments[(instruments['name'] == 'NIFTY') &
                           (instruments['instrumenttype'].str.contains('FUT', na=False)) &
                           (instruments['exch_seg'] == 'NFO')].copy()
        if futs.empty:
            return None, None
        # parse expiry and pick nearest upcoming
        def parse_date(s):
            try:
                return datetime.strptime(s, '%d%b%Y')
            except:
                return None
        futs['exp_dt'] = futs['expiry'].apply(parse_date)
        futs = futs.dropna(subset=['exp_dt'])
        futs = futs[futs['exp_dt'] >= now - timedelta(days=2)]
        futs = futs.sort_values('exp_dt')
        if futs.empty:
            return None, None
        row = futs.iloc[0]
        return row['symbol'], str(row['token'])
    except Exception as e:
        print(f"⚠️ FUT detection error: {e}")
        return None, None

def detect_india_vix_token(instruments: pd.DataFrame):
    try:
        vix = instruments[(instruments['name'].str.contains('INDIA VIX', na=False)) &
                          (instruments['instrumenttype'] == 'INDEX') &
                          (instruments['exch_seg'] == 'NSE')]
        if vix.empty:
            return None, None
        row = vix.iloc[0]
        return row['symbol'], str(row['token'])
    except Exception as e:
        print(f"⚠️ VIX detection error: {e}")
        return None, None

NIFTY_FUT_SYMBOL, NIFTY_FUT_TOKEN = detect_nifty_current_month_future(instrument_list)
VIX_SYMBOL, VIX_TOKEN = detect_india_vix_token(instrument_list)

if NIFTY_FUT_SYMBOL and NIFTY_FUT_TOKEN:
    print(f"🧭 NIFTY FUT detected: {NIFTY_FUT_SYMBOL} (token {NIFTY_FUT_TOKEN})")
else:
    print("🧭 NIFTY FUT not found — proceeding without futures stream.")

if VIX_SYMBOL and VIX_TOKEN:
    print(f"⚡ INDIA VIX detected: {VIX_SYMBOL} (token {VIX_TOKEN})")
else:
    print("⚡ INDIA VIX not found — proceeding without VIX stream.")

# --- WS sampler: copy WS cache → RollingTicks every second ---
HIST_SAMPLER_STOP = threading.Event()

def _history_sampler_loop():
    while not HIST_SAMPLER_STOP.is_set():
        now = time.time()
        with WS_LOCK:
            cache_copy = dict(TICKS_CACHE)
        # spot (special key)
        spot = cache_copy.get("NIFTY_SPOT")
        if spot and spot.get("ltp"):
            TICK_HISTORY.push("NIFTY_SPOT", now, spot.get("ltp"))

        # futures & vix if present in cache
        if NIFTY_FUT_SYMBOL and NIFTY_FUT_SYMBOL in cache_copy:
            ft = cache_copy[NIFTY_FUT_SYMBOL]
            TICK_HISTORY.push(NIFTY_FUT_SYMBOL, now, ft.get("ltp"), ft.get("bid"), ft.get("ask"))
        if VIX_SYMBOL and VIX_SYMBOL in cache_copy:
            vx = cache_copy[VIX_SYMBOL]
            TICK_HISTORY.push(VIX_SYMBOL, now, vx.get("ltp"))

        # options in cache
        for sym, pack in cache_copy.items():
            if sym in ("NIFTY_SPOT", NIFTY_FUT_SYMBOL, VIX_SYMBOL):
                continue
            if isinstance(sym, str) and ("CE" in sym or "PE" in sym):
                TICK_HISTORY.push(sym, now, pack.get("ltp"), pack.get("bid"), pack.get("ask"))
        time.sleep(HIST_SAMPLE_SECS)

def start_history_sampler():
    t = threading.Thread(target=_history_sampler_loop, daemon=True)
    t.start()
    return t

# Kick off sampler
start_history_sampler()

# --- hook: record OI/Greeks history whenever your merged table gets produced ---
# We won't replace your big function; we'll wrap it to append history after it returns.
if 'format_table_output_improved' in globals():
    _orig_format_table_output_improved = format_table_output_improved

    def format_table_output_improved(*args, **kwargs):
        merged, market_analysis, trading_signals = _orig_format_table_output_improved(*args, **kwargs)
        try:
            snap_ts = time.time()
            for _, r in merged.iterrows():
                OI_HISTORY.push_row(r, ts=snap_ts)
        except Exception as e:
            print(f"⚠️ OI history push error: {e}")
        return merged, market_analysis, trading_signals


# =========================
# AI PAYLOAD UPGRADE — PART B
# Build rich payload + upgraded ai_trade_coach & maybe_ai_hint
# =========================

AI_MODEL = "openai/gpt-oss-120b"  # change if you prefer another OpenRouter model

def _atm_candidates_from_spot_for_ai():
    with WS_LOCK:
        spot = TICKS_CACHE.get("NIFTY_SPOT", {}).get("ltp", None)
    if not spot:
        return []
    return pick_atm_strikes_for_watch(spot, AI_ATM_WINDOW)

def _series_pack(sym, last_secs=180):
    """Return last ~N seconds of ticks + quick stats for a symbol."""
    series = TICK_HISTORY.series(sym)
    if not series:
        return {"symbol": sym, "series": []}
    now = time.time()
    recent = [x for x in series if now - x["ts"] <= last_secs]
    vwap_5m = TICK_HISTORY.vwap(sym, last_secs=300)
    spread_bps = TICK_HISTORY.spread_bps(sym)
    mom12 = TICK_HISTORY.momentum(sym, secs=12)
    acc6 = TICK_HISTORY.accel(sym, secs=6)
    latest = series[-1]
    return {
        "symbol": sym,
        "latest": latest,
        "series": recent,
        "vwap5m": vwap_5m,
        "spread_bps": spread_bps,
        "mom12": mom12,
        "acc6": acc6
    }

def _last_oi_pack(sym, n=3):
    """Return last n OI snapshots for this option trading symbol."""
    return OI_HISTORY.last(sym, n=n)

def _context_levels_from_last_merge():
    """Try to reconstruct last S/R, PCR, MaxPain from recent OI snapshot."""
    # We don't keep the whole merged df around, but market_analysis was returned in last call.
    # As a proxy, we compute from last entries across symbols.
    # If that's not available, return minimal.
    try:
        # Compute PCR from latest OI points in history (approx)
        call_oi_sum = 0.0; put_oi_sum = 0.0
        for sym, q in OI_HISTORY.buf.items():
            if not q: continue
            last = q[-1]
            if sym.endswith("CE"):
                call_oi_sum += float(last.get("oi", 0) or 0)
            elif sym.endswith("PE"):
                put_oi_sum += float(last.get("oi", 0) or 0)
        pcr = (put_oi_sum / call_oi_sum) if call_oi_sum > 0 else None
        return {"pcr": pcr}
    except Exception:
        return {"pcr": None}

def _key_levels_guess():
    """Basic supports/resistances using recent OI history around ATM; lightweight."""
    try:
        with WS_LOCK:
            spot = TICKS_CACHE.get("NIFTY_SPOT", {}).get("ltp", None)
        if not spot:
            return {"supports": [], "resistances": []}
        atm = int(round(spot / 50.0) * 50)
        # collect last OI per strike
        levels = {}
        for sym, q in OI_HISTORY.buf.items():
            if not q: continue
            last = q[-1]
            k = int(round(float(last.get("strike", 0)) / 50.0) * 50)
            oi = float(last.get("oi", 0))
            levels.setdefault(k, 0.0)
            # assign CE negative weight above spot, PE positive below spot (simple)
            if sym.endswith("CE") and k >= atm:
                levels[k] -= oi
            if sym.endswith("PE") and k <= atm:
                levels[k] += oi
        # pick top 3 positive as supports, top 3 negative (by abs) as resistances
        supports = sorted([(k, v) for k, v in levels.items() if v > 0], key=lambda x: x[1], reverse=True)[:3]
        resistances = sorted([(k, v) for k, v in levels.items() if v < 0], key=lambda x: abs(x[1]), reverse=True)[:3]
        return {
            "supports": [{"strike": int(k), "strength": float(v)} for k, v in supports],
            "resistances": [{"strike": int(k), "strength": float(abs(v))} for k, v in resistances],
        }
    except Exception:
        return {"supports": [], "resistances": []}

def build_ai_payload():
    # Safe symbol guards
    NIFTY_FUT_SYMBOL = globals().get('NIFTY_FUT_SYMBOL', None)
    VIX_SYMBOL = globals().get('VIX_SYMBOL', None)

    """Bundle a pro-grade intraday context for the AI coach."""
    with WS_LOCK:
        spot_tick = TICKS_CACHE.get("NIFTY_SPOT", {})
        fut_tick = TICKS_CACHE.get(NIFTY_FUT_SYMBOL, {}) if NIFTY_FUT_SYMBOL else {}
        vix_tick = TICKS_CACHE.get(VIX_SYMBOL, {}) if VIX_SYMBOL else {}

    atm_syms = _atm_candidates_from_spot_for_ai()

    options_block = []
    for s in atm_syms:
        block = _series_pack(s, last_secs=240)  # last 4 minutes of option ticks
        block["oi_last3"] = _last_oi_pack(s, n=3)
        options_block.append(block)

    payload = {
        "meta": {
            "as_of_ts": time.time(),
            "window_secs": HIST_WINDOW_SECS,
            "ai_model": AI_MODEL,
        },
        "spot": _series_pack("NIFTY_SPOT", last_secs=240),
        "futures": _series_pack(NIFTY_FUT_SYMBOL, last_secs=240) if NIFTY_FUT_SYMBOL else None,
        "vix": _series_pack(VIX_SYMBOL, last_secs=600) if VIX_SYMBOL else None,
        "options": options_block,
        "context": {
            "pcr_guess": _context_levels_from_last_merge().get("pcr"),
            **_key_levels_guess(),
        },
        "positions": fetch_open_positions(obj),  # normalized positions (paper/live)
    }
    return payload

# --- Upgraded ai_trade_coach that sends the rich payload ---
def ai_trade_coach_rich():
    try:
        payload = build_ai_payload()
        prompt = {
            "role": "system",
            "content": (
                "You are an Indian index options scalping coach for NIFTY. "
                "Use the JSON context to give one of: ENTER, HOLD, EXIT, or WAIT. "
                "If ENTER, provide: symbol, entry, sl, target, confidence (0-100), and a 1-line reason. "
                "If HOLD, optionally suggest new trailed SL. "
                "If EXIT, include 1-line reason (momentum fade, spread widened, SL/Target met, etc.). "
                "Prefer ATM or ATM±1 if spread tight and momentum aligns with spot; avoid wide spreads or no momentum. "
                "Consider PCR, supports/resistances, and VIX regime for risk. Keep the answer compact."
            )
        }
        user = {
            "role": "user",
            "content": json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        }
        resp = _ai_client.chat([prompt, user], model=AI_MODEL, temperature=0.2, max_tokens=300)
        # Expected lightweight JSON in resp["message"]
        msg = resp.get("message") or resp.get("content") or ""
        # We accept either JSON or short text; try JSON first
        advice = {}
        try:
            advice = json.loads(msg)
        except Exception:
            # fallback: tiny parser by keywords
            text = msg.lower()
            if "enter" in text:
                advice["coach"] = "ENTER"
            elif "exit" in text:
                advice["coach"] = "EXIT"
            elif "hold" in text:
                advice["coach"] = "HOLD"
            else:
                advice["coach"] = "WAIT"
            advice["note"] = msg
        return advice
    except Exception as e:
        print(f"AI coach error: {e}")
        return {}





# ==================================================================================================
# === Implemented Suggestions Merge (Non-Destructive) ==============================================
# - Inline OpenRouterClient (avoids external utils import)
# - Single global SmartWebSocketV2 instance with clean start/stop/subscribe
# - 1s Coach sampler + 3-min snapshot cycle (PCR/MaxPain/S/R)
# - SQLite logging & Telegram emit glue
# - start_system()/stop_system()/run() orchestration
# NOTE: This block is ADDITIVE. Your original functions remain unchanged above.
# ==================================================================================================

import threading, logging, json, sqlite3, re
from collections import deque, defaultdict
from datetime import datetime
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ===== Inline OpenRouterClient =====
class OpenRouterClient:
    def __init__(self, api_key: str = None, default_model: str = "mistralai/mistral-small-3.2-24b-instruct"):
        import os, time, requests
        self.os = os
        self.time = time
        self.requests = requests
        self.api_key = api_key or os.getenv('OPENROUTER_API_KEY', '')
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.default_model = default_model
        self.rate_limit = 2
        self.last_request_time = 0
        self.logger = logging.getLogger('openrouter_client')

    def _rate_limit_delay(self):
        elapsed = self.time.time() - self.last_request_time
        want = 1.0 / max(self.rate_limit, 1)
        if elapsed < want:
            self.time.sleep(want - elapsed)
        self.last_request_time = self.time.time()

    def _request(self, payload: dict, max_retries: int = 3):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://oi-tracker.local",
            "X-Title": "OI Tracker AI"
        }
        for attempt in range(max_retries):
            try:
                self._rate_limit_delay()
                r = self.requests.post(self.base_url, headers=headers, json=payload, timeout=30)
                if r.status_code == 200:
                    return r.json()
                if r.status_code == 429:
                    wait = 2 ** attempt
                    self.logger.warning(f"429 rate limited; sleeping {wait}s")
                    self.time.sleep(wait)
                    continue
                self.logger.error(f"OpenRouter error {r.status_code}: {r.text[:200]}")
                return None
            except Exception as e:
                self.logger.error(f"OpenRouter request error: {e}")
                if attempt < max_retries - 1:
                    self.time.sleep(2 ** attempt)
                    continue
                return None
        return None

    def chat(self, model: str, messages: list, temperature: float = 0.2, max_tokens: int = 300):
        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": float(temperature),
            "max_tokens": int(max_tokens)
        }
        resp = self._request(payload)
        if not resp:
            return {"content": ""}
        try:
            content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception:
            content = ""
        return {"content": content}

# Initialize AI client after class definition
try:
    _ai_client = OpenRouterClient(api_key=os.getenv("OPENROUTER_API_KEY", ""))
except Exception as _e:
    print(f"⚠️ OpenRouterClient not available: {_e}")
    _ai_client = None
    USE_AI_COACH = False



# ===== WebSocket v2 lifecycle (single instance) =====
try:
    from SmartApi.smartWebSocketV2 import SmartWebSocketV2
except Exception as _e:
    SmartWebSocketV2 = None
    print(f"WSv2 import warning: {_e}")

sws = None
_ws_lock = threading.Lock()
_ws_running = False
_ws_connected = False
_symbol_ticks = defaultdict(lambda: deque(maxlen=2000))
_symbol_spreads = defaultdict(lambda: deque(maxlen=2000))
_active_tokens = set()
_symbol_by_token = {}
_token_by_symbol = {}
_last_spot = None
_last_tick_time = 0

def _now_ts():
    import time as _t
    return _t.time()

def _on_tick_ws(tick_data):
    global _last_spot, _last_tick_time
    try:
        tok = str(tick_data.get('token') or tick_data.get('tk') or "")
        if not tok:
            return
        sym = TOKEN_TO_SYMBOL.get(tok, tok) if 'TOKEN_TO_SYMBOL' in globals() else tok
        ltp = tick_data.get('last_traded_price') or tick_data.get('ltp') or 0.0
        bid = tick_data.get('best_bid_price') or tick_data.get('bp') or 0.0
        ask = tick_data.get('best_ask_price') or tick_data.get('ap') or 0.0
        vol = tick_data.get('last_traded_qty') or tick_data.get('ltq') or 0
        ts = _now_ts()
        _symbol_ticks[sym].append((ts, float(ltp), float(bid), float(ask), int(vol)))
        spr = 0.0
        try:
            if float(bid) > 0 and float(ask) > 0:
                spr = float(ask) - float(bid)
        except Exception:
            pass
        _symbol_spreads[sym].append((ts, spr))
        _last_tick_time = ts
        # spot convenience if mapping exists
        if 'nifty_index_token' in globals():
            if sym == TOKEN_TO_SYMBOL.get(str(nifty_index_token), "NIFTY_SPOT"):
                _last_spot = float(ltp)
    except Exception as e:
        print(f"WS tick parse error: {e}")

def _on_connect_ws():
    global _ws_connected
    _ws_connected = True
    print("🔌 WSv2 opened")

def _on_close_ws(code, reason):
    global _ws_connected
    _ws_connected = False
    print(f"🔒 WSv2 closed ({code}) {reason}")

def _on_error_ws(e):
    print(f"❌ WSv2 error: {e}")

def ws_start(initial_tokens=None):
    global sws, _ws_running, _ws_connected
    if SmartWebSocketV2 is None:
        print("WSv2 not available in this environment.")
        return
    with _ws_lock:
        if _ws_running:
            if initial_tokens:
                ws_subscribe(initial_tokens)
            return
        if 'obj' not in globals():
            raise RuntimeError("Angel One SmartConnect 'obj' not initialized")
        try:
            ftok = obj.getfeedToken()
        except Exception:
            ftok = None
        if not ftok:
            raise RuntimeError("No FEED_TOKEN available for WebSocketV2")
        sws = SmartWebSocketV2(
            obj.api_key, ftok, user_id,
            on_message=_on_tick_ws, on_open=_on_connect_ws, on_close=_on_close_ws, on_error=_on_error_ws
        )
        _ws_running = True
        def _run():
            try:
                sws.connect()
            except Exception as e:
                print(f"WS connect exception: {e}")
            finally:
                with _ws_lock:
                    _ws_running = False
                    _ws_connected = False
        threading.Thread(target=_run, name="WS-Runner", daemon=True).start()
    import time as _t
    t_end = _t.time() + 5
    while not _ws_connected and _t.time() < t_end:
        _t.sleep(0.05)
    if initial_tokens:
        ws_subscribe(initial_tokens)

def ws_subscribe(tokens):
    if not tokens or not sws:
        return
    new_list = []
    for tok in map(str, tokens):
        if tok not in _active_tokens:
            _active_tokens.add(tok)
            new_list.append(tok)
    if not new_list:
        return
    channels = []
    for tok in new_list:
        sym = TOKEN_TO_SYMBOL.get(tok, "")
        exch = "NSE" if (sym == "NIFTY 50" or tok == str(globals().get('nifty_index_token',''))) else "NFO"
        channels.append((exch, tok))
    try:
        sws.subscribe(correlation_id="oi-monitor", mode="full", tokens=channels)
        for tok in new_list:
            sym = TOKEN_TO_SYMBOL.get(tok, f"TOKEN_{tok}")
            _symbol_by_token[tok] = sym
            _token_by_symbol[sym] = tok
        print(f"📡 WS subscribed {len(new_list)} new tokens (total {len(_active_tokens)})")
    except Exception as e:
        print(f"Subscribe failed: {e}")

def ws_unsubscribe(tokens):
    if not tokens or not sws:
        return
    remove_list = []
    for tok in map(str, tokens):
        if tok in _active_tokens:
            _active_tokens.remove(tok)
            remove_list.append(tok)
    if not remove_list:
        return
    channels = []
    for tok in remove_list:
        sym = TOKEN_TO_SYMBOL.get(tok, "")
        exch = "NSE" if (sym == "NIFTY 50" or tok == str(globals().get('nifty_index_token',''))) else "NFO"
        channels.append((exch, tok))
    try:
        sws.unsubscribe(correlation_id="oi-monitor", mode="full", tokens=channels)
        print(f"📵 WS unsubscribed {len(remove_list)} tokens (total {len(_active_tokens)})")
    except Exception as e:
        print(f"Unsubscribe failed: {e}")


def ws_stop():
    """Cleanly stop WS and reset flags; safe if not connected."""
    global sws, _ws_running, _ws_connected, _active_tokens
    try:
        HIST_SAMPLER_STOP.set()
    except Exception:
        pass
    try:
        if 'sws' in globals() and sws is not None:
            try:
                if hasattr(sws, 'close'):
                    sws.close()
                elif hasattr(sws, 'disconnect'):
                    sws.disconnect()
            except Exception as e:
                print(f"WS close error: {e}")
    finally:
        try:
            _active_tokens = set()
        except Exception:
            pass
        sws = None
        try:
            _ws_running = False
            _ws_connected = False
        except Exception:
            pass
        print("🛑 WS stopped (safe)")

def compute_pcr_maxpain_support_resistance(snapshot_df):
    if snapshot_df is None or snapshot_df.empty:
        return {"pcr": None, "max_pain": None, "support": [], "resistance": [], "call_oi_by_strike": {}, "put_oi_by_strike": {}}
    if 'current_expiry_short' not in globals():
        return {"pcr": None, "max_pain": None, "support": [], "resistance": [], "call_oi_by_strike": {}, "put_oi_by_strike": {}}
    ces, pes = {}, {}
    for _, r in snapshot_df.iterrows():
        sym = str(r.get("symbol",""))
        m = re.search(r"NIFTY" + re.escape(current_expiry_short) + r"(\d{5})([CP]E)$", sym)
        if not m: 
            continue
        st = int(m.group(1)); side = m.group(2)
        if side == "CE":
            ces[st] = ces.get(st, 0) + int(r.get("oi", 0))
        else:
            pes[st] = pes.get(st, 0) + int(r.get("oi", 0))
    totc = sum(ces.values()) or 1
    totp = sum(pes.values()) or 1
    pcr = round(totp / totc, 2)
    merged = sorted(set(list(ces.keys()) + list(pes.keys())))
    max_pain, best = None, None
    for k in merged:
        sc = abs(ces.get(k,0) - pes.get(k,0))
        if best is None or sc < best:
            best = sc; max_pain = k
    support = sorted(((k,pes.get(k,0)) for k in merged), key=lambda x: x[1], reverse=True)[:3]
    resistance = sorted(((k,ces.get(k,0)) for k in merged), key=lambda x: x[1], reverse=True)[:3]
    return {"pcr": pcr, "max_pain": max_pain, "support": support, "resistance": resistance,
            "call_oi_by_strike": ces, "put_oi_by_strike": pes}

# ===== Minimal market data snapshot helper (expects obj.getMarketData) =====
def _get_tokens_for_symbols(symbols):
    toks = []
    for s in symbols or []:
        tok = SYMBOL_TO_TOKEN.get(s) if 'SYMBOL_TO_TOKEN' in globals() else None
        if tok: toks.append(str(tok))
    return toks

def get_option_chain_snapshot(target_symbols):
    if not target_symbols:
        return pd.DataFrame(columns=["symbol","token","ltp","bid","ask","oi","volume","ts"])
    try:
        # partition NSE/NFO like SDK expects
        exch_map = {"NSE": [], "NFO": []}
        for s in target_symbols:
            tok = SYMBOL_TO_TOKEN.get(s) if 'SYMBOL_TO_TOKEN' in globals() else None
            if not tok:
                continue
            sym = s
            if sym == "NIFTY 50" or str(tok) == str(globals().get('nifty_index_token','')):
                exch_map["NSE"].append(str(tok))
            else:
                exch_map["NFO"].append(str(tok))
        exch_map = {k:v for k,v in exch_map.items() if v}
        resp = obj.getMarketData("FULL", exch_map) if 'obj' in globals() else []
        raw = resp.get('data', []) if isinstance(resp, dict) else (resp or [])
        rows, ts = [], datetime.now()
        for item in raw:
            try:
                tok = str(item.get('token') or item.get('tk') or "")
                sym = TOKEN_TO_SYMBOL.get(tok, "") if 'TOKEN_TO_SYMBOL' in globals() else tok
                ltp = item.get('last_traded_price') or item.get('ltp') or 0.0
                bid = item.get('best_bid_price') or item.get('bp') or 0.0
                ask = item.get('best_ask_price') or item.get('ap') or 0.0
                vol = item.get('volume') or item.get('v') or 0
                oi  = item.get('oi') or item.get('open_interest') or 0
                rows.append([sym, tok, float(ltp), float(bid), float(ask), int(oi), int(vol), ts])
            except Exception:
                continue
        return pd.DataFrame(rows, columns=["symbol","token","ltp","bid","ask","oi","volume","ts"])
    except Exception as e:
        print(f"get_option_chain_snapshot error: {e}")
        return pd.DataFrame(columns=["symbol","token","ltp","bid","ask","oi","volume","ts"])

# ===== PositionCoach (simple slope+spread blend) =====
class PositionCoach:
    @staticmethod
    def analyze(spot_price, ce_ticks: dict, pe_ticks: dict, oi_context: dict, config=None):
        def _recent_slope(series):
            if len(series) < 5:
                return 0.0
            pts = list(series)[-10:]
            xs = np.arange(len(pts))
            ys = np.array([p[1] for p in pts], dtype=float)
            try:
                slope = np.polyfit(xs, ys, 1)[0]
            except Exception:
                slope = 0.0
            return slope
        def _pick_key(d):
            if not d: return None
            best_k, best_v = None, -1
            for k, dq in d.items():
                if not dq: continue
                v = sum(x[4] for x in list(dq)[-10:])
                if v > best_v: best_v, best_k = v, k
            return best_k
        ce_key = _pick_key(ce_ticks); pe_key = _pick_key(pe_ticks)
        ce_slope = _recent_slope(ce_ticks.get(ce_key, [])) if ce_key else 0.0
        pe_slope = _recent_slope(pe_ticks.get(pe_key, [])) if pe_key else 0.0
        pcr = (oi_context or {}).get("pcr")
        bias = 0
        if pcr is not None:
            if pcr > 1.1: bias = -0.5
            elif pcr < 0.9: bias = 0.5
        score = (ce_slope - pe_slope) + bias
        if score > 0.4:
            signal = "ENTER"; strength = "HIGH" if score > 0.8 else "MODERATE"
            reason = f"CE slope {ce_slope:.3f} > PE slope {pe_slope:.3f}, PCR {pcr}"
        elif score < -0.4:
            signal = "ENTER"; strength = "HIGH" if score < -0.8 else "MODERATE"
            reason = f"PE slope {pe_slope:.3f} > CE slope {ce_slope:.3f}, PCR {pcr}"
        else:
            spreads_ce = _symbol_spreads.get(ce_key, deque()) if ce_key else deque()
            spreads_pe = _symbol_spreads.get(pe_key, deque()) if pe_key else deque()
            vals = []; 
            for dq in (spreads_ce, spreads_pe):
                if dq:
                    vs = [x[1] for x in list(dq)[-8:] if x[1] is not None]
                    if vs: vals.append(float(np.mean(vs)))
            avg_spr = (sum(vals)/len(vals)) if vals else 0.0
            if avg_spr > 1.5:
                signal, strength, reason = "EXIT", "LOW", f"Wide spreads {avg_spr:.2f}"
            else:
                signal, strength, reason = "HOLD", "LOW", f"Low momentum | spread {avg_spr:.2f}"
        context_for_ai = {
            "spot": float(spot_price or 0), "pcr": pcr,
            "max_pain": (oi_context or {}).get("max_pain"),
            "support": (oi_context or {}).get("support"),
            "resistance": (oi_context or {}).get("resistance"),
            "ce_key": ce_key, "pe_key": pe_key,
            "ce_tail": list(ce_ticks.get(ce_key, []))[-15:] if ce_key else [],
            "pe_tail": list(pe_ticks.get(pe_key, []))[-15:] if pe_key else [],
        }
        return {"signal": signal, "strength": strength, "reason": reason, "context_for_ai": context_for_ai}

# ===== SQLite + Telegram glue (non-destructive) =====

DB_PATH = "paper_trades.sqlite3"

def _db_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def _init_db():
    con = _db_conn(); cur = con.cursor()
    # Core paper signals log (non-destructive)
    cur.execute("""CREATE TABLE IF NOT EXISTS paper_signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        advice TEXT, strength TEXT, reason TEXT,
        index_spot REAL, pcr REAL, max_pain INTEGER,
        ce_key TEXT, pe_key TEXT,
        ai_note TEXT, pos_size REAL,
        meta_json TEXT
    )""")
    # Core option snapshots (for charts/history)
    cur.execute("""CREATE TABLE IF NOT EXISTS option_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        symbol TEXT, exch TEXT,
        ltp REAL, bid REAL, ask REAL,
        oi INTEGER, volume INTEGER
    )""")
    con.commit(); con.close()

_init_db()

def _ensure_trade_tables():
    con = _db_conn(); cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY,
        symbol TEXT,
        entry_time TEXT,
        entry_price REAL,
        exit_time TEXT,
        exit_price REAL,
        pnl REAL,
        reason TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS signals (
        id INTEGER PRIMARY KEY,
        timestamp TEXT,
        symbol TEXT,
        direction TEXT,
        entry_price REAL,
        target REAL,
        sl REAL,
        confidence INTEGER,
        status TEXT,
        exit_time TEXT,
        exit_price REAL,
        exit_reason TEXT
    )""")
    con.commit(); con.close()

_ensure_trade_tables()

def log_signal_to_db(payload: dict):
    try:
        con = _db_conn(); cur = con.cursor()
        ctx = payload.get("context_for_ai", {})
        cur.execute("""INSERT INTO paper_signals
            (ts, advice, strength, reason, index_spot, pcr, max_pain, ce_key, pe_key, ai_note, pos_size, meta_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (
            datetime.now().isoformat(timespec="seconds"),
            payload.get("advice") or payload.get("signal"),
            payload.get("strength"), payload.get("reason"),
            float(ctx.get("spot") or 0), ctx.get("pcr"),
            ctx.get("max_pain"), ctx.get("ce_key"), ctx.get("pe_key"),
            payload.get("ai_note", ""), float(payload.get("pos_size", 0)),
            json.dumps(payload, default=str)[:6000]
        ))
        con.commit(); con.close()
    except Exception as e:
        print(f"DB log_signal error: {e}")

def log_snapshot_df(df: pd.DataFrame):
    if df is None or df.empty: return
    try:
        con = _db_conn(); cur = con.cursor()
        rows = [(r['ts'].isoformat(timespec="seconds") if isinstance(r['ts'], datetime) else str(r['ts']),
                 str(r['symbol']), str(r['token']), float(r['ltp']), float(r['bid']), float(r['ask']), int(r['oi']), int(r['volume']))
                for _, r in df.iterrows()]
        cur.executemany("""INSERT INTO option_snapshots (ts, symbol, token, ltp, bid, ask, oi, volume)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", rows)
        con.commit(); con.close()
    except Exception as e:
        print(f"DB log_snapshot_df error: {e}")

# You likely already have send_telegram_message_simple() defined above; if not, add a no-op fallback:
if 'send_telegram_message_simple' not in globals():
    def send_telegram_message_simple(message, chat_id=None):
        print("[Telegram mock] ", message[:120])

def _position_size_for_strength(strength: str) -> float:
    mult = {'HIGH':1.0,'STRONG':1.0,'MODERATE':0.6,'MEDIUM':0.6}
    return mult.get((strength or '').upper(), 0.3)

def emit_signal(advice: str, strength: str, reason: str, ctx: dict, ai_note: str):
    payload = {"advice": advice, "strength": strength, "reason": reason, "ai_note": ai_note,
               "pos_size": _position_size_for_strength(strength), "context_for_ai": ctx}
    log_signal_to_db(payload)
    try:
        msg = f"🤖 Coach: *{advice}* ({strength})\n📈 Spot: {ctx.get('spot')} | PCR: {ctx.get('pcr')} | MP: {ctx.get('max_pain')}\n" \
              f"🎯 CE: {ctx.get('ce_key')} | PE: {ctx.get('pe_key')}\n📝 {reason}\n" + (f"🧠 {ai_note}" if ai_note else "")
        send_telegram_message_simple(msg)
    except Exception as e:
        print(f"Telegram emit error: {e}")

# ===== 1s Coach Sampler + 3-min Snapshot Cycle =====
_coach_thread = None
_coach_thread_stop = threading.Event()

def _collect_ticks_by_side():
    ce_ticks, pe_ticks = {}, {}
    for sym, dq in _symbol_ticks.items():
        if sym.endswith("CE"): ce_ticks[sym] = dq
        elif sym.endswith("PE"): pe_ticks[sym] = dq
    return ce_ticks, pe_ticks

def _coach_sampler_loop():
    print("🎧 Coach sampler started")
    last_emit = 0
    import time as _t
    while not _coach_thread_stop.is_set():
        try:
            ce_ticks, pe_ticks = _collect_ticks_by_side()
            oi_snapshot_syms = list(ce_ticks.keys())[:10] + list(pe_ticks.keys())[:10]
            snap = get_option_chain_snapshot(oi_snapshot_syms)
            oi_ctx = compute_pcr_maxpain_support_resistance(snap)
            coach = PositionCoach().decide(_last_spot, ce_ticks, pe_ticks, oi_ctx, None)
            advice = coach["signal"]; strength = coach["strength"]; reason = coach["reason"]
            nudge = ai_trade_coach(coach.get("context_for_ai", {}))
            ai_note = nudge.get("note","") if nudge else ""
            if nudge and nudge.get("advice"):
                advice = nudge["advice"]
            now = _t.time()
            if now - last_emit > 3:
                last_emit = now
                print(f"🤖 Coach: {advice} ({strength}) — {reason}" + (f" | AI: {ai_note}" if ai_note else ""))
                emit_signal(advice, strength, reason, coach.get("context_for_ai", {}), ai_note)
        except Exception as e:
            print(f"Coach sampler error: {e}")
        finally:
            _t.sleep(1.0)
    print("🛌 Coach sampler stopped")

def start_coach_sampler():
    global _coach_thread
    if _coach_thread and _coach_thread.is_alive(): return
    _coach_thread_stop.clear()
    _coach_thread = threading.Thread(target=_coach_sampler_loop, name="CoachSampler", daemon=True)
    _coach_thread.start()

def stop_coach_sampler():
    _coach_thread_stop.set()

_snapshot_thread = None
_snapshot_stop = threading.Event()
SNAPSHOT_INTERVAL_SECS = 180

def _pick_focus_symbols():
    syms = [k for k in _symbol_ticks.keys()]
    # keep up to 12 symbols with most recent activity
    syms = syms[-12:]
    return syms

def _snapshot_loop():
    print("⏱️ Snapshot cycle started")
    import time as _t
    while not _snapshot_stop.is_set():
        try:
            symbols = _pick_focus_symbols()
            if not symbols:
                _t.sleep(2.0); continue
            snap = get_option_chain_snapshot(symbols)
            if snap is not None and not snap.empty:
                log_snapshot_df(snap)
                ctx = compute_pcr_maxpain_support_resistance(snap)
                print(f"📦 Snapshot @ {datetime.now().strftime('%H:%M:%S')} | PCR {ctx.get('pcr')} | MP {ctx.get('max_pain')}")
        except Exception as e:
            print(f"Snapshot loop error: {e}")
        finally:
            for _ in range(SNAPSHOT_INTERVAL_SECS):
                if _snapshot_stop.is_set(): break
                _t.sleep(1.0)
    print("🛌 Snapshot cycle stopped")

def start_snapshot_cycle():
    global _snapshot_thread
    if _snapshot_thread and _snapshot_thread.is_alive(): return
    _snapshot_stop.clear()
    _snapshot_thread = threading.Thread(target=_snapshot_loop, name="SnapshotCycle", daemon=True)
    _snapshot_thread.start()

def stop_snapshot_cycle():
    _snapshot_stop.set()

# ===== System Orchestration =====
def start_system():
    print("🚀 Starting system…")
    # Prepare initial tokens: NIFTY spot + any known option tokens in your SYMBOL_TO_TOKEN map
    initial_tokens = []
    if 'nifty_index_token' in globals() and nifty_index_token:
        initial_tokens.append(str(nifty_index_token))
    if 'SYMBOL_TO_TOKEN' in globals():
        # take up to 20 popular option tokens
        initial_tokens += list(map(str, list(SYMBOL_TO_TOKEN.values())[:20]))
    try:
        ws_start(initial_tokens)
    except Exception as e:
        print(f"WS start failed: {e}")
    try:
        start_coach_sampler()
    except Exception as e:
        print(f"Coach sampler start failed: {e}")
    try:
        start_snapshot_cycle()
    except Exception as e:
        print(f"Snapshot cycle start failed: {e}")
    print("✅ System started")

def stop_system():
    print("🧹 Stopping system…")
    try: stop_snapshot_cycle()
    except Exception as e: print(f"Stop snapshot error: {e}")
    try: stop_coach_sampler()
    except Exception as e: print(f"Stop coach sampler error: {e}")
    try: ws_stop()
    except Exception as e: print(f"Stop WS error: {e}")
    print("✅ System stopped")

def run():
    start_system()
    import time as _t
    try:
        while True: _t.sleep(0.5)
    except KeyboardInterrupt:
        print("\\n🧯 Interrupted by user")
    except Exception as e:
        print(f"Fatal run loop error: {e}")
    finally:
        stop_system()

# Auto-run guard
if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print(f"Startup error: {e}")



# ==================================================================================================
# === FINAL WIRING OVERRIDES (Unify Coach + WS + Secrets + AI Payload Trim) ========================
# This block overrides earlier definitions to fix runtime wiring without removing prior code.
# ==================================================================================================

import os

# ---------- Secrets from ENV (override hard-coded when present) ----------
def apply_env_secrets():
    global TELEGRAM_BOT_TOKEN, _ai_client
    try:
        TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', TELEGRAM_BOT_TOKEN)
    except Exception:
        pass
    try:
        key = os.getenv('OPENROUTER_API_KEY')
        if key:
            try:
                _ai_client = OpenRouterClient(api_key=key)  # rebind to env-backed client
            except Exception:
                pass
    except Exception:
        pass

apply_env_secrets()

# ---------- AI payload trimming ----------
MAX_AI_SERIES_POINTS = 12

def _trim_series(seq, n=MAX_AI_SERIES_POINTS):
    if not seq:
        return []
    # Keep only [ts, ltp] and limit length
    tail = list(seq)[-n:]
    out = []
    for row in tail:
        # accept tuples like (ts, ltp, bid, ask, vol)
        try:
            ts, ltp = row[0], row[1]
        except Exception:
            # unknown shape; just append raw
            out.append(row)
            continue
        out.append([ts, ltp])
    return out

def compact_ai_context(ctx: dict) -> dict:
    if not isinstance(ctx, dict):
        return {}
    slim = {
        "spot": float(ctx.get("spot") or 0.0),
        "pcr": ctx.get("pcr"),
        "max_pain": ctx.get("max_pain"),
        "support": (ctx.get("support") or [])[:1],
        "resistance": (ctx.get("resistance") or [])[:1],
        "ce_key": ctx.get("ce_key"),
        "pe_key": ctx.get("pe_key"),
        "ce_tail": _trim_series(ctx.get("ce_tail") or []),
        "pe_tail": _trim_series(ctx.get("pe_tail") or []),
    }
    return slim

# Override ai_trade_coach to use compact context
def ai_trade_coach(context: dict) -> dict:  # type: ignore[override]
    try:
        client = _ai_client if '_ai_client' in globals() and _ai_client else OpenRouterClient()
        prompt = (
            "You are an Indian index options scalping coach for NIFTY. "
            "Given spot, compact CE/PE series (last ~60–120s), and PCR/MaxPain hints, "
            "answer with exactly one of: ENTER, HOLD, EXIT, or WAIT, then a brief reason.\n\n"
            f"Context JSON:\n{json.dumps(compact_ai_context(context))[:3500]}"
        )
        out = _ai_client.chat(
            model="deepseek/deepseek-r1",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2, max_tokens=200
        )
        msg = out.get("content", "") if isinstance(out, dict) else str(out)
        decision = "WAIT"
        for k in ("ENTER","HOLD","EXIT","WAIT"):
            if k in msg.upper():
                decision = k; break
        return {"advice": decision, "note": msg[:240]}
    except Exception as e:
        print(f"AI coach error: {e}")
        return {}

# ---------- Unified PositionCoach (supports both static and instance usage) ----------
class PositionCoach:  # type: ignore[override]
    """
    Unified coach that supports both styles used across the file.
    - Static: PositionCoach().decide(spot_price, ce_ticks, pe_ticks, oi_context, config)
    - Instance: PositionCoach().decide(spot=..., ce_ticks=..., pe_ticks=..., oi_context=..., config=...)
    - Robust kwargs: accepts spot or spot_price; can accept ticks={'CE':..., 'PE':...}
    """
    def __init__(self, config=None):
        self.config = config

    @staticmethod
    def _normalize_inputs(*args, **kwargs):
        # Handle arg-style
        if args and len(args) >= 4:
            spot = args[0]
            ce_ticks = args[1]
            pe_ticks = args[2]
            oi_context = args[3]
            config = args[4] if len(args) >= 5 else kwargs.get("config")
            return spot, ce_ticks, pe_ticks, oi_context, config

        # Kwarg-style
        spot = kwargs.get("spot")
        if spot is None:
            spot = kwargs.get("spot_price")
        ticks = kwargs.get("ticks")
        ce_ticks = kwargs.get("ce_ticks")
        pe_ticks = kwargs.get("pe_ticks")

        if ticks and (not ce_ticks or not pe_ticks):
            # ticks can be a dict or a tuple
            if isinstance(ticks, dict):
                ce_ticks = ticks.get("CE") or ticks.get("ce") or ce_ticks
                pe_ticks = ticks.get("PE") or ticks.get("pe") or pe_ticks
            elif isinstance(ticks, (list, tuple)) and len(ticks) >= 2:
                ce_ticks = ce_ticks or ticks[0]
                pe_ticks = pe_ticks or ticks[1]

        oi_context = kwargs.get("oi_context") or {}
        config = kwargs.get("config")
        return spot, ce_ticks, pe_ticks, oi_context, config

    @classmethod
    def analyze(cls, *args, **kwargs):
        spot, ce_ticks, pe_ticks, oi_context, config = cls._normalize_inputs(*args, **kwargs)

        def _recent_slope(series):
            if not series or len(series) < 5:
                return 0.0
            pts = list(series)[-10:]
            xs = np.arange(len(pts))
            ys = np.array([p[1] for p in pts], dtype=float)
            try:
                slope = np.polyfit(xs, ys, 1)[0]
            except Exception:
                slope = 0.0
            return slope

        def _pick_key(d):
            if not d: return None
            best_k, best_v = None, -1
            for k, dq in d.items():
                if not dq: continue
                v = sum(x[4] for x in list(dq)[-10:])
                if v > best_v: best_v, best_k = v, k
            return best_k

        ce_key = _pick_key(ce_ticks) if isinstance(ce_ticks, dict) else None
        pe_key = _pick_key(pe_ticks) if isinstance(pe_ticks, dict) else None
        ce_slope = _recent_slope(ce_ticks.get(ce_key, [])) if ce_key else 0.0
        pe_slope = _recent_slope(pe_ticks.get(pe_key, [])) if pe_key else 0.0

        pcr = (oi_context or {}).get("pcr")
        bias = 0.0
        if pcr is not None:
            if pcr > 1.1: bias = -0.5
            elif pcr < 0.9: bias = 0.5

        score = (ce_slope - pe_slope) + bias
        if score > 0.4:
            signal = "ENTER"; strength = "HIGH" if score > 0.8 else "MODERATE"
            reason = f"CE slope {ce_slope:.3f} > PE slope {pe_slope:.3f}, PCR {pcr}"
        elif score < -0.4:
            signal = "ENTER"; strength = "HIGH" if score < -0.8 else "MODERATE"
            reason = f"PE slope {pe_slope:.3f} > CE slope {ce_slope:.3f}, PCR {pcr}"
        else:
            spreads_ce = _symbol_spreads.get(ce_key, deque()) if ce_key else deque()
            spreads_pe = _symbol_spreads.get(pe_key, deque()) if pe_key else deque()
            vals = []
            for dq in (spreads_ce, spreads_pe):
                if dq:
                    vs = [x[1] for x in list(dq)[-8:] if x[1] is not None]
                    if vs: vals.append(float(np.mean(vs)))
            avg_spr = (sum(vals)/len(vals)) if vals else 0.0
            if avg_spr > 1.5:
                signal, strength, reason = "EXIT", "LOW", f"Wide spreads {avg_spr:.2f}"
            else:
                signal, strength, reason = "HOLD", "LOW", f"Low momentum | spread {avg_spr:.2f}"

        context_for_ai = {
            "spot": float(spot or 0), "pcr": pcr,
            "max_pain": (oi_context or {}).get("max_pain"),
            "support": (oi_context or {}).get("support"),
            "resistance": (oi_context or {}).get("resistance"),
            "ce_key": ce_key, "pe_key": pe_key,
            "ce_tail": list(ce_ticks.get(ce_key, []))[-15:] if (isinstance(ce_ticks, dict) and ce_key) else [],
            "pe_tail": list(pe_ticks.get(pe_key, []))[-15:] if (isinstance(pe_ticks, dict) and pe_key) else [],
        }
        return {"signal": signal, "strength": strength, "reason": reason, "context_for_ai": context_for_ai}

    # Instance API
    def decide(self, *args, **kwargs):
        return self.analyze(*args, **kwargs)

    # ---- Back-compat shim so your main loop remains unchanged ----
    def analyze(self, spot, ticks, positions, ai_hint):
        """
        Backwards-compat wrapper that:
          - calls decide(...) under the hood
          - sets last_signal_* attributes expected by the existing main loop
          - returns (advice, note)
        """
        # feed the new path
        decision = self.decide(
            market_analysis={},  # not used by the current decide()
            open_positions=positions,
            watch_syms=_coach_watch_list_from_spot(),
            ticks=ticks
        ) or {}

        advice = decision.get("coach", "WAIT")
        note   = decision.get("why", "")

        # Populate legacy fields the loop uses
        if advice == "ENTER":
            self.last_signal_dir    = "LONG" if "CE" in decision.get("symbol","") else "SHORT"
            self.last_signal_price  = float(decision.get("entry", 0.0))
            self.last_signal_target = float(decision.get("target", 0.0))
            self.last_signal_sl     = float(decision.get("sl", 0.0))
            self.last_signal_conf   = int(decision.get("confidence", ai_hint.get("confidence", 70) if isinstance(ai_hint, dict) else 70))
            self.last_exit_price    = None
            self.last_exit_reason   = ""
        elif advice == "EXIT":
            self.last_exit_price  = float(ticks.get(decision.get("symbol",""),{}).get("ltp", 0.0)) if isinstance(ticks, dict) else 0.0
            self.last_exit_reason = decision.get("why", "Exit")
        else:
            # HOLD/WAIT
            pass

        # prefer AI note if present
        if isinstance(ai_hint, dict) and ai_hint.get("note"):
            note = ai_hint["note"]
        return advice, note

# ---------- WS lifecycle unification wrappers (compat with older calls) ----------
def _normalize_to_tokens(items):
    if not items:
        return []
    toks = []
    for it in items:
        s = str(it)
        if s.isdigit():
            toks.append(s)
        else:
            tok = SYMBOL_TO_TOKEN.get(s) if 'SYMBOL_TO_TOKEN' in globals() else None
            if tok:
                toks.append(str(tok))
    return toks


def start_ws_feed(initial=None):
    try:
        toks = _normalize_to_tokens(initial or []) if '_normalize_to_tokens' in globals() else (initial or [])
        ws_start(toks)
    except Exception as e:
        print(f"start_ws_feed error: {e}")


def ws_refresh_subscription(items):
    try:
        toks = _normalize_to_tokens(items or []) if '_normalize_to_tokens' in globals() else (items or [])
        ws_subscribe(toks)
    except Exception as e:
        print(f"ws_refresh_subscription error: {e}")


def stop_ws_feed():
    try:
        ws_stop()
    except Exception as e:
        print(f"stop_ws_feed error: {e}")


# ---- Guard against accidental class-level subscribe calls ----
try:
    from SmartApi.smartWebSocketV2 import SmartWebSocketV2 as _WSClass
    if hasattr(_WSClass, 'subscribe'):
        def _guarded_cls_sub(*a, **k):
            raise RuntimeError('Do not call SmartWebSocketV2.subscribe on the CLASS. Use sws.subscribe via ws_subscribe().')
        _WSClass.subscribe = _guarded_cls_sub
except Exception:
    pass
