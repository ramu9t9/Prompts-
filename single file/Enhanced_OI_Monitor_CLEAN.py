import os
import time
import pandas as pd
import numpy as np
import hashlib
import requests
import io
import matplotlib
matplotlib.use('Agg')  # Set non-interactive backend to avoid tkinter errors
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from datetime import datetime, timedelta
from dateutil import parser
from SmartApi import SmartConnect
import pyotp
import warnings
from collections import Counter, deque, defaultdict
import sqlite3
import re
import threading
import json
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
import logging

# Suppress pandas warnings
warnings.filterwarnings('ignore', category=pd.errors.SettingWithCopyWarning)

# Base directory for logs
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ====== LOGGING FOR AI ANALYSIS ======
import json
from datetime import datetime
import threading

LOG_LOCK = threading.Lock()

def log_ai_interaction(analysis_type, prompt, response, context_data=None, api_request=None):
    """Append a single log record (atomic) to dated logs folder.
    - Writes NDJSON (one JSON per line) to avoid concurrency truncation
    - Also appends a human-readable .txt entry
    """
    try:
        # Prepare directory structure
        day_str = datetime.now().strftime('%Y-%m-%d')
        logs_folder = os.path.join(BASE_DIR, 'logs', day_str)
        os.makedirs(logs_folder, exist_ok=True)

        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        record = {
            "timestamp": ts,
            "analysis_type": analysis_type,
            "prompt": prompt,
            "full_response": response,
            "context_data": context_data,
            "api_request": api_request,
        }

        ndjson_path = os.path.join(logs_folder, f"ai_log_{day_str}.ndjson")
        txt_path = os.path.join(logs_folder, f"ai_log_{day_str}.txt")

        with LOG_LOCK:
            # Append NDJSON line
            with open(ndjson_path, 'a', encoding='utf-8') as jf:
                jf.write(json.dumps(record, ensure_ascii=False) + "\n")

            # Append human-readable text
            with open(txt_path, 'a', encoding='utf-8') as tf:
                tf.write("\n" + ("=" * 80) + "\n")
                tf.write(f"TIMESTAMP: {ts}\n")
                tf.write(f"ANALYSIS TYPE: {analysis_type.upper()}\n")
                tf.write(f"PROMPT LENGTH: {len(prompt) if prompt else 0} characters\n")
                tf.write(f"RESPONSE LENGTH: {len(response) if response else 0} characters\n")
                tf.write("FULL PROMPT SENT TO OPENROUTER:\n")
                tf.write((prompt or "") + "\n")
                tf.write("FULL RESPONSE FROM OPENROUTER:\n")
                tf.write((response or "") + "\n")
                tf.write(f"CONTEXT DATA KEYS: {list((context_data or {}).keys()) if isinstance(context_data, dict) else 'None'}\n")
                if api_request:
                    try:
                        tf.write("OPENROUTER API REQUEST:\n")
                        tf.write(json.dumps(api_request, indent=2, ensure_ascii=False) + "\n")
                    except Exception:
                        tf.write("OPENROUTER API REQUEST: <unserializable>\n")
                tf.write(("=" * 80) + "\n")
            print(f"📝 Logged {analysis_type} AI entry to {ndjson_path}")
    except Exception as e:
        print(f"❌ Logging error: {e}")

def log_context_summary(context_data):
    """Create a summary of context data for logging."""
    if not context_data:
        return "No context data"
    
    summary = {}
    for key, value in context_data.items():
        if isinstance(value, dict):
            summary[key] = f"dict with {len(value)} items"
        elif isinstance(value, list):
            summary[key] = f"list with {len(value)} items"
        elif isinstance(value, pd.DataFrame):
            summary[key] = f"DataFrame with {len(value)} rows, {len(value.columns)} columns"
        else:
            summary[key] = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
    
    return summary

# ====== CONFIGURATION ======
TELEGRAM_BOT_TOKEN = "8396648490:AAFQfknYdi3oXqIDk9r6U9AZUzEgtAqgV7E"
TELEGRAM_CHAT_ID = "1022980118, 1585910202"
ATM_WINDOW = 2  # ATM ±2 strikes

# Interactive market segment selection
def select_market_segment():
    """Allow user to select market segment interactively."""
    print("\n" + "="*60)
    print("🎯 MARKET SEGMENT SELECTION")
    print("="*60)
    print("1. NFO - NIFTY Options (Full AI Analysis + OI Table)")
    print("2. MCX - Commodities (Tick Streaming Only)")
    print("3. NSE - Equity (Basic Mode)")
    print("="*60)
    
    while True:
        try:
            choice = input("Select market segment (1/2/3) [Default: 1-NFO]: ").strip()
            if choice == "" or choice == "1":
                print("✅ Selected: NFO (NIFTY Options)")
                return "NFO"
            elif choice == "2":
                print("✅ Selected: MCX (Commodities)")
                return "MCX"
            elif choice == "3":
                print("✅ Selected: NSE (Equity)")
                return "NSE"
            else:
                print("❌ Invalid choice. Please enter 1, 2, or 3.")
        except KeyboardInterrupt:
            print("\n✅ Using default: NFO (NIFTY Options)")
            return "NFO"

# Data feed segment: 'NFO' (default, NIFTY Options) or 'MCX' (commodities streaming only)
FEED_SEGMENT = select_market_segment()
# MCX target commodity name (per instruments list 'name' column), e.g., 'SILVERMIC'
def select_mcx_commodity():
    """Allow user to select MCX commodity interactively."""
    if FEED_SEGMENT != 'MCX':
        return 'SILVERMIC'  # Hardcoded MCX commodity
    
    print("\n" + "="*60)
    print("🏭 MCX COMMODITY SELECTION")
    print("="*60)
    print("Popular MCX Commodities:")
    print("1. SILVERMIC - Silver Mini")
    print("2. GOLDMIC - Gold Mini")
    print("3. COPPER - Copper")
    print("4. CRUDEOIL - Crude Oil")
    print("5. NATURALGAS - Natural Gas")
    print("6. ZINC - Zinc")
    print("7. NICKEL - Nickel")
    print("8. ALUMINIUM - Aluminium")
    print("="*60)
    
    commodities = {
        "1": "SILVERMIC",
        "2": "GOLDMIC", 
        "3": "COPPER",
        "4": "CRUDEOIL",
        "5": "NATURALGAS",
        "6": "ZINC",
        "7": "NICKEL",
        "8": "ALUMINIUM"
    }
    
    while True:
        try:
            choice = input("Select commodity (1-8) [Default: 1-SILVERMIC]: ").strip()
            if choice == "" or choice == "1":
                print("✅ Selected: SILVERMIC")
                return "SILVERMIC"
            elif choice in commodities:
                selected = commodities[choice]
                print(f"✅ Selected: {selected}")
                return selected
            else:
                print("❌ Invalid choice. Please enter 1-8.")
        except KeyboardInterrupt:
            print("\n✅ Using default: SILVERMIC")
            return "SILVERMIC"

MCX_NAME = select_mcx_commodity()
AI_ATM_WINDOW = 3  # AI uses ATM ±3 for context
MAX_TICK_POINTS = 2000
OI_MAX_POINTS = 100
MAX_AI_SERIES_POINTS = 50
SNAPSHOT_INTERVAL_SECS = 180  # 3 minutes for rich AI analysis
COACH_INTERVAL_SECS = 1  # 1 second for minimal AI analysis

# ====== API Authentication ======
ANGEL_API_KEY = "IF0vWmnY"
ANGEL_USER_ID = "r117172"
ANGEL_PIN = 9029
ANGEL_TOTP_SECRET = "Y4GDOA6SL5VOCKQPFLR5EM3HOY"

obj = SmartConnect(api_key=ANGEL_API_KEY)
user_id = ANGEL_USER_ID
try:
    totp = pyotp.TOTP(ANGEL_TOTP_SECRET).now()
    data = obj.generateSession(user_id, ANGEL_PIN, totp)
except Exception as _auth_e:
    print(f"❌ SmartConnect auth error: {_auth_e}")
    data = {}

# ====== GLOBAL VARIABLES ======
current_expiry = None
current_expiry_short = None
SYMBOL_TO_TOKEN = {}
TOKEN_TO_SYMBOL = {}
nifty_index_token = None
MCX_TOKENS = []  # Filled when FEED_SEGMENT == 'MCX'
NIFTY_FUT_SYMBOL = None
NIFTY_FUT_TOKEN = None
VIX_SYMBOL = None
VIX_TOKEN = None

# ====== CACHE & LOCKS ======
TICKS_CACHE = {}
WS_LOCK = threading.Lock()
HIST_SAMPLER_STOP = threading.Event()

# ====== AI COACH ======
USE_AI_COACH = True
_Ai_MINIMAL_MODEL = "openai/gpt-4o-mini-2024-07-18"  # fast, reliable JSON
_Ai_MINIMAL_FALLBACK = "qwen/qwen-2.5-7b-instruct"
_Ai_RICH_MODEL = "qwen/qwen-2.5-72b-instruct"       # strong reasoning + JSON
_Ai_FALLBACK_RICH_MODEL = "deepseek/deepseek-v3"
_ai_client = None  # Will be initialized after OpenRouterClient class is defined

# ====== THREADING FOR DUAL AI PATTERN ======
_coach_thread = None
_coach_thread_stop = threading.Event()
_snapshot_thread = None
_snapshot_stop = threading.Event()

# ====== TICK HISTORY CLASSES ======
class RollingTicks:
    def __init__(self, max_points=MAX_TICK_POINTS):
        self.max_points = max_points
        self.buf = defaultdict(lambda: deque(maxlen=max_points))
    
    def push(self, sym, ts, ltp, bid=None, ask=None, vol=None):
        self.buf[sym].append({
            "ts": ts, "ltp": ltp, "bid": bid, "ask": ask, "vol": vol
        })
    
    def series(self, sym, last_n=None):
        series = list(self.buf[sym])
        if last_n:
            series = series[-last_n:]
        return series
    
    def latest(self, sym):
        series = self.buf[sym]
        return series[-1] if series else None
    
    def vwap(self, sym, last_secs=300):
        now = time.time()
        recent = [x for x in self.buf[sym] if now - x["ts"] <= last_secs]
        if not recent:
            return None
        total_vol = sum(x.get("vol", 1) for x in recent)
        if total_vol == 0:
            return sum(x["ltp"] for x in recent) / len(recent)
        return sum(x["ltp"] * x.get("vol", 1) for x in recent) / total_vol
    
    def spread_bps(self, sym):
        latest = self.latest(sym)
        if not latest or not latest.get("bid") or not latest.get("ask"):
            return None
        bid, ask = latest["bid"], latest["ask"]
        return ((ask - bid) / bid) * 10000 if bid > 0 else None
    
    def momentum(self, sym, secs=12):
        now = time.time()
        recent = [x for x in self.buf[sym] if now - x["ts"] <= secs]
        if len(recent) < 2:
            return 0.0
        return recent[-1]["ltp"] - recent[0]["ltp"]
    
    def accel(self, sym, secs=12):
        now = time.time()
        recent = [x for x in self.buf[sym] if now - x["ts"] <= secs]
        if len(recent) < 3:
            return 0.0
        return (recent[-1]["ltp"] - recent[-2]["ltp"]) - (recent[-2]["ltp"] - recent[-3]["ltp"])

# ====== OI DATA COMPARISON & HISTORY ======
class OIHistory:
    """Keeps track of OI data history for comparison."""
    def __init__(self, max_points=10):
        self.history = deque(maxlen=max_points)
        self.last_snapshot = None
        self.last_snapshot_time = None
    
    def add_snapshot(self, snapshot_df, timestamp=None):
        """Add a new snapshot to history."""
        if timestamp is None:
            timestamp = datetime.now()
        
        # Store current snapshot
        self.last_snapshot = snapshot_df.copy()
        self.last_snapshot_time = timestamp
        
        # Add to history
        self.history.append({
            'timestamp': timestamp,
            'data': snapshot_df.copy()
        })
    
    def has_significant_changes(self, current_df, min_change_threshold=0.005):
        """Check if current data has significant changes compared to last snapshot."""
        if self.last_snapshot is None or current_df.empty:
            return True  # First run or no previous data
        
        if self.last_snapshot.empty:
            return True
        
        # Create OI maps for comparison
        current_oi_map = {}
        previous_oi_map = {}
        
        for _, row in current_df.iterrows():
            symbol = row.get('symbol', '')
            oi = row.get('oi', 0)
            if symbol and oi > 0:
                current_oi_map[symbol] = oi
        
        for _, row in self.last_snapshot.iterrows():
            symbol = row.get('symbol', '')
            oi = row.get('oi', 0)
            if symbol and oi > 0:
                previous_oi_map[symbol] = oi
        
        # Count changes
        changed_symbols = 0
        total_symbols = len(current_oi_map)
        changes_details = []
        
        for symbol, current_oi in current_oi_map.items():
            previous_oi = previous_oi_map.get(symbol, 0)
            if previous_oi > 0:
                change_pct = abs(current_oi - previous_oi) / previous_oi
                if change_pct >= min_change_threshold:
                    changed_symbols += 1
                    changes_details.append(f"{symbol}: {change_pct:.2%}")
        
        # Consider significant if more than 5% of symbols changed by at least 0.5%
        significant_threshold = max(1, total_symbols * 0.05)
        is_significant = changed_symbols >= significant_threshold
        
        if is_significant:
            print(f"📊 OI Changes detected: {changed_symbols}/{total_symbols} symbols changed")
            if changes_details:
                print(f"   Top changes: {', '.join(changes_details[:5])}")
        
        return is_significant
    
    def get_last_snapshot(self):
        """Get the last snapshot data."""
        return self.last_snapshot
    
    def get_last_snapshot_time(self):
        """Get the last snapshot timestamp."""
        return self.last_snapshot_time

def get_strikes_with_oi_changes(current_df, previous_df):
    """Get symbols that have OI changes."""
    changed_strikes = set()
    if previous_df.empty:
        return set(current_df['symbol'].tolist()) if not current_df.empty else set()
    
    current_oi_map = current_df.set_index('symbol')['oi'].to_dict()
    previous_oi_map = previous_df.set_index('symbol')['oi'].to_dict()
    
    for symbol in current_oi_map:
        current_oi = pd.to_numeric(current_oi_map.get(symbol, 0), errors='coerce')
        previous_oi = pd.to_numeric(previous_oi_map.get(symbol, 0), errors='coerce')
        if pd.notna(current_oi) and pd.notna(previous_oi) and current_oi != previous_oi:
            changed_strikes.add(symbol)
    
    return changed_strikes

# Initialize tick history
TICK_HISTORY = RollingTicks()
OI_HISTORY = OIHistory()

# Global OI history tracker (for backward compatibility)
oi_history = OI_HISTORY

# Forward declarations to prevent "not defined" errors
def _db_conn(): pass
def start_ws_feed(initial=None): pass
def ws_stop(): pass

# ====== WEB SOCKET VARIABLES ======
sws = None
_ws_running = False
_ws_connected = False
_active_tokens = set()

def start_ws_feed(initial=None):
    """Start WebSocket feed."""
    global sws, _ws_running, _ws_connected
    
    try:
        # Get feed token and auth token
        feed_token = obj.getfeedToken()
        auth_token = data.get('data', {}).get('jwtToken', '')
        
        if not feed_token:
            print("❌ No feed token available")
            return
        
        # Create WebSocket with correct parameters
        sws = SmartWebSocketV2(
            auth_token=auth_token,
            api_key=obj.api_key,
            client_code=user_id,
            feed_token=feed_token
        )
        
        # Set up callbacks
        sws.on_data = _on_tick_ws
        sws.on_open = _on_connect_ws
        sws.on_close = _on_close_ws
        sws.on_error = _on_error_ws
        
        _ws_running = True
        
        # Run connection in separate thread
        def _run():
            try:
                sws.connect()
            except Exception as e:
                print(f"WS connect exception: {e}")
            finally:
                global _ws_running, _ws_connected
                _ws_running = False
                _ws_connected = False
        
        threading.Thread(target=_run, name="WS-Runner", daemon=True).start()
        
        # Wait for connection
        t_end = time.time() + 5
        while not _ws_connected and time.time() < t_end:
            time.sleep(0.05)
        
        # Subscribe to initial tokens
        if initial:
            ws_subscribe(initial)
            
        print("✅ WebSocket feed started")
        
    except Exception as e:
        print(f"❌ WebSocket start error: {e}")

def ws_subscribe(tokens):
    """Subscribe to WebSocket feed for given tokens."""
    global sws, _active_tokens
    
    if not tokens or not sws:
        return
    
    new_list = []
    for tok in map(str, tokens):
        if tok not in _active_tokens:
            _active_tokens.add(tok)
            new_list.append(tok)
    
    if not new_list:
        return
    
    # Format for SmartWebSocketV2 API
    token_list = []
    nse_tokens = []
    nfo_tokens = []
    mcx_tokens = []
    
    for tok in new_list:
        sym = TOKEN_TO_SYMBOL.get(tok, "")
        if FEED_SEGMENT == 'MCX':
            mcx_tokens.append(tok)
        else:
            if sym == "NIFTY 50" or tok == str(nifty_index_token):
                nse_tokens.append(tok)
            else:
                nfo_tokens.append(tok)
    
    if mcx_tokens:
        token_list.append({"exchangeType": 5, "tokens": mcx_tokens})  # MCX
    if nse_tokens:
        token_list.append({"exchangeType": 1, "tokens": nse_tokens})  # NSE
    if nfo_tokens:
        token_list.append({"exchangeType": 2, "tokens": nfo_tokens})  # NFO
    
    try:
        # Use positional args as per SDK: subscribe(correlation_id, mode, token_list)
        # mode=1 for LTP (lighter, faster). token_list must contain string tokens.
        correlation_id = f"oi-monitor-{int(time.time())}"
        sws.subscribe(correlation_id, 1, token_list)
        print(f"WS subscribed {len(new_list)} new tokens (total {len(_active_tokens)}) | mode=1 | lists={token_list}")
    except Exception as e:
        print(f"Subscribe failed: {e}")

def ws_refresh_subscription(items):
    """Refresh WebSocket subscription."""
    if not items:
        return
    
    # Convert to tokens
    tokens = []
    for item in items:
        if item in SYMBOL_TO_TOKEN:
            tokens.append(SYMBOL_TO_TOKEN[item])
    
    if tokens:
        ws_subscribe(tokens)

def stop_ws_feed():
    """Stop WebSocket feed."""
    global sws, _ws_running, _ws_connected, _active_tokens
    
    try:
        HIST_SAMPLER_STOP.set()
    except Exception:
        pass
    
    try:
        if sws is not None:
            try:
                if hasattr(sws, 'close_connection'):
                    sws.close_connection()
                elif hasattr(sws, 'close'):
                    sws.close()
                elif hasattr(sws, 'disconnect'):
                    sws.disconnect()
            except Exception as e:
                print(f"WS close error: {e}")
    finally:
        _active_tokens = set()
        sws = None
        _ws_running = False
        _ws_connected = False
        print("🛑 WebSocket feed stopped")

def _on_tick_ws(wsapp, message):
    """WebSocket tick data handler. Supports dict or JSON string payloads."""
    try:
        payload = message
        if isinstance(message, (bytes, str)):
            try:
                payload = json.loads(message)
            except Exception:
                # If not JSON, ignore
                return

        def extract_ltp(entry: dict):
            raw = (
                entry.get('last_traded_price')
                or entry.get('ltp')
                or entry.get('lastTradedPrice')
                or entry.get('lastTradePrice')
                or entry.get('lastPrice')
                or entry.get('LTP')
                or entry.get('ap')
                or entry.get('lp')
            )
            if isinstance(raw, (int, float)) and raw > 10000:
                return float(raw) / 100.0
            try:
                return float(raw) if raw is not None else None
            except Exception:
                return None

        def handle_entry(entry: dict):
            token = str(
                entry.get('symbolToken')
                or entry.get('token')
                or entry.get('tk')
                or entry.get('instrument_token')
                or ''
            )
            if not token:
                return
            ltp = extract_ltp(entry)
            bid = entry.get('bestBid') or entry.get('bid') or entry.get('bp') or 0
            ask = entry.get('bestAsk') or entry.get('ask') or entry.get('ap') or 0
            vol = entry.get('volume') or entry.get('vol') or 0
            ts = time.time()

            # Update cache and history; log first few messages when MCX to help debug
            with WS_LOCK:
                sym = TOKEN_TO_SYMBOL.get(token)
                is_index = bool(nifty_index_token and token == str(nifty_index_token))
                if sym:
                    TICKS_CACHE[sym] = {"ltp": ltp, "bid": bid, "ask": ask, "volume": vol, "ts": ts}
                    TICK_HISTORY.push(sym, ts, ltp if ltp is not None else 0.0, float(bid) or 0.0, float(ask) or 0.0, int(vol) or 0)
                # Always maintain NIFTY_SPOT for index token consumers
                if is_index:
                    TICKS_CACHE["NIFTY_SPOT"] = {"ltp": ltp, "bid": bid, "ask": ask, "volume": vol, "ts": ts}
                    TICK_HISTORY.push("NIFTY_SPOT", ts, ltp if ltp is not None else 0.0, float(bid) or 0.0, float(ask) or 0.0, int(vol) or 0)
            try:
                if FEED_SEGMENT == 'MCX' and int(time.time()) % 10 == 0:
                    print(f"🧪 WS tick: token={token} sym={TOKEN_TO_SYMBOL.get(token, 'NA')} ltp={ltp}")
            except Exception:
                pass
        
        # Support different payload container shapes
        if isinstance(payload, dict) and isinstance(payload.get('data'), list):
            for entry in payload.get('data') or []:
                if isinstance(entry, dict):
                    handle_entry(entry)
            return
        if isinstance(payload, list):
            for entry in payload:
                if isinstance(entry, dict):
                    handle_entry(entry)
            return
        if isinstance(payload, dict):
            handle_entry(payload)
            return

    except Exception as e:
        print(f"WebSocket tick parse error: {e}")

def _on_connect_ws(wsapp):
    """WebSocket on connect callback."""
    global _ws_connected
    _ws_connected = True
    print("🔌 WSv2 opened (connected)")

def _on_close_ws(wsapp):
    """WebSocket on close callback (SDK uses single parameter)."""
    global _ws_connected
    _ws_connected = False
    print("🔒 WSv2 closed")

def _on_error_ws(wsapp, error):
    """WebSocket on error callback."""
    print(f"❌ WSv2 error: {error}")

def fetch_greeks(obj, underlying='NIFTY', expiry='14AUG2025'):
    """Fetch Greeks data using optionGreek API."""
    greekParam = {"name": underlying, "expirydate": expiry}
    try:
        greekRes = obj.optionGreek(greekParam)
        
        if greekRes.get('status', False):
            data = greekRes.get('data', [])
            if data:
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
                
                return df_greeks
            else:
                print("❌ No Greeks data in API response")
        else:
            print(f"❌ Greeks API failed: {greekRes.get('message', 'Unknown error')}")
    except Exception as e:
        print(f"❌ Error fetching Greeks: {e}")
    return pd.DataFrame()

def enrich_with_greeks(df: pd.DataFrame) -> pd.DataFrame:
    """Enrich DataFrame with Greeks data."""
    if df.empty:
        return df
    df = df.copy()
    
    # Extract option type and strike from trading symbol
    df['optionType'] = df['symbol'].str.extract(r'(CE|PE)')
    
    # Extract strike from symbol (e.g., NIFTY14AUG2524650CE -> 24650)
    def extract_strike(symbol):
        match = re.search(r'NIFTY\d{2}[A-Z]{3}\d{2}(\d{5})(CE|PE)', symbol)
        return int(match.group(1)) if match else 0
    df['strike'] = df['symbol'].apply(extract_strike)
    
    # Get current expiry for Greeks - use a simple approach to avoid circular dependency
    try:
        # Try to get expiry from global variable first
        if 'current_expiry' in globals() and globals()['current_expiry']:
            current_expiry = globals()['current_expiry']
        else:
            # Fallback: use current date to guess expiry
            current_date = datetime.now()
            # For August 2025, use 07AUG2025 as fallback
            current_expiry = "07AUG25"  # Use known working expiry
        
        # Fix: Convert from 14AUG25 format to 14AUG2025 format properly
        if current_expiry and len(current_expiry) == 7:  # Format: 14AUG25
            expiry_for_greeks = current_expiry[:-2] + '2025'  # Convert 14AUG25 to 14AUG2025
        else:
            expiry_for_greeks = current_expiry  # Use as is if already in correct format
        
        # Fetch Greeks data
        df_greeks = fetch_greeks(obj, 'NIFTY', expiry_for_greeks)
        if not df_greeks.empty:
            # Merge Greeks data
            df = df.merge(df_greeks, on=['strike', 'optionType'], how='left', suffixes=('', '_greeks'))
        else:
            print("❌ No Greeks data available - using fallback values")
    except Exception as e:
        print(f"❌ Error getting expiry for Greeks: {e} - using fallback values")
    
    # Ensure all Greeks columns exist
    for col in ['delta', 'gamma', 'vega', 'theta', 'iv']:
        if col not in df.columns:
            df[col] = 0.0
        else:
            df[col] = df[col].fillna(0.0)
    
    return df

def get_option_chain_snapshot(target_symbols):
    """Get option chain snapshot for PCR calculation with Greeks data."""
    if not target_symbols:
        return pd.DataFrame()
    
    try:
        # Group symbols by exchange
        exchanges = {}
        for sym in target_symbols:
            if sym in SYMBOL_TO_TOKEN:
                tok = SYMBOL_TO_TOKEN[sym]
                if tok.startswith('4'):  # NFO tokens start with 4
                    if 'NFO' not in exchanges:
                        exchanges['NFO'] = []
                    exchanges['NFO'].append(tok)
        
        if not exchanges:
            return pd.DataFrame()
        
        # Get market data
        resp = obj.getMarketData("FULL", exchanges)
        
        # Get the data field
        data_field = resp.get('data', {}) if isinstance(resp, dict) else {}
        
        # Try different data field structures
        raw = None
        if isinstance(data_field, dict):
            raw = data_field.get('fetched', [])
            if not raw:
                raw = data_field.get('data', [])
            if not raw:
                raw = data_field.get('ltpData', [])
        
        if not raw:
            raw = resp.get('data', []) if isinstance(resp, dict) else (resp or [])
        
        rows, ts = [], datetime.now()
        for i, item in enumerate(raw):
            try:
                if isinstance(item, dict):
                    tok = str(item.get('symbolToken') or item.get('token') or item.get('tk') or "")
                    sym = item.get('tradingSymbol', "")  # Use tradingSymbol directly
                    ltp = item.get('ltp') or 0.0
                    bid = item.get('depth', {}).get('buy', [{}])[0].get('price', 0.0) if item.get('depth', {}).get('buy') else 0.0
                    ask = item.get('depth', {}).get('sell', [{}])[0].get('price', 0.0) if item.get('depth', {}).get('sell') else 0.0
                    vol = item.get('tradeVolume') or item.get('volume') or item.get('v') or 0
                    oi  = item.get('opnInterest') or item.get('oi') or item.get('open_interest') or 0
                else:
                    continue
                rows.append([sym, tok, float(ltp), float(bid), float(ask), int(oi), int(vol), ts])
            except Exception as e:
                continue
        
        df = pd.DataFrame(rows, columns=["symbol","token","ltp","bid","ask","oi","volume","ts"])
        
        # Enrich with Greeks data using existing function
        if not df.empty:
            df = enrich_with_greeks(df)
        
        return df
        
    except Exception as e:
        print(f"❌ Snapshot error: {e}")
        return pd.DataFrame()

def compute_pcr_maxpain_support_resistance(snapshot_df):
    """Compute PCR, Max Pain, Support, Resistance from snapshot."""
    if snapshot_df.empty:
        return {"pcr": None, "max_pain": None, "support": [], "resistance": []}
    
    try:
        # Parse symbols and extract CE/PE data
        ces, pes = {}, {}
        
        for idx, r in snapshot_df.iterrows():
            sym = str(r.get("symbol",""))
            # Fix regex pattern to match actual symbol format: NIFTY14AUG2524750CE
            # Pattern: NIFTY + expiry (14AUG25) + strike (24750) + side (CE/PE)
            m = re.search(r"NIFTY(\d{2}[A-Z]{3}\d{2})(\d{5})([CP]E)$", sym)
            
            if not m:
                continue
                
            expiry_part = m.group(1)  # 14AUG25
            strike = int(m.group(2))   # 24750
            side = m.group(3)          # CE or PE
            
            if side == "CE":
                ces[strike] = ces.get(strike, 0) + int(r.get("oi", 0))
            else:
                pes[strike] = pes.get(strike, 0) + int(r.get("oi", 0))
        
        # Calculate PCR
        total_ce_oi = sum(ces.values())
        total_pe_oi = sum(pes.values())
        pcr = total_pe_oi / total_ce_oi if total_ce_oi > 0 else None
        
        # Calculate Max Pain
        max_pain = None
        min_pain = float('inf')
        all_strikes = sorted(set(list(ces.keys()) + list(pes.keys())))
        
        for strike in all_strikes:
            pain = 0
            for s in all_strikes:
                if s < strike:
                    pain += ces.get(s, 0) * (strike - s)
                elif s > strike:
                    pain += pes.get(s, 0) * (s - strike)
            if pain < min_pain:
                min_pain = pain
                max_pain = strike
        
        # Calculate Support/Resistance (top 3 by OI)
        support = sorted(pes.items(), key=lambda x: x[1], reverse=True)[:3]
        resistance = sorted(ces.items(), key=lambda x: x[1], reverse=True)[:3]
        
        return {
            "pcr": pcr,
            "max_pain": max_pain,
            "support": support,
            "resistance": resistance
        }
        
    except Exception as e:
        print(f"❌ PCR calculation error: {e}")
        return {"pcr": None, "max_pain": None, "support": [], "resistance": []}

def _get_tokens_for_symbols(symbols):
    """Get tokens for symbols."""
    toks = []
    for s in symbols or []:
        tok = SYMBOL_TO_TOKEN.get(s) if 'SYMBOL_TO_TOKEN' in globals() else None
        if tok: toks.append(str(tok))
    return toks

# ====== CORE FUNCTIONS ======

def fetch_instruments():
    """Fetch all NIFTY instruments and build token mappings."""
    global SYMBOL_TO_TOKEN, TOKEN_TO_SYMBOL, nifty_index_token, current_expiry, current_expiry_short
    global NIFTY_FUT_SYMBOL, NIFTY_FUT_TOKEN, VIX_SYMBOL, VIX_TOKEN
    global MCX_TOKENS
    
    try:
        # Use the same method as old file - fetch from Angel Broking's JSON
        response = requests.get("https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json")
        if response.ok:
            try:
                df = pd.DataFrame(response.json())
                print(f"✅ Fetched and stored {len(df)} instruments")

                # If MCX mode requested, collect a small watchlist of MCX tokens for streaming
                if FEED_SEGMENT == 'MCX':
                    try:
                        # Prefer futures for specific commodity name
                        df['name_up'] = df['name'].astype(str).str.upper()
                        is_mcx = df['exch_seg'].astype(str).str.upper().eq('MCX')
                        is_target = df['name_up'].eq(MCX_NAME)
                        fut = df[is_mcx & is_target & (df['instrumenttype'] == 'FUTCOM')].copy()
                        # Fallback to spot/COMDTY for same name if futures empty
                        spot = df[is_mcx & is_target & (df['instrumenttype'] == 'COMDTY')].copy()

                        mcx_df = fut if not fut.empty else spot
                        # Sort by expiry nearest if available
                        if 'expiry' in mcx_df.columns:
                            try:
                                mcx_df['exp_dt'] = pd.to_datetime(mcx_df['expiry'], format='%d%b%Y', errors='coerce')
                                mcx_df = mcx_df.sort_values(['exp_dt']).drop(columns=['exp_dt'])
                            except Exception:
                                pass
                        # Take up to 40 contracts
                        mcx_head = mcx_df.head(40)
                        MCX_TOKENS = [str(t) for t in mcx_head['token'].astype(str).tolist()]
                        for _, row in mcx_head.iterrows():
                            token = str(row['token'])
                            symbol = str(row['symbol'])
                            TOKEN_TO_SYMBOL[token] = symbol
                            SYMBOL_TO_TOKEN[symbol] = token
                        preview_cols = [c for c in ['symbol','token','expiry','instrumenttype'] if c in mcx_head.columns]
                        example = mcx_head[preview_cols].head(5).values.tolist()
                        print(f"⛏️ MCX({MCX_NAME}) prepared {len(MCX_TOKENS)} tokens: {example}")
                    except Exception as _mcx_e:
                        print(f"⚠️ MCX list error: {_mcx_e}")
                
                # Check required columns
                required_columns = ['name', 'instrumenttype', 'exch_seg', 'token', 'symbol', 'expiry']
                if not all(col in df.columns for col in required_columns):
                    print(f"⚠️ Warning: Missing columns in instrument_list. Available columns: {df.columns.tolist()}")
                
                # Filter NIFTY options
                nifty_options = df[df['name'] == 'NIFTY'].copy()
                
                if nifty_options.empty:
                    print("⚠️ No NIFTY instruments found")
                    return
                
                # Get current expiry
                current_expiry = get_current_expiry(df)
                if current_expiry:
                    current_expiry_short = current_expiry.replace('-', '')
                    
                    # Filter for current expiry
                    current_options = nifty_options[nifty_options['expiry'] == current_expiry]
                    
                    # If no exact match, try to find the closest expiry
                    if current_options.empty:
                        available_expiries = sorted(nifty_options['expiry'].unique())
                        for exp in available_expiries:
                            if 'AUG' in exp and '25' in exp:
                                current_expiry = exp
                                current_expiry_short = exp.replace('-', '')
                                current_options = nifty_options[nifty_options['expiry'] == current_expiry]
                                break
                    
                    # Build mappings
                    for _, row in current_options.iterrows():
                        symbol = row['symbol']
                        token = str(row['token'])
                        SYMBOL_TO_TOKEN[symbol] = token
                        TOKEN_TO_SYMBOL[token] = symbol
                    
                    # Get NIFTY index token
                    nifty_index_df = df[
                        (df['name'] == 'NIFTY 50') &
                        (df['instrumenttype'] == 'INDEX') &
                        (df['exch_seg'] == 'NSE')
                    ]
                    if not nifty_index_df.empty:
                        nifty_index_token = str(nifty_index_df.iloc[0]['token'])
                        SYMBOL_TO_TOKEN['NIFTY 50'] = nifty_index_token
                        TOKEN_TO_SYMBOL[nifty_index_token] = 'NIFTY 50'
                    else:
                        # Hardcode token and ensure mappings exist
                        nifty_index_token = '99926000'
                        SYMBOL_TO_TOKEN['NIFTY 50'] = nifty_index_token
                        TOKEN_TO_SYMBOL[nifty_index_token] = 'NIFTY 50'
                        print("Used hardcoded NIFTY index token: 99926000")
                    
                    # Detect NIFTY FUT and VIX
                    NIFTY_FUT_SYMBOL, NIFTY_FUT_TOKEN = detect_nifty_current_month_future(df)
                    VIX_SYMBOL, VIX_TOKEN = detect_india_vix_token(df)
                    
                    print(f"✅ Loaded {len(SYMBOL_TO_TOKEN)} symbols, expiry: {current_expiry}")
                else:
                    print("❌ Could not determine current expiry")
                    
            except ValueError as e:
                print(f"❌ Error parsing JSON response: {e}")
        else:
            print(f"❌ Failed to fetch instruments. Status code: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error fetching instruments: {e}")

def get_current_expiry(instrument_df=None, index_name='NIFTY'):
    """Get the current month expiry date."""
    try:
        # Use provided instrument_df or fetch if not provided
        if instrument_df is None:
            # This should not happen in normal flow, but handle gracefully
            print("⚠️ Warning: get_current_expiry called without instrument_df")
            return None
            
        current_time = datetime.now()
        options_df = instrument_df[(instrument_df['name'] == index_name) & (instrument_df['instrumenttype'] == 'OPTIDX')]
        
        if options_df.empty:
            return None
        
        # Get unique expiries and sort
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
        
        # Find Thursday expiry
        for date in expiry_dates:
            if date > current_time and date.weekday() == 3:  # Thursday
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
        
        # Fix: Return the correct format that matches the symbols
        # Use format like "14AUG25" instead of "14AUG2025"
        current_expiry_str = current_expiry.strftime('%d%b%y').upper()  # Changed from %Y to %y
        print(f"📅 Detected current expiry: {current_expiry_str}")
        return current_expiry_str
        
    except Exception as e:
        print(f"❌ Error getting expiry: {e}")
        return None

def _guess_spot_for_mapping():
    """Get current NIFTY spot price for ATM calculation."""
    try:
        # 1) Try from cache first
        with WS_LOCK:
            cache_spot = TICKS_CACHE.get("NIFTY_SPOT", {}).get("ltp", None)
        if cache_spot and float(cache_spot) > 0:
            return float(cache_spot)
    except Exception:
        pass
    
    try:
        # 2) Try live API call
        if nifty_index_token:
            resp = obj.getMarketData("LTP", {"NSE": [nifty_index_token]})
            if resp and 'data' in resp:
                ltp = resp['data'][0].get('ltp', 0)
                if ltp > 0:
                    return float(ltp)
    except Exception:
        pass
    
    try:
        # 3) Try from last known WS spot
        with WS_LOCK:
            last_spot = TICKS_CACHE.get("NIFTY_SPOT", {}).get("ltp", None)
        if last_spot and float(last_spot) > 0:
            print(f"📊 Using last known WS spot: {last_spot}")
            return float(last_spot)
    except Exception:
        pass
    
    # 4) No fallback - throw error
    raise ValueError("❌ Cannot get NIFTY spot price. Check WS connection and 'NIFTY 50' subscription.")

def build_symbol_token_maps():
    """Build symbol to token mappings."""
    fetch_instruments()

# ====== TELEGRAM FUNCTIONS ======

def send_telegram_message(message, parse_mode='Markdown'):
    """Send message to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    
    try:
        import requests
        # Parse chat IDs (comma-separated string)
        chat_ids = [cid.strip() for cid in TELEGRAM_CHAT_ID.split(',')]
        
        success_count = 0
        for chat_id in chat_ids:
            try:
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                data = {
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": parse_mode
                }
                response = requests.post(url, data=data, timeout=10)
                if response.status_code == 200:
                    success_count += 1
                else:
                    print(f"⚠️ Telegram error for chat {chat_id}: {response.status_code}")
            except Exception as e:
                print(f"⚠️ Telegram send error for chat {chat_id}: {e}")
        
        if success_count > 0:
            print(f"✅ Message sent to {success_count}/{len(chat_ids)} Telegram chats")
    except Exception as e:
        print(f"⚠️ Telegram send error: {e}")

def send_telegram_image(image_buffer, caption=""):
    """Send image to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    
    try:
        import requests
        # Parse chat IDs (comma-separated string)
        chat_ids = [cid.strip() for cid in TELEGRAM_CHAT_ID.split(',')]
        
        success_count = 0
        for chat_id in chat_ids:
            try:
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
                files = {'photo': ('image.png', image_buffer, 'image/png')}
                data = {'chat_id': chat_id, 'caption': caption}
                response = requests.post(url, files=files, data=data, timeout=30)
                if response.status_code == 200:
                    success_count += 1
                else:
                    print(f"⚠️ Telegram image error for chat {chat_id}: {response.status_code}")
            except Exception as e:
                print(f"⚠️ Telegram image send error for chat {chat_id}: {e}")
        
        if success_count > 0:
            print(f"✅ Image sent to {success_count}/{len(chat_ids)} Telegram chats")
    except Exception as e:
        print(f"⚠️ Telegram image send error: {e}")

# ====== WEB SOCKET FUNCTIONS ======

def pick_atm_strikes_for_watch(spot: float, window: int = ATM_WINDOW):
    """Pick ATM strikes for monitoring."""
    if not pd.notna(spot) or spot <= 0:
        return []
    
    atm = int(round(spot / 50.0) * 50)
    
    # Fix: Use the correct expiry format that matches the symbols
    # The symbols use format like "NIFTY14AUG2522650CE" (25 for 2025)
    # So we need to convert "14AUG2025" to "14AUG25"
    if current_expiry_short and '2025' in current_expiry_short:
        expiry_format = current_expiry_short.replace('2025', '25')
    else:
        expiry_format = current_expiry_short
    
    desired = set()
    for off in range(-window, window+1):
        strike = atm + off * 50
        ce = f"NIFTY{expiry_format}{int(strike):05d}CE"
        pe = f"NIFTY{expiry_format}{int(strike):05d}PE"
        if ce in SYMBOL_TO_TOKEN: 
            desired.add(ce)
        if pe in SYMBOL_TO_TOKEN: 
            desired.add(pe)
    
    return sorted(desired)

def pick_focused_strikes_for_oi_analysis(spot: float, top_bottom_count: int = 5):
    """Pick top 5, bottom 5, and ATM strike for focused OI analysis (total 11 strikes)."""
    if not pd.notna(spot) or spot <= 0:
        return []
    
    atm = int(round(spot / 50.0) * 50)
    
    # Fix: Use the correct expiry format that matches the symbols
    if current_expiry_short and '2025' in current_expiry_short:
        expiry_format = current_expiry_short.replace('2025', '25')
    else:
        expiry_format = current_expiry_short
    
    desired = set()
    
    # Get bottom 5 strikes (below ATM)
    for off in range(-top_bottom_count, 0):
        strike = atm + off * 50
        ce = f"NIFTY{expiry_format}{int(strike):05d}CE"
        pe = f"NIFTY{expiry_format}{int(strike):05d}PE"
        if ce in SYMBOL_TO_TOKEN: 
            desired.add(ce)
        if pe in SYMBOL_TO_TOKEN: 
            desired.add(pe)
    
    # Get ATM strike
    ce = f"NIFTY{expiry_format}{int(atm):05d}CE"
    pe = f"NIFTY{expiry_format}{int(atm):05d}PE"
    if ce in SYMBOL_TO_TOKEN: 
        desired.add(ce)
    if pe in SYMBOL_TO_TOKEN: 
        desired.add(pe)
    
    # Get top 5 strikes (above ATM)
    for off in range(1, top_bottom_count + 1):
        strike = atm + off * 50
        ce = f"NIFTY{expiry_format}{int(strike):05d}CE"
        pe = f"NIFTY{expiry_format}{int(strike):05d}PE"
        if ce in SYMBOL_TO_TOKEN: 
            desired.add(ce)
        if pe in SYMBOL_TO_TOKEN: 
            desired.add(pe)
    
    return sorted(desired)

def fetch_realtime_ticks_from_ws(symbols):
    """Return a dict {symbol: {ltp,bid,ask,vol,ts}, "NIFTY_SPOT": {...}} using the WS cache."""
    out = {}
    with WS_LOCK:
        if "NIFTY_SPOT" in TICKS_CACHE:
            out["NIFTY_SPOT"] = TICKS_CACHE["NIFTY_SPOT"].copy()
        for s in symbols:
            if s in TICKS_CACHE:
                out[s] = TICKS_CACHE[s].copy()
    return out

# ====== AI COACH ======

class OpenRouterClient:
    def __init__(self, api_key: str = None, default_model: str = "mistralai/mistral-small-3.2-24b-instruct"):
        import os, time, requests
        self.os = os
        self.time = time
        self.requests = requests
        self.api_key = api_key or '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'
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

    def chat(self, model: str, messages: list, temperature: float = 0.2, max_tokens: int | None = None):
        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": float(temperature)
        }
        if max_tokens is not None:
            payload["max_tokens"] = int(max_tokens)
        
        # Store the complete API request for logging
        api_request = {
            "url": self.base_url,
            "headers": {"Authorization": f"Bearer {self.api_key[:10]}..." if self.api_key else "No API Key"},
            "payload": payload
        }
        
        resp = self._request(payload)
        if not resp:
            return {"content": "", "api_request": api_request}
        try:
            content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception:
            content = ""
        return {"content": content, "api_request": api_request}

# Initialize AI client after class definition
try:
    _ai_client = OpenRouterClient(api_key='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')
except Exception as _e:
    print(f"⚠️ OpenRouterClient not available: {_e}")
    _ai_client = None
    USE_AI_COACH = False

def ai_trade_coach(context: dict) -> dict:
    """AI trade coach with compact context."""
    if not USE_AI_COACH or not _ai_client:
        return {}
    
    try:
        # Compact context for faster processing
        spot = context.get("spot", 0)
        pcr = context.get("pcr")
        ce_series = context.get("ce_series", {})
        pe_series = context.get("pe_series", {})
        levels = context.get("levels", {})
        
        # Get additional market data for better analysis
        current_time = datetime.now().strftime("%H:%M:%S")
        
        # Get recent tick data for momentum analysis
        recent_ce_ticks = TICK_HISTORY.series("NIFTY_CE", 5) if 'TICK_HISTORY' in globals() else []
        recent_pe_ticks = TICK_HISTORY.series("NIFTY_PE", 5) if 'TICK_HISTORY' in globals() else []
        
        # Calculate momentum
        ce_momentum = "NEUTRAL"
        pe_momentum = "NEUTRAL"
        if len(recent_ce_ticks) >= 2:
            ce_change = recent_ce_ticks[-1].get("ltp", 0) - recent_ce_ticks[0].get("ltp", 0)
            ce_momentum = "UP" if ce_change > 0 else "DOWN" if ce_change < 0 else "NEUTRAL"
        
        if len(recent_pe_ticks) >= 2:
            pe_change = recent_pe_ticks[-1].get("ltp", 0) - recent_pe_ticks[0].get("ltp", 0)
            pe_momentum = "UP" if pe_change > 0 else "DOWN" if pe_change < 0 else "NEUTRAL"
        
        # Build more detailed prompt based on available data
        if pcr is not None:
            # PCR is available - provide specific guidance
            if pcr > 1.2:
                pcr_analysis = f"PCR is {pcr:.2f} (bearish - puts > calls). Consider PUT options or wait for reversal."
            elif pcr < 0.8:
                pcr_analysis = f"PCR is {pcr:.2f} (bullish - calls > puts). Consider CALL options or wait for reversal."
            else:
                pcr_analysis = f"PCR is {pcr:.2f} (neutral). Monitor for breakout."
        else:
            pcr_analysis = "PCR data unavailable. Using technical analysis only."
        
        # Build structured payload with history
        structured = build_ai_payload({
            "spot": spot,
            "pcr": pcr,
            "levels": levels,
            "support": context.get("support", []),
            "resistance": context.get("resistance", []),
            "max_pain": context.get("max_pain")
        }, ce_series, pe_series, include_ticks=True, include_oi_history=True)

        prompt = (
            "[MINIMAL]\n"
            "You are an Indian NIFTY index options scalper BUYER with 20+ years of experience. \n"
            "You must ONLY suggest long options (CALL or PUT buying). Never suggest selling, shorting, credit strategies, short straddles/strangles, or spreads. If nothing qualifies, set decision=WAIT and entry_ok=false.\n"
            "Return ONLY a JSON object with keys: decision, side, strike, entry_ok, stop_loss, target, reason, confidence. No extra text.\n\n"
            f"Market Context ({current_time}):\n"
            f"- NIFTY Spot: {spot}\n"
            f"- PCR: {pcr_analysis}\n"
            f"- CE Momentum: {ce_momentum} ({len(recent_ce_ticks)} ticks)\n"
            f"- PE Momentum: {pe_momentum} ({len(recent_pe_ticks)} ticks)\n"
            f"- CE Series: {len(ce_series)} strikes\n"
            f"- PE Series: {len(pe_series)} strikes\n"
            f"- Support/Resistance: {len(levels)} levels\n\n"
            f"Structured Data (ticks, OI history, top symbols):\n{json.dumps(structured, indent=2)[:4000]}\n\n"
            "Respond with pure JSON only."
        )
        
        # Debug: Show data size being sent to AI
        prompt_size = len(prompt)
        ce_strikes = list(ce_series.keys()) if ce_series else []
        pe_strikes = list(pe_series.keys()) if pe_series else []
        
        resp = _ai_client.chat(
            model=_Ai_MINIMAL_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=400
        )
        
        msg = resp.get("content", "") if isinstance(resp, dict) else str(resp)
        api_request = resp.get("api_request", {}) if isinstance(resp, dict) else {}
        
        # Log the AI interaction
        context_summary = log_context_summary(context)
        log_ai_interaction("minimal", prompt, msg, context_summary, api_request)
        
        # Parse strict JSON
        decision = "WAIT"; direction = "NEUTRAL"; parsed = None
        try:
            parsed = json.loads(msg)
        except Exception:
            parsed = None
        if isinstance(parsed, dict):
            decision = str(parsed.get("decision", "WAIT")).upper()
            direction = str(parsed.get("side", "NEUTRAL")).upper()
            strike = parsed.get("strike")
            sl = parsed.get("stop_loss")
            tgt = parsed.get("target")
            note = parsed.get("reason", "")
            entry_ok = bool(parsed.get("entry_ok", False))
            # Enforce buyer-only constraints
            forbidden = False
            forbidden_words = ["SHORT", "STRADDLE", "STRANGLE", "CREDIT", "SELL", "SPREAD"]
            for w in forbidden_words:
                if w in str(parsed.get("strategy", "")).upper() or w in note.upper():
                    forbidden = True; break
            if decision == "ENTER" and (direction not in ("CALL", "PUT") or forbidden or not entry_ok):
                decision = "WAIT"; direction = "NEUTRAL";
                note = "WAIT (buyer-only constraint; rejecting short/credit/non-CALL/PUT)"
        else:
            note = msg

        # Micro-gates (spread/momentum recency). Default to WAIT if gates fail
        gated_reason = None
        spot_mom = TICK_HISTORY.momentum("NIFTY_SPOT", secs=12) if 'TICK_HISTORY' in globals() else 0.0
        if abs(spot_mom) < 6:
            gated_reason = f"WAIT (weak momentum {spot_mom:.1f})"
        # If we had symbol tick spreads, we could gate further; for now momentum gate
        if gated_reason:
            decision = "WAIT"; direction = "NEUTRAL"; note = gated_reason

        _log_decision_row(ts=time.time(), decision=decision, side=direction, strike=strike if 'strike' in locals() else None, sl=sl if 'sl' in locals() else None, tgt=tgt if 'tgt' in locals() else None, reason=note, source="minimal")
        return {"coach": decision, "direction": direction, "note": note}
        
    except Exception as e:
        print(f"AI coach error: {e}")
        return {"coach": "WAIT", "direction": "NEUTRAL", "note": "AI error"}

def ai_trade_coach_rich(context: dict = None) -> dict:
    """AI trade coach with rich context."""
    if not USE_AI_COACH or not _ai_client:
        return {}
    
    try:
        # Use provided context or get rich context data
        if context:
            spot = context.get("spot", 0)
            pcr = context.get("pcr")
            max_pain = context.get("max_pain")
            support = context.get("support", [])
            resistance = context.get("resistance", [])
            ce_series = context.get("ce_series", {})
            pe_series = context.get("pe_series", {})
            snapshot = context.get("snapshot", pd.DataFrame())
        else:
            # Fallback to getting data directly
            spot = _guess_spot_for_mapping()
            ce_series = TICK_HISTORY.series("NIFTY_CE", 10)
            pe_series = TICK_HISTORY.series("NIFTY_PE", 10)
            oi_history = OI_HISTORY.last("NIFTY", 10)
            
            # Get current PCR and market analysis
            symbols = pick_atm_strikes_for_watch(spot, 10) if spot else []
            snapshot = get_option_chain_snapshot(symbols) if symbols else pd.DataFrame()
            market_analysis = compute_pcr_maxpain_support_resistance(snapshot) if not snapshot.empty else {}
            
            pcr = market_analysis.get("pcr")
            max_pain = market_analysis.get("max_pain")
            support = market_analysis.get("support", [])
            resistance = market_analysis.get("resistance", [])
        
        # Calculate momentum and volatility
        ce_momentum = "NEUTRAL"
        pe_momentum = "NEUTRAL"
        
        if isinstance(ce_series, list) and len(ce_series) >= 2:
            ce_change = ce_series[-1].get("ltp", 0) - ce_series[0].get("ltp", 0)
            ce_momentum = "UP" if ce_change > 0 else "DOWN" if ce_change < 0 else "NEUTRAL"
        elif isinstance(ce_series, dict) and ce_series:
            ce_momentum = "ACTIVE" if len(ce_series) > 0 else "NEUTRAL"
        
        if isinstance(pe_series, list) and len(pe_series) >= 2:
            pe_change = pe_series[-1].get("ltp", 0) - pe_series[0].get("ltp", 0)
            pe_momentum = "UP" if pe_change > 0 else "DOWN" if pe_change < 0 else "NEUTRAL"
        elif isinstance(pe_series, dict) and pe_series:
            pe_momentum = "ACTIVE" if len(pe_series) > 0 else "NEUTRAL"
        
        # Build comprehensive analysis
        pcr_str = f"{pcr:.2f}" if pcr is not None else "N/A"
        analysis = f"NIFTY Spot: {spot}\n"
        analysis += f"PCR: {pcr_str}\n"
        analysis += f"Max Pain: {max_pain if max_pain else 'N/A'}\n"
        analysis += f"CE Series: {len(ce_series) if isinstance(ce_series, dict) else 0} strikes\n"
        analysis += f"PE Series: {len(pe_series) if isinstance(pe_series, dict) else 0} strikes\n"
        analysis += f"Support Levels: {len(support)} (Top: {support[0] if support else 'N/A'})\n"
        analysis += f"Resistance Levels: {len(resistance)} (Top: {resistance[0] if resistance else 'N/A'})\n"
        analysis += f"Option Chain: {len(snapshot)} strikes\n"
        
        # Build structured payload with history
        structured = build_ai_payload({
            "spot": spot,
            "pcr": pcr,
            "support": support,
            "resistance": resistance,
            "max_pain": max_pain
        }, ce_series if isinstance(ce_series, dict) else {}, pe_series if isinstance(pe_series, dict) else {}, include_ticks=True, include_oi_history=True)

        prompt = (
            "[RICH]\n"
            "You are an Indian NIFTY index options scalper BUYER with 20+ years of experience and access to rich market data.\n"
            "You must ONLY suggest long options (CALL or PUT buying). Never suggest selling, shorting, credit strategies, short straddles/strangles, or spreads. If nothing qualifies, set decision=WAIT and entry_ok=false.\n"
            "Return ONLY a JSON object with keys: decision, side, strike, entry_ok, stop_loss, target, reason, confidence, strategy, risk. No extra text.\n\n"
            f"Market Analysis:\n"
            f"NIFTY Spot: {spot}\n"
            f"PCR: {pcr_str}\n"
            f"Max Pain: {max_pain if max_pain else 'N/A'}\n"
            f"CE Series: {len(ce_series) if isinstance(ce_series, dict) else 0} strikes\n"
            f"PE Series: {len(pe_series) if isinstance(pe_series, dict) else 0} strikes\n"
            f"Support Levels: {len(support)} (Top: {support[0] if support else 'N/A'})\n"
            f"Resistance Levels: {len(resistance)} (Top: {resistance[0] if resistance else 'N/A'})\n"
            f"Option Chain: {len(snapshot)} strikes\n\n"
            f"Structured Data (ticks, OI history, top symbols):\n{json.dumps(structured, indent=2)[:8000]}\n\n"
            "Respond with pure JSON only."
        )
        
        # Debug: Show data size being sent to AI
        prompt_size = len(prompt)
        
        resp = _ai_client.chat(
            model=_Ai_RICH_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=800
        )
        
        msg = resp.get("content", "") if isinstance(resp, dict) else str(resp)
        api_request = resp.get("api_request", {}) if isinstance(resp, dict) else {}
        
        # Log the AI interaction
        context_summary = log_context_summary(context)
        log_ai_interaction("rich", prompt, msg, context_summary, api_request)
        
        # Parse strict JSON
        decision = "WAIT"; direction = "NEUTRAL"; strategy = "MONITOR"; risk = "LOW"; note = msg; strike=None; sl=None; tgt=None
        try:
            parsed = json.loads(msg)
            decision = str(parsed.get("decision", "WAIT")).upper()
            direction = str(parsed.get("side", "NEUTRAL")).upper()
            strategy = parsed.get("strategy", strategy)
            risk = str(parsed.get("risk", risk)).upper()
            strike = parsed.get("strike")
            sl = parsed.get("stop_loss")
            tgt = parsed.get("target")
            note = parsed.get("reason", note)
            entry_ok = bool(parsed.get("entry_ok", False))
            forbidden = False
            forbidden_words = ["SHORT", "STRADDLE", "STRANGLE", "CREDIT", "SELL", "SPREAD"]
            for w in forbidden_words:
                if w in str(strategy).upper() or w in note.upper():
                    forbidden = True; break
            if decision == "ENTER" and (direction not in ("CALL", "PUT") or forbidden or not entry_ok):
                decision = "WAIT"; direction = "NEUTRAL"; strategy = "MONITOR"; risk = "LOW";
                note = "WAIT (buyer-only constraint; rejecting short/credit/non-CALL/PUT)"
        except Exception:
            pass
        _log_decision_row(ts=time.time(), decision=decision, side=direction, strike=strike, sl=sl, tgt=tgt, reason=note, source="rich")
        return {"coach": decision, "direction": direction, "strategy": strategy, "risk": risk, "note": note}
        
    except Exception as e:
        print(f"AI coach error: {e}")
        return {"coach": "WAIT", "direction": "NEUTRAL", "strategy": "MONITOR", "risk": "LOW", "note": "AI error"}

# ====== POSITION COACH ======

class PositionCoach:
    def __init__(self):
        self.last_signal = None
        self.last_signal_time = 0
        self.last_signal_strength = None
        self.last_signal_reason = None

    def push_tick(self, ticks: dict):
        """Update with latest ticks."""
        pass

    def _mom(self, sym, n):
        """Calculate momentum for symbol."""
        return 0.0

    def _accel(self, sym, n):
        """Calculate acceleration for symbol."""
        return 0.0

    def _spread_ok(self, sym):
        """Check if spread is acceptable."""
        return True

    def _last_price(self, sym):
        """Get last price for symbol."""
        return 0.0

    def _spot_dir(self):
        """Get spot direction."""
        return 0

    def _best_candidate(self, watch_syms):
        """Find best trading candidate."""
        return None

    def decide(self, market_analysis, open_positions, watch_syms, ticks):
        """Make trading decision."""
        # Simple decision logic
        spot = _guess_spot_for_mapping()
        if not spot:
            return {"signal": "WAIT", "strength": "LOW", "reason": "No spot data"}
        
        # Get AI hint
        ai_hint = ai_trade_coach({
            "spot": spot,
            "pcr": market_analysis.get("pcr"),
            "ce_series": {},
            "pe_series": {},
            "levels": market_analysis.get("levels", {})
        })
        
        decision = ai_hint.get("coach", "WAIT")
        direction = ai_hint.get("direction", "NEUTRAL")
        note = ai_hint.get("note", "AI analysis")
        
        return {
            "signal": decision,
            "strength": "MODERATE",
            "reason": note,
            "context_for_ai": {"spot": spot}
        }

    # Back-compat wrapper
    def analyze(self, spot, ticks, positions, ai_hint):
        """Backwards-compat wrapper."""
        decision = self.decide(
            market_analysis={},
            open_positions=positions,
            watch_syms=[],
            ticks=ticks
        ) or {}
        
        advice = decision.get("signal", "WAIT")
        note = decision.get("reason", "")
        
        # Set attributes expected by main loop
        self.last_signal = advice
        self.last_signal_time = time.time()
        self.last_signal_strength = decision.get("strength", "LOW")
        self.last_signal_reason = note
        
        return (advice, note)

# ====== OI ANALYSIS FUNCTIONS ======

def analyze_oi_change_pattern(oi_change_pct, price_change_pct, option_type, absolute_oi_change=0):
    """Enhanced OI analysis with improved thresholds and confidence scoring."""
    if (abs(oi_change_pct) < 2.0 or abs(price_change_pct) < 1.0 or absolute_oi_change < 50):
        return "Neutral", 0, 0, 0

    def get_strength_score(oi_change, price_change):
        oi_score = 0
        price_score = 0
        if abs(oi_change) >= 20: oi_score = 4
        elif abs(oi_change) >= 10: oi_score = 3
        elif abs(oi_change) >= 5: oi_score = 2
        elif abs(oi_change) >= 2: oi_score = 1

        if abs(price_change) >= 10: price_score = 4
        elif abs(price_change) >= 5: price_score = 3
        elif abs(price_change) >= 2.5: price_score = 2
        elif abs(price_change) >= 1: price_score = 1
        return (oi_score + price_score) / 2

    strength = get_strength_score(oi_change_pct, price_change_pct)
    confidence = min(strength * 20 + (absolute_oi_change / 50) * 10, 100)
    volume_multiplier = 2.0 if absolute_oi_change >= 500 else 1.5 if absolute_oi_change >= 100 else 1.0

    if option_type == "CE":
        if oi_change_pct > 0 and price_change_pct > 0:
            return "Call Long Buildup", 1.5 * volume_multiplier, strength, confidence
        elif oi_change_pct > 0 and price_change_pct < 0:
            return "Call Short Buildup", -2.0 * volume_multiplier, strength, confidence
        elif oi_change_pct < 0 and price_change_pct > 0:
            return "Call Short Covering", 2.5 * volume_multiplier, strength, confidence
        elif oi_change_pct < 0 and price_change_pct < 0:
            return "Call Long Unwinding", -1.0 * volume_multiplier, strength, confidence
    elif option_type == "PE":
        if oi_change_pct > 0 and price_change_pct > 0:
            return "Put Long Buildup", -1.5 * volume_multiplier, strength, confidence
        elif oi_change_pct > 0 and price_change_pct < 0:
            return "Put Short Buildup", 2.0 * volume_multiplier, strength, confidence
        elif oi_change_pct < 0 and price_change_pct > 0:
            return "Put Short Covering", -2.5 * volume_multiplier, strength, confidence
        elif oi_change_pct < 0 and price_change_pct < 0:
            return "Put Long Unwinding", 1.0 * volume_multiplier, strength, confidence

    return "Neutral", 0, 0, 0

def calculate_strike_verdict_new(row):
    """Calculate verdict for each strike based on OI and price changes."""
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

def calculate_comprehensive_market_direction(merged_df):
    """Calculate market direction with improved confidence weighting."""
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

def calculate_max_pain(merged_df):
    """Calculate max pain strike."""
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

def generate_trading_signal(merged_df, market_analysis):
    """Generate trading signals based on market analysis."""
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

def format_pct(val):
    """Format percentage values."""
    if pd.isna(val):
        return " 0.0"
    elif val > 0:
        return f"+{val:5.1f}"
    elif val < 0:
        return f"{val:6.1f}"
    else:
        return f" 0.0"

def create_enhanced_caption(label, changed_count, market_analysis, trading_signals):
    """Create enhanced caption for Telegram images."""
    # Remove emojis from label to avoid font issues
    clean_label = label.replace('🔄', '').replace('📊', '').replace('🎯', '').strip()
    final_icon = "[BULL]" if "BULLISH" in market_analysis.get('direction','') else "[BEAR]" if "BEARISH" in market_analysis.get('direction','') else "[NEUT]"
    confidence_level = market_analysis.get('confidence_factor',0)
    caption = f"{clean_label[:50]}"
    if changed_count > 0:
        caption += f"\n{changed_count} strikes updated"
    caption += f"\n{final_icon} {market_analysis.get('direction','')[:20]} ({confidence_level:.0f}%)"
    caption += f"\n{market_analysis.get('dominant_side','')}: {max(market_analysis.get('bullish_pct',0), market_analysis.get('bearish_pct',0)):.1f}%"
    caption += f"\nPCR: {market_analysis.get('pcr',0):.2f} | Max Pain: {market_analysis.get('max_pain',0)}"
    if trading_signals:
        caption += "\nSignals: "
        for signal in trading_signals[:1]:
            action_icon = "[BUY]" if signal['action'] == 'BUY' else "[SELL]"
            caption += f"{action_icon}{signal['action']}"
    return caption[:1000]

def create_improved_table_image(merged_df, market_analysis, label="OI Analysis", changed_count=0):
    """Create improved table image for Telegram."""
    plt.style.use('default')
    plt.rcParams.update({
        'font.family': ['DejaVu Sans', 'Arial', 'sans-serif'],
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
    # Remove emoji from label to avoid font issues
    clean_label = label.replace('🔄', '').replace('📊', '').replace('🎯', '').strip()
    title = f"{clean_label} - {datetime.now().strftime('%H:%M:%S')}"
    if changed_count > 0:
        title += f"\n{changed_count} strikes with OI changes detected"
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

    headers = ['Theta', 'Delta', 'Cls Chg%', 'OI Chg%', 'Prev Close', 'Curr Close', 'Prev OI', 'Curr OI',
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

        # Convert OI values to lakhs for display
        prev_oi_call_lakhs = row.get('prev_oi_call', 0) / 100000
        curr_oi_call_lakhs = row.get('opnInterest_call', 0) / 100000
        prev_oi_put_lakhs = row.get('prev_oi_put', 0) / 100000
        curr_oi_put_lakhs = row.get('opnInterest_put', 0) / 100000
        
        row_data = [
            f"{row.get('theta_call', 0):.2f}",
            f"{row.get('delta_call', 0):.2f}",
            format_pct(row.get('cls_chg_pct_call', 0)),
            format_pct(row.get('oi_chg_pct_call', 0)),
            f"{row.get('prev_close_call', 0):.1f}",
            f"{row.get('close_call', 0):.1f}",
            f"{prev_oi_call_lakhs:.1f}",
            f"{curr_oi_call_lakhs:.1f}",
            f"{int(row['strike'])}",
            f"{curr_oi_put_lakhs:.1f}",
            f"{prev_oi_put_lakhs:.1f}",
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
            elif j in [0, 1, 13, 14, 16, 17]:  # Theta, Delta, OI Chg%, Cls Chg% for both sides
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

    # Use constrained_layout instead of tight_layout for gridspec compatibility
    plt.subplots_adjust(left=0.02, right=0.98, top=0.95, bottom=0.02)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight', facecolor='black', edgecolor='none')
    buf.seek(0)
    plt.close()
    return buf

def merge_current_previous_data(current_df, previous_df):
    """Merge current and previous data for analysis with Greeks data."""
    if current_df.empty:
        return pd.DataFrame()
    
    try:
        # Parse symbols to extract strike and side information
        parsed_data = []
        
        for _, row in current_df.iterrows():
            symbol = str(row.get('symbol', ''))
            m = re.search(r"NIFTY(\d{2}[A-Z]{3}\d{2})(\d{5})([CP]E)$", symbol)
            
            if not m:
                continue
                
            expiry_part = m.group(1)  # 14AUG25
            strike = int(m.group(2))   # 24750
            side = m.group(3)          # CE or PE
            
            # Get current data
            current_ltp = row.get('ltp', 0.0)
            current_oi = row.get('oi', 0)
            current_volume = row.get('volume', 0)
            current_delta = row.get('delta', 0.0)
            current_theta = row.get('theta', 0.0)
            
            # Find corresponding previous data
            prev_row = previous_df[previous_df['symbol'] == symbol]
            prev_ltp = prev_row['ltp'].iloc[0] if not prev_row.empty else current_ltp
            prev_oi = prev_row['oi'].iloc[0] if not prev_row.empty else current_oi
            prev_volume = prev_row['volume'].iloc[0] if not prev_row.empty else current_volume
            prev_delta = prev_row['delta'].iloc[0] if not prev_row.empty else current_delta
            prev_theta = prev_row['theta'].iloc[0] if not prev_row.empty else current_theta
            
            # Calculate changes
            ltp_change_pct = ((current_ltp - prev_ltp) / prev_ltp * 100) if prev_ltp > 0 else 0
            oi_change_pct = ((current_oi - prev_oi) / prev_oi * 100) if prev_oi > 0 else 0
            volume_change_pct = ((current_volume - prev_volume) / prev_volume * 100) if prev_volume > 0 else 0
            delta_change = current_delta - prev_delta
            theta_change = current_theta - prev_theta
            
            parsed_data.append({
                'symbol': symbol,
                'strike': strike,
                'side': side,
                'expiry': expiry_part,
                'current_ltp': current_ltp,
                'current_oi': current_oi,
                'current_volume': current_volume,
                'current_delta': current_delta,
                'current_theta': current_theta,
                'prev_ltp': prev_ltp,
                'prev_oi': prev_oi,
                'prev_volume': prev_volume,
                'prev_delta': prev_delta,
                'prev_theta': prev_theta,
                'ltp_change_pct': ltp_change_pct,
                'oi_change_pct': oi_change_pct,
                'volume_change_pct': volume_change_pct,
                'delta_change': delta_change,
                'theta_change': theta_change
            })
        
        if not parsed_data:
            return pd.DataFrame()
        
        # Convert to DataFrame
        merged_df = pd.DataFrame(parsed_data)
        
        # Pivot to get CE and PE data side by side
        ce_data = merged_df[merged_df['side'] == 'CE'].copy()
        pe_data = merged_df[merged_df['side'] == 'PE'].copy()
        
        # Merge CE and PE data by strike
        final_data = []
        all_strikes = sorted(set(ce_data['strike'].tolist() + pe_data['strike'].tolist()))
        
        for strike in all_strikes:
            ce_row = ce_data[ce_data['strike'] == strike]
            pe_row = pe_data[pe_data['strike'] == strike]
            
            row_data = {'strike': strike}
            
            # CE data
            if not ce_row.empty:
                ce = ce_row.iloc[0]
                row_data.update({
                    'close_call': ce['current_ltp'],
                    'prev_close_call': ce['prev_ltp'],
                    'opnInterest_call': ce['current_oi'],
                    'prev_oi_call': ce['prev_oi'],
                    'volume_call': ce['current_volume'],
                    'prev_volume_call': ce['prev_volume'],
                    'cls_chg_pct_call': ce['ltp_change_pct'],
                    'oi_chg_pct_call': ce['oi_change_pct'],
                    'volume_chg_pct_call': ce['volume_change_pct'],
                    'delta_call': ce['current_delta'],
                    'prev_delta_call': ce['prev_delta'],
                    'theta_call': ce['current_theta'],
                    'prev_theta_call': ce['prev_theta'],
                    'delta_change_call': ce['delta_change'],
                    'theta_change_call': ce['theta_change']
                })
            else:
                row_data.update({
                    'close_call': 0, 'prev_close_call': 0, 'opnInterest_call': 0, 'prev_oi_call': 0,
                    'volume_call': 0, 'prev_volume_call': 0, 'cls_chg_pct_call': 0, 'oi_chg_pct_call': 0,
                    'volume_chg_pct_call': 0, 'delta_call': 0, 'prev_delta_call': 0, 'theta_call': 0,
                    'prev_theta_call': 0, 'delta_change_call': 0, 'theta_change_call': 0
                })
            
            # PE data
            if not pe_row.empty:
                pe = pe_row.iloc[0]
                row_data.update({
                    'close_put': pe['current_ltp'],
                    'prev_close_put': pe['prev_ltp'],
                    'opnInterest_put': pe['current_oi'],
                    'prev_oi_put': pe['prev_oi'],
                    'volume_put': pe['current_volume'],
                    'prev_volume_put': pe['prev_volume'],
                    'cls_chg_pct_put': pe['ltp_change_pct'],
                    'oi_chg_pct_put': pe['oi_change_pct'],
                    'volume_chg_pct_put': pe['volume_change_pct'],
                    'delta_put': pe['current_delta'],
                    'prev_delta_put': pe['prev_delta'],
                    'theta_put': pe['current_theta'],
                    'prev_theta_put': pe['prev_theta'],
                    'delta_change_put': pe['delta_change'],
                    'theta_change_put': pe['theta_change']
                })
            else:
                row_data.update({
                    'close_put': 0, 'prev_close_put': 0, 'opnInterest_put': 0, 'prev_oi_put': 0,
                    'volume_put': 0, 'prev_volume_put': 0, 'cls_chg_pct_put': 0, 'oi_chg_pct_put': 0,
                    'volume_chg_pct_put': 0, 'delta_put': 0, 'prev_delta_put': 0, 'theta_put': 0,
                    'prev_theta_put': 0, 'delta_change_put': 0, 'theta_change_put': 0
                })
            
            final_data.append(row_data)
        
        result_df = pd.DataFrame(final_data)
        
        # Calculate verdicts for each strike
        result_df['verdict'] = result_df.apply(calculate_strike_verdict_new, axis=1)
        
        return result_df
        
    except Exception as e:
        print(f"❌ Merge data error: {e}")
        return pd.DataFrame()

def format_table_output_improved(current_df, previous_df, label="OI Analysis", changed_count=0, send_to_telegram=False):
    """Format OI analysis table with improved layout and Greeks data."""
    if current_df.empty:
        print("❌ No current data available for table formatting")
        return
    
    try:
        # Merge current and previous data
        merged_df = merge_current_previous_data(current_df, previous_df)
        
        if merged_df.empty:
            print("❌ No merged data available for table formatting")
            return
        
        # Calculate market analysis
        market_analysis = compute_pcr_maxpain_support_resistance(current_df)
        
        # Generate console output
        print("\n" + "=" * 120)
        print(f"📊 {label} - {len(merged_df)} strikes analyzed")
        print("=" * 120)
        
        # Market summary
        direction = market_analysis.get('direction', 'NEUTRAL')
        pcr = market_analysis.get('pcr', 0)
        max_pain = market_analysis.get('max_pain', 0)
        
        print(f"Market Direction: {direction} | PCR: {pcr:.2f} | Max Pain: {max_pain}")
        print("-" * 120)
        
        # Header with proper column order
        header = (f"{'Theta':>6} | {'Delta':>6} | {'Cls Chg%':>8} | {'OI Chg%':>8} | {'Prev Close':>12} | {'Curr Close':>12} | "
                  f"{'Prev OI':>10} | {'Curr OI':>10} || {'Strike':^7} || "
                  f"{'Curr OI':>10} | {'Prev OI':>10} | {'Curr Close':>12} | {'Prev Close':>12} | "
                  f"{'OI Chg%':>8} | {'Cls Chg%':>8} | {'Delta':>6} | {'Theta':>6} | {'Verdict':>25}")
        print(header)
        print("-" * 120)
        
        # Data rows
        for _, row in merged_df.iterrows():
            strike = int(row['strike'])
            
            # Format verdict
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
            
            # Format row with Greeks data and OI in lakhs
            prev_oi_call_lakhs = row.get('prev_oi_call', 0) / 100000
            curr_oi_call_lakhs = row.get('opnInterest_call', 0) / 100000
            prev_oi_put_lakhs = row.get('prev_oi_put', 0) / 100000
            curr_oi_put_lakhs = row.get('opnInterest_put', 0) / 100000
            
            row_str = (f"{row.get('theta_call', 0):>6.2f} | {row.get('delta_call', 0):>6.2f} | "
                      f"{format_pct(row.get('cls_chg_pct_call', 0)):>8} | {format_pct(row.get('oi_chg_pct_call', 0)):>8} | "
                      f"{row.get('prev_close_call', 0):>12.1f} | {row.get('close_call', 0):>12.1f} | "
                      f"{prev_oi_call_lakhs:>10.1f} | {curr_oi_call_lakhs:>10.1f} || "
                      f"{strike:^7} || "
                      f"{curr_oi_put_lakhs:>10.1f} | {prev_oi_put_lakhs:>10.1f} | "
                      f"{row.get('close_put', 0):>12.1f} | {row.get('prev_close_put', 0):>12.1f} | "
                      f"{format_pct(row.get('oi_chg_pct_put', 0)):>8} | {format_pct(row.get('cls_chg_pct_put', 0)):>8} | "
                      f"{row.get('delta_put', 0):>6.2f} | {row.get('theta_put', 0):>6.2f} | {verdict_display:>25}")
            print(row_str)
        
        print("-" * 120)
        print(f"Total strikes: {len(merged_df)} | Changed: {changed_count} | PCR: {pcr:.2f} | Max Pain: {max_pain}")
        print("=" * 120)
        
        # Send to Telegram if requested
        if send_to_telegram:
            try:
                image_buffer = create_improved_table_image(merged_df, market_analysis, label, changed_count)
                caption = f"📊 {label} - {datetime.now().strftime('%H:%M:%S')} | PCR: {pcr:.2f} | Max Pain: {max_pain}"
                send_telegram_image(image_buffer, caption)
                print("📱 Telegram image created and sent")
            except Exception as e:
                print(f"❌ Telegram image error: {e}")
                
    except Exception as e:
        print(f"❌ Table formatting error: {e}")

# ====== UTILITY FUNCTIONS ======

def detect_nifty_current_month_future(instruments: pd.DataFrame):
    """Detect NIFTY current month future."""
    try:
        nifty_fut = instruments[
            (instruments['name'] == 'NIFTY') & 
            (instruments['instrumenttype'] == 'FUTIDX')
        ]
        
        if not nifty_fut.empty:
            # Find current month future
            current_date = datetime.now()
            for _, row in nifty_fut.iterrows():
                expiry = datetime.strptime(row['expiry'], '%d%b%Y')
                if expiry > current_date:
                    return row['tradingsymbol'], str(row['token'])
        
        return None, None
    except Exception:
        return None, None

def detect_india_vix_token(instruments: pd.DataFrame):
    """Detect India VIX token."""
    try:
        vix = instruments[instruments['name'] == 'INDIA VIX']
        if not vix.empty:
            row = vix.iloc[0]
            return row['tradingsymbol'], str(row['token'])
        return None, None
    except Exception:
        return None, None

def _trim_series(seq, n=MAX_AI_SERIES_POINTS):
    """Trim series to max points."""
    if len(seq) <= n:
        return seq
    return seq[-n:]

def compact_ai_context(ctx: dict) -> dict:
    """Create compact AI context."""
    return {
        "spot": ctx.get("spot", 0),
        "pcr": ctx.get("pcr"),
        "ce_series": _trim_series(ctx.get("ce_series", []), 10),
        "pe_series": _trim_series(ctx.get("pe_series", []), 10),
        "levels": ctx.get("levels", {})
    }

# ====== AI PAYLOAD BUILDER ======

def _select_top_symbols_by_atm(spot: float, ce_series: dict, pe_series: dict, max_per_side: int = 4):
    """Pick up to N CE and N PE symbols nearest to ATM based on strike distance."""
    if not spot or spot <= 0:
        return [], []
    atm = int(round(spot / 50.0) * 50)
    def sort_keys(series):
        strikes = list(series.keys())
        strikes.sort(key=lambda k: abs(int(k) - atm))
        return strikes[:max_per_side]
    ce_keys = sort_keys(ce_series) if ce_series else []
    pe_keys = sort_keys(pe_series) if pe_series else []
    ce_syms = [ce_series[k].get("symbol") for k in ce_keys if isinstance(ce_series.get(k), dict)]
    pe_syms = [pe_series[k].get("symbol") for k in pe_keys if isinstance(pe_series.get(k), dict)]
    return [s for s in ce_syms if s], [s for s in pe_syms if s]


def _build_oi_series_from_history(oi_history_obj, target_strikes: list, max_points: int = 8):
    """Construct per-strike OI time-series across the last snapshots for target strikes."""
    out = {}
    if not oi_history_obj or not getattr(oi_history_obj, 'history', None):
        return out
    history = list(oi_history_obj.history)[-max_points:]
    # Aggregate CE/PE OI by strike per snapshot
    for strike in target_strikes:
        out[str(strike)] = []
    for entry in history:
        ts = entry.get('timestamp')
        df = entry.get('data')
        if df is None or getattr(df, 'empty', True):
            continue
        # Build maps per snapshot
        ce_map, pe_map = {}, {}
        for _, r in df.iterrows():
            sym = str(r.get('symbol', ''))
            m = re.search(r"NIFTY(\d{2}[A-Z]{3}\d{2})(\d{5})([CP]E)$", sym)
            if not m:
                continue
            strike = int(m.group(2))
            side = m.group(3)
            oi_val = int(r.get('oi', 0))
            if side == 'CE':
                ce_map[strike] = ce_map.get(strike, 0) + oi_val
            else:
                pe_map[strike] = pe_map.get(strike, 0) + oi_val
        # Pack for targets
        for k in list(out.keys()):
            sk = int(k)
            ce = ce_map.get(sk, 0)
            pe = pe_map.get(sk, 0)
            out[k].append({"ts": ts.timestamp() if hasattr(ts, 'timestamp') else float(datetime.now().timestamp()), "ce_oi": ce, "pe_oi": pe})
    return out


def build_ai_payload(context: dict, ce_series: dict, pe_series: dict, include_ticks: bool = True, include_oi_history: bool = True) -> dict:
    """Build a structured payload with historical ticks and OI series for AI."""
    spot = context.get("spot", 0)
    pcr = context.get("pcr")
    support = context.get("support", []) or context.get("levels", [])
    resistance = context.get("resistance", [])
    max_pain = context.get("max_pain")

    ce_top_syms, pe_top_syms = _select_top_symbols_by_atm(spot, ce_series, pe_series, max_per_side=4)

    payload = {
        "meta": {
            "ts": datetime.now().isoformat(timespec='seconds'),
            "spot": spot,
            "pcr": pcr,
            "max_pain": max_pain,
            "support_top": support[:3] if isinstance(support, list) else support,
            "resistance_top": resistance[:3] if isinstance(resistance, list) else resistance,
            "ce_count": len(ce_series or {}),
            "pe_count": len(pe_series or {}),
            "ce_symbols": ce_top_syms,
            "pe_symbols": pe_top_syms,
        },
        "tick_series_by_symbol": {},
        "oi_series_by_strike": {},
    }

    # Tick series
    if include_ticks and 'TICK_HISTORY' in globals() and TICK_HISTORY:
        for sym in (ce_top_syms + pe_top_syms):
            series = []
            try:
                pts = TICK_HISTORY.series(sym, last_n=30)
                for it in pts:
                    series.append({
                        "ts": it.get("ts"),
                        "ltp": it.get("ltp"),
                        "bid": it.get("bid"),
                        "ask": it.get("ask"),
                        "vol": it.get("vol"),
                    })
            except Exception:
                series = []
            payload["tick_series_by_symbol"][sym] = series

    # OI series
    if include_oi_history and 'oi_history' in globals() and oi_history:
        # choose target strikes from selected symbols
        target_strikes = []
        for sym in (ce_top_syms + pe_top_syms):
            m = re.search(r"(\d{5})([CP]E)$", sym or "")
            if m:
                target_strikes.append(int(m.group(1)))
        target_strikes = sorted(list(set(target_strikes)))[:8]
        payload["oi_series_by_strike"] = _build_oi_series_from_history(oi_history, target_strikes, max_points=8)

    return payload

# ====== DUAL AI PATTERN FUNCTIONS ======

def _coach_sampler_loop():
    """Minimal AI analysis every 1 second."""
    print("🎧 Coach sampler started (minimal AI every 1s)")
    last_emit = 0
    
    while not _coach_thread_stop.is_set():
        try:
            # Get current spot
            spot = _guess_spot_for_mapping()
            if not spot:
                time.sleep(1)
                continue
            
            # Get PCR data by fetching option chain snapshot using focused strikes
            symbols = pick_focused_strikes_for_oi_analysis(spot, 5)  # Use focused strikes for PCR
            if symbols:
                snapshot = get_option_chain_snapshot(symbols)
                market_analysis = compute_pcr_maxpain_support_resistance(snapshot)
                pcr = market_analysis.get("pcr")
                
                # Extract CE/PE series data from snapshot
                ce_series = {}
                pe_series = {}
                
                if not snapshot.empty:
                    for _, row in snapshot.iterrows():
                        symbol = row['symbol']
                        # Parse symbol to get strike and side
                        m = re.search(r"NIFTY(\d{2}[A-Z]{3}\d{2})(\d{5})([CP]E)$", symbol)
                        if m:
                            strike = int(m.group(2))
                            side = m.group(3)
                            ltp = row['ltp']
                            oi = row['oi']
                            volume = row['volume']
                            
                            if side == "CE":
                                ce_series[strike] = {
                                    "ltp": ltp,
                                    "oi": oi,
                                    "volume": volume,
                                    "symbol": symbol
                                }
                            else:
                                pe_series[strike] = {
                                    "ltp": ltp,
                                    "oi": oi,
                                    "volume": volume,
                                    "symbol": symbol
                                }
            else:
                pcr = None
                ce_series = {}
                pe_series = {}
            
            # Minimal AI call with PCR data and option series
            ai_hint = ai_trade_coach({
                "spot": spot,
                "pcr": pcr,
                "ce_series": ce_series,
                "pe_series": pe_series,
                "levels": market_analysis.get("support", []) + market_analysis.get("resistance", []) if 'market_analysis' in locals() else []
            })
            
            decision = ai_hint.get("coach", "WAIT")
            direction = ai_hint.get("direction", "NEUTRAL")
            note = ai_hint.get("note", "AI analysis")
            
            # Always show guidance every 2 seconds for testing
            now = time.time()
            if now - last_emit > 2:  # Changed from 3 to 2 seconds
                last_emit = now
                # Get NIFTY LTP from cache or API fallback
                nifty_ltp = "N/A"
                try:
                    # Try WebSocket cache first
                    with WS_LOCK:
                        spot_data = TICKS_CACHE.get("NIFTY_SPOT", {})
                        if spot_data and spot_data.get("ltp"):
                            nifty_ltp = f"{float(spot_data['ltp']):.1f}"
                    
                    # Fallback to API if WebSocket cache is empty
                    if nifty_ltp == "N/A" and nifty_index_token:
                        try:
                            resp = obj.getMarketData("LTP", {"NSE": [nifty_index_token]})
                            if resp and 'data' in resp and resp['data']:
                                ltp = resp['data'][0].get('ltp', 0)
                                if ltp > 0:
                                    nifty_ltp = f"{float(ltp):.1f}"
                        except Exception:
                            pass
                except Exception:
                    pass
                
                # Get current timestamp
                timestamp = datetime.now().strftime("%H:%M:%S")
                
                pcr_info = f" | PCR: {pcr:.2f}" if pcr else " | PCR: N/A"
                direction_info = f" | {direction}" if direction != "NEUTRAL" else ""
                ce_count = len(ce_series)
                pe_count = len(pe_series)
                sep = "-" * 80
                print(f"\n{sep}\n🤖 [MINIMAL] Coach: {decision} —{direction_info} | {note}{pcr_info} | CE: {ce_count} | PE: {pe_count} | NIFTY: {nifty_ltp} @ {timestamp}\n{sep}")
            
        except Exception as e:
            print(f"Coach sampler error: {e}")
        finally:
            time.sleep(COACH_INTERVAL_SECS)  # 1 second interval
    
    print("🛌 Coach sampler stopped")

def _snapshot_loop():
    """Rich AI analysis based on OI data changes only."""
    print("⏱️ Snapshot cycle started (rich AI based on OI changes only)")
    last_check_time = 0  # allow immediate first run
    min_check_interval = 30  # Check at least every 30 seconds
    
    while not _snapshot_stop.is_set():
        try:
            current_time = time.time()
            
            # Check if enough time has passed since last check
            if current_time - last_check_time < min_check_interval:
                time.sleep(1)
                continue
            
            last_check_time = current_time
            
            # Get current snapshot with focused strikes (top 5 + bottom 5 from ATM)
            current_spot = _guess_spot_for_mapping()
            if current_spot:
                symbols = pick_focused_strikes_for_oi_analysis(current_spot, 5)
                atm_strike = int(round(current_spot / 50.0) * 50)
                print(f"📊 Focused OI Analysis: {len(symbols)} strikes (top 5 + bottom 5 from ATM {atm_strike})")
            else:
                symbols = []
            
            if not symbols:
                time.sleep(2)
                continue
            
            current_snapshot = get_option_chain_snapshot(symbols)
            if current_snapshot.empty:
                time.sleep(2)
                continue
            
            # Check if there are significant OI changes
            has_changes = oi_history.has_significant_changes(current_snapshot, min_change_threshold=0.005)
            
            if has_changes:
                print(f"🔄 Rich AI triggered: OI changes detected")
                
                # Calculate market analysis
                market_analysis = compute_pcr_maxpain_support_resistance(current_snapshot)
                
                # Extract CE/PE series data
                ce_series = {}
                pe_series = {}
                
                for _, row in current_snapshot.iterrows():
                    symbol = row['symbol']
                    m = re.search(r"NIFTY(\d{2}[A-Z]{3}\d{2})(\d{5})([CP]E)$", symbol)
                    if m:
                        strike = int(m.group(2))
                        side = m.group(3)
                        ltp = row['ltp']
                        oi = row['oi']
                        volume = row['volume']
                        delta = row.get('delta', 0.0)
                        theta = row.get('theta', 0.0)
                        
                        if side == "CE":
                            ce_series[strike] = {
                                "ltp": ltp,
                                "oi": oi,
                                "volume": volume,
                                "delta": delta,
                                "theta": theta,
                                "symbol": symbol
                            }
                        else:
                            pe_series[strike] = {
                                "ltp": ltp,
                                "oi": oi,
                                "volume": volume,
                                "delta": delta,
                                "theta": theta,
                                "symbol": symbol
                            }
                
                # Get changed symbols count
                previous_snapshot = oi_history.get_last_snapshot()
                if previous_snapshot is not None:
                    changed_symbols = get_strikes_with_oi_changes(current_snapshot, previous_snapshot)
                    changed_count = len(changed_symbols)
                else:
                    changed_count = len(current_snapshot)  # First run
                
                # Generate OI table with verdicts and send to Telegram
                if changed_count > 0:
                    print(f"Generating OI analysis table for {changed_count} changed strikes...")
                    format_table_output_improved(
                        current_snapshot.copy(),
                        previous_snapshot if previous_snapshot is not None else current_snapshot.copy(),
                        label=f"OI Analysis @ {datetime.now().strftime('%H:%M:%S')}",
                        changed_count=changed_count,
                        send_to_telegram=True
                    )
                
                # Rich AI call with complete data
                ai_hint = ai_trade_coach_rich({
                    "spot": _guess_spot_for_mapping(),
                    "pcr": market_analysis.get("pcr"),
                    "max_pain": market_analysis.get("max_pain"),
                    "support": market_analysis.get("support", []),
                    "resistance": market_analysis.get("resistance", []),
                    "ce_series": ce_series,
                    "pe_series": pe_series,
                    "snapshot": current_snapshot
                })
                
                # Store snapshot in history
                oi_history.add_snapshot(current_snapshot)
                
                print(f"📊 Rich AI completed at {datetime.now().strftime('%H:%M:%S')}")
            else:
                print(f"⏳ No significant OI changes detected, waiting...")
            
        except Exception as e:
            print(f"❌ Snapshot loop error: {e}")
            time.sleep(5)
    
    print("Snapshot cycle stopped")

def start_coach_sampler():
    """Start minimal AI coach sampler."""
    global _coach_thread
    if _coach_thread and _coach_thread.is_alive():
        return
    _coach_thread_stop.clear()
    _coach_thread = threading.Thread(target=_coach_sampler_loop, name="CoachSampler", daemon=True)
    _coach_thread.start()

def stop_coach_sampler():
    """Stop minimal AI coach sampler."""
    _coach_thread_stop.set()

def start_snapshot_cycle():
    """Start rich AI snapshot cycle."""
    global _snapshot_thread
    if _snapshot_thread and _snapshot_thread.is_alive():
        return
    _snapshot_stop.clear()
    _snapshot_thread = threading.Thread(target=_snapshot_loop, name="SnapshotCycle", daemon=True)
    _snapshot_thread.start()

def stop_snapshot_cycle():
    """Stop rich AI snapshot cycle."""
    _snapshot_stop.set()

def start_system():
    """Start the complete system with dual AI pattern."""
    print("🚀 Starting system with dual AI pattern...")
    
    try:
        # Build mappings
        build_symbol_token_maps()
        
        # Apply environment secrets
        apply_env_secrets()
        
        # Check AI client status
        print(f"AI Client status: {'Initialized' if _ai_client else 'Not available'}")
        print(f"AI Coach enabled: {'Yes' if USE_AI_COACH else 'No'}")
        
        # Start WebSocket feed early
        initial_tokens = []
        if FEED_SEGMENT == 'MCX':
            initial_tokens = list(MCX_TOKENS)
        else:
            if nifty_index_token:
                initial_tokens.append(str(nifty_index_token))
        start_ws_feed(initial_tokens)

        # After WS starts, derive spot and subscribe focused option tokens
        if FEED_SEGMENT != 'MCX':
            try:
                t0 = time.time()
                spot = None
                while time.time() - t0 < 3 and spot is None:
                    with WS_LOCK:
                        spot = TICKS_CACHE.get("NIFTY_SPOT", {}).get("ltp")
                    if spot is None:
                        time.sleep(0.1)
                if not spot:
                    spot = _guess_spot_for_mapping()
                if spot:
                    # Subscribe to focused strikes (top 5 + bottom 5 from ATM) for better performance
                    symbols = pick_focused_strikes_for_oi_analysis(float(spot), 5)
                    atm_strike = int(round(float(spot) / 50.0) * 50)
                    print(f"📡 WebSocket: Subscribing to {len(symbols)} focused strikes (top 5 + bottom 5 from ATM {atm_strike})")
                    ws_refresh_subscription(symbols)
            except Exception:
                pass
        
        # Start dual AI pattern (NIFTY only). In MCX mode, skip AI loops.
        if FEED_SEGMENT == 'MCX':
            print("🧾 MCX mode: AI coach and PCR/snapshot loops are disabled (NIFTY-only).")
        else:
            # Generate initial OI table to show current state
            try:
                print("📊 Generating initial OI analysis table...")
                current_spot = _guess_spot_for_mapping()
                if current_spot:
                    initial_symbols = pick_focused_strikes_for_oi_analysis(current_spot, 5)
                    atm_strike = int(round(current_spot / 50.0) * 50)
                    print(f"Initial Focused Analysis: {len(initial_symbols)} strikes (top 5 + bottom 5 from ATM {atm_strike})")
                    
                    if initial_symbols:
                        initial_snapshot = get_option_chain_snapshot(initial_symbols)
                        if not initial_snapshot.empty:
                            format_table_output_improved(
                                initial_snapshot.copy(),
                                initial_snapshot.copy(),  # No previous data for initial run
                                label="Initial Focused OI Analysis",
                                changed_count=len(initial_snapshot),
                                send_to_telegram=True
                            )
                            # Store initial snapshot
                            oi_history.add_snapshot(initial_snapshot, datetime.now())
            except Exception as e:
                print(f"Initial OI table generation failed: {e}")
            
            start_coach_sampler()  # Minimal AI every 1s
            start_snapshot_cycle()  # Rich AI based on OI changes
        
        print("System started with dual AI pattern")
        print("OI Monitor running...")
        if FEED_SEGMENT != 'MCX':
            print("Minimal AI analysis: Every 1 second")
            print("Rich AI analysis: Based on OI data changes (not fixed time)")
        else:
            print("Streaming MCX ticks only (no NIFTY PCR/AI).")
        print("Press Ctrl+C to stop")
        
    except Exception as e:
        print(f"System start error: {e}")

def stop_system():
    """Stop the complete system."""
    print("Stopping system...")
    
    try:
        stop_coach_sampler()
        stop_snapshot_cycle()
        stop_ws_feed()
        print("System stopped")
    except Exception as e:
        print(f"System stop error: {e}")

# ====== ENVIRONMENT SECRETS ======

def apply_env_secrets():
    """Apply hardcoded secrets."""
    global TELEGRAM_BOT_TOKEN, _ai_client
    
    # All credentials are now hardcoded, no need to fetch from environment
    print("Using hardcoded credentials")
    
    # Ensure AI client has the correct API key
    if _ai_client:
        _ai_client.api_key = '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'

# ====== SQLITE LOGGING ======
_DB_PATH = os.path.join(BASE_DIR, "logs", "decisions.sqlite3")

def _init_db():
    try:
        os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
        conn = sqlite3.connect(_DB_PATH)
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
          id INTEGER PRIMARY KEY,
          ts REAL NOT NULL,
          decision TEXT NOT NULL,
          side TEXT,
          strike INTEGER,
          sl REAL,
          tgt REAL,
          reason TEXT,
          source TEXT NOT NULL
        )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_decisions_ts ON decisions(ts)")
        conn.commit(); conn.close()
    except Exception as e:
        print(f"DB init error: {e}")

def _log_decision_row(ts: float, decision: str, side: str, strike, sl, tgt, reason: str, source: str):
    try:
        conn = sqlite3.connect(_DB_PATH)
        cur = conn.cursor()
        cur.execute("INSERT INTO decisions (ts,decision,side,strike,sl,tgt,reason,source) VALUES (?,?,?,?,?,?,?,?)",
                    (ts, decision, side, strike, sl, tgt, reason, source))
        conn.commit(); conn.close()
    except Exception as e:
        print(f"DB log error: {e}")

# ====== MAIN EXECUTION ======

def main():
    """Main execution function with dual AI pattern."""
    try:
        _init_db()
        # Start the complete system with dual AI pattern
        start_system()
        
        # Keep main thread alive
        last_hb = 0
        while True:
            try:
                time.sleep(1)
                now = time.time()
                if now - last_hb > 60:
                    with WS_LOCK:
                        tick_count = len(TICKS_CACHE)
                    last_snap = oi_history.get_last_snapshot_time()
                    last_snap_str = last_snap.strftime('%H:%M:%S') if last_snap else 'N/A'
                    print(f"💓 Heartbeat | WS symbols: {tick_count} | Last snapshot: {last_snap_str}")
                    last_hb = now
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ Main loop error: {e}")
                time.sleep(1)
        
        # Cleanup
        stop_system()
        print("👋 OI Monitor stopped")
        
    except Exception as e:
        print(f"💥 Fatal error: {e}")

if __name__ == "__main__":
    main()