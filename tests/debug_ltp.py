#!/usr/bin/env python3
"""
Debug script to test LTP fetching for indices
"""

def test_ltp_fetching():
    print("🔍 Testing LTP fetching for indices...")
    
    try:
        from angel_login import angel_login
        
        # Login
        if not angel_login.login():
            print("❌ Failed to login")
            return
        
        smart_api = angel_login.get_smart_api()
        
        # Test NIFTY with correct token and symbol
        print("\n📊 Testing NIFTY...")
        try:
            nifty_ltp = smart_api.ltpData("NSE", "NIFTY", "99926000")
            print(f"NIFTY Response: {nifty_ltp}")
            if nifty_ltp['status']:
                print(f"✅ NIFTY LTP: {nifty_ltp['data']['ltp']}")
            else:
                print(f"❌ NIFTY Error: {nifty_ltp.get('message', 'Unknown error')}")
        except Exception as e:
            print(f"❌ NIFTY Exception: {e}")
        
        # Test BANKNIFTY with correct token and symbol
        print("\n📊 Testing BANKNIFTY...")
        try:
            banknifty_ltp = smart_api.ltpData("NSE", "BANKNIFTY", "99926009")
            print(f"BANKNIFTY Response: {banknifty_ltp}")
            if banknifty_ltp['status']:
                print(f"✅ BANKNIFTY LTP: {banknifty_ltp['data']['ltp']}")
            else:
                print(f"❌ BANKNIFTY Error: {banknifty_ltp.get('message', 'Unknown error')}")
        except Exception as e:
            print(f"❌ BANKNIFTY Exception: {e}")
        
        # Test with alternative symbol names from the JSON
        print("\n📊 Testing alternative symbol names...")
        test_cases = [
            ("NIFTY", "99926000"),
            ("BANKNIFTY", "99926009"),
            ("NIFTY 50", "99926000"),
            ("NIFTY BANK", "99926009"),
            ("NIFTY50", "99926000"),
            ("NIFTYBANK", "99926009")
        ]
        
        for symbol, token in test_cases:
            try:
                ltp = smart_api.ltpData("NSE", symbol, token)
                print(f"{symbol} (token: {token}) Response: {ltp}")
                if ltp['status']:
                    print(f"✅ {symbol} LTP: {ltp['data']['ltp']}")
                else:
                    print(f"❌ {symbol} Error: {ltp.get('message', 'Unknown error')}")
            except Exception as e:
                print(f"❌ {symbol} Exception: {e}")
        
        # Logout
        angel_login.logout()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_ltp_fetching() 