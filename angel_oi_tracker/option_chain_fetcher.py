"""
Option Chain Data Fetcher Module

This module fetches real-time option chain data from Angel One SmartAPI.
Always refer to official documentation: https://smartapi.angelone.in/docs

API Compliance:
- Rate Limits: https://smartapi.angelone.in/docs/rate-limits
- Data Usage: Use data only for authorized purposes
- Terms of Service: Follow Angel One's terms and conditions
"""

import time
from datetime import datetime, timedelta
import pytz
from utils.symbols import get_index_token, INDEX_TOKENS
from utils.strike_range import get_filtered_strikes, filter_option_chain_by_strikes
from utils.scrip_master import get_token_for_symbol, search_symbols

class OptionChainFetcher:
    def __init__(self, smart_api):
        self.smart_api = smart_api
        self.ist_tz = pytz.timezone('Asia/Kolkata')
        
    def get_index_ltp(self, index_name):
        """Get current LTP for the given index"""
        try:
            token = get_index_token(index_name)
            if not token:
                raise ValueError(f"Invalid index name: {index_name}")
            
            # Get LTP for the index using the correct API method
            ltp_data = self.smart_api.ltpData("NSE", index_name, str(token))
            
            if ltp_data['status'] and ltp_data['data']:
                return float(ltp_data['data']['ltp'])
            else:
                raise Exception(f"Failed to get LTP for {index_name}: {ltp_data.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"❌ Error getting LTP for {index_name}: {str(e)}")
            return None
    
    def get_expiry_date(self, index_name):
        """
        Get the current month expiry date for the given index.
        Since SmartAPI doesn't have a direct method, we'll use a workaround.
        """
        try:
            # For now, let's use the current month's last Thursday
            # This is a simplified approach - in production, you'd want to get this from the exchange
            now = datetime.now(self.ist_tz)
            
            # Find the last Thursday of the current month
            last_day = (now.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
            last_thursday = last_day - timedelta(days=(last_day.weekday() - 3) % 7)
            
            # If today is past the last Thursday, use next month's last Thursday
            if now > last_thursday:
                next_month = (now.replace(day=1) + timedelta(days=32)).replace(day=1)
                last_day_next = (next_month.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
                last_thursday = last_day_next - timedelta(days=(last_day_next.weekday() - 3) % 7)
            
            expiry_date = last_thursday.strftime('%Y-%m-%d')
            print(f"📅 Using expiry date for {index_name}: {expiry_date}")
            return expiry_date
            
        except Exception as e:
            print(f"❌ Error getting expiry date for {index_name}: {str(e)}")
            return None
    
    def get_option_contracts_for_strikes(self, index_name, expiry_date, strikes):
        """Get actual option contract symbols and tokens for given strikes"""
        contracts = []
        
        # Convert expiry date to required format (DDMMMYY)
        expiry_obj = datetime.strptime(expiry_date, '%Y-%m-%d')
        expiry_str = expiry_obj.strftime('%d%b%y').upper()
        
        for strike in strikes:
            # Generate CE and PE symbol names
            ce_symbol = f"{index_name}{expiry_str}{strike}CE"
            pe_symbol = f"{index_name}{expiry_str}{strike}PE"
            
            # Get tokens from scrip master
            ce_token = get_token_for_symbol(ce_symbol, "NFO")
            pe_token = get_token_for_symbol(pe_symbol, "NFO")
            
            if ce_token:
                contracts.append({
                    'symbol': ce_symbol,
                    'token': ce_token,
                    'strike': strike,
                    'type': 'CE'
                })
            
            if pe_token:
                contracts.append({
                    'symbol': pe_symbol,
                    'token': pe_token,
                    'strike': strike,
                    'type': 'PE'
                })
        
        return contracts
    
    def get_market_data_for_options(self, option_contracts):
        """Get market data (LTP, OI, Volume) for option contracts using getMarketData"""
        try:
            if not option_contracts:
                return {}
            
            # Prepare exchange tokens for getMarketData
            exchange_tokens = {
                "NFO": [str(contract['token']) for contract in option_contracts]
            }
            
            print(f"📊 Fetching market data for {len(option_contracts)} option contracts...")
            
            # Get market data using getMarketData API
            response = self.smart_api.getMarketData("FULL", exchange_tokens)
            
            market_data = {}
            
            if response['status'] and 'data' in response and 'fetched' in response['data']:
                for item in response['data']['fetched']:
                    symbol_token = item.get('symbolToken')
                    if symbol_token:
                        market_data[symbol_token] = {
                            'ltp': float(item.get('ltp', 0)),
                            'volume': int(item.get('tradeVolume', item.get('volume', 0))),
                            'oi': int(item.get('opnInterest', item.get('oi', item.get('openInterest', 0)))),
                            'change': float(item.get('netChange', item.get('change', 0))),
                            'change_percent': float(item.get('pChange', item.get('percentChange', 0))),
                            'open': float(item.get('open', 0)),
                            'high': float(item.get('high', 0)),
                            'low': float(item.get('low', 0)),
                            'close': float(item.get('close', 0))
                        }
                
                print(f"✅ Successfully fetched market data for {len(market_data)} contracts")
            else:
                print(f"⚠️  No market data received: {response.get('message', 'Unknown error')}")
            
            return market_data
            
        except Exception as e:
            print(f"❌ Error fetching market data: {str(e)}")
            return {}
    
    def get_option_greeks(self, index_name, expiry_date):
        """Get Greeks and IV for options using optionGreek API"""
        try:
            # Convert expiry date to required format (DDMMMYYYY)
            expiry_obj = datetime.strptime(expiry_date, '%Y-%m-%d')
            expiry_str = expiry_obj.strftime('%d%b%Y').upper()
            
            print(f"📊 Fetching Greeks for {index_name} {expiry_str}...")
            
            greek_params = {
                "name": index_name,
                "expirydate": expiry_str
            }
            
            # Get Greeks using optionGreek API
            response = self.smart_api.optionGreek(greek_params)
            
            greeks_data = {}
            
            if response['status'] and 'data' in response:
                for row in response['data']:
                    strike = float(row.get('strikePrice', row.get('strike', 0)))
                    option_type = row.get('optionType', row.get('type', ''))
                    
                    # Create key for easy lookup
                    key = f"{strike}_{option_type}"
                    
                    greeks_data[key] = {
                        'delta': float(row.get('delta', 0)),
                        'gamma': float(row.get('gamma', 0)),
                        'theta': float(row.get('theta', 0)),
                        'vega': float(row.get('vega', 0)),
                        'iv': float(row.get('impliedVolatility', row.get('iv', 0)))
                    }
                
                print(f"✅ Successfully fetched Greeks for {len(greeks_data)} option types")
            else:
                print(f"⚠️  No Greeks data received: {response.get('message', 'Unknown error')}")
            
            return greeks_data
            
        except Exception as e:
            print(f"❌ Error fetching Greeks: {str(e)}")
            return {}
    
    def fetch_option_chain_data(self, index_name, expiry_date, range_strikes=5):
        """Fetch complete option chain data including OI and Greeks"""
        try:
            # Get index LTP first
            index_ltp = self.get_index_ltp(index_name)
            if not index_ltp:
                return None
            
            print(f"📈 {index_name} LTP: {index_ltp}")
            
            # Get filtered strikes around ATM
            strike_info = get_filtered_strikes(index_ltp, index_name, range_strikes)
            atm_strike = strike_info['atm_strike']
            target_strikes = strike_info['strikes']
            
            print(f"🎯 ATM Strike: {atm_strike}")
            print(f"📋 Target Strikes: {target_strikes}")
            
            # Get actual option contracts for these strikes
            option_contracts = self.get_option_contracts_for_strikes(index_name, expiry_date, target_strikes)
            
            if not option_contracts:
                print(f"⚠️  No option contracts found for {index_name}")
                return None
            
            print(f"📊 Found {len(option_contracts)} option contracts")
            
            # Get market data (LTP, OI, Volume) for all contracts
            market_data = self.get_market_data_for_options(option_contracts)
            
            # Get Greeks data for the index and expiry
            greeks_data = self.get_option_greeks(index_name, expiry_date)
            
            # Prepare option data using DataFrame mapping
            option_data = []
            for contract in option_contracts:
                symbol = contract['symbol']
                token = str(contract['token'])
                strike = float(contract['strike'])
                option_type = contract['type']
                
                # Get market data
                contract_market_data = market_data.get(token, {})
                
                # Compute percentChange if not present
                ltp = contract_market_data.get('ltp', 0)
                close = contract_market_data.get('close', 0)
                percent_change = contract_market_data.get('percentChange')
                if percent_change is None:
                    percent_change = ((ltp - close) / close * 100) if close else 0
                
                # Merge Greeks data
                greek_key = f"{strike}_{option_type}"
                contract_greeks = greeks_data.get(greek_key, {})
                
                option_info = {
                    'symbol': symbol,
                    'token': token,
                    'strike': strike,
                    'type': option_type,
                    'ltp': ltp,
                    'open': contract_market_data.get('open', 0),
                    'high': contract_market_data.get('high', 0),
                    'low': contract_market_data.get('low', 0),
                    'close': close,
                    'change': contract_market_data.get('change', 0),
                    'change_percent': percent_change,
                    'volume': contract_market_data.get('volume', 0),
                    'oi': contract_market_data.get('oi', 0),
                    'depth': contract_market_data.get('depth', {}),
                    'delta': contract_greeks.get('delta', 0),
                    'gamma': contract_greeks.get('gamma', 0),
                    'theta': contract_greeks.get('theta', 0),
                    'vega': contract_greeks.get('vega', 0),
                    'iv': contract_greeks.get('iv', 0)
                }
                option_data.append(option_info)
                time.sleep(0.05)
            
            if not option_data:
                print(f"⚠️  No option data fetched for {index_name}")
                return None
            
            print(f"✅ Fetched complete data for {len(option_data)} options")
            
            return {
                'index_name': index_name,
                'index_ltp': index_ltp,
                'atm_strike': atm_strike,
                'expiry_date': expiry_date,
                'options': option_data,
                'timestamp': datetime.now(self.ist_tz)
            }
        except Exception as e:
            print(f"❌ Error fetching option chain data for {index_name}: {str(e)}")
            return None
    
    def fetch_index_data(self, index_name, range_strikes=5):
        """Fetch complete data for a single index"""
        try:
            print(f"📊 Fetching data for {index_name}...")
            
            # Get expiry date
            expiry_date = self.get_expiry_date(index_name)
            if not expiry_date:
                print(f"❌ Failed to get expiry for {index_name}")
                return None
            
            # Fetch option chain data
            option_chain_data = self.fetch_option_chain_data(index_name, expiry_date, range_strikes)
            if not option_chain_data:
                print(f"⚠️  No option chain data available for {index_name}")
                return None
            
            return option_chain_data
            
        except Exception as e:
            print(f"❌ Error fetching data for {index_name}: {str(e)}")
            return None
    
    def fetch_all_indices_data(self, range_strikes=5):
        """Fetch data for all supported indices"""
        all_data = []
        
        for index_name in INDEX_TOKENS.keys():
            data = self.fetch_index_data(index_name, range_strikes)
            if data:
                all_data.append(data)
            else:
                print(f"⚠️  Failed to fetch data for {index_name}")
            
            # Small delay between indices
            time.sleep(1)
        
        return all_data

def fetch_option_chain_data(smart_api, ts_override=None):
    """
    Main function to fetch option chain data
    
    Args:
        smart_api: SmartAPI instance
        ts_override: Optional timestamp override for backfill
    
    Returns:
        dict: Processed option chain data for all indices
    """
    fetcher = OptionChainFetcher(smart_api)
    
    # Use override timestamp if provided (for backfill)
    if ts_override:
        print(f"🕐 Using override timestamp: {ts_override}")
    
    # Fetch data for all indices
    all_data = fetcher.fetch_all_indices_data(range_strikes=5)
    
    if not all_data:
        print("❌ No data fetched for any index")
        return None
    
    print(f"✅ Successfully fetched data for {len(all_data)} indices")
    return all_data 