#!/usr/bin/env python3
"""
Simple WebSocket Test - Debug Connection Issues
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

def login():
    global obj, data
    try:
        obj = SmartConnect(api_key=API_KEY)
        totp = pyotp.TOTP(TOTP_SECRET).now()
        data = obj.generateSession(USER_ID, PIN, totp)
        if data['status']:
            print("✅ Login successful")
            print(f"📊 Feed Token: {data['data']['feedToken']}")
            print(f"🔑 Auth Token: {data['data']['jwtToken']}")
            return True
        else:
            print(f"❌ Login failed: {data}")
            return False
    except Exception as e:
        print(f"❌ Login error: {e}")
        return False

def on_data(ws, message):
    """Callback for data messages"""
    try:
        print(f"📊 Data received: {message[:100]}...")
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

def test_basic_connection():
    """Test basic WebSocket connection without subscription"""
    global ws, WS_RUNNING
    
    try:
        print("\n🔗 Testing basic WebSocket connection...")
        
        # Get tokens
        feed_token = obj.getfeedToken()
        auth_token = data.get('data', {}).get('jwtToken', '')
        
        print(f"📊 Feed Token: {feed_token}")
        print(f"🔑 Auth Token: {auth_token[:20]}...")
        
        # Create WebSocket
        ws = SmartWebSocketV2(
            auth_token=auth_token,
            api_key=API_KEY,
            client_code=USER_ID,
            feed_token=feed_token
        )
        
        # Set callbacks (using correct names from main file)
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
        
        if WS_CONNECTED:
            print("✅ Connection successful!")
            return True
        else:
            print("❌ Connection timeout")
            return False
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def test_subscription():
    """Test subscription with a simple token"""
    global ws
    
    if not WS_CONNECTED:
        print("❌ WebSocket not connected")
        return False
    
    try:
        print("\n📡 Testing subscription...")
        
        # Get NIFTY 50 index token
        response = requests.get("https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json")
        instruments = response.json()
        
        nifty50_token = None
        for instrument in instruments:
            if (instrument.get('name') == 'NIFTY 50' and 
                instrument.get('exch_seg') == 'NSE'):
                nifty50_token = instrument.get('token')
                break
        
        if not nifty50_token:
            print("❌ NIFTY 50 token not found")
            return False
        
        print(f"📊 NIFTY 50 Token: {nifty50_token}")
        
        # Subscribe to NIFTY 50
        token_list = [{
            "exchangeType": 1,  # NSE
            "tokens": [str(nifty50_token)]
        }]
        
        print("📡 Subscribing to NIFTY 50...")
        ws.subscribe(correlation_id="test", mode=3, token_list=token_list)
        
        print("✅ Subscription sent!")
        return True
        
    except Exception as e:
        print(f"❌ Subscription error: {e}")
        return False

def monitor_connection():
    """Monitor connection for 30 seconds"""
    print("\n📊 Monitoring connection for 30 seconds...")
    
    start_time = time.time()
    try:
        while time.time() - start_time < 30 and WS_RUNNING:
            time.sleep(1)
            
            if not WS_CONNECTED:
                print("❌ Connection lost")
                break
                
            elapsed = int(time.time() - start_time)
            if elapsed % 5 == 0:
                print(f"⏱️ Still connected... ({elapsed}s)")
    
    except KeyboardInterrupt:
        print("\n⏹️ Stopping...")
    
    finally:
        if ws:
            try:
                ws.close()
                print("🔌 WebSocket closed")
            except:
                pass

def main():
    print("🧪 Simple WebSocket Test")
    print("="*50)
    
    # Step 1: Login
    if not login():
        return
    
    # Step 2: Test basic connection
    if not test_basic_connection():
        return
    
    # Step 3: Test subscription
    test_subscription()
    
    # Step 4: Monitor
    monitor_connection()
    
    print("\n✅ Test completed!")

if __name__ == "__main__":
    main()
