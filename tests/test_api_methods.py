#!/usr/bin/env python3
"""
Test script to check available SmartAPI methods
"""

def test_smartapi_methods():
    print("🔍 Testing SmartAPI methods...")
    
    try:
        from angel_login import angel_login
        
        # Login
        if not angel_login.login():
            print("❌ Failed to login")
            return
        
        smart_api = angel_login.get_smart_api()
        
        # List all available methods
        print("📋 Available methods in SmartAPI:")
        methods = [method for method in dir(smart_api) if not method.startswith('_')]
        for method in sorted(methods):
            print(f"  - {method}")
        
        # Test specific methods that might be related to expiry
        print("\n🔍 Testing expiry-related methods:")
        
        # Try different possible method names
        possible_methods = [
            'getExpiryDate',
            'getExpiryDates', 
            'getExpiry',
            'getExpiries',
            'getOptionExpiry',
            'getOptionExpiries'
        ]
        
        for method_name in possible_methods:
            if hasattr(smart_api, method_name):
                print(f"✅ Found method: {method_name}")
                try:
                    # Try to call it with sample parameters
                    if method_name in ['getExpiryDate', 'getExpiryDates']:
                        result = getattr(smart_api, method_name)("NFO", "NIFTY")
                        print(f"   Result: {result}")
                    else:
                        print(f"   Method exists but parameters unknown")
                except Exception as e:
                    print(f"   Error calling {method_name}: {e}")
            else:
                print(f"❌ Method not found: {method_name}")
        
        # Test option chain methods
        print("\n🔍 Testing option chain methods:")
        option_methods = [
            'getOptionChain',
            'getOptionData',
            'getOptions',
            'getOptionChainData'
        ]
        
        for method_name in option_methods:
            if hasattr(smart_api, method_name):
                print(f"✅ Found method: {method_name}")
            else:
                print(f"❌ Method not found: {method_name}")
        
        # Logout
        angel_login.logout()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_smartapi_methods() 