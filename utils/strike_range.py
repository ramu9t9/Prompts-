# utils/strike_range.py

def get_strike_range(atm_strike: int, width: int = 5) -> list:
    """
    Returns a list of strike prices around the ATM.
    E.g., ATM = 45000, width = 5 ⇒ [44900, 45000, 45100, ..., 45500]
    """
    strikes = []
    for i in range(-width, width + 1):
        strikes.append(atm_strike + (i * 100))  # 100-point gap
    return sorted(strikes)
