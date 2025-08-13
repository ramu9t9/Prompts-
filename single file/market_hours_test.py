#!/usr/bin/env python3
"""
Market Hours WebSocket Test
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

# Globals
obj = None
data = None
ws = None
WS_RUNNING = False
WS_CONNECTED = False
DATA_RECEIVED = False

def check_market_hours():
    """Check if we're within market hours"""
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    
    # Market hours: 9:15 AM - 3:30 PM IST (Monday to Friday)
    market_start = "09:15"
    market_end = "15:30"
    
    is_weekday = now.weekday() < 5  # Monday = 0, Friday = 4
    is_market_hours = market_start <= current_time <= market_end
    
    print(f"📅 Date: {now.strftime('%Y-%m-%d %A')}")
    print(f"🕐 Time: {current_time}")
    print(f"📊 Market Hours: {market_start} - {market_end}")
    print(f"✅ Weekday: {'Yes' if is_weekday else 'No'}")
    print(f"✅ Market Hours: {'Yes' if is_market_hours else 'No'}")
    
    return is_weekday and is_market_hours

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

def on_data(ws, message):
    """Callback for data messages"""
    global DATA_RECEIVED
    try:
        DATA_RECEIVED = True
        print(f"📊 LIVE DATA: {message[:200]}...")
    except Exception as e:
        print(f"❌ Data callback error: {e}")

def on_open(ws):
    """Callback for connection open"""
    print("🔗 WebSocket opened")
    global WS_CONNECTED
    WS_CONNECTED = True

def on_close(ws, close_status_code, close_msg):
    """Callback for connection close"""
    print(f"🔌 WebSocket closed: {close_status_code} - {close_msg}")
    global WS_CONNECTED, WS_RUNNING
    WS_CONNECTED = False
    WS_RUNNING = False

def on_error(ws, error):
    """Callback for errors"""
    print(f"❌ WebSocket error: {error}")

def get_nifty50_token():
    """Get NIFTY 50 index token"""
    try:
        response = requests.get("https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json")
        instruments = response.json()
        
        for instrument in instruments:
            if (instrument.get('name') == 'NIFTY' and 
                instrument.get('symbol') == 'Nifty 50' and
                instrument.get('exch_seg') == 'NSE'):
                return instrument.get('token')
        
        return None
    except Exception as e:
        print(f"❌ Error getting NIFTY 50 token: {e}")
        return None

def test_live_data():
    """Test live data streaming"""
    global ws, WS_RUNNING, DATA_RECEIVED
    
    try:
        print("\n🔗 Testing live data streaming...")
        
        # Get tokens
        feed_token = obj.getfeedToken()
        auth_token = data.get('data', {}).get('jwtToken', '')
        
        # Get NIFTY 50 token
        nifty50_token = get_nifty50_token()
        if not nifty50_token:
            print("❌ NIFTY 50 token not found")
            return False
        
        print(f"📊 NIFTY 50 Token: {nifty50_token}")
        
        # Create WebSocket
        ws = SmartWebSocketV2(
            auth_token=auth_token,
            api_key=API_KEY,
            client_code=USER_ID,
            feed_token=feed_token
        )
        
        # Set callbacks
        ws.on_data = on_data
        ws.on_open = on_open
        ws.on_close = on_close
        ws.on_error = on_error
        
        WS_RUNNING = True
        
        print("🔗 Connecting...")
        ws.connect()
        
        # Wait for connection
        timeout = 10
        start_time = time.time()
        while not WS_CONNECTED and time.time() - start_time < timeout:
            time.sleep(0.1)
        
        if not WS_CONNECTED:
            print("❌ Connection timeout")
            return False
        
        print("✅ Connected! Subscribing to NIFTY 50...")
        
        # Subscribe to NIFTY 50
        token_list = [{
            "exchangeType": 1,  # NSE
            "tokens": [str(nifty50_token)]
        }]
        
        ws.subscribe(correlation_id="market-test", mode=3, token_list=token_list)
        
        print("📡 Subscription sent! Waiting for data...")
        
        # Monitor for data
        data_timeout = 30
        data_start = time.time()
        
        while time.time() - data_start < data_timeout and WS_RUNNING:
            time.sleep(1)
            
            if DATA_RECEIVED:
                print("🎉 LIVE DATA RECEIVED!")
                return True
            
            elapsed = int(time.time() - data_start)
            if elapsed % 5 == 0:
                print(f"⏱️ Waiting for data... ({elapsed}s)")
        
        if not DATA_RECEIVED:
            print("❌ No data received within timeout")
            return False
            
    except Exception as e:
        print(f"❌ Test error: {e}")
        return False

def main():
    print("🧪 Market Hours WebSocket Test")
    print("="*50)
    
    # Check market hours
    if not check_market_hours():
        print("\n❌ Outside market hours - WebSocket may not work")
        print("💡 Try running during 9:15 AM - 3:30 PM IST on weekdays")
        return
    
    print("\n✅ Within market hours - proceeding with test")
    
    # Login
    if not login():
        return
    
    # Test live data
    if test_live_data():
        print("\n🎉 SUCCESS: Live data streaming working!")
    else:
        print("\n❌ FAILED: No live data received")
    
    # Cleanup
    if ws:
        try:
            ws.close()
            print("🔌 WebSocket closed")
        except:
            pass
    
    print("\n✅ Test completed!")

if __name__ == "__main__":
    main()
