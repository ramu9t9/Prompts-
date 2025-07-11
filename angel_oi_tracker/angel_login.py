"""
Angel One SmartAPI Login Module

This module handles authentication with Angel One SmartAPI using TOTP.
Always refer to official documentation: https://smartapi.angelone.in/docs

API Compliance:
- Rate Limits: https://smartapi.angelone.in/docs/rate-limits
- Authentication: https://smartapi.angelone.in/docs/authentication
- Terms of Service: Follow Angel One's terms and conditions
"""

import pyotp
import time
import os
from datetime import datetime
import json

# Import SmartConnect with proper error handling
try:
    from SmartApi import SmartConnect
    SMARTAPI_AVAILABLE = True
except ImportError:
    print("❌ Error: smartapi package not found. Please install it with: pip install smartapi-python")
    SmartConnect = None
    SMARTAPI_AVAILABLE = False

class AngelOneLogin:
    def __init__(self):
        self.api_key = None
        self.client_id = None
        self.pwd = None
        self.totp_key = None
        self.smart_api = None
        self.is_logged_in = False
        self.session_secret = None
    
    def load_credentials(self):
        self.api_key = os.getenv('ANGEL_API_KEY')
        self.client_id = os.getenv('ANGEL_CLIENT_ID')
        self.pwd = os.getenv('ANGEL_PASSWORD')
        self.totp_key = os.getenv('ANGEL_TOTP_KEY')
        self.session_secret = None
        if not all([self.api_key, self.client_id, self.pwd, self.totp_key]):
            self._load_from_config_file()
    
    def _load_from_config_file(self):
        config_file = 'angel_config.txt'
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                lines = f.readlines()
                for line in lines:
                    if '=' in line and not line.strip().startswith('#'):
                        key, value = line.strip().split('=', 1)
                        if key == 'API_KEY':
                            self.api_key = value
                        elif key == 'CLIENT_ID':
                            self.client_id = value
                        elif key == 'PASSWORD':
                            self.pwd = value
                        elif key == 'TOTP_KEY':
                            self.totp_key = value
        else:
            print("⚠️  Config file not found. Please create 'angel_config.txt' with your credentials:")
            print("API_KEY=your_api_key")
            print("CLIENT_ID=your_client_id")
            print("PASSWORD=your_password")
            print("TOTP_KEY=your_totp_key")
    
    def generate_totp(self):
        if not self.totp_key:
            raise ValueError("TOTP key not found. Please set ANGEL_TOTP_KEY environment variable or add to config file.")
        totp = pyotp.TOTP(self.totp_key)
        return totp.now()
    
    def login(self):
        try:
            if not SMARTAPI_AVAILABLE or SmartConnect is None:
                print("❌ SmartAPI not available. Please install: pip install smartapi-python")
                return False
            self.load_credentials()
            if not all([self.api_key, self.client_id, self.pwd, self.totp_key]):
                raise ValueError("Missing credentials. Please check your configuration.")
            self.smart_api = SmartConnect(api_key=self.api_key)
            totp = self.generate_totp()
            data = self.smart_api.generateSession(self.client_id, self.pwd, totp)
            # If data is bytes, decode and load as JSON
            if isinstance(data, bytes):
                data = json.loads(data.decode())
            if isinstance(data, str):
                data = json.loads(data)
            if isinstance(data, dict) and data.get('status'):
                self.is_logged_in = True
                print(f"✅ Successfully logged in to Angel One at {datetime.now()}")
                print(f"📊 User: {data['data'].get('name', 'N/A') if 'data' in data else 'N/A'}")
                if 'data' in data and 'sessionId' in data['data']:
                    self.session_secret = data['data']['sessionId']
                    print(f"🔑 Session ID: {self.session_secret}")
                return True
            else:
                print(f"❌ Login failed: {data.get('message', 'Unknown error') if isinstance(data, dict) else data}")
                return False
        except Exception as e:
            print(f"❌ Login error: {str(e)}")
            return False
    
    def logout(self):
        if self.smart_api and self.is_logged_in:
            try:
                self.smart_api.terminateSession(self.client_id)
                self.is_logged_in = False
                print("✅ Successfully logged out from Angel One")
            except Exception as e:
                print(f"⚠️  Logout error: {str(e)}")
    
    def get_smart_api(self):
        if not self.is_logged_in:
            raise Exception("Not logged in. Please call login() first.")
        return self.smart_api
    
    def is_authenticated(self):
        return self.is_logged_in and self.smart_api is not None

# Global login instance
angel_login = AngelOneLogin() 