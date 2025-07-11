import pyotp
from SmartApi import SmartConnect

def login():
    api_key = "P9ErUZG0"
    token_1 = "Y4GDOA6SL5VOCKQPFLR5EM3HOY"
    client_id = "R117172"
    pin = 9029

    try:
        obj = SmartConnect(api_key)
        totp = pyotp.TOTP(token_1).now()
        data = obj.generateSession(client_id, pin, totp)
        print("✅ Logged in as", data['data']['name'])

        return {
            "smartapi": obj,
            "auth_token": data["data"]["jwtToken"],
            "refresh_token": data["data"]["refreshToken"],
            "feed_token": obj.getfeedToken()
        }

    except Exception as e:
        print("❌ Login failed:", str(e))
        return None
