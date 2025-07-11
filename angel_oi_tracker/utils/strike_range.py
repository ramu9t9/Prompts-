from .atm_utils import find_atm_strike, get_strike_range

def get_filtered_strikes(index_ltp, index_name, range_strikes=5):
    """
    Get filtered strikes around ATM for a given index
    
    Args:
        index_ltp (float): Current LTP of the index
        index_name (str): Name of the index (NIFTY or BANKNIFTY)
        range_strikes (int): Number of strikes above and below ATM to include
    
    Returns:
        dict: Dictionary with ATM strike and filtered strike range
    """
    
    # Find ATM strike
    atm_strike = find_atm_strike(index_ltp, index_name)
    
    # Get strike range around ATM
    strikes = get_strike_range(atm_strike, range_strikes, index_name)
    
    return {
        'atm_strike': atm_strike,
        'strikes': strikes,
        'min_strike': min(strikes),
        'max_strike': max(strikes)
    }

def filter_option_chain_by_strikes(option_chain_data, target_strikes):
    """
    Filter option chain data to include only specified strikes
    
    Args:
        option_chain_data (list): Raw option chain data from Angel One
        target_strikes (list): List of strike prices to include
    
    Returns:
        list: Filtered option chain data
    """
    
    filtered_data = []
    target_strikes_set = set(target_strikes)
    
    for option in option_chain_data:
        if option.get('strikePrice') in target_strikes_set:
            filtered_data.append(option)
    
    return filtered_data

def get_strike_range_for_tokens(index_ltp, index_name, range_strikes=5):
    """
    Get strike range and prepare for token filtering
    
    Args:
        index_ltp (float): Current LTP of the index
        index_name (str): Name of the index
        range_strikes (int): Number of strikes around ATM
    
    Returns:
        dict: Complete strike range information for token filtering
    """
    
    strike_info = get_filtered_strikes(index_ltp, index_name, range_strikes)
    
    return {
        'index_name': index_name,
        'index_ltp': index_ltp,
        'atm_strike': strike_info['atm_strike'],
        'strikes': strike_info['strikes'],
        'range_strikes': range_strikes,
        'total_strikes': len(strike_info['strikes'])
    } 