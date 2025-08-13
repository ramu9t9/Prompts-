#!/usr/bin/env python3
"""
Debug Instrument Fetch
"""

import requests
import json

def debug_instruments():
    print("🔍 Debugging instrument fetch...")
    
    try:
        print("📥 Fetching instruments from Angel Broking...")
        response = requests.get("https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json")
        
        if response.status_code != 200:
            print(f"❌ HTTP Error: {response.status_code}")
            return
        
        instruments = response.json()
        print(f"📊 Total instruments: {len(instruments)}")
        
        # Check for NIFTY instruments
        nifty_instruments = []
        nifty50_instruments = []
        
        for instrument in instruments:
            name = instrument.get('name', '')
            exch_seg = instrument.get('exch_seg', '')
            instrumenttype = instrument.get('instrumenttype', '')
            symbol = instrument.get('symbol', '')
            
            if 'NIFTY' in name and exch_seg == 'NFO':
                nifty_instruments.append({
                    'name': name,
                    'symbol': symbol,
                    'instrumenttype': instrumenttype,
                    'token': instrument.get('token', ''),
                    'exch_seg': exch_seg
                })
            
            if 'NIFTY 50' in name and exch_seg == 'NSE':
                nifty50_instruments.append({
                    'name': name,
                    'symbol': symbol,
                    'instrumenttype': instrumenttype,
                    'token': instrument.get('token', ''),
                    'exch_seg': exch_seg
                })
        
        print(f"\n📈 NIFTY NFO instruments: {len(nifty_instruments)}")
        print(f"📊 NIFTY 50 NSE instruments: {len(nifty50_instruments)}")
        
        if nifty_instruments:
            print("\n📋 Sample NIFTY NFO instruments:")
            for i, inst in enumerate(nifty_instruments[:10]):
                print(f"   {i+1}. {inst['name']} - {inst['symbol']} - {inst['instrumenttype']} - Token: {inst['token']}")
        
        if nifty50_instruments:
            print("\n📋 NIFTY 50 NSE instruments:")
            for inst in nifty50_instruments:
                print(f"   {inst['name']} - {inst['symbol']} - Token: {inst['token']}")
        
        # Check for CE/PE instruments specifically
        ce_instruments = [inst for inst in nifty_instruments if inst['instrumenttype'] == 'CE']
        pe_instruments = [inst for inst in nifty_instruments if inst['instrumenttype'] == 'PE']
        
        print(f"\n📊 CE instruments: {len(ce_instruments)}")
        print(f"📊 PE instruments: {len(pe_instruments)}")
        
        if ce_instruments:
            print("\n📋 Sample CE instruments:")
            for i, inst in enumerate(ce_instruments[:5]):
                print(f"   {i+1}. {inst['symbol']} - Token: {inst['token']}")
        
        if pe_instruments:
            print("\n📋 Sample PE instruments:")
            for i, inst in enumerate(pe_instruments[:5]):
                print(f"   {i+1}. {inst['symbol']} - Token: {inst['token']}")
        
        # Check for current expiry instruments
        current_month_ce = [inst for inst in ce_instruments if 'AUG' in inst['symbol']]
        current_month_pe = [inst for inst in pe_instruments if 'AUG' in inst['symbol']]
        
        print(f"\n📅 Current month (AUG) CE: {len(current_month_ce)}")
        print(f"📅 Current month (AUG) PE: {len(current_month_pe)}")
        
        if current_month_ce:
            print("\n📋 Sample current month CE:")
            for i, inst in enumerate(current_month_ce[:3]):
                print(f"   {i+1}. {inst['symbol']} - Token: {inst['token']}")
        
        if current_month_pe:
            print("\n📋 Sample current month PE:")
            for i, inst in enumerate(current_month_pe[:3]):
                print(f"   {i+1}. {inst['symbol']} - Token: {inst['token']}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    debug_instruments()
