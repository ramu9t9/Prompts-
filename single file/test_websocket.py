#!/usr/bin/env python3
"""
WebSocket Test for NIFTY/MCX Live Feed
"""

import time
import json
import threading
from datetime import datetime
from SmartApi import SmartConnect
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
import pyotp
import requests

# Config
API_KEY = "IF0vWmnY"
USER_ID = "r117172"
PIN = 9029
TOTP_SECRET = "Y4GDOA6SL5VOCKQPFLR5EM3HOY"

# Test mode: 'NFO' for NIFTY options, 'MCX' for commodities
TEST_MODE = 'MCX'

# Globals
obj = None
data = None
ws = None
TICKS_CACHE = {}
WS_LOCK = threading.Lock()
WS_RUNNING = False
SYMBOL_TO_TOKEN = {}
NIFTY50_TOKEN = None
MCX_TOKENS = []  # list[str]


def login():
    global obj, data
    try:
        obj = SmartConnect(api_key=API_KEY)
        totp = pyotp.TOTP(TOTP_SECRET).now()
        data = obj.generateSession(USER_ID, PIN, totp)
        if data['status']:
            print("✅ Login successful")
            return True
        else:
            print(f"❌ Login failed: {data}")
            return False
    except Exception as e:
        print(f"❌ Login error: {e}")
        return False


def fetch_instruments():
    global SYMBOL_TO_TOKEN, NIFTY50_TOKEN, MCX_TOKENS
    try:
        print("📥 Fetching instruments...")
        response = requests.get("https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json")
        instruments = response.json()

        if TEST_MODE == 'MCX':
            # Collect a handful of MCX tokens (FUTCOM/COMDTY)
            mcx = []
            for inst in instruments:
                if inst.get('exch_seg') == 'MCX' and inst.get('instrumenttype') in ('FUTCOM', 'COMDTY'):
                    token = inst.get('token')
                    symbol = inst.get('symbol')
                    if token and symbol:
                        mcx.append((symbol, str(token)))
            MCX_TOKENS = [tok for _, tok in mcx[:20]]
            print(f"⛏️ MCX selected {len(MCX_TOKENS)} tokens")
            if mcx:
                print("   e.g.")
                for s, t in mcx[:5]:
                    print(f"   {s} -> {t}")
            return True

        # Default: NIFTY options (NFO) + NIFTY 50 index
        nifty_instruments = []
        for instrument in instruments:
            if (instrument.get('name') == 'NIFTY' and 
                instrument.get('exch_seg') == 'NFO' and
                instrument.get('instrumenttype') == 'OPTIDX'):
                nifty_instruments.append(instrument)

        # Find NIFTY 50 index token on NSE
        for instrument in instruments:
            if (instrument.get('name') == 'NIFTY' and instrument.get('symbol') == 'Nifty 50' and instrument.get('exch_seg') == 'NSE'):
                NIFTY50_TOKEN = str(instrument.get('token'))
                break
        if NIFTY50_TOKEN:
            print(f"📊 NIFTY 50 token: {NIFTY50_TOKEN}")
        else:
            print("⚠️ NIFTY 50 token not found")

        print(f"📈 Found {len(nifty_instruments)} NIFTY option instruments")

        for instrument in nifty_instruments[:20]:  # Take first 20
            symbol = instrument.get('symbol')
            token = instrument.get('token')
            if symbol and token:
                SYMBOL_TO_TOKEN[symbol] = token

        print(f"🗺️ Built mappings for {len(SYMBOL_TO_TOKEN)} symbols")
        return True

    except Exception as e:
        print(f"❌ Error fetching instruments: {e}")
        return False

_raw_dump_count = 0


def on_data(wsapp, message):
    try:
        global _raw_dump_count
        payload = message
        if isinstance(message, (bytes, str)):
            try:
                payload = json.loads(message)
            except Exception:
                pass
        # Dump first few payloads for inspection
        if _raw_dump_count < 5:
            _raw_dump_count += 1
            try:
                with open("ws_payload_samples.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps({"ts": datetime.now().isoformat(), "payload": payload}, default=str) + "\n")
            except Exception:
                pass

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
                return raw / 100.0
            return raw

        def handle_entry(entry):
            token = str(
                entry.get('symbolToken')
                or entry.get('token')
                or entry.get('tk')
                or entry.get('instrument_token')
                or 'UNKNOWN'
            )
            ltp = extract_ltp(entry)
            ts = datetime.now().strftime("%H:%M:%S")
            with WS_LOCK:
                TICKS_CACHE[token] = {
                    'ltp': ltp,
                    'timestamp': ts,
                    'bid': entry.get('bestBid') or entry.get('bid') or entry.get('bp'),
                    'ask': entry.get('bestAsk') or entry.get('ask') or entry.get('ap')
                }
            # Map token to a readable label if we have one
            sym = next((s for s, t in SYMBOL_TO_TOKEN.items() if str(t) == token), token)
            print(f"📊 [{ts}] {sym}: LTP={ltp}")

        if isinstance(payload, dict) and isinstance(payload.get('data'), list):
            for entry in payload['data']:
                if isinstance(entry, dict):
                    handle_entry(entry)
        elif isinstance(payload, list):
            for entry in payload:
                if isinstance(entry, dict):
                    handle_entry(entry)
        elif isinstance(payload, dict):
            handle_entry(payload)
        else:
            print(f"ℹ️ Unhandled message type: {type(payload)}")
    except Exception as e:
        print(f"❌ Message error: {e}")


def on_open(wsapp):
    print("🔗 WebSocket connected")
    global WS_RUNNING
    WS_RUNNING = True

    try:
        token_list = []
        if TEST_MODE == 'MCX':
            if not MCX_TOKENS:
                print("❌ No MCX tokens to subscribe")
                return
            token_list.append({"exchangeType": 5, "tokens": [str(t) for t in MCX_TOKENS]})
        else:
            test_symbols = list(SYMBOL_TO_TOKEN.items())[:10]
            if NIFTY50_TOKEN:
                token_list.append({"exchangeType": 1, "tokens": [str(NIFTY50_TOKEN)]})
            if test_symbols:
                token_list.append({"exchangeType": 2, "tokens": [str(tok) for _, tok in test_symbols]})

        if not token_list:
            print("❌ No tokens to subscribe")
            return

        correlation_id = f"ws-test-{TEST_MODE.lower()}-{int(time.time())}"
        # LTP mode for lightweight ticks
        ws.subscribe(correlation_id, 1, token_list)
        print("📡 Subscribe sent")
    except Exception as e:
        print(f"❌ Subscribe error: {e}")


def on_error(wsapp, error):
    print(f"❌ WebSocket error: {error}")


def on_close(wsapp):
    print("🔌 WebSocket closed")
    global WS_RUNNING
    WS_RUNNING = False


def start_websocket_test():
    global ws
    try:
        print("🔗 Creating WebSocket...")
        feed_token = obj.getfeedToken()
        auth_token = data.get('data', {}).get('jwtToken', '')

        ws = SmartWebSocketV2(
            auth_token=auth_token,
            api_key=API_KEY,
            client_code=USER_ID,
            feed_token=feed_token
        )
        ws.on_open = on_open
        ws.on_data = on_data
        ws.on_error = on_error
        ws.on_close = on_close

        ws.connect()
        time.sleep(2)

        if not WS_RUNNING:
            print("❌ WebSocket failed to connect")
            return False

        print("✅ WebSocket test started!")
        return True

    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        return False


def monitor_data():
    start_time = time.time()
    print("\n📊 Monitoring for 30 seconds...")

    try:
        while time.time() - start_time < 30 and WS_RUNNING:
            time.sleep(1)
            with WS_LOCK:
                if len(TICKS_CACHE) > 0:
                    print(f"📈 Received data for {len(TICKS_CACHE)} tokens")
                    break
    except KeyboardInterrupt:
        print("\n⏹️ Stopping...")

    print("\n📊 Final Status:")
    with WS_LOCK:
        print(f"📈 Total tokens: {len(TICKS_CACHE)}")
        if TICKS_CACHE:
            print("📊 Sample data:")
            for token, data in list(TICKS_CACHE.items())[:5]:
                print(f"   {token}: LTP={data.get('ltp', 'N/A')}")

    if ws:
        try:
            ws.close_connection()
        except:
            pass


def main():
    print("🧪 WebSocket Test (Mode: " + TEST_MODE + ")")
    print("="*40)

    if not login():
        return

    if not fetch_instruments():
        return

    if not start_websocket_test():
        return

    monitor_data()
    print("\n✅ Test completed!")


if __name__ == "__main__":
    main()
