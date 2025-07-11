#!/usr/bin/env python3
"""
Simple test to isolate SmartConnect initialization
"""

def test_smartconnect():
    print("🔧 Testing SmartConnect initialization...")
    
    try:
        from SmartApi import SmartConnect
        print("✅ SmartApi import successful")
        
        # Test with just api_key
        api_key = "P9ErUZG0"  # Your API key
        smart_api = SmartConnect(api_key=api_key)
        print("✅ SmartConnect created with api_key only")
        
        return True
        
    except Exception as e:
        print(f"❌ SmartConnect error: {e}")
        return False

def test_angel_login_class():
    print("\n🔧 Testing AngelOneLogin class...")
    
    try:
        from angel_login import AngelOneLogin
        
        login_instance = AngelOneLogin()
        print("✅ AngelOneLogin instance created")
        
        # Test credential loading
        login_instance.load_credentials()
        print("✅ Credentials loaded")
        
        # Test SmartConnect creation
        from SmartApi import SmartConnect
        smart_api = SmartConnect(api_key=login_instance.api_key)
        print("✅ SmartConnect created in class context")
        
        return True
        
    except Exception as e:
        print(f"❌ AngelOneLogin error: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Simple SmartConnect Test")
    print("=" * 40)
    
    test1 = test_smartconnect()
    test2 = test_angel_login_class()
    
    print("\n" + "=" * 40)
    print(f"Direct SmartConnect: {'✅' if test1 else '❌'}")
    print(f"Class SmartConnect: {'✅' if test2 else '❌'}") 