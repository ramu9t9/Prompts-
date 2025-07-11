"""
MySQL Option Data Storage Module

This module handles storing option chain data in MySQL database.
Always refer to official documentation: https://smartapi.angelone.in/docs

API Compliance:
- Data Usage: Use data only for authorized purposes
- Terms of Service: Follow Angel One's terms and conditions
"""

import mysql.connector
from mysql.connector import Error
import os
from datetime import datetime
import pytz

class MySQLOptionDataStore:
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
    
    def process_option_data(self, option_data_list, timestamp):
        """Process and format option data for storage"""
        processed_records = []
        
        for index_data in option_data_list:
            index_name = index_data['index_name']
            expiry = index_data['expiry_date']
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
                    'change': option['change'],
                    'change_percent': option['change_percent'],
                    'delta': option.get('delta', 0),
                    'gamma': option.get('gamma', 0),
                    'theta': option.get('theta', 0),
                    'vega': option.get('vega', 0),
                    'iv': option.get('iv', 0)
                }
            
            # Process each strike
            for strike, strike_data in strikes_data.items():
                ce_data = strike_data.get('CE', {})
                pe_data = strike_data.get('PE', {})
                
                # Get previous snapshot for comparison
                previous_data = self.get_previous_snapshot(index_name, expiry, strike, timestamp)
                
                # Current data
                current_data = {
                    'ce_oi': ce_data.get('oi', 0),  # Now available from getMarketData
                    'ce_ltp': ce_data.get('ltp', 0),
                    'pe_oi': pe_data.get('oi', 0),  # Now available from getMarketData
                    'pe_ltp': pe_data.get('ltp', 0)
                }
                
                # Calculate changes
                changes = self.calculate_changes(current_data, previous_data)
                
                # Calculate OI bars
                ce_vs_pe_oi_bar, pe_vs_ce_oi_bar = self.calculate_oi_bars(
                    current_data['ce_oi'], current_data['pe_oi']
                )
                
                # Prepare record for insertion
                record = {
                    'time': timestamp,
                    'index_name': index_name,
                    'expiry': expiry,
                    'strike': strike,
                    
                    # CE data
                    'ce_oi': current_data['ce_oi'],
                    'ce_oi_change': changes['ce_oi_change'],
                    'ce_oi_percent_change': changes['ce_oi_percent_change'],
                    'ce_ltp': current_data['ce_ltp'],
                    'ce_ltp_change': changes['ce_ltp_change'],
                    'ce_ltp_percent_change': changes['ce_ltp_percent_change'],
                    'ce_volume': ce_data.get('volume', 0),
                    'ce_iv': ce_data.get('iv', 0),  # Now available from optionGreek API
                    'ce_delta': ce_data.get('delta', 0),  # Now available from optionGreek API
                    'ce_theta': ce_data.get('theta', 0),
                    'ce_vega': ce_data.get('vega', 0),
                    'ce_gamma': ce_data.get('gamma', 0),
                    'ce_vs_pe_oi_bar': ce_vs_pe_oi_bar,
                    
                    # PE data
                    'pe_oi': current_data['pe_oi'],
                    'pe_oi_change': changes['pe_oi_change'],
                    'pe_oi_percent_change': changes['pe_oi_percent_change'],
                    'pe_ltp': current_data['pe_ltp'],
                    'pe_ltp_change': changes['pe_ltp_change'],
                    'pe_ltp_percent_change': changes['pe_ltp_percent_change'],
                    'pe_volume': pe_data.get('volume', 0),
                    'pe_iv': pe_data.get('iv', 0),  # Now available from optionGreek API
                    'pe_delta': pe_data.get('delta', 0),  # Now available from optionGreek API
                    'pe_theta': pe_data.get('theta', 0),
                    'pe_vega': pe_data.get('vega', 0),
                    'pe_gamma': pe_data.get('gamma', 0),
                    'pe_vs_ce_oi_bar': pe_vs_ce_oi_bar
                }
                
                processed_records.append(record)
        
        return processed_records
    
    def store_option_data(self, option_data, timestamp=None):
        """Store option data in MySQL database"""
        try:
            if timestamp is None:
                timestamp = datetime.now(self.ist_tz).strftime('%Y-%m-%d %H:%M:%S')
            
            # Process the data
            processed_records = self.process_option_data(option_data, timestamp)
            
            if not processed_records:
                print("⚠️  No records to store")
                return False
            
            # Connect to database
            connection = self.get_connection()
            if connection is None:
                return False
            
            cursor = connection.cursor()
            
            # Insert records
            insert_query = '''
                INSERT INTO option_snapshots (
                    time, index_name, expiry, strike,
                    ce_oi, ce_oi_change, ce_oi_percent_change,
                    ce_ltp, ce_ltp_change, ce_ltp_percent_change,
                    ce_volume, ce_iv, ce_delta, ce_theta, ce_vega, ce_gamma,
                    ce_vs_pe_oi_bar,
                    pe_oi, pe_oi_change, pe_oi_percent_change,
                    pe_ltp, pe_ltp_change, pe_ltp_percent_change,
                    pe_volume, pe_iv, pe_delta, pe_theta, pe_vega, pe_gamma,
                    pe_vs_ce_oi_bar
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            '''
            
            for record in processed_records:
                cursor.execute(insert_query, (
                    record['time'], record['index_name'], record['expiry'], record['strike'],
                    record['ce_oi'], record['ce_oi_change'], record['ce_oi_percent_change'],
                    record['ce_ltp'], record['ce_ltp_change'], record['ce_ltp_percent_change'],
                    record['ce_volume'], record['ce_iv'], record['ce_delta'], record['ce_theta'], record['ce_vega'], record['ce_gamma'],
                    record['ce_vs_pe_oi_bar'],
                    record['pe_oi'], record['pe_oi_change'], record['pe_oi_percent_change'],
                    record['pe_ltp'], record['pe_ltp_change'], record['pe_ltp_percent_change'],
                    record['pe_volume'], record['pe_iv'], record['pe_delta'], record['pe_theta'], record['pe_vega'], record['pe_gamma'],
                    record['pe_vs_ce_oi_bar']
                ))
            
            connection.commit()
            connection.close()
            
            print(f"✅ Stored {len(processed_records)} option records in MySQL")
            return True
            
        except Error as e:
            print(f"❌ Error storing option data in MySQL: {e}")
            return False

def store_option_chain_data(option_data, timestamp=None):
    """
    Main function to store option chain data in MySQL
    
    Args:
        option_data: List of option data dictionaries
        timestamp: Optional timestamp override
    
    Returns:
        bool: True if successful, False otherwise
    """
    store = MySQLOptionDataStore()
    return store.store_option_data(option_data, timestamp) 