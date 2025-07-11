import os
import json
import requests

SCRIP_MASTER_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
SCRIP_MASTER_FILE = os.path.join(os.path.dirname(__file__), "OpenAPIScripMaster.json")


def download_scrip_master(force_refresh=False):
    """
    Download the Angel One Scrip Master JSON if not present or if force_refresh is True.
    """
    if not os.path.exists(SCRIP_MASTER_FILE) or force_refresh:
        print("⬇️  Downloading Scrip Master JSON...")
        response = requests.get(SCRIP_MASTER_URL)
        response.raise_for_status()
        with open(SCRIP_MASTER_FILE, "w", encoding="utf-8") as f:
            f.write(response.text)
        print("✅ Scrip Master downloaded.")
    else:
        print("ℹ️  Scrip Master already present.")


def load_scrip_master():
    """
    Load the Scrip Master JSON as a list of dicts.
    """
    if not os.path.exists(SCRIP_MASTER_FILE):
        download_scrip_master()
    with open(SCRIP_MASTER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_token_for_symbol(symbol_name, exchange=None):
    """
    Look up the instrument token for a given symbol name (and optional exchange).
    Returns the token as a string, or None if not found.
    """
    scrips = load_scrip_master()
    symbol_name = symbol_name.upper().replace(" ", "")
    for scrip in scrips:
        scrip_symbol = scrip.get("symbol", "").upper().replace(" ", "")
        if scrip_symbol == symbol_name:
            if exchange is None or scrip.get("exch_seg", "").upper() == exchange.upper():
                return scrip.get("token")
    return None


def search_symbols(partial_name):
    """
    Search for all symbols containing the partial_name (case-insensitive).
    Returns a list of dicts with symbol and token.
    """
    scrips = load_scrip_master()
    partial = partial_name.upper().replace(" ", "")
    results = []
    for scrip in scrips:
        scrip_symbol = scrip.get("symbol", "").upper().replace(" ", "")
        if partial in scrip_symbol:
            results.append({
                "symbol": scrip.get("symbol"),
                "token": scrip.get("token"),
                "exch_seg": scrip.get("exch_seg"),
                "name": scrip.get("name")
            })
    return results


if __name__ == "__main__":
    # Example usage
    download_scrip_master(force_refresh=True)
    print("NIFTY 50 token:", get_token_for_symbol("NIFTY 50"))
    print("BANKNIFTY token:", get_token_for_symbol("BANKNIFTY"))
    print("NIFTY24JUL17500CE token:", get_token_for_symbol("NIFTY24JUL17500CE"))
    print("Search for NIFTY option contracts:")
    for result in search_symbols("NIFTY24JUL"):
        print(result) 