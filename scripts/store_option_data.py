"""
Option Data Storage Module

This module handles storing option chain data in SQLite database.
Always refer to official documentation: https://smartapi.angelone.in/docs

API Compliance:
- Data Usage: Use data only for authorized purposes
- Terms of Service: Follow Angel One's terms and conditions
"""

import sqlite3
import os
from datetime import datetime
import pytz

class OptionDataStore:
    def __init__(self, db_path='option_chain.db'):
        self.db_path = db_path
        self.ist_tz = pytz.timezone('Asia/Kolkata')
        
    def get_previous_snapshot(self, index_name, expiry, strike):
        """Get the previous snapshot for comparison"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT ce_oi, ce_ltp, pe_oi, pe_ltp
                FROM option_snapshots
                WHERE index_name = ? AND expiry = ? AND strike = ?
                ORDER BY time DESC
                LIMIT 1
            ''', (index_name, expiry, strike))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    'ce_oi': result[0],
                    'ce_ltp': result[1],
                    'pe_oi': result[2],
                    'pe_ltp': result[3]
                }
            return None
            
        except Exception as e:
            print(f"❌ Error getting previous snapshot: {str(e)}")
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
            # Calculate CE changes
            ce_oi_change = current_data.get('ce_oi', 0) - previous_data.get('ce_oi', 0)
            ce_oi_percent_change = (ce_oi_change / (previous_data.get('ce_oi', 1) + 1e-5)) * 100
            
            ce_ltp_change = current_data.get('ce_ltp', 0) - previous_data.get('ce_ltp', 0)
            ce_ltp_percent_change = (ce_ltp_change / (previous_data.get('ce_ltp', 1) + 1e-5)) * 100
            
            # Calculate PE changes
            pe_oi_change = current_data.get('pe_oi', 0) - previous_data.get('pe_oi', 0)
            pe_oi_percent_change = (pe_oi_change / (previous_data.get('pe_oi', 1) + 1e-5)) * 100
            
            pe_ltp_change = current_data.get('pe_ltp', 0) - previous_data.get('pe_ltp', 0)
            pe_ltp_percent_change = (pe_ltp_change / (previous_data.get('pe_ltp', 1) + 1e-5)) * 100
            
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
        ce_vs_pe_oi_bar = ce_oi / (pe_oi + 1e-5)
        pe_vs_ce_oi_bar = pe_oi / (ce_oi + 1e-5)
        
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
                    'change': option['change'],
                    'change_percent': option['change_percent']
                }
            
            # Process each strike
            for strike, strike_data in strikes_data.items():
                ce_data = strike_data.get('CE', {})
                pe_data = strike_data.get('PE', {})
                
                # Get previous snapshot for comparison
                previous_data = self.get_previous_snapshot(index_name, expiry, strike)
                
                # Current data
                current_data = {
                    'ce_oi': 0,  # OI not available in current API response
                    'ce_ltp': ce_data.get('ltp', 0),
                    'pe_oi': 0,  # OI not available in current API response
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
                    'ce_iv': 0,  # IV not available in current API response
                    'ce_delta': 0,  # Greeks not available in current API response
                    'ce_theta': 0,
                    'ce_vega': 0,
                    'ce_gamma': 0,
                    'ce_vs_pe_oi_bar': ce_vs_pe_oi_bar,
                    
                    # PE data
                    'pe_oi': current_data['pe_oi'],
                    'pe_oi_change': changes['pe_oi_change'],
                    'pe_oi_percent_change': changes['pe_oi_percent_change'],
                    'pe_ltp': current_data['pe_ltp'],
                    'pe_ltp_change': changes['pe_ltp_change'],
                    'pe_ltp_percent_change': changes['pe_ltp_percent_change'],
                    'pe_volume': pe_data.get('volume', 0),
                    'pe_iv': 0,  # IV not available in current API response
                    'pe_delta': 0,  # Greeks not available in current API response
                    'pe_theta': 0,
                    'pe_vega': 0,
                    'pe_gamma': 0,
                    'pe_vs_ce_oi_bar': pe_vs_ce_oi_bar
                }
                
                processed_records.append(record)
        
        return processed_records
    
    def store_option_data(self, option_data, timestamp=None):
        """Store option data in SQLite database"""
        try:
            if timestamp is None:
                timestamp = datetime.now(self.ist_tz).strftime('%Y-%m-%d %H:%M:%S')
            
            # Process the data
            processed_records = self.process_option_data(option_data, timestamp)
            
            if not processed_records:
                print("⚠️  No records to store")
                return False
            
            # Connect to database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Insert records
            for record in processed_records:
                cursor.execute('''
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
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
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
            
            conn.commit()
            conn.close()
            
            print(f"✅ Stored {len(processed_records)} option records")
            return True
            
        except Exception as e:
            print(f"❌ Error storing option data: {str(e)}")
            return False

def store_option_chain_data(option_data, timestamp=None):
    """
    Main function to store option chain data
    
    Args:
        option_data: List of option data dictionaries
        timestamp: Optional timestamp override
    
    Returns:
        bool: True if successful, False otherwise
    """
    store = OptionDataStore()
    return store.store_option_data(option_data, timestamp) 