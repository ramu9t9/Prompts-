# Exchange tokens for NIFTY and BANKNIFTY indices
# These are the instrument tokens used to get current LTP for ATM calculation
# Updated with correct Angel One instrument tokens from OpenAPI Scrip Master

# NIFTY 50 index - token from OpenAPI Scrip Master
NIFTY_TOKEN = 99926000  # "Nifty 50" from the JSON

# BANKNIFTY index - token from OpenAPI Scrip Master  
BANKNIFTY_TOKEN = 99926009  # "Nifty Bank" with name "BANKNIFTY" from the JSON

# Dictionary mapping index names to their tokens
INDEX_TOKENS = {
    'NIFTY': NIFTY_TOKEN,
    'BANKNIFTY': BANKNIFTY_TOKEN
}

def get_index_token(index_name):
    """Get the exchange token for a given index"""
    return INDEX_TOKENS.get(index_name.upper())

def get_all_index_tokens():
    """Get all available index tokens"""
    return INDEX_TOKENS.copy()

def is_valid_index(index_name):
    """Check if the given index name is valid"""
    return index_name.upper() in INDEX_TOKENS 