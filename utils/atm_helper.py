# utils/atm_helper.py
def get_atm_strike(index_price, symbol):
    if symbol == "NIFTY":
        return round(index_price / 50) * 50
    elif symbol == "BANKNIFTY":
        return round(index_price / 100) * 100
    return None
