"""
Upgraded Option Chain Data Fetcher Module

This module implements adaptive polling with 20-second intervals and 3-minute bucket snapshots.
Uses getMarketData for OI and getCandleData for close prices.

Key Features:
- 20-second polling loop
- OI change detection
- 3-minute bucket alignment
- getCandleData integration for index close prices
- In-memory previous snapshot comparison

Always refer to official documentation: https://smartapi.angelone.in/docs
"""

import time
import math
from datetime import datetime, timedelta
import pytz
from utils.symbols import get_index_token, INDEX_TOKENS
from utils.strike_range import get_filtered_strikes, filter_option_chain_by_strikes
from utils.scrip_master import get_token_for_symbol, search_symbols

class AdaptiveOptionChainFetcher:
    def __init__(self, smart_api):
        self.smart_api = smart_api
        self.ist_tz = pytz.timezone('Asia/Kolkata')
        
        # In-memory storage for previous snapshots
        self.previous_snapshots = {}  # key: (index_name, expiry, strike), value: snapshot_data
        self.last_bucket_time = {}    # key: index_name, value: last 3-min bucket timestamp
        
    def floor_to_3min(self, timestamp):
        """Floor timestamp to the nearest 3-minute bucket"""
        # Convert to minutes since midnight, floor to 3-minute intervals
        minutes_since_midnight = timestamp.hour * 60 + timestamp.minute
        floored_minutes = (minutes_since_midnight // 3) * 3
        
        # Create new timestamp with floored minutes
        floored_time = timestamp.replace(minute=floored_minutes, second=0, microsecond=0)
        return floored_time
    
    def get_index_candle_data(self, index_name, timestamp):
        """Get 3-minute candle data for the index using getCandleData"""
        try:
            token = get_index_token(index_name)
            if not token:
                raise ValueError(f"Invalid index name: {index_name}")
            
            # Floor timestamp to 3-minute bucket
            bucket_time = self.floor_to_3min(timestamp)
            
            # Convert to required format for getCandleData
            # Format: YYYY-MM-DD HH:MM:SS
            from_time = bucket_time.strftime('%Y-%m-%d %H:%M:%S')
            to_time = (bucket_time + timedelta(minutes=3)).strftime('%Y-%m-%d %H:%M:%S')
            
            print(f"📊 Fetching candle data for {index_name} from {from_time} to {to_time}")
            
            # Get candle data using getCandleData API
            candle_params = {
                "exchange": "NSE",
                "symboltoken": str(token),
                "interval": "THREE_MINUTE",
                "fromdate": from_time,
                "todate": to_time
            }
            
            response = self.smart_api.getCandleData(candle_params)
            
            if response['status'] and 'data' in response and response['data']:
                # Get the first (and should be only) candle for this 3-minute period
                candle = response['data'][0]
                
                candle_data = {
                    'open': float(candle.get('open', 0)),
                    'high': float(candle.get('high', 0)),
                    'low': float(candle.get('low', 0)),
                    'close': float(candle.get('close', 0)),
                    'volume': int(candle.get('volume', 0))
                }
                
                print(f"✅ Candle data for {index_name}: O={candle_data['open']}, H={candle_data['high']}, L={candle_data['low']}, C={candle_data['close']}")
                return candle_data
            else:
                print(f"⚠️  No candle data received for {index_name}: {response.get('message', 'Unknown error')}")
                return None
                
        except Exception as e:
            print(f"❌ Error getting candle data for {index_name}: {str(e)}")
            return None
    
    def get_option_market_data(self, option_contracts):
        """Get market data (OI, LTP, Volume) for option contracts using getMarketData"""
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
                            'change_percent': float(item.get('pChange', item.get('percentChange', 0)))
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
    
    def detect_oi_changes(self, current_data, index_name, expiry_date):
        """Detect OI changes compared to previous snapshot"""
        changes_detected = []
        
        for option in current_data:
            strike = option['strike']
            option_type = option['type']
            current_oi = option.get('oi', 0)
            
            # Create key for previous snapshot lookup
            key = (index_name, expiry_date, strike)
            
            if key in self.previous_snapshots:
                prev_data = self.previous_snapshots[key]
                prev_oi = prev_data.get(f'{option_type.lower()}_oi', 0)
                
                # Check if OI has changed
                if current_oi != prev_oi:
                    changes_detected.append({
                        'strike': strike,
                        'type': option_type,
                        'prev_oi': prev_oi,
                        'current_oi': current_oi,
                        'change': current_oi - prev_oi
                    })
        
        return changes_detected
    
    def update_previous_snapshots(self, current_data, index_name, expiry_date):
        """Update in-memory previous snapshots"""
        for option in current_data:
            strike = option['strike']
            option_type = option['type']
            
            key = (index_name, expiry_date, strike)
            
            if key not in self.previous_snapshots:
                self.previous_snapshots[key] = {}
            
            self.previous_snapshots[key][f'{option_type.lower()}_oi'] = option.get('oi', 0)
            self.previous_snapshots[key][f'{option_type.lower()}_ltp'] = option.get('ltp', 0)
    
    def fetch_complete_option_data(self, index_name, expiry_date, range_strikes=5):
        """Fetch complete option chain data with OI change detection"""
        try:
            current_time = datetime.now(self.ist_tz)
            bucket_time = self.floor_to_3min(current_time)
            
            print(f"🔄 Fetching option data for {index_name} at {current_time.strftime('%H:%M:%S')} (bucket: {bucket_time.strftime('%H:%M:%S')})")
            
            # Get index LTP for ATM calculation
            index_ltp = self.get_index_ltp(index_name)
            if not index_ltp:
                print(f"❌ Failed to get index LTP for {index_name}")
                return None
            
            # Get filtered strikes around ATM
            strikes_info = get_filtered_strikes(index_ltp, index_name, range_strikes)
            target_strikes = strikes_info['strikes']
            
            # Get option contracts for these strikes
            option_contracts = self.get_option_contracts_for_strikes(index_name, expiry_date, target_strikes)
            
            if not option_contracts:
                print(f"❌ No option contracts found for {index_name}")
                return None
            
            # Get market data for options
            market_data = self.get_option_market_data(option_contracts)
            
            # Get Greeks data
            greeks_data = self.get_option_greeks(index_name, expiry_date)
            
            # Combine all data
            complete_data = []
            for contract in option_contracts:
                token = str(contract['token'])
                if token in market_data:
                    market_info = market_data[token]
                    
                    # Get Greeks for this option
                    greek_key = f"{contract['strike']}_{contract['type']}"
                    greeks = greeks_data.get(greek_key, {})
                    
                    option_data = {
                        'symbol': contract['symbol'],
                        'token': contract['token'],
                        'strike': contract['strike'],
                        'type': contract['type'],
                        'ltp': market_info['ltp'],
                        'volume': market_info['volume'],
                        'oi': market_info['oi'],
                        'change': market_info['change'],
                        'change_percent': market_info['change_percent'],
                        'delta': greeks.get('delta', 0),
                        'gamma': greeks.get('gamma', 0),
                        'theta': greeks.get('theta', 0),
                        'vega': greeks.get('vega', 0),
                        'iv': greeks.get('iv', 0)
                    }
                    
                    complete_data.append(option_data)
            
            # Detect OI changes
            oi_changes = self.detect_oi_changes(complete_data, index_name, expiry_date)
            
            # Update previous snapshots
            self.update_previous_snapshots(complete_data, index_name, expiry_date)
            
            # Check if we need to save to database
            should_save = False
            if oi_changes:
                print(f"📈 OI changes detected: {len(oi_changes)} options")
                should_save = True
            
            # Check if bucket time has changed
            if index_name not in self.last_bucket_time or self.last_bucket_time[index_name] != bucket_time:
                print(f"🕐 New 3-minute bucket: {bucket_time.strftime('%H:%M:%S')}")
                should_save = True
                self.last_bucket_time[index_name] = bucket_time
            
            if should_save:
                # Get candle data for this bucket
                candle_data = self.get_index_candle_data(index_name, current_time)
                
                return {
                    'index_name': index_name,
                    'expiry_date': expiry_date,
                    'bucket_time': bucket_time,
                    'index_ltp': index_ltp,
                    'candle_data': candle_data,
                    'options': complete_data,
                    'oi_changes': oi_changes,
                    'should_save': True
                }
            else:
                return {
                    'index_name': index_name,
                    'expiry_date': expiry_date,
                    'bucket_time': bucket_time,
                    'index_ltp': index_ltp,
                    'options': complete_data,
                    'oi_changes': [],
                    'should_save': False
                }
                
        except Exception as e:
            print(f"❌ Error fetching complete option data: {str(e)}")
            return None
    
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
        """Get the current month expiry date for the given index"""
        try:
            # For now, let's use the current month's last Thursday
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

# Legacy function for backward compatibility
def fetch_option_chain_data(smart_api, ts_override=None):
    """Legacy function - now uses the new adaptive fetcher"""
    fetcher = AdaptiveOptionChainFetcher(smart_api)
    
    # Get expiry date for current month
    expiry_date = fetcher.get_expiry_date('NIFTY')  # Default to NIFTY
    
    # Fetch data for both indices
    all_data = []
    
    for index_name in ['NIFTY', 'BANKNIFTY']:
        data = fetcher.fetch_complete_option_data(index_name, expiry_date)
        if data:
            all_data.append(data)
    
    return all_data 