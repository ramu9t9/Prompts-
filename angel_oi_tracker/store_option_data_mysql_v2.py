"""
Upgraded MySQL Option Data Storage Module

This module handles storing option chain data in MySQL database with the new schema
that includes candle close prices from getCandleData API.

Key Features:
- New schema with index candle data (open, high, low, close, volume)
- 3-minute bucket timestamp handling
- OI change detection and storage
- Unique constraint to ensure one snapshot per 3-minute bucket per strike

Always refer to official documentation: https://smartapi.angelone.in/docs
"""

import mysql.connector
from mysql.connector import Error
import os
from datetime import datetime
import pytz

class UpgradedMySQLOptionDataStore:
    def __init__(self, host='localhost', user='root', password='YourNewPassword', database='options_analytics'):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.ist_tz = pytz.timezone('Asia/Kolkata')
        
        # Load from environment variables if available
        self.host = os.getenv('MYSQL_HOST', self.host)
        self.user = os.getenv('MYSQL_USER', self.user)
        self.password = os.getenv('MYSQL_PASSWORD', self.password)
        self.database = os.getenv('MYSQL_DATABASE', self.database)
    
    def get_connection(self):
        """Get MySQL connection"""
        try:
            connection = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database
            )
            return connection
        except Error as e:
            print(f"❌ Error connecting to MySQL: {e}")
            return None
    
    def get_previous_snapshot(self, index_name, expiry, strike, current_timestamp):
        """Get the previous snapshot for comparison"""
        try:
            connection = self.get_connection()
            if connection is None:
                return None
            
            cursor = connection.cursor()
            
            # Only get records with timestamps BEFORE the current timestamp
            cursor.execute('''
                SELECT ce_oi, ce_ltp, pe_oi, pe_ltp
                FROM option_snapshots
                WHERE index_name = %s AND expiry = %s AND strike = %s AND time < %s
                ORDER BY time DESC
                LIMIT 1
            ''', (index_name, expiry, strike, current_timestamp))
            
            result = cursor.fetchone()
            connection.close()
            
            if result and len(result) >= 4:
                # Use tuple unpacking to avoid linter issues
                ce_oi, ce_ltp, pe_oi, pe_ltp = result
                return {
                    'ce_oi': ce_oi,
                    'ce_ltp': ce_ltp,
                    'pe_oi': pe_oi,
                    'pe_ltp': pe_ltp
                }
            return None
            
        except Error as e:
            print(f"❌ Error getting previous snapshot: {e}")
            return None
    
    def calculate_changes(self, current_data, previous_data):
        """Calculate changes from previous snapshot"""
        changes = {}
        
        if not previous_data:
            # No previous data, set all changes to 0
            changes = {
                'ce_oi_change': 0, 'ce_oi_percent_change': 0,
                'ce_ltp_change': 0, 'ce_ltp_percent_change': 0,
                'pe_oi_change': 0, 'pe_oi_percent_change': 0,
                'pe_ltp_change': 0, 'pe_ltp_percent_change': 0
            }
        else:
            # Convert all values to float to handle decimal.Decimal from MySQL
            def safe_float(value):
                if value is None:
                    return 0.0
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return 0.0
            
            # Get current values as floats
            ce_oi_current = safe_float(current_data.get('ce_oi', 0))
            ce_ltp_current = safe_float(current_data.get('ce_ltp', 0))
            pe_oi_current = safe_float(current_data.get('pe_oi', 0))
            pe_ltp_current = safe_float(current_data.get('pe_ltp', 0))
            
            # Get previous values as floats
            ce_oi_prev = safe_float(previous_data.get('ce_oi', 0))
            ce_ltp_prev = safe_float(previous_data.get('ce_ltp', 0))
            pe_oi_prev = safe_float(previous_data.get('pe_oi', 0))
            pe_ltp_prev = safe_float(previous_data.get('pe_ltp', 0))
            
            # Calculate CE changes
            ce_oi_change = ce_oi_current - ce_oi_prev
            ce_oi_percent_change = (ce_oi_change / (ce_oi_prev + 1e-5)) * 100
            # Limit percentage change to reasonable bounds (-1000% to +1000%)
            ce_oi_percent_change = max(-1000.0, min(1000.0, ce_oi_percent_change))
            
            ce_ltp_change = ce_ltp_current - ce_ltp_prev
            ce_ltp_percent_change = (ce_ltp_change / (ce_ltp_prev + 1e-5)) * 100
            # Limit percentage change to reasonable bounds (-1000% to +1000%)
            ce_ltp_percent_change = max(-1000.0, min(1000.0, ce_ltp_percent_change))
            
            # Calculate PE changes
            pe_oi_change = pe_oi_current - pe_oi_prev
            pe_oi_percent_change = (pe_oi_change / (pe_oi_prev + 1e-5)) * 100
            # Limit percentage change to reasonable bounds (-1000% to +1000%)
            pe_oi_percent_change = max(-1000.0, min(1000.0, pe_oi_percent_change))
            
            pe_ltp_change = pe_ltp_current - pe_ltp_prev
            pe_ltp_percent_change = (pe_ltp_change / (pe_ltp_prev + 1e-5)) * 100
            # Limit percentage change to reasonable bounds (-1000% to +1000%)
            pe_ltp_percent_change = max(-1000.0, min(1000.0, pe_ltp_percent_change))
            
            changes = {
                'ce_oi_change': ce_oi_change,
                'ce_oi_percent_change': ce_oi_percent_change,
                'ce_ltp_change': ce_ltp_change,
                'ce_ltp_percent_change': ce_ltp_percent_change,
                'pe_oi_change': pe_oi_change,
                'pe_oi_percent_change': pe_oi_percent_change,
                'pe_ltp_change': pe_ltp_change,
                'pe_ltp_percent_change': pe_ltp_percent_change
            }
        
        return changes
    
    def calculate_oi_bars(self, ce_oi, pe_oi):
        """Calculate OI bar indicators"""
        # Convert to float to handle decimal.Decimal from MySQL
        def safe_float(value):
            if value is None:
                return 0.0
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0.0
        
        ce_oi_float = safe_float(ce_oi)
        pe_oi_float = safe_float(pe_oi)
        
        ce_vs_pe_oi_bar = ce_oi_float / (pe_oi_float + 1e-5)
        pe_vs_ce_oi_bar = pe_oi_float / (ce_oi_float + 1e-5)
        
        return ce_vs_pe_oi_bar, pe_vs_ce_oi_bar
    
    def store_option_snapshot(self, snapshot_data):
        """Store a single option snapshot with the new schema"""
        try:
            connection = self.get_connection()
            if connection is None:
                return False
            
            cursor = connection.cursor()
            
            # Extract data from snapshot
            time = snapshot_data['time']
            index_name = snapshot_data['index_name']
            expiry = snapshot_data['expiry']
            strike = snapshot_data['strike']
            
            # Index candle data
            candle_data = snapshot_data.get('candle_data', {})
            index_open = candle_data.get('open', 0)
            index_high = candle_data.get('high', 0)
            index_low = candle_data.get('low', 0)
            index_close = candle_data.get('close', 0)
            index_volume = candle_data.get('volume', 0)
            
            # CE data
            ce_data = snapshot_data.get('ce_data', {})
            ce_oi = ce_data.get('oi', 0)
            ce_ltp = ce_data.get('ltp', 0)
            ce_volume = ce_data.get('volume', 0)
            ce_iv = ce_data.get('iv', 0)
            ce_delta = ce_data.get('delta', 0)
            ce_theta = ce_data.get('theta', 0)
            ce_vega = ce_data.get('vega', 0)
            ce_gamma = ce_data.get('gamma', 0)
            
            # PE data
            pe_data = snapshot_data.get('pe_data', {})
            pe_oi = pe_data.get('oi', 0)
            pe_ltp = pe_data.get('ltp', 0)
            pe_volume = pe_data.get('volume', 0)
            pe_iv = pe_data.get('iv', 0)
            pe_delta = pe_data.get('delta', 0)
            pe_theta = pe_data.get('theta', 0)
            pe_vega = pe_data.get('vega', 0)
            pe_gamma = pe_data.get('gamma', 0)
            
            # Changes
            changes = snapshot_data.get('changes', {})
            ce_oi_change = changes.get('ce_oi_change', 0)
            ce_oi_percent_change = changes.get('ce_oi_percent_change', 0)
            ce_ltp_change = changes.get('ce_ltp_change', 0)
            ce_ltp_percent_change = changes.get('ce_ltp_percent_change', 0)
            pe_oi_change = changes.get('pe_oi_change', 0)
            pe_oi_percent_change = changes.get('pe_oi_percent_change', 0)
            pe_ltp_change = changes.get('pe_ltp_change', 0)
            pe_ltp_percent_change = changes.get('pe_ltp_percent_change', 0)
            
            # OI bars
            ce_vs_pe_oi_bar, pe_vs_ce_oi_bar = self.calculate_oi_bars(ce_oi, pe_oi)
            
            # Insert with new schema
            insert_query = '''
            INSERT INTO option_snapshots (
                time, index_name, expiry, strike,
                index_open, index_high, index_low, index_close, index_volume,
                ce_oi, ce_oi_change, ce_oi_percent_change, ce_ltp, ce_ltp_change, ce_ltp_percent_change,
                ce_volume, ce_iv, ce_delta, ce_theta, ce_vega, ce_gamma, ce_vs_pe_oi_bar,
                pe_oi, pe_oi_change, pe_oi_percent_change, pe_ltp, pe_ltp_change, pe_ltp_percent_change,
                pe_volume, pe_iv, pe_delta, pe_theta, pe_vega, pe_gamma, pe_vs_ce_oi_bar
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s
            ) ON DUPLICATE KEY UPDATE
                index_open = VALUES(index_open),
                index_high = VALUES(index_high),
                index_low = VALUES(index_low),
                index_close = VALUES(index_close),
                index_volume = VALUES(index_volume),
                ce_oi = VALUES(ce_oi),
                ce_oi_change = VALUES(ce_oi_change),
                ce_oi_percent_change = VALUES(ce_oi_percent_change),
                ce_ltp = VALUES(ce_ltp),
                ce_ltp_change = VALUES(ce_ltp_change),
                ce_ltp_percent_change = VALUES(ce_ltp_percent_change),
                ce_volume = VALUES(ce_volume),
                ce_iv = VALUES(ce_iv),
                ce_delta = VALUES(ce_delta),
                ce_theta = VALUES(ce_theta),
                ce_vega = VALUES(ce_vega),
                ce_gamma = VALUES(ce_gamma),
                ce_vs_pe_oi_bar = VALUES(ce_vs_pe_oi_bar),
                pe_oi = VALUES(pe_oi),
                pe_oi_change = VALUES(pe_oi_change),
                pe_oi_percent_change = VALUES(pe_oi_percent_change),
                pe_ltp = VALUES(pe_ltp),
                pe_ltp_change = VALUES(pe_ltp_change),
                pe_ltp_percent_change = VALUES(pe_ltp_percent_change),
                pe_volume = VALUES(pe_volume),
                pe_iv = VALUES(pe_iv),
                pe_delta = VALUES(pe_delta),
                pe_theta = VALUES(pe_theta),
                pe_vega = VALUES(pe_vega),
                pe_gamma = VALUES(pe_gamma),
                pe_vs_ce_oi_bar = VALUES(pe_vs_ce_oi_bar),
                updated_at = CURRENT_TIMESTAMP
            '''
            
            values = (
                time, index_name, expiry, strike,
                index_open, index_high, index_low, index_close, index_volume,
                ce_oi, ce_oi_change, ce_oi_percent_change, ce_ltp, ce_ltp_change, ce_ltp_percent_change,
                ce_volume, ce_iv, ce_delta, ce_theta, ce_vega, ce_gamma, ce_vs_pe_oi_bar,
                pe_oi, pe_oi_change, pe_oi_percent_change, pe_ltp, pe_ltp_change, pe_ltp_percent_change,
                pe_volume, pe_iv, pe_delta, pe_theta, pe_vega, pe_gamma, pe_vs_ce_oi_bar
            )
            
            cursor.execute(insert_query, values)
            connection.commit()
            connection.close()
            
            print(f"✅ Stored snapshot for {index_name} {strike} at {time}")
            return True
            
        except Error as e:
            print(f"❌ Error storing option snapshot: {e}")
            return False
    
    def process_and_store_option_data(self, option_data_list):
        """Process and store option data with the new schema"""
        try:
            if not option_data_list:
                print("⚠️  No option data to store")
                return False
            
            success_count = 0
            total_count = 0
            
            for index_data in option_data_list:
                if not index_data.get('should_save', False):
                    continue
                
                index_name = index_data['index_name']
                expiry_date = index_data['expiry_date']
                bucket_time = index_data['bucket_time']
                candle_data = index_data.get('candle_data', {})
                options = index_data['options']
                
                # Group options by strike
                strikes_data = {}
                for option in options:
                    strike = option['strike']
                    option_type = option['type']
                    
                    if strike not in strikes_data:
                        strikes_data[strike] = {'CE': {}, 'PE': {}}
                    
                    strikes_data[strike][option_type] = {
                        'ltp': option['ltp'],
                        'volume': option['volume'],
                        'oi': option.get('oi', 0),
                        'iv': option.get('iv', 0),
                        'delta': option.get('delta', 0),
                        'theta': option.get('theta', 0),
                        'vega': option.get('vega', 0),
                        'gamma': option.get('gamma', 0)
                    }
                
                # Store each strike as a separate snapshot
                for strike, strike_data in strikes_data.items():
                    total_count += 1
                    
                    # Get previous snapshot for change calculation
                    previous_data = self.get_previous_snapshot(index_name, expiry_date, strike, bucket_time)
                    
                    # Prepare snapshot data
                    snapshot_data = {
                        'time': bucket_time,
                        'index_name': index_name,
                        'expiry': expiry_date,
                        'strike': strike,
                        'candle_data': candle_data,
                        'ce_data': strike_data.get('CE', {}),
                        'pe_data': strike_data.get('PE', {})
                    }
                    
                    # Calculate changes
                    current_data = {
                        'ce_oi': strike_data.get('CE', {}).get('oi', 0),
                        'ce_ltp': strike_data.get('CE', {}).get('ltp', 0),
                        'pe_oi': strike_data.get('PE', {}).get('oi', 0),
                        'pe_ltp': strike_data.get('PE', {}).get('ltp', 0)
                    }
                    
                    changes = self.calculate_changes(current_data, previous_data)
                    snapshot_data['changes'] = changes
                    
                    # Store the snapshot
                    if self.store_option_snapshot(snapshot_data):
                        success_count += 1
            
            print(f"📊 Storage Summary: {success_count}/{total_count} snapshots stored successfully")
            return success_count > 0
            
        except Exception as e:
            print(f"❌ Error processing and storing option data: {str(e)}")
            return False

# Global function for backward compatibility
def store_option_chain_data(option_data, timestamp=None):
    """Store option chain data using the upgraded storage system"""
    try:
        store = UpgradedMySQLOptionDataStore()
        return store.process_and_store_option_data(option_data)
    except Exception as e:
        print(f"❌ Error in store_option_chain_data: {str(e)}")
        return False 