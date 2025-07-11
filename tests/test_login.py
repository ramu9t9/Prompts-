#!/usr/bin/env python3

from SmartApi import SmartConnect
import pandas as pd
import pyotp, requests


obj = SmartConnect(api_key="P9ErUZG0")
user_id = "r117172"
pin = 9029
api_secret = "7fcb7f2a-fd0a-4d12-a010-16d37fbdbd6e"
totp = pyotp.TOTP("Y4GDOA6SL5VOCKQPFLR5EM3HOY").now()
data = obj.generateSession(user_id, pin, totp)
refresh_token = data['data']['refreshToken']
# response = obj.generateToken(refresh_token)
# response = obj.getProfile(refresh_token)
# print(response)
def fetch_instruments():
    response = requests.get("https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json")
    if response.ok:
        df = pd.DataFrame(response.json())
        print(f"Fetched and stored {len(df)} instruments")
        return df
    print("Failed to fetch instruments")
    return pd.DataFrame()
    
instrument_list = fetch_instruments()
tokens = instrument_list[(instrument_list['name'] == 'NIFTY') & (instrument_list['expiry'] == '10JUL2025')]['token'][:5].tolist()


name = data['data']['name']
print(name)

ex_token = {
    "NSE": [

    ],
    "NFO": tokens
}

oi_data = obj.getMarketData("FULL", ex_token)
oi_data_pd = pd.DataFrame(oi_data['data']['fetched'])

# Display complete information about the data structure
print("\n" + "="*80)
print("📊 COMPLETE DATA STRUCTURE ANALYSIS")
print("="*80)

print(f"\n📋 Total records: {len(oi_data_pd)}")
print(f"📋 Total columns: {len(oi_data_pd.columns)}")

print(f"\n📋 Column names:")
for i, col in enumerate(oi_data_pd.columns):
    print(f"   {i+1:2d}. {col}")

print(f"\n📋 Data types:")
print(oi_data_pd.dtypes)

print(f"\n📋 Sample data (first 2 rows):")
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
print(oi_data_pd.head(2).to_string())

print(f"\n📋 Key fields for our project:")
key_fields = ['tradingSymbol', 'symbolToken', 'ltp', 'opnInterest', 'tradeVolume', 
              'netChange', 'pChange', 'open', 'high', 'low', 'close']
for field in key_fields:
    if field in oi_data_pd.columns:
        print(f"   ✅ {field}: {oi_data_pd[field].iloc[0] if len(oi_data_pd) > 0 else 'N/A'}")
    else:
        print(f"   ❌ {field}: Not found")

print(f"\n📋 All available fields with sample values:")
for col in oi_data_pd.columns:
    sample_value = oi_data_pd[col].iloc[0] if len(oi_data_pd) > 0 else 'N/A'
    print(f"   {col}: {sample_value}")

