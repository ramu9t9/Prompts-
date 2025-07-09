def get_atm_strike(index_ltp: float, symbol: str, strike_interval: int = 50) -> int:
    """
    Returns the nearest ATM strike for the given index LTP and symbol.
    Rounds to the nearest strike based on interval (default: 50).
    """
    if symbol == "NIFTY":
        strike_interval = 50
    elif symbol == "BANKNIFTY":
        strike_interval = 100
    return round(index_ltp / strike_interval) * strike_interval
