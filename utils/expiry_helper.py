# utils/expiry_helper.py
import datetime

def get_latest_expiry(expiry_list):
    """
    Return nearest expiry from list (sorted ascending).
    """
    today = datetime.date.today()
    expiry_list = sorted([datetime.datetime.strptime(x, "%d%b%y").date() for x in expiry_list])
    for expiry in expiry_list:
        if expiry >= today:
            return expiry.strftime("%d%b%y").upper()
    return None
