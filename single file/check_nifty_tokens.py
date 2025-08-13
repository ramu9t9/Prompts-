#!/usr/bin/env python3
"""
Check NIFTY Tokens
"""

import requests

def check_nifty_tokens():
    print("🔍 Checking NIFTY tokens...")
    
    try:
        response = requests.get("https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json")
        instruments = response.json()
        
        nifty_tokens = []
        
        for instrument in instruments:
            name = instrument.get('name', '')
            exch_seg = instrument.get('exch_seg', '')
            symbol = instrument.get('symbol', '')
            token = instrument.get('token', '')
            
            if 'NIFTY' in name and exch_seg == 'NSE':
                nifty_tokens.append({
                    'name': name,
                    'symbol': symbol,
                    'token': token,
                    'exch_seg': exch_seg
                })
        
        print(f"📊 Found {len(nifty_tokens)} NIFTY NSE instruments:")
        
        for i, token_info in enumerate(nifty_tokens):
            print(f"   {i+1}. {token_info['name']} - {token_info['symbol']} - Token: {token_info['token']}")
        
        # Look for specific NIFTY index
        for token_info in nifty_tokens:
            if 'NIFTY' in token_info['name'] and '500' not in token_info['name']:
                print(f"\n🎯 Potential NIFTY index: {token_info['name']} - Token: {token_info['token']}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_nifty_tokens()
