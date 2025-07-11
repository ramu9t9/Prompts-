#!/usr/bin/env python3
"""
Debug script to test login process
"""

def test_credentials():
    print("🔐 Testing credentials...")
    
    try:
        from angel_login import angel_login
        
        # Load credentials
        angel_login.load_credentials()
        
        print(f"API Key: {angel_login.api_key}")
        print(f"Client ID: {angel_login.client_id}")
        print(f"Password: {angel_login.pwd}")
        print(f"TOTP Key: {angel_login.totp_key}")
        print(f"Session Secret: {angel_login.session_secret}")
        
        # Check if all required fields are present
        required_fields = ['api_key', 'client_id', 'pwd', 'totp_key']
        missing_fields = []
        
        for field in required_fields:
            if not getattr(angel_login, field):
                missing_fields.append(field)
        
        if missing_fields:
            print(f"❌ Missing fields: {missing_fields}")
            return False
        else:
            print("✅ All credentials present")
            return True
            
    except Exception as e:
        print(f"❌ Error loading credentials: {e}")
        return False

def test_totp():
    print("\n🔢 Testing TOTP generation...")
    
    try:
        from angel_login import angel_login
        
        totp = angel_login.generate_totp()
        print(f"✅ TOTP generated: {totp}")
        return True
        
    except Exception as e:
        print(f"❌ TOTP generation failed: {e}")
        return False

def test_smartapi_connection():
    print("\n🌐 Testing SmartAPI connection...")
    
    try:
        from angel_login import angel_login
        
        if not angel_login.api_key:
            print("❌ No API key available")
            return False
        
        # Try to create SmartConnect instance
        from SmartApi import SmartConnect
        
        smart_api = SmartConnect(api_key=angel_login.api_key)
        print("✅ SmartConnect instance created")
        
        # Try to generate session
        totp = angel_login.generate_totp()
        print(f"Using TOTP: {totp}")
        
        data = smart_api.generateSession(angel_login.client_id, angel_login.pwd, totp)
        print(f"Login response: {data}")
        
        if data.get('status'):
            print("✅ Login successful!")
            return True
        else:
            print(f"❌ Login failed: {data.get('message', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ SmartAPI connection failed: {e}")
        return False

def main():
    print("🚀 Angel One Login Debug")
    print("=" * 40)
    
    # Test 1: Credentials
    creds_ok = test_credentials()
    
    # Test 2: TOTP
    totp_ok = test_totp()
    
    # Test 3: SmartAPI connection
    if creds_ok and totp_ok:
        api_ok = test_smartapi_connection()
    else:
        api_ok = False
    
    print("\n" + "=" * 40)
    print("📊 DEBUG SUMMARY:")
    print(f"Credentials: {'✅' if creds_ok else '❌'}")
    print(f"TOTP: {'✅' if totp_ok else '❌'}")
    print(f"SmartAPI: {'✅' if api_ok else '❌'}")
    
    if creds_ok and totp_ok and api_ok:
        print("\n🎉 All tests passed! Login should work.")
    else:
        print("\n⚠️  Some tests failed. Check the errors above.")

if __name__ == "__main__":
    main() 