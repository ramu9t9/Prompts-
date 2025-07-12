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
import time
from typing import Dict

def safe_int(val):
    try:
        if isinstance(val, (int, float)):
            return int(val)
        if isinstance(val, str):
            return int(float(val))
        if hasattr(val, '__int__'):
            return int(val)
    except Exception:
        pass
    return 0

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
            
            if result is not None and len(result) >= 4:
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
    
    def create_new_schema(self):
        """Create the new Phase 1 schema with three tables for OI tracking"""
        try:
            connection = self.get_connection()
            if connection is None:
                return False
            
            cursor = connection.cursor()
            
            # 1. Create options_raw_data table
            create_raw_table_query = """
            CREATE TABLE IF NOT EXISTS options_raw_data (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                bucket_ts TIMESTAMP NOT NULL,
                trading_symbol VARCHAR(25) NOT NULL,
                strike INT NOT NULL,
                option_type CHAR(2) NOT NULL,

                -- Raw Market Data
                ltp DECIMAL(10,2) DEFAULT 0,
                volume BIGINT DEFAULT 0,
                oi BIGINT DEFAULT 0,
                price_change DECIMAL(10,2) DEFAULT 0,
                change_percent DECIMAL(8,2) DEFAULT 0,
                open_price DECIMAL(10,2) DEFAULT 0,
                high_price DECIMAL(10,2) DEFAULT 0,
                low_price DECIMAL(10,2) DEFAULT 0,
                close_price DECIMAL(10,2) DEFAULT 0,

                -- Greeks
                delta DECIMAL(8,4) DEFAULT 0,
                gamma DECIMAL(8,4) DEFAULT 0,
                theta DECIMAL(8,4) DEFAULT 0,
                vega DECIMAL(8,4) DEFAULT 0,
                iv DECIMAL(8,2) DEFAULT 0,

                -- Metadata
                index_name VARCHAR(20) NOT NULL,
                expiry_date DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                INDEX idx_bucket_symbol (bucket_ts, trading_symbol),
                INDEX idx_strike_type (strike, option_type),
                INDEX idx_index_expiry (index_name, expiry_date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
            
            # 2. Create historical_oi_tracking table
            create_historical_table_query = """
            CREATE TABLE IF NOT EXISTS historical_oi_tracking (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                bucket_ts TIMESTAMP NOT NULL,
                trading_symbol VARCHAR(25) NOT NULL,
                strike INT NOT NULL,

                -- OI (combined)
                ce_oi BIGINT DEFAULT 0,
                pe_oi BIGINT DEFAULT 0,
                total_oi BIGINT DEFAULT 0,

                -- OI Changes (calculated)
                ce_oi_change BIGINT DEFAULT 0,
                pe_oi_change BIGINT DEFAULT 0,
                ce_oi_pct_change DECIMAL(8,2) DEFAULT 0,
                pe_oi_pct_change DECIMAL(8,2) DEFAULT 0,

                -- Price Data
                ce_ltp DECIMAL(10,2) DEFAULT 0,
                pe_ltp DECIMAL(10,2) DEFAULT 0,
                ce_ltp_change_pct DECIMAL(8,2) DEFAULT 0,
                pe_ltp_change_pct DECIMAL(8,2) DEFAULT 0,
                index_ltp DECIMAL(10,2) DEFAULT 0,

                -- Volume
                ce_volume BIGINT DEFAULT 0,
                pe_volume BIGINT DEFAULT 0,
                ce_volume_change BIGINT DEFAULT 0,
                pe_volume_change BIGINT DEFAULT 0,

                -- OI Ratio Metrics
                pcr DECIMAL(8,4) DEFAULT 0,
                ce_pe_ratio DECIMAL(8,4) DEFAULT 0,

                -- Classification + Confidence
                oi_quadrant ENUM('LONG_BUILDUP', 'SHORT_COVERING', 'SHORT_BUILDUP', 'LONG_UNWINDING', 'NEUTRAL') DEFAULT 'NEUTRAL',
                confidence_score INT DEFAULT 0,
                strike_rank INT DEFAULT NULL,
                delta_band ENUM('FAR_OTM','OTM','ATM','ITM','DEEP_ITM') DEFAULT 'ATM',

                -- Metadata
                index_name VARCHAR(20) NOT NULL,
                expiry_date DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                UNIQUE KEY unique_bucket_strike (bucket_ts, trading_symbol),
                INDEX idx_bucket_ts (bucket_ts),
                INDEX idx_strike (strike),
                INDEX idx_quadrant (oi_quadrant)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
            
            # 3. Create live_oi_tracking table
            create_live_table_query = """
            CREATE TABLE IF NOT EXISTS live_oi_tracking (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                bucket_ts TIMESTAMP NOT NULL,
                trading_symbol VARCHAR(25) NOT NULL,
                strike INT NOT NULL,

                ce_oi BIGINT DEFAULT 0,
                pe_oi BIGINT DEFAULT 0,
                ce_oi_change BIGINT DEFAULT 0,
                pe_oi_change BIGINT DEFAULT 0,

                -- Metrics
                pcr DECIMAL(8,4) DEFAULT 0,
                oi_quadrant ENUM('LONG_BUILDUP', 'SHORT_COVERING', 'SHORT_BUILDUP', 'LONG_UNWINDING', 'NEUTRAL') DEFAULT 'NEUTRAL',

                -- Metadata
                index_name VARCHAR(20) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                UNIQUE KEY unique_live_bucket_strike (bucket_ts, trading_symbol),
                INDEX idx_live_bucket (bucket_ts)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
            
            # Execute table creation
            cursor.execute(create_raw_table_query)
            cursor.execute(create_historical_table_query)
            cursor.execute(create_live_table_query)
            
            # Phase 3: Add performance indexes
            print("🔧 Adding Phase 3 performance indexes...")
            def ensure_index(connection, table, index_name, create_sql):
                with connection.cursor() as cursor:
                    cursor.execute(f"SHOW INDEX FROM {table} WHERE Key_name = %s", (index_name,))
                    results = cursor.fetchall()
                    if not results:
                        try:
                            cursor.execute(create_sql)
                        except Exception:
                            pass
            ensure_index(connection, 'historical_oi_tracking', 'idx_bucket_index', "ALTER TABLE historical_oi_tracking ADD INDEX idx_bucket_index (bucket_ts, index_name)")
            ensure_index(connection, 'historical_oi_tracking', 'idx_confidence', "ALTER TABLE historical_oi_tracking ADD INDEX idx_confidence (confidence_score DESC)")
            ensure_index(connection, 'options_raw_data', 'idx_trading_symbol', "ALTER TABLE options_raw_data ADD INDEX idx_trading_symbol (trading_symbol)")
            ensure_index(connection, 'live_oi_tracking', 'idx_live_bucket_ts', "ALTER TABLE live_oi_tracking ADD INDEX idx_live_bucket_ts (bucket_ts)")
            ensure_index(connection, 'live_oi_tracking', 'idx_live_index', "ALTER TABLE live_oi_tracking ADD INDEX idx_live_index (index_name)")
            
            connection.commit()
            connection.close()
            
            print("✅ Phase 1 schema created successfully with three tables:")
            print("   - options_raw_data")
            print("   - historical_oi_tracking") 
            print("   - live_oi_tracking")
            print("✅ Phase 3 performance indexes added")
            return True
            
        except Error as e:
            print(f"❌ Error creating Phase 1 schema: {e}")
            return False
    
    def insert_single_snapshot(self, snapshot_data):
        """Insert a single snapshot using the new schema"""
        try:
            connection = self.get_connection()
            if connection is None:
                return False
            
            cursor = connection.cursor()
            
            # Insert using new schema
            insert_query = '''
                INSERT INTO option_snapshots (
                    bucket_ts, trading_symbol, option_type, strike,
                    ce_oi, ce_price_close, pe_oi, pe_price_close
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    ce_oi = VALUES(ce_oi),
                    ce_price_close = VALUES(ce_price_close),
                    pe_oi = VALUES(pe_oi),
                    pe_price_close = VALUES(pe_price_close)
            '''
            
            values = (
                snapshot_data['bucket_ts'],
                snapshot_data['trading_symbol'],
                snapshot_data['option_type'],
                snapshot_data['strike'],
                snapshot_data['ce_oi'],
                snapshot_data['ce_price_close'],
                snapshot_data['pe_oi'],
                snapshot_data['pe_price_close']
            )
            
            cursor.execute(insert_query, values)
            connection.commit()
            connection.close()
            
            return True
            
        except Error as e:
            print(f"❌ Error inserting snapshot: {e}")
            return False

    def insert_raw_data(self, raw_data_list):
        """Insert raw option data into options_raw_data table using batch inserts"""
        try:
            if not raw_data_list:
                return False
            
            connection = self.get_connection()
            if connection is None:
                return False
            
            cursor = connection.cursor()
            
            # Phase 3: Use batch INSERT for better performance
            insert_query = '''
                INSERT INTO options_raw_data (
                    bucket_ts, trading_symbol, strike, option_type,
                    ltp, volume, oi, price_change, change_percent,
                    open_price, high_price, low_price, close_price,
                    delta, gamma, theta, vega, iv,
                    index_name, expiry_date
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            '''
            
            # Phase 3: True batch insert for better performance
            values_list = []
            for raw_data in raw_data_list:
                values = (
                    raw_data['bucket_ts'],
                    raw_data['trading_symbol'],
                    raw_data['strike'],
                    raw_data['option_type'],
                    raw_data.get('ltp', 0),
                    raw_data.get('volume', 0),
                    raw_data.get('oi', 0),
                    raw_data.get('price_change', 0),
                    raw_data.get('change_percent', 0),
                    raw_data.get('open_price', 0),
                    raw_data.get('high_price', 0),
                    raw_data.get('low_price', 0),
                    raw_data.get('close_price', 0),
                    raw_data.get('delta', 0),
                    raw_data.get('gamma', 0),
                    raw_data.get('theta', 0),
                    raw_data.get('vega', 0),
                    raw_data.get('iv', 0),
                    raw_data['index_name'],
                    raw_data['expiry_date']
                )
                values_list.append(values)
            
            # Execute batch insert
            cursor.executemany(insert_query, values_list)
            
            connection.commit()
            connection.close()
            
            print(f"✅ Inserted {len(raw_data_list)} raw data records")
            return True
            
        except Error as e:
            print(f"❌ Error inserting raw data: {e}")
            return False

    def insert_historical_data(self, historical_data_list):
        """Insert processed historical data into historical_oi_tracking table"""
        try:
            if not historical_data_list:
                return False
            
            connection = self.get_connection()
            if connection is None:
                return False
            
            cursor = connection.cursor()
            
            insert_query = '''
                INSERT INTO historical_oi_tracking (
                    bucket_ts, trading_symbol, strike,
                    ce_oi, pe_oi, total_oi,
                    ce_oi_change, pe_oi_change, ce_oi_pct_change, pe_oi_pct_change,
                    ce_ltp, pe_ltp, ce_ltp_change_pct, pe_ltp_change_pct, index_ltp,
                    ce_volume, pe_volume, ce_volume_change, pe_volume_change,
                    pcr, ce_pe_ratio,
                    oi_quadrant, confidence_score, strike_rank, delta_band,
                    index_name, expiry_date
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    ce_oi = VALUES(ce_oi), pe_oi = VALUES(pe_oi), total_oi = VALUES(total_oi),
                    ce_oi_change = VALUES(ce_oi_change), pe_oi_change = VALUES(pe_oi_change),
                    ce_oi_pct_change = VALUES(ce_oi_pct_change), pe_oi_pct_change = VALUES(pe_oi_pct_change),
                    ce_ltp = VALUES(ce_ltp), pe_ltp = VALUES(pe_ltp),
                    ce_ltp_change_pct = VALUES(ce_ltp_change_pct), pe_ltp_change_pct = VALUES(pe_ltp_change_pct),
                    index_ltp = VALUES(index_ltp),
                    ce_volume = VALUES(ce_volume), pe_volume = VALUES(pe_volume),
                    ce_volume_change = VALUES(ce_volume_change), pe_volume_change = VALUES(pe_volume_change),
                    pcr = VALUES(pcr), ce_pe_ratio = VALUES(ce_pe_ratio),
                    oi_quadrant = VALUES(oi_quadrant), confidence_score = VALUES(confidence_score),
                    strike_rank = VALUES(strike_rank), delta_band = VALUES(delta_band)
            '''
            
            # Phase 3: True batch insert for better performance
            values_list = []
            for historical_data in historical_data_list:
                values = (
                    historical_data['bucket_ts'],
                    historical_data['trading_symbol'],
                    historical_data['strike'],
                    historical_data.get('ce_oi', 0),
                    historical_data.get('pe_oi', 0),
                    historical_data.get('total_oi', 0),
                    historical_data.get('ce_oi_change', 0),
                    historical_data.get('pe_oi_change', 0),
                    historical_data.get('ce_oi_pct_change', 0),
                    historical_data.get('pe_oi_pct_change', 0),
                    historical_data.get('ce_ltp', 0),
                    historical_data.get('pe_ltp', 0),
                    historical_data.get('ce_ltp_change_pct', 0),
                    historical_data.get('pe_ltp_change_pct', 0),
                    historical_data.get('index_ltp', 0),
                    historical_data.get('ce_volume', 0),
                    historical_data.get('pe_volume', 0),
                    historical_data.get('ce_volume_change', 0),
                    historical_data.get('pe_volume_change', 0),
                    historical_data.get('pcr', 0),
                    historical_data.get('ce_pe_ratio', 0),
                    historical_data.get('oi_quadrant', 'NEUTRAL'),
                    historical_data.get('confidence_score', 0),
                    historical_data.get('strike_rank', None),
                    historical_data.get('delta_band', 'ATM'),
                    historical_data['index_name'],
                    historical_data['expiry_date']
                )
                values_list.append(values)
            
            # Execute batch insert
            cursor.executemany(insert_query, values_list)
            
            connection.commit()
            connection.close()
            
            print(f"✅ Inserted {len(historical_data_list)} historical data records")
            return True
            
        except Error as e:
            print(f"❌ Error inserting historical data: {e}")
            return False

    def insert_live_data(self, live_data_list):
        """Insert live data into live_oi_tracking table"""
        try:
            if not live_data_list:
                return False
            
            connection = self.get_connection()
            if connection is None:
                return False
            
            cursor = connection.cursor()
            
            insert_query = '''
                INSERT INTO live_oi_tracking (
                    bucket_ts, trading_symbol, strike,
                    ce_oi, pe_oi, ce_oi_change, pe_oi_change,
                    pcr, oi_quadrant, index_name
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    ce_oi = VALUES(ce_oi), pe_oi = VALUES(pe_oi),
                    ce_oi_change = VALUES(ce_oi_change), pe_oi_change = VALUES(pe_oi_change),
                    pcr = VALUES(pcr), oi_quadrant = VALUES(oi_quadrant)
            '''
            
            for live_data in live_data_list:
                values = (
                    live_data['bucket_ts'],
                    live_data['trading_symbol'],
                    live_data['strike'],
                    live_data.get('ce_oi', 0),
                    live_data.get('pe_oi', 0),
                    live_data.get('ce_oi_change', 0),
                    live_data.get('pe_oi_change', 0),
                    live_data.get('pcr', 0),
                    live_data.get('oi_quadrant', 'NEUTRAL'),
                    live_data['index_name']
                )
                cursor.execute(insert_query, values)
            
            connection.commit()
            connection.close()
            
            print(f"✅ Inserted {len(live_data_list)} live data records")
            return True
            
        except Error as e:
            print(f"❌ Error inserting live data: {e}")
            return False

    def insert_ai_trade_setup(self, setup_data: Dict) -> bool:
        """Insert AI trade setup into ai_trade_setups table"""
        try:
            connection = self.get_connection()
            if connection is None:
                return False
            
            cursor = connection.cursor()
            
            insert_query = '''
                INSERT INTO ai_trade_setups (
                    bucket_ts, index_name, bias, strategy, entry_strike, entry_type,
                    entry_price, stop_loss, target, confidence, rationale, model_used,
                    response_raw, spot_ltp, pcr_oi, pcr_volume, vwap, cpr_top, cpr_bottom
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            '''
            
            values = (
                setup_data['bucket_ts'],
                setup_data['index_name'],
                setup_data['bias'],
                setup_data['strategy'],
                setup_data['entry_strike'],
                setup_data['entry_type'],
                setup_data['entry_price'],
                setup_data['stop_loss'],
                setup_data['target'],
                setup_data['confidence'],
                setup_data['rationale'],
                setup_data['model_used'],
                setup_data['response_raw'],
                setup_data.get('spot_ltp'),
                setup_data.get('pcr_oi'),
                setup_data.get('pcr_volume'),
                setup_data.get('vwap'),
                setup_data.get('cpr_top'),
                setup_data.get('cpr_bottom')
            )
            
            cursor.execute(insert_query, values)
            connection.commit()
            connection.close()
            
            return True
            
        except Error as e:
            print(f"❌ Error inserting AI trade setup: {e}")
            return False

    # Phase 2 Methods
    def clear_live_tracking(self):
        """Clear the live_oi_tracking table (called at start of new market day)"""
        try:
            connection = self.get_connection()
            if connection is None:
                return False
            
            cursor = connection.cursor()
            cursor.execute("TRUNCATE TABLE live_oi_tracking")
            connection.commit()
            connection.close()
            
            print("✅ Live tracking table cleared")
            return True
            
        except Error as e:
            print(f"❌ Error clearing live tracking: {e}")
            return False

    def is_new_market_day(self):
        """Check if we're starting a new market day by checking last bucket timestamp"""
        try:
            connection = self.get_connection()
            if connection is None:
                return True  # Assume new day if can't connect
            
            cursor = connection.cursor()
            
            # Check last bucket timestamp from historical table
            cursor.execute("""
                SELECT MAX(bucket_ts) FROM historical_oi_tracking 
                WHERE bucket_ts >= CURDATE()
            """)
            
            result = cursor.fetchone()
            connection.close()
            
            if result is not None and safe_int(result[0]):
                return True  # No data today, so it's a new day
            
            last_bucket = safe_int(result[0]) if result is not None else 0
            now = datetime.now(self.ist_tz)
            
            # Handle different data types from database
            try:
                if isinstance(last_bucket, datetime):
                    last_bucket_date = last_bucket.date()
                elif isinstance(last_bucket, str):
                    last_bucket_date = datetime.strptime(last_bucket, '%Y-%m-%d %H:%M:%S').date()
                else:
                    # Assume it's a datetime object
                    last_bucket_date = last_bucket.date()
                
                return last_bucket_date != now.date()
            except Exception as e:
                print(f"⚠️  Error comparing dates: {e}")
                return True  # Assume new day on error
            
        except Error as e:
            print(f"❌ Error checking new market day: {e}")
            return True  # Assume new day on error

    def get_existing_buckets(self, start_time, end_time, index_name=None):
        """Get set of existing bucket timestamps for gap detection"""
        try:
            connection = self.get_connection()
            if connection is None:
                return set()
            
            cursor = connection.cursor()
            
            if index_name:
                query = """
                    SELECT DISTINCT bucket_ts FROM historical_oi_tracking 
                    WHERE bucket_ts BETWEEN %s AND %s AND index_name = %s
                """
                cursor.execute(query, (start_time, end_time, index_name))
            else:
                query = """
                    SELECT DISTINCT bucket_ts FROM historical_oi_tracking 
                    WHERE bucket_ts BETWEEN %s AND %s
                """
                cursor.execute(query, (start_time, end_time))
            
            results = cursor.fetchall()
            connection.close()
            
            existing_buckets = set()
            for result in results:
                if result is not None and result[0]:
                    existing_buckets.add(safe_int(result[0]))
            
            return existing_buckets
            
        except Error as e:
            print(f"❌ Error getting existing buckets: {e}")
            return set()

    def backfill_missing_buckets(self, start_dt, end_dt, index_name=None, fetcher=None):
        """
        Backfill missing buckets between start_dt and end_dt
        
        Args:
            start_dt: Start datetime
            end_dt: End datetime  
            index_name: Specific index to backfill (None for all)
            fetcher: OptionChainFetcher instance
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            print(f"🔄 Starting backfill from {start_dt} to {end_dt}")
            
            if not fetcher:
                print("❌ Fetcher instance required for backfill")
                return False
            
            # Get existing buckets
            existing_buckets = self.get_existing_buckets(start_dt, end_dt, index_name)
            print(f"📊 Found {len(existing_buckets)} existing buckets")
            
            # Generate all required buckets
            from utils.market_calendar import MarketCalendar
            calendar = MarketCalendar()
            all_buckets = calendar.generate_bucket_timestamps(start_dt, end_dt)
            
            # Find missing buckets
            missing_buckets = [b for b in all_buckets if b not in existing_buckets]
            print(f"📊 Found {len(missing_buckets)} missing buckets to backfill")
            
            if not missing_buckets:
                print("✅ No missing buckets to backfill")
                return True
            
            success_count = 0
            
            for i, bucket_ts in enumerate(missing_buckets, 1):
                print(f"🔄 Backfilling {i}/{len(missing_buckets)}: {bucket_ts.strftime('%H:%M:%S')}")
                
                try:
                    # Fetch snapshot for this bucket
                    complete_snapshot = fetcher.fetch_complete_snapshot(range_strikes=5)
                    
                    if complete_snapshot:
                        # Override bucket timestamp for historical data
                        for raw_data in complete_snapshot['raw_data']:
                            raw_data['bucket_ts'] = bucket_ts
                        
                        for historical_data in complete_snapshot['historical_data']:
                            historical_data['bucket_ts'] = bucket_ts
                        
                        # Store only raw and historical data (no live data for backfill)
                        if self.insert_raw_data(complete_snapshot['raw_data']):
                            if self.insert_historical_data(complete_snapshot['historical_data']):
                                success_count += 1
                                print(f"✅ Backfilled bucket {bucket_ts.strftime('%H:%M:%S')}")
                            else:
                                print(f"❌ Failed to insert historical data for {bucket_ts.strftime('%H:%M:%S')}")
                        else:
                            print(f"❌ Failed to insert raw data for {bucket_ts.strftime('%H:%M:%S')}")
                    else:
                        print(f"⚠️  No data fetched for {bucket_ts.strftime('%H:%M:%S')}")
                    
                    # Small delay to avoid rate limiting
                    time.sleep(1)
                    
                except Exception as e:
                    print(f"❌ Error backfilling {bucket_ts.strftime('%H:%M:%S')}: {str(e)}")
                    continue
            
            print(f"🎉 Backfill completed: {success_count}/{len(missing_buckets)} buckets filled")
            return success_count > 0
            
        except Exception as e:
            print(f"❌ Error in backfill_missing_buckets: {str(e)}")
            return False

    def get_last_bucket_timestamp(self, index_name=None):
        """Get the last bucket timestamp from historical_oi_tracking"""
        try:
            connection = self.get_connection()
            if connection is None:
                return None
            
            cursor = connection.cursor()
            
            if index_name:
                query = """
                    SELECT MAX(bucket_ts) FROM historical_oi_tracking 
                    WHERE index_name = %s
                """
                cursor.execute(query, (index_name,))
            else:
                query = "SELECT MAX(bucket_ts) FROM historical_oi_tracking"
                cursor.execute(query)
            
            result = cursor.fetchone()
            connection.close()
            
            if result is not None and result[0]:
                return safe_int(result[0])
            return None
            
        except Error as e:
            print(f"❌ Error getting last bucket timestamp: {e}")
            return None

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

# Wrapper Functions
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

def insert_snapshot(snapshot_data):
    """
    Insert a single snapshot into the database using the new schema
    
    Args:
        snapshot_data: Dictionary containing snapshot data
    
    Returns:
        bool: True if successful, False otherwise
    """
    store = MySQLOptionDataStore()
    return store.insert_single_snapshot(snapshot_data)

def insert_phase1_raw_data(raw_data_list):
    """
    Insert raw data into options_raw_data table
    
    Args:
        raw_data_list: List of raw data dictionaries
    
    Returns:
        bool: True if successful, False otherwise
    """
    store = MySQLOptionDataStore()
    return store.insert_raw_data(raw_data_list)

def insert_phase1_historical_data(historical_data_list):
    """
    Insert historical data into historical_oi_tracking table
    
    Args:
        historical_data_list: List of historical data dictionaries
    
    Returns:
        bool: True if successful, False otherwise
    """
    store = MySQLOptionDataStore()
    return store.insert_historical_data(historical_data_list)

def insert_phase1_live_data(live_data_list):
    """
    Insert live data into live_oi_tracking table
    
    Args:
        live_data_list: List of live data dictionaries
    
    Returns:
        bool: True if successful, False otherwise
    """
    store = MySQLOptionDataStore()
    return store.insert_live_data(live_data_list)

def create_phase1_schema():
    """
    Create the Phase 1 schema with three tables
    
    Returns:
        bool: True if successful, False otherwise
    """
    store = MySQLOptionDataStore()
    return store.create_new_schema()

def store_phase1_complete_snapshot(complete_snapshot):
    """
    Store a complete snapshot in all three Phase 1 tables
    
    Args:
        complete_snapshot: Dictionary containing raw_data, historical_data, and live_data lists
    
    Returns:
        bool: True if successful, False otherwise
    """
    store = MySQLOptionDataStore()
    
    success = True
    
    # Insert raw data
    if complete_snapshot.get('raw_data'):
        if not store.insert_raw_data(complete_snapshot['raw_data']):
            success = False
    
    # Insert historical data
    if complete_snapshot.get('historical_data'):
        if not store.insert_historical_data(complete_snapshot['historical_data']):
            success = False
    
    # Insert live data
    if complete_snapshot.get('live_data'):
        if not store.insert_live_data(complete_snapshot['live_data']):
            success = False
    
    return success

def insert_ai_trade_setup(setup_data: Dict) -> bool:
    """
    Insert AI trade setup into ai_trade_setups table
    
    Args:
        setup_data: Dictionary containing AI trade setup data
    
    Returns:
        bool: True if successful, False otherwise
    """
    store = MySQLOptionDataStore()
    return store.insert_ai_trade_setup(setup_data)

# Phase 2 Wrapper Functions
def clear_live_tracking():
    """Clear the live_oi_tracking table"""
    store = MySQLOptionDataStore()
    return store.clear_live_tracking()

def is_new_market_day():
    """Check if we're starting a new market day"""
    store = MySQLOptionDataStore()
    return store.is_new_market_day()

def backfill_missing_buckets(start_dt, end_dt, index_name=None, fetcher=None):
    """Backfill missing buckets between start_dt and end_dt"""
    store = MySQLOptionDataStore()
    return store.backfill_missing_buckets(start_dt, end_dt, index_name, fetcher)

def get_last_bucket_timestamp(index_name=None):
    """Get the last bucket timestamp from historical_oi_tracking"""
    store = MySQLOptionDataStore()
    return store.get_last_bucket_timestamp(index_name)

def should_store_snapshot(prev_snapshot, new_snapshot, bucket_ts):
    """Determine if we should store a new snapshot"""
    store = MySQLOptionDataStore()
    return store.should_store_snapshot(prev_snapshot, new_snapshot, bucket_ts) 