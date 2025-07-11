
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

def fetch_instruments():
    response = requests.get("https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json")
    if response.ok:
        df = pd.DataFrame(response.json())
        print(f"Fetched and stored {len(df)} instruments")
        return df
    print("Failed to fetch instruments")
    return pd.DataFrame()
    
instrument_list = fetch_instruments()

tokens = instrument_list[(instrument_list['name'] == 'NIFTY') & (instrument_list['expiry'] == '17JUL2025')]['token'].tolist()

name = data['data']['name']
print(name)

ex_token = {
    "NSE": [

    ],
    "NFO": tokens[85:96]
}

oi_data = obj.getMarketData("FULL", ex_token)

greekParam = {
    "name": "NIFTY",  # Here Name represents the Underlying stock
    "expirydate": "17JUL2025"
}
greekRes = obj.optionGreek(greekParam)
greekRes_pd = pd.DataFrame(greekRes['data'])

# Display complete information about the Greeks data structure
print("\n" + "="*80)
print("📊 GREEKS DATA STRUCTURE ANALYSIS")
print("="*80)

print(f"\n📋 Total records: {len(greekRes_pd)}")
print(f"📋 Total columns: {len(greekRes_pd.columns)}")

print(f"\n📋 Column names:")
for i, col in enumerate(greekRes_pd.columns):
    print(f"   {i+1:2d}. {col}")

print(f"\n📋 Data types:")
print(greekRes_pd.dtypes)

print(f"\n📋 Sample data (first 3 rows):")
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
print(greekRes_pd.head(3).to_string())

print(f"\n📋 Key fields for our project:")
key_fields = ['name', 'expiry', 'strikePrice', 'optionType', 'delta', 'gamma', 'theta', 'vega', 'impliedVolatility']
for field in key_fields:
    if field in greekRes_pd.columns:
        print(f"   ✅ {field}: {greekRes_pd[field].iloc[0] if len(greekRes_pd) > 0 else 'N/A'}")
    else:
        print(f"   ❌ {field}: Not found")

print(f"\n📋 All available fields with sample values:")
for col in greekRes_pd.columns:
    sample_value = greekRes_pd[col].iloc[0] if len(greekRes_pd) > 0 else 'N/A'
    print(f"   {col}: {sample_value}")

# Show sample data for specific strikes
print(f"\n📋 Sample data for specific strikes:")
sample_strikes = [25500, 25600, 25700]
for strike in sample_strikes:
    ce_data = greekRes_pd[(greekRes_pd['strikePrice'] == strike) & (greekRes_pd['optionType'] == 'CE')]
    pe_data = greekRes_pd[(greekRes_pd['strikePrice'] == strike) & (greekRes_pd['optionType'] == 'PE')]
    
    if not ce_data.empty:
        print(f"   Strike {strike} CE: Delta={ce_data['delta'].iloc[0]}, Gamma={ce_data['gamma'].iloc[0]}, IV={ce_data['impliedVolatility'].iloc[0]}")
    if not pe_data.empty:
        print(f"   Strike {strike} PE: Delta={pe_data['delta'].iloc[0]}, Gamma={pe_data['gamma'].iloc[0]}, IV={pe_data['impliedVolatility'].iloc[0]}")


