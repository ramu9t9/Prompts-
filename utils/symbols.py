# utils/symbols.py

from utils.atm_utils import get_atm_strike
from utils.strike_range import get_strike_range

def generate_token(index, expiry, strike, option_type):
    return f"{index}{expiry}{strike}{option_type}"

def get_exchange_tokens(obj, index, expiry, atm, strike_gap=100, range_count=5):
    """
    Returns a list of option trading symbols (e.g., BANKNIFTY11JUL247900CE)
    within ATM ± range_count strikes.
    """
    exchange = "NFO"
    tokens = []

    strike_list = get_strike_range(atm, gap=strike_gap, count=range_count)

    for strike in strike_list:
        ce_token = generate_token(index, expiry, strike, "CE")
        pe_token = generate_token(index, expiry, strike, "PE")
        tokens.append(ce_token)
        tokens.append(pe_token)

    return {exchange: tokens}
