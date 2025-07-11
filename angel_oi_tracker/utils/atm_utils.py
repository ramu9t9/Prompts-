def find_atm_strike(index_ltp, index_name):
    """
    Find the At-The-Money (ATM) strike price based on index LTP
    
    Args:
        index_ltp (float): Current LTP of the index
        index_name (str): Name of the index (NIFTY or BANKNIFTY)
    
    Returns:
        int: Nearest ATM strike price
    """
    
    # Strike intervals for different indices
    if index_name.upper() == 'NIFTY':
        strike_interval = 50
    elif index_name.upper() == 'BANKNIFTY':
        strike_interval = 100
    else:
        raise ValueError(f"Unsupported index: {index_name}")
    
    # Calculate nearest strike
    atm_strike = round(index_ltp / strike_interval) * strike_interval
    
    return int(atm_strike)

def get_strike_range(atm_strike, range_strikes=5, index_name='NIFTY'):
    """
    Get a range of strikes around ATM
    
    Args:
        atm_strike (int): ATM strike price
        range_strikes (int): Number of strikes above and below ATM
        index_name (str): Name of the index for strike interval
    
    Returns:
        list: List of strike prices from ATM-range_strikes to ATM+range_strikes
    """
    
    # Strike intervals for different indices
    if index_name.upper() == 'NIFTY':
        strike_interval = 50
    elif index_name.upper() == 'BANKNIFTY':
        strike_interval = 100
    else:
        raise ValueError(f"Unsupported index: {index_name}")
    
    # Generate strike range
    strikes = []
    for i in range(-range_strikes, range_strikes + 1):
        strike = atm_strike + (i * strike_interval)
        strikes.append(strike)
    
    return strikes

def is_atm_strike(strike, index_ltp, index_name):
    """
    Check if a given strike is ATM based on index LTP
    
    Args:
        strike (int): Strike price to check
        index_ltp (float): Current index LTP
        index_name (str): Name of the index
    
    Returns:
        bool: True if strike is ATM, False otherwise
    """
    atm_strike = find_atm_strike(index_ltp, index_name)
    return strike == atm_strike 