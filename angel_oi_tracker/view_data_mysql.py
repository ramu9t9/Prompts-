#!/usr/bin/env python3
"""
MySQL Data Viewer for Angel One Options Analytics

This script allows you to view and analyze option data stored in MySQL database.
"""

import mysql.connector
from mysql.connector import Error
import pandas as pd
import os
from datetime import datetime, timedelta
import pytz

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

class MySQLDataViewer:
    def __init__(self, host='localhost', user='root', password='YourNewPassword', database='options_analytics'):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        
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
    
    def get_latest_data(self, limit=20):
        """Get the latest option data"""
        try:
            connection = self.get_connection()
            if connection is None:
                return None
            
            query = '''
                SELECT time, index_name, expiry, strike,
                       ce_ltp, ce_volume, ce_oi,
                       pe_ltp, pe_volume, pe_oi,
                       ce_vs_pe_oi_bar, pe_vs_ce_oi_bar
                FROM option_snapshots
                ORDER BY time DESC
                LIMIT %s
            '''
            
            df = pd.read_sql(query, connection, params=(limit,))
            connection.close()
            
            return df
            
        except Error as e:
            print(f"❌ Error fetching latest data: {e}")
            return None
    
    def get_summary_stats(self):
        """Get summary statistics"""
        try:
            connection = self.get_connection()
            if connection is None:
                return None
            
            # Total records
            cursor = connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM option_snapshots")
            result = cursor.fetchone()
            total_records = result[0] if result is not None else 0
            
            # Date range
            cursor.execute("SELECT MIN(time), MAX(time) FROM option_snapshots")
            result = cursor.fetchone()
            if result is not None:
                min_time, max_time = result
            else:
                min_time, max_time = None, None
            
            # Records by index
            cursor.execute("""
                SELECT index_name, COUNT(*) as count
                FROM option_snapshots
                GROUP BY index_name
                ORDER BY count DESC
            """)
            index_counts = cursor.fetchall()
            
            # Today's records
            today = datetime.now(self.ist_tz).strftime('%Y-%m-%d')
            cursor.execute("""
                SELECT COUNT(*) FROM option_snapshots 
                WHERE DATE(time) = %s
            """, (today,))
            result = cursor.fetchone()
            today_count = result[0] if result is not None else 0
            
            connection.close()
            
            return {
                'total_records': total_records,
                'date_range': (min_time, max_time),
                'index_counts': index_counts,
                'today_count': today_count
            }
            
        except Error as e:
            print(f"❌ Error fetching summary stats: {e}")
            return None
    
    def get_index_data(self, index_name, limit=50):
        """Get data for a specific index"""
        try:
            connection = self.get_connection()
            if connection is None:
                return None
            
            query = '''
                SELECT time, expiry, strike,
                       ce_ltp, ce_volume, ce_oi, ce_oi_change,
                       pe_ltp, pe_volume, pe_oi, pe_oi_change,
                       ce_vs_pe_oi_bar, pe_vs_ce_oi_bar
                FROM option_snapshots
                WHERE index_name = %s
                ORDER BY time DESC, strike
                LIMIT %s
            '''
            
            df = pd.read_sql(query, connection, params=(index_name, limit))
            connection.close()
            
            return df
            
        except Error as e:
            print(f"❌ Error fetching {index_name} data: {e}")
            return None
    
    def get_high_volume_options(self, min_volume=1000, limit=20):
        """Get options with high volume"""
        try:
            connection = self.get_connection()
            if connection is None:
                return None
            
            query = '''
                SELECT time, index_name, expiry, strike,
                       ce_ltp, ce_volume, pe_ltp, pe_volume,
                       (ce_volume + pe_volume) as total_volume
                FROM option_snapshots
                WHERE (ce_volume + pe_volume) >= %s
                ORDER BY (ce_volume + pe_volume) DESC
                LIMIT %s
            '''
            
            df = pd.read_sql(query, connection, params=(min_volume, limit))
            connection.close()
            
            return df
            
        except Error as e:
            print(f"❌ Error fetching high volume data: {e}")
            return None
    
    def get_strike_analysis(self, index_name, expiry, limit=20):
        """Get analysis for a specific strike range"""
        try:
            connection = self.get_connection()
            if connection is None:
                return None
            
            query = '''
                SELECT time, strike,
                       ce_ltp, ce_volume, ce_oi, ce_oi_change,
                       pe_ltp, pe_volume, pe_oi, pe_oi_change,
                       ce_vs_pe_oi_bar, pe_vs_ce_oi_bar
                FROM option_snapshots
                WHERE index_name = %s AND expiry = %s
                ORDER BY time DESC, strike
                LIMIT %s
            '''
            
            df = pd.read_sql(query, connection, params=(index_name, expiry, limit))
            connection.close()
            
            return df
            
        except Error as e:
            print(f"❌ Error fetching strike analysis: {e}")
            return None

def display_data():
    """Main function to display data"""
    print("📊 MySQL Options Analytics Data Viewer")
    print("=" * 50)
    
    viewer = MySQLDataViewer()
    
    # Get summary statistics
    print("\n📈 Summary Statistics:")
    print("-" * 30)
    
    stats = viewer.get_summary_stats()
    if stats:
        print(f"📊 Total Records: {stats['total_records']:,}")
        print(f"📅 Date Range: {stats['date_range'][0]} to {stats['date_range'][1]}")
        print(f"📈 Today's Records: {stats['today_count']:,}")
        
        print("\n📋 Records by Index:")
        for index_name, count in stats['index_counts']:
            print(f"   {index_name}: {count:,}")
    else:
        print("❌ Could not fetch summary statistics")
        return
    
    # Get latest data
    print("\n🕒 Latest Data (Last 10 records):")
    print("-" * 40)
    
    latest_df = viewer.get_latest_data(10)
    if latest_df is not None and not latest_df.empty:
        # Format the display
        display_df = latest_df.copy()
        display_df['time'] = pd.to_datetime(display_df['time']).dt.strftime('%H:%M:%S')
        display_df['strike'] = display_df['strike'].astype(int)
        
        # Round numeric columns
        numeric_cols = ['ce_ltp', 'pe_ltp', 'ce_vs_pe_oi_bar', 'pe_vs_ce_oi_bar']
        for col in numeric_cols:
            if col in display_df.columns:
                display_df[col] = display_df[col].round(2)
        
        print(display_df.to_string(index=False))
    else:
        print("❌ No data found")
    
    # Get NIFTY data
    print("\n📈 NIFTY Data (Last 10 records):")
    print("-" * 35)
    
    nifty_df = viewer.get_index_data('NIFTY', 10)
    if nifty_df is not None and not nifty_df.empty:
        display_df = nifty_df.copy()
        display_df['time'] = pd.to_datetime(display_df['time']).dt.strftime('%H:%M:%S')
        display_df['strike'] = display_df['strike'].astype(int)
        
        # Round numeric columns
        numeric_cols = ['ce_ltp', 'pe_ltp', 'ce_vs_pe_oi_bar', 'pe_vs_ce_oi_bar']
        for col in numeric_cols:
            if col in display_df.columns:
                display_df[col] = display_df[col].round(2)
        
        print(display_df.to_string(index=False))
    else:
        print("❌ No NIFTY data found")
    
    # Get BANKNIFTY data
    print("\n📈 BANKNIFTY Data (Last 10 records):")
    print("-" * 40)
    
    banknifty_df = viewer.get_index_data('BANKNIFTY', 10)
    if banknifty_df is not None and not banknifty_df.empty:
        display_df = banknifty_df.copy()
        display_df['time'] = pd.to_datetime(display_df['time']).dt.strftime('%H:%M:%S')
        display_df['strike'] = display_df['strike'].astype(int)
        
        # Round numeric columns
        numeric_cols = ['ce_ltp', 'pe_ltp', 'ce_vs_pe_oi_bar', 'pe_vs_ce_oi_bar']
        for col in numeric_cols:
            if col in display_df.columns:
                display_df[col] = display_df[col].round(2)
        
        print(display_df.to_string(index=False))
    else:
        print("❌ No BANKNIFTY data found")
    
    # Get high volume options
    print("\n🔥 High Volume Options (Volume >= 1000):")
    print("-" * 45)
    
    high_volume_df = viewer.get_high_volume_options(1000, 10)
    if high_volume_df is not None and not high_volume_df.empty:
        display_df = high_volume_df.copy()
        display_df['time'] = pd.to_datetime(display_df['time']).dt.strftime('%H:%M:%S')
        display_df['strike'] = display_df['strike'].astype(int)
        
        # Round numeric columns
        numeric_cols = ['ce_ltp', 'pe_ltp', 'total_volume']
        for col in numeric_cols:
            if col in display_df.columns:
                display_df[col] = display_df[col].round(2)
        
        print(display_df.to_string(index=False))
    else:
        print("❌ No high volume options found")

if __name__ == "__main__":
    display_data() 