#!/usr/bin/env python3
"""
Test script to verify smartapi import works
"""

def test_imports():
    print("Testing imports...")
    
    # Test SmartApi (new version)
    try:
        from SmartApi import SmartConnect
        print("✅ SmartApi imported successfully")
        return True
    except Exception as e:
        print(f"❌ SmartApi import failed: {e}")
        
        # Try old version
        try:
            from SmartApi import SmartConnect
            print("✅ smartapi imported successfully")
            return True
        except Exception as e2:
            print(f"❌ smartapi import failed: {e2}")
            return False

def test_login_class():
    print("\nTesting login class...")
    
    try:
        from angel_login import angel_login
        print("✅ angel_login imported successfully")
        return True
    except Exception as e:
        print(f"❌ angel_login import failed: {e}")
        return False

def main():
    print("🚀 Import Test")
    print("=" * 30)
    
    smartapi_ok = test_imports()
    login_ok = test_login_class()
    
    print("\n" + "=" * 30)
    if smartapi_ok and login_ok:
        print("✅ All imports working!")
        print("🚀 You can now run: python main.py")
    else:
        print("❌ Some imports failed")
        print("💡 Try: pip install smartapi-python")

if __name__ == "__main__":
    main() 