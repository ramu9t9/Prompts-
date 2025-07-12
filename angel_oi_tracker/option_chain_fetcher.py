"""
Option Chain Data Fetcher Module - Adaptive Polling Version

This module implements adaptive polling with 20-second intervals and 3-minute bucket snapshots.
Uses getMarketData ("FULL") for OI and getCandleData ("THREE_MINUTE") for close prices.

Key Features:
- 20-second polling loop
- OI change detection
- 3-minute bucket alignment
- Candle close price integration
- In-memory snapshot comparison

Always refer to official documentation: https://smartapi.angelone.in/docs

API Compliance:
- Rate Limits: https://smartapi.angelone.in/docs/rate-limits
- Data Usage: Use data only for authorized purposes
- Terms of Service: Follow Angel One's terms and conditions
"""

import time
import math
from datetime import datetime, timedelta
import pytz
from utils.symbols import get_index_token, INDEX_TOKENS
from utils.strike_range import get_filtered_strikes, filter_option_chain_by_strikes
from utils.scrip_master import get_token_for_symbol, search_symbols
from utils.expiry_manager import get_current_expiry, get_all_expiries

# Constants for adaptive polling
REFRESH_WINDOW = 30   # seconds
POLL_FREQUENCY = 20   # seconds

class OptionChainFetcher:
    def __init__(self, smart_api):
        self.smart_api = smart_api
        self.ist_tz = pytz.timezone('Asia/Kolkata')
        
        # In-memory storage for adaptive polling
        self.last_saved_bucket = {}  # key: trading_symbol, value: last 3-min bucket timestamp
        self.last_snapshot = {}      # key: trading_symbol, value: last snapshot data
        
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
        """Get current expiry date for an index"""
        try:
            # Use the new expiry manager to get current expiry
            current_expiry = get_current_expiry(index_name)
            
            if current_expiry:
                expiry_date = current_expiry.strftime('%Y-%m-%d')
                print(f"📅 Using current expiry for {index_name}: {expiry_date}")
                return expiry_date
            else:
                print(f"❌ No valid expiry found for {index_name}")
                return None
            
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

    def fetch_complete_snapshot(self, range_strikes=5):
        """
        Fetch complete snapshot data for all indices in Phase 1 format
        
        Returns:
            dict: Complete snapshot with raw data ready for Phase 1 tables
        """
        try:
            print("📊 Fetching complete snapshot for Phase 1 schema...")
            
            # Get current timestamp and floor to 3-minute bucket
            current_time = datetime.now(self.ist_tz)
            bucket_ts = self.floor_to_3min(current_time)
            
            # Fetch data for all indices
            all_indices_data = self.fetch_all_indices_data(range_strikes)
            
            if not all_indices_data:
                print("⚠️  No data fetched for any index")
                return None
            
            # Prepare raw data for options_raw_data table
            raw_data_list = []
            
            # Prepare historical data for historical_oi_tracking table
            historical_data_list = []
            
            # Prepare live data for live_oi_tracking table
            live_data_list = []
            
            for index_data in all_indices_data:
                index_name = index_data['index_name']
                index_ltp = index_data['index_ltp']
                expiry_date = index_data['expiry_date']
                options = index_data['options']
                
                # Group options by strike for historical and live data
                strikes_data = {}
                
                for option in options:
                    strike = option['strike']
                    option_type = option['type']
                    trading_symbol = option['symbol']
                    
                    # Prepare raw data record
                    raw_data = {
                        'bucket_ts': bucket_ts,
                        'trading_symbol': trading_symbol,
                        'strike': strike,
                        'option_type': option_type,
                        'ltp': option['ltp'],
                        'volume': option['volume'],
                        'oi': option['oi'],
                        'price_change': option['change'],
                        'change_percent': option['change_percent'],
                        'open_price': option['open'],
                        'high_price': option['high'],
                        'low_price': option['low'],
                        'close_price': option['close'],
                        'delta': option['delta'],
                        'gamma': option['gamma'],
                        'theta': option['theta'],
                        'vega': option['vega'],
                        'iv': option['iv'],
                        'index_name': index_name,
                        'expiry_date': expiry_date
                    }
                    raw_data_list.append(raw_data)
                    
                    # Group by strike for historical/live data
                    if strike not in strikes_data:
                        strikes_data[strike] = {'CE': {}, 'PE': {}}
                    
                    strikes_data[strike][option_type] = {
                        'oi': option['oi'],
                        'ltp': option['ltp'],
                        'volume': option['volume'],
                        'change_percent': option['change_percent']
                    }
                
                # Process strikes data for historical and live tables
                for strike, strike_data in strikes_data.items():
                    ce_data = strike_data.get('CE', {})
                    pe_data = strike_data.get('PE', {})
                    
                    # Calculate basic metrics
                    ce_oi = ce_data.get('oi', 0)
                    pe_oi = pe_data.get('oi', 0)
                    total_oi = ce_oi + pe_oi
                    
                    # Calculate PCR
                    pcr = (pe_oi / (ce_oi + 1e-5))
                    ce_pe_ratio = (ce_oi / (pe_oi + 1e-5))
                    
                    # Prepare historical data record
                    historical_data = {
                        'bucket_ts': bucket_ts,
                        'trading_symbol': f"{index_name}{strike}",
                        'strike': strike,
                        'ce_oi': ce_oi,
                        'pe_oi': pe_oi,
                        'total_oi': total_oi,
                        'ce_oi_change': 0,  # Will be calculated in Phase 2
                        'pe_oi_change': 0,  # Will be calculated in Phase 2
                        'ce_oi_pct_change': 0,  # Will be calculated in Phase 2
                        'pe_oi_pct_change': 0,  # Will be calculated in Phase 2
                        'ce_ltp': ce_data.get('ltp', 0),
                        'pe_ltp': pe_data.get('ltp', 0),
                        'ce_ltp_change_pct': ce_data.get('change_percent', 0),
                        'pe_ltp_change_pct': pe_data.get('change_percent', 0),
                        'index_ltp': index_ltp,
                        'ce_volume': ce_data.get('volume', 0),
                        'pe_volume': pe_data.get('volume', 0),
                        'ce_volume_change': 0,  # Will be calculated in Phase 2
                        'pe_volume_change': 0,  # Will be calculated in Phase 2
                        'pcr': pcr,
                        'ce_pe_ratio': ce_pe_ratio,
                        'oi_quadrant': 'NEUTRAL',  # Will be calculated in Phase 2
                        'confidence_score': 0,  # Will be calculated in Phase 2
                        'strike_rank': None,  # Will be calculated in Phase 2
                        'delta_band': 'ATM',  # Will be calculated in Phase 2
                        'index_name': index_name,
                        'expiry_date': expiry_date
                    }
                    historical_data_list.append(historical_data)
                    
                    # Prepare live data record (simplified version)
                    live_data = {
                        'bucket_ts': bucket_ts,
                        'trading_symbol': f"{index_name}{strike}",
                        'strike': strike,
                        'ce_oi': ce_oi,
                        'pe_oi': pe_oi,
                        'ce_oi_change': 0,  # Will be calculated in Phase 2
                        'pe_oi_change': 0,  # Will be calculated in Phase 2
                        'pcr': pcr,
                        'oi_quadrant': 'NEUTRAL',  # Will be calculated in Phase 2
                        'index_name': index_name
                    }
                    live_data_list.append(live_data)
            
            complete_snapshot = {
                'bucket_ts': bucket_ts,
                'raw_data': raw_data_list,
                'historical_data': historical_data_list,
                'live_data': live_data_list,
                'timestamp': current_time
            }
            
            print(f"✅ Complete snapshot prepared:")
            print(f"   - Raw data records: {len(raw_data_list)}")
            print(f"   - Historical data records: {len(historical_data_list)}")
            print(f"   - Live data records: {len(live_data_list)}")
            
            return complete_snapshot
            
        except Exception as e:
            print(f"❌ Error fetching complete snapshot: {str(e)}")
            return None
    
    def floor_to_3min(self, timestamp):
        """Floor timestamp to the nearest 3-minute bucket"""
        # Convert to minutes since midnight, floor to 3-minute intervals
        minutes_since_midnight = timestamp.hour * 60 + timestamp.minute
        floored_minutes = (minutes_since_midnight // 3) * 3
        
        # Ensure floored_minutes is within valid range (0-59)
        if floored_minutes >= 60:
            # Handle edge case where floored_minutes could be 60
            floored_minutes = 57  # Last valid 3-minute interval
        
        # Create new timestamp with floored minutes
        floored_time = timestamp.replace(minute=floored_minutes, second=0, microsecond=0)
        return floored_time
    
    def get_index_candle_data(self, index_name, bucket_time):
        """Get 3-minute candle data for the index using getCandleData"""
        try:
            token = get_index_token(index_name)
            if not token:
                raise ValueError(f"Invalid index name: {index_name}")
            
            # Convert to required format for getCandleData (DD-MM-YYYY HH:MM)
            from_time = bucket_time.strftime('%d-%m-%Y %H:%M')
            to_time = (bucket_time + timedelta(minutes=3)).strftime('%d-%m-%Y %H:%M')
            
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
    
    def detect_oi_changes(self, current_data, trading_symbol):
        """Detect OI changes compared to previous snapshot"""
        if trading_symbol not in self.last_snapshot:
            return True  # First time, consider it a change
        
        last_data = self.last_snapshot[trading_symbol]
        current_ce_oi = current_data.get('ce_oi', 0)
        current_pe_oi = current_data.get('pe_oi', 0)
        
        last_ce_oi = last_data.get('ce_oi', 0)
        last_pe_oi = last_data.get('pe_oi', 0)
        
        # Check if OI has changed
        return (current_ce_oi != last_ce_oi) or (current_pe_oi != last_pe_oi)
    
    def update_last_snapshot(self, trading_symbol, snapshot_data):
        """Update in-memory last snapshot"""
        self.last_snapshot[trading_symbol] = snapshot_data
    
    def should_save_snapshot(self, trading_symbol, current_time):
        """Determine if we should save a snapshot based on OI changes and bucket time"""
        bucket_time = self.floor_to_3min(current_time)
        
        # Check if bucket has changed
        if trading_symbol not in self.last_saved_bucket:
            self.last_saved_bucket[trading_symbol] = bucket_time
            return True
        
        if bucket_time != self.last_saved_bucket[trading_symbol]:
            self.last_saved_bucket[trading_symbol] = bucket_time
            return True
        
        return False
    
    def start_live_poll(self):
        """Start the adaptive polling loop with 20-second intervals"""
        print(f"🔄 Starting adaptive polling loop (20-second intervals)")
        print(f"📊 Refresh window: {REFRESH_WINDOW}s, Poll frequency: {POLL_FREQUENCY}s")
        
        candle_cache = {}  # Cache candle data to avoid repeated API calls
        last_candle_fetch = {}  # Track last candle fetch time per index
        
        while True:
            try:
                current_time = datetime.now(self.ist_tz)
                bucket_time = self.floor_to_3min(current_time)
                print(f"\n🔄 Polling at {current_time.strftime('%H:%M:%S')} (bucket: {bucket_time.strftime('%H:%M:%S')})")
                
                # Fetch data for all indices
                all_data = self.fetch_all_indices_data(range_strikes=5)
                
                if all_data:
                    # Process each index data
                    for index_data in all_data:
                        index_name = index_data['index_name']
                        index_ltp = index_data['index_ltp']  # Use index LTP as fallback
                        options = index_data['options']
                        
                        # Get candle data once per index per 3-minute bucket (with rate limiting)
                        candle_data = None
                        candle_cache_key = f"{index_name}_{bucket_time.strftime('%H:%M')}"
                        
                        # Only fetch candle data if we haven't cached it and it's been at least 30 seconds
                        should_fetch_candle = (
                            candle_cache_key not in candle_cache and 
                            (index_name not in last_candle_fetch or 
                             (current_time - last_candle_fetch[index_name]).total_seconds() > 30)
                        )
                        
                        if should_fetch_candle:
                            try:
                                candle_data = self.get_index_candle_data(index_name, bucket_time)
                                if candle_data:
                                    candle_cache[candle_cache_key] = candle_data
                                    last_candle_fetch[index_name] = current_time
                                    # Keep cache size manageable
                                    if len(candle_cache) > 20:
                                        # Remove oldest entries
                                        oldest_key = next(iter(candle_cache))
                                        del candle_cache[oldest_key]
                                else:
                                    # If candle data fails, use index LTP as fallback
                                    candle_data = {'close': index_ltp}
                                    candle_cache[candle_cache_key] = candle_data
                            except Exception as e:
                                print(f"⚠️  Candle data fetch failed for {index_name}: {str(e)}")
                                # Use index LTP as fallback
                                candle_data = {'close': index_ltp}
                                candle_cache[candle_cache_key] = candle_data
                        else:
                            candle_data = candle_cache.get(candle_cache_key, {'close': index_ltp})
                        
                        # Group options by strike for processing
                        strikes_data = {}
                        for option in options:
                            strike = option['strike']
                            option_type = option['type']
                            
                            if strike not in strikes_data:
                                strikes_data[strike] = {'CE': {}, 'PE': {}}
                            
                            strikes_data[strike][option_type] = {
                                'oi': option.get('oi', 0),
                                'ltp': option.get('ltp', 0)
                            }
                        
                        # Process each strike
                        for strike, strike_data in strikes_data.items():
                            trading_symbol = f"{index_name}{strike}"
                            
                            # Prepare current snapshot data
                            current_snapshot = {
                                'ce_oi': strike_data.get('CE', {}).get('oi', 0),
                                'pe_oi': strike_data.get('PE', {}).get('oi', 0),
                                'ce_ltp': strike_data.get('CE', {}).get('ltp', 0),
                                'pe_ltp': strike_data.get('PE', {}).get('ltp', 0)
                            }
                            
                            # Check if we should save snapshot
                            if self.should_save_snapshot(trading_symbol, current_time):
                                # Use candle close price or index LTP as fallback
                                close_price = candle_data.get('close', index_ltp)
                                
                                # Prepare snapshot for storage
                                snapshot_data = {
                                    'bucket_ts': bucket_time,
                                    'trading_symbol': trading_symbol,
                                    'option_type': 'XX',  # Placeholder, will be set per option
                                    'strike': strike,
                                    'ce_oi': current_snapshot['ce_oi'],
                                    'ce_price_close': close_price,
                                    'pe_oi': current_snapshot['pe_oi'],
                                    'pe_price_close': close_price
                                }
                                
                                # Store CE option
                                ce_snapshot = snapshot_data.copy()
                                ce_snapshot['option_type'] = 'CE'
                                if self.insert_snapshot(ce_snapshot):
                                    print(f"✅ Saved CE snapshot for {trading_symbol} at {bucket_time.strftime('%H:%M:%S')}")
                                
                                # Store PE option
                                pe_snapshot = snapshot_data.copy()
                                pe_snapshot['option_type'] = 'PE'
                                if self.insert_snapshot(pe_snapshot):
                                    print(f"✅ Saved PE snapshot for {trading_symbol} at {bucket_time.strftime('%H:%M:%S')}")
                                
                                # Update last snapshot
                                self.update_last_snapshot(trading_symbol, current_snapshot)
                
                # Wait for next polling interval
                time.sleep(POLL_FREQUENCY)
                
            except KeyboardInterrupt:
                print("\n🛑 Polling stopped by user")
                break
            except Exception as e:
                print(f"❌ Error in polling loop: {str(e)}")
                time.sleep(5)  # Short delay on error
    
    def insert_snapshot(self, snapshot_data):
        """Insert a single snapshot into the database"""
        try:
            # Import here to avoid circular imports
            from store_option_data_mysql import insert_snapshot
            return insert_snapshot(snapshot_data)
        except Exception as e:
            print(f"❌ Error inserting snapshot: {str(e)}")
            return False

# --- Begin OIAnalysis class (moved from backup_old_files/oi_analysis.py) ---
from datetime import datetime, timedelta
import pytz
from store_option_data_mysql import MySQLOptionDataStore

def safe_float(val):
    try:
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            return float(val)
        if hasattr(val, '__float__'):
            return float(val)
    except Exception:
        pass
    return 0.0

class OIAnalysis:
    def __init__(self):
        self.ist_tz = pytz.timezone('Asia/Kolkata')
        self.store = MySQLOptionDataStore()
    def get_oi_changes(self, trading_symbol, start_time=None, end_time=None):
        try:
            connection = self.store.get_connection()
            if connection is None:
                return None
            if start_time is None:
                start_time = datetime.now(self.ist_tz) - timedelta(days=1)
            if end_time is None:
                end_time = datetime.now(self.ist_tz)
            cursor = connection.cursor()
            cursor.execute('''SELECT bucket_ts, ce_oi, pe_oi, ce_price_close, pe_price_close FROM option_snapshots WHERE trading_symbol = %s AND bucket_ts BETWEEN %s AND %s ORDER BY bucket_ts''', (trading_symbol, start_time, end_time))
            records = cursor.fetchall()
            connection.close()
            if not records:
                return None
            changes = []
            for i in range(1, len(records)):
                prev_record = records[i-1]
                curr_record = records[i]
                try:
                    # Unpack tuples for clarity and type safety
                    (_, prev_ce_oi, prev_pe_oi, prev_ce_price, prev_pe_price, *_) = prev_record
                    (_, curr_ce_oi, curr_pe_oi, curr_ce_price, curr_pe_price, *_) = curr_record
                    ce_oi_change = safe_float(curr_ce_oi) - safe_float(prev_ce_oi)
                    pe_oi_change = safe_float(curr_pe_oi) - safe_float(prev_pe_oi)
                    ce_price_change = safe_float(curr_ce_price) - safe_float(prev_ce_price)
                    pe_price_change = safe_float(curr_pe_price) - safe_float(prev_pe_price)
                    ce_oi_pct_change = (ce_oi_change / safe_float(prev_ce_oi) * 100) if safe_float(prev_ce_oi) > 0 else 0
                    pe_oi_pct_change = (pe_oi_change / safe_float(prev_pe_oi) * 100) if safe_float(prev_pe_oi) > 0 else 0
                    changes.append({
                        'timestamp': curr_record[0],
                        'ce_oi_change': ce_oi_change,
                        'pe_oi_change': pe_oi_change,
                        'ce_oi_pct_change': ce_oi_pct_change,
                        'pe_oi_pct_change': pe_oi_pct_change,
                        'ce_price_change': ce_price_change,
                        'pe_price_change': pe_price_change,
                        'ce_oi': safe_float(curr_ce_oi),
                        'pe_oi': safe_float(curr_pe_oi),
                        'ce_price': safe_float(curr_ce_price),
                        'pe_price': safe_float(curr_pe_price)
                    })
                except Exception as e:
                    print(f"⚠️  Error processing record {i}: {str(e)}")
                    continue
            return changes
        except Exception as e:
            print(f"❌ Error getting OI changes: {str(e)}")
            return None
    def get_strike_analysis(self, index_name, start_time=None, end_time=None):
        try:
            connection = self.store.get_connection()
            if connection is None:
                return None
            if start_time is None:
                start_time = datetime.now(self.ist_tz) - timedelta(days=1)
            if end_time is None:
                end_time = datetime.now(self.ist_tz)
            cursor = connection.cursor()
            cursor.execute('''SELECT trading_symbol, option_type, strike, MAX(ce_oi) as max_ce_oi, MIN(ce_oi) as min_ce_oi, MAX(pe_oi) as max_pe_oi, MIN(pe_oi) as min_pe_oi, AVG(ce_oi) as avg_ce_oi, AVG(pe_oi) as avg_pe_oi, COUNT(*) as data_points FROM option_snapshots WHERE trading_symbol LIKE %s AND bucket_ts BETWEEN %s AND %s GROUP BY trading_symbol, option_type, strike ORDER BY strike''', (f"{index_name}%", start_time, end_time))
            records = cursor.fetchall()
            connection.close()
            if not records:
                return None
            analysis = {}
            for record in records:
                trading_symbol, option_type, strike = record[0], record[1], record[2]
                if strike not in analysis:
                    analysis[strike] = {'strike': strike,'ce': {'max_oi': 0, 'min_oi': 0, 'avg_oi': 0,'current_oi': 0, 'oi_change': 0},'pe': {'max_oi': 0, 'min_oi': 0, 'avg_oi': 0,'current_oi': 0, 'oi_change': 0},'data_points': 0}
                if option_type == 'CE':
                    analysis[strike]['ce'].update({'max_oi': record[3],'min_oi': record[4],'avg_oi': record[7]})
                elif option_type == 'PE':
                    analysis[strike]['pe'].update({'max_oi': record[5],'min_oi': record[6],'avg_oi': record[8]})
                analysis[strike]['data_points'] = record[9]
            return analysis
        except Exception as e:
            print(f"❌ Error getting strike analysis: {str(e)}")
            return None
    def get_ce_pe_ratio_analysis(self, index_name, start_time=None, end_time=None):
        try:
            connection = self.store.get_connection()
            if connection is None:
                return None
            if start_time is None:
                start_time = datetime.now(self.ist_tz) - timedelta(days=1)
            if end_time is None:
                end_time = datetime.now(self.ist_tz)
            cursor = connection.cursor()
            cursor.execute('''SELECT bucket_ts, trading_symbol, strike, ce_oi, pe_oi, CASE WHEN pe_oi > 0 THEN ce_oi / pe_oi ELSE NULL END as ce_pe_ratio, CASE WHEN ce_oi > 0 THEN pe_oi / ce_oi ELSE NULL END as pe_ce_ratio FROM option_snapshots WHERE trading_symbol LIKE %s AND bucket_ts BETWEEN %s AND %s ORDER BY bucket_ts, strike''', (f"{index_name}%", start_time, end_time))
            records = cursor.fetchall()
            connection.close()
            if not records:
                return None
            ratio_analysis = {}
            for record in records:
                timestamp, trading_symbol, strike = record[0], record[1], record[2]
                ce_oi, pe_oi = record[3], record[4]
                ce_pe_ratio, pe_ce_ratio = record[5], record[6]
                if strike not in ratio_analysis:
                    ratio_analysis[strike] = []
                ratio_analysis[strike].append({'timestamp': timestamp,'ce_oi': ce_oi,'pe_oi': pe_oi,'ce_pe_ratio': ce_pe_ratio,'pe_ce_ratio': pe_ce_ratio})
            return ratio_analysis
        except Exception as e:
            print(f"❌ Error getting CE/PE ratio analysis: {str(e)}")
            return None
    def get_oi_summary(self, index_name, hours_back=24):
        try:
            end_time = datetime.now(self.ist_tz)
            start_time = end_time - timedelta(hours=hours_back)
            connection = self.store.get_connection()
            if connection is None:
                return None
            cursor = connection.cursor()
            cursor.execute('''SELECT trading_symbol, option_type, strike, ce_oi, pe_oi, ce_price_close, pe_price_close FROM option_snapshots WHERE trading_symbol LIKE %s AND bucket_ts >= %s AND bucket_ts = (SELECT MAX(bucket_ts) FROM option_snapshots s2 WHERE s2.trading_symbol = option_snapshots.trading_symbol) ORDER BY strike, option_type''', (f"{index_name}%", start_time))
            records = cursor.fetchall()
            connection.close()
            if not records:
                return None
            summary = {'index_name': index_name,'analysis_time': end_time,'hours_back': hours_back,'strikes': {},'total_ce_oi': 0,'total_pe_oi': 0,'pcr': 0}
            for record in records:
                trading_symbol, option_type, strike = record[0], record[1], record[2]
                ce_oi, pe_oi = record[3], record[4]
                ce_price, pe_price = record[5], record[6]
                if strike not in summary['strikes']:
                    summary['strikes'][strike] = {'strike': strike,'ce_oi': 0,'pe_oi': 0,'ce_price': 0,'pe_price': 0}
                if option_type == 'CE':
                    summary['strikes'][strike]['ce_oi'] = ce_oi
                    summary['strikes'][strike]['ce_price'] = ce_price
                    summary['total_ce_oi'] += ce_oi
                elif option_type == 'PE':
                    summary['strikes'][strike]['pe_oi'] = pe_oi
                    summary['strikes'][strike]['pe_price'] = pe_price
                    summary['total_pe_oi'] += pe_oi
            if summary['total_ce_oi'] > 0:
                summary['pcr'] = summary['total_pe_oi'] / summary['total_ce_oi']
            return summary
        except Exception as e:
            print(f"❌ Error getting OI summary: {str(e)}")
            return None
    def print_oi_summary(self, index_name, hours_back=24):
        summary = self.get_oi_summary(index_name, hours_back)
        if not summary:
            print(f"❌ No OI summary available for {index_name}")
            return
        print(f"\n📊 OI Summary for {index_name}")
        print("=" * 50)
        print(f"⏰ Analysis Time: {summary['analysis_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📅 Period: Last {summary['hours_back']} hours")
        print(f"📈 Total CE OI: {summary['total_ce_oi']:,}")
        print(f"📉 Total PE OI: {summary['total_pe_oi']:,}")
        print(f"🔄 Put-Call Ratio: {summary['pcr']:.2f}")
        print(f"\n📋 Strike-wise Analysis:")
        print("-" * 50)
        print(f"{'Strike':<8} {'CE OI':<12} {'PE OI':<12} {'CE Price':<10} {'PE Price':<10}")
        print("-" * 50)
        for strike in sorted(summary['strikes'].keys()):
            strike_data = summary['strikes'][strike]
            print(f"{strike:<8} {strike_data['ce_oi']:<12,} {strike_data['pe_oi']:<12,} "
                  f"{strike_data['ce_price']:<10.2f} {strike_data['pe_price']:<10.2f}")
# --- End OIAnalysis class ---

class AdaptivePollingEngine:
    """
    Adaptive Polling Engine for Phase 2 with Phase 3 CLI Dashboard
    
    Implements intelligent polling based on OI changes and 3-minute bucket alignment.
    Now includes real-time CLI dashboard with OI analytics.
    """
    
    def __init__(self, smart_api, calendar, datastore, analysis_engine=None):
        self.smart_api = smart_api
        self.calendar = calendar
        self.datastore = datastore
        self.analysis_engine = analysis_engine
        self.fetcher = OptionChainFetcher(smart_api)
        self.ist_tz = pytz.timezone('Asia/Kolkata')
        
        # Polling state
        self.last_poll_time = None
        self.last_snapshot = None
        self.last_saved_bucket_ts = None
        self.is_running = False
        
        # Polling constants
        self.POLL_FREQ = 20  # seconds
        self.REFRESH_WINDOW = 30  # seconds
        
        # CLI Dashboard state
        self.last_dashboard_time = None
        self.dashboard_interval = 180  # 3 minutes for CLI updates
    
    def should_store_snapshot(self, prev_snapshot, new_snapshot, bucket_ts):
        """
        Determine if we should store a new snapshot based on OI changes and bucket timing
        
        Args:
            prev_snapshot: Previous snapshot data
            new_snapshot: New snapshot data
            bucket_ts: Current bucket timestamp
            
        Returns:
            bool: True if should store, False otherwise
        """
        try:
            # If no previous snapshot, always store
            if not prev_snapshot:
                return True
            
            # Check if bucket timestamp is different (new 3-min bucket)
            prev_bucket_ts = prev_snapshot.get('bucket_ts')
            if prev_bucket_ts != bucket_ts:
                return True
            
            # Check for OI changes in any option
            if 'raw_data' in new_snapshot and 'raw_data' in prev_snapshot:
                new_raw_data = {item['trading_symbol']: item for item in new_snapshot['raw_data']}
                prev_raw_data = {item['trading_symbol']: item for item in prev_snapshot['raw_data']}
                
                for symbol, new_data in new_raw_data.items():
                    if symbol in prev_raw_data:
                        prev_data = prev_raw_data[symbol]
                        if new_data.get('oi', 0) != prev_data.get('oi', 0):
                            return True
            
            return False
            
        except Exception as e:
            print(f"❌ Error in should_store_snapshot: {str(e)}")
            return True  # Store on error to be safe
    
    def start_live_poll(self):
        """
        Start adaptive live polling during market hours
        
        This method runs a 20-second polling loop that:
        1. Fetches complete snapshot data
        2. Checks for OI changes and new 3-minute buckets
        3. Stores data only when changes are detected
        4. Updates live tracking table
        """
        print("🚀 Starting adaptive live polling...")
        self.is_running = True
        
        # Check if it's a new market day and clear live table if needed
        if self.datastore.is_new_market_day():
            print("📅 New market day detected - clearing live tracking table")
            self.datastore.clear_live_tracking()
        
        try:
            while self.is_running and self.calendar.is_market_live_now():
                current_time = datetime.now(self.ist_tz)
                
                # Check if we should poll now
                if not self.calendar.should_poll_now(self.last_poll_time):
                    time.sleep(1)
                    continue
                
                print(f"📊 Polling at {current_time.strftime('%H:%M:%S')}")
                
                try:
                    # Fetch complete snapshot
                    new_snapshot = self.fetcher.fetch_complete_snapshot(range_strikes=5)
                    
                    if new_snapshot:
                        # Get current bucket timestamp
                        bucket_ts = self.calendar.floor_to_3min(current_time)
                        
                        # Check if we should store this snapshot
                        if self.should_store_snapshot(self.last_snapshot, new_snapshot, bucket_ts):
                            print(f"💾 Storing snapshot for bucket {bucket_ts.strftime('%H:%M:%S')}")
                            
                            # Store raw data
                            if new_snapshot.get('raw_data'):
                                self.datastore.insert_raw_data(new_snapshot['raw_data'])
                            
                            # Store historical data
                            if new_snapshot.get('historical_data'):
                                self.datastore.insert_historical_data(new_snapshot['historical_data'])
                            
                            # Store live data (only during live market)
                            if new_snapshot.get('live_data'):
                                self.datastore.insert_live_data(new_snapshot['live_data'])
                            
                            # Update state
                            self.last_snapshot = new_snapshot
                            self.last_saved_bucket_ts = bucket_ts
                            
                            print(f"✅ Snapshot stored successfully")
                            
                            # Phase 3: Generate and display CLI dashboard
                            if self.analysis_engine and self.should_update_dashboard(current_time):
                                self.update_cli_dashboard(bucket_ts)
                        else:
                            print(f"⏭️  Skipping snapshot - no significant changes")
                    else:
                        print(f"⚠️  No data fetched")
                    
                    # Update last poll time
                    self.last_poll_time = current_time
                    
                except Exception as e:
                    print(f"❌ Error during polling: {str(e)}")
                
                # Sleep for polling interval
                time.sleep(self.POLL_FREQ)
            
            print("🛑 Adaptive polling stopped")
            
        except KeyboardInterrupt:
            print("🛑 Adaptive polling interrupted by user")
        except Exception as e:
            print(f"❌ Error in adaptive polling: {str(e)}")
        finally:
            self.is_running = False
    
    def stop_polling(self):
        """Stop the adaptive polling"""
        self.is_running = False
        print("🛑 Stopping adaptive polling...")
    
    def get_polling_status(self):
        """Get current polling status"""
        return {
            'is_running': self.is_running,
            'last_poll_time': self.last_poll_time,
            'last_saved_bucket_ts': self.last_saved_bucket_ts,
            'market_live': self.calendar.is_market_live_now()
        }
    
    def should_update_dashboard(self, current_time):
        """Check if we should update the CLI dashboard (every 3 minutes)"""
        if not self.last_dashboard_time:
            return True
        
        time_diff = (current_time - self.last_dashboard_time).total_seconds()
        return time_diff >= self.dashboard_interval
    
    def update_cli_dashboard(self, bucket_ts):
        """Update and display the CLI dashboard for all indices"""
        try:
            if not self.analysis_engine:
                return
            
            # Get indices from the last snapshot
            if not self.last_snapshot or 'raw_data' not in self.last_snapshot:
                return
            
            # Extract unique indices from raw data
            indices = set()
            for item in self.last_snapshot['raw_data']:
                index_name = item.get('index_name')
                if index_name:
                    indices.add(index_name)
            
            # Generate dashboard for each index
            for index_name in indices:
                try:
                    # Generate live summary
                    summary = self.analysis_engine.generate_live_summary(bucket_ts, index_name)
                    
                    # Format and display CLI dashboard
                    dashboard_text = self.analysis_engine.format_cli_display(summary)
                    print(f"\n{dashboard_text}")
                    
                except Exception as e:
                    print(f"❌ Error generating dashboard for {index_name}: {str(e)}")
            
            # Update dashboard time
            self.last_dashboard_time = datetime.now(self.ist_tz)
            
        except Exception as e:
            print(f"❌ Error updating CLI dashboard: {str(e)}")

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