"""
MySQL Data Verification Tool

This tool helps verify what data is actually being stored in the MySQL database.
It can fetch and display recent data, check data quality, and identify missing columns.
"""

import mysql.connector
import pandas as pd
from datetime import datetime, timedelta
import pytz

class MySQLDataVerifier:
    def __init__(self, host='localhost', user='root', password='YourNewPassword', database='options_analytics'):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.ist_tz = pytz.timezone('Asia/Kolkata')
    
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
        except Exception as e:
            print(f"❌ Database connection error: {str(e)}")
            return None
    
    def get_recent_data(self, limit=50):
        """Get recent data from MySQL"""
        try:
            connection = self.get_connection()
            if not connection:
                return None
            
            query = f"""
            SELECT * FROM option_snapshots 
            ORDER BY time DESC, id DESC 
            LIMIT {limit}
            """
            
            df = pd.read_sql(query, connection)
            connection.close()
            
            return df
            
        except Exception as e:
            print(f"❌ Error fetching recent data: {str(e)}")
            return None
    
    def get_data_by_timestamp(self, timestamp):
        """Get data for a specific timestamp"""
        try:
            connection = self.get_connection()
            if not connection:
                return None
            
            query = """
            SELECT * FROM option_snapshots 
            WHERE time = %s
            ORDER BY index_name, strike
            """
            
            df = pd.read_sql(query, connection, params=(timestamp,))
            connection.close()
            
            return df
            
        except Exception as e:
            print(f"❌ Error fetching data for timestamp {timestamp}: {str(e)}")
            return None
    
    def check_data_quality(self, df):
        """Check data quality and identify issues"""
        if df is None or df.empty:
            print("❌ No data to analyze")
            return
        
        print(f"\n📊 Data Quality Analysis for {len(df)} records:")
        print("=" * 60)
        
        # Check for zero values in important columns
        zero_columns = []
        for col in df.columns:
            if col in ['ce_oi', 'pe_oi', 'ce_volume', 'pe_volume', 'ce_iv', 'pe_iv', 'ce_delta', 'pe_delta']:
                zero_count = (df[col] == 0).sum()
                zero_percent = (zero_count / len(df)) * 100
                if zero_percent > 50:  # More than 50% zeros
                    zero_columns.append((col, zero_count, zero_percent))
        
        if zero_columns:
            print("⚠️  Columns with high percentage of zero values:")
            for col, count, percent in zero_columns:
                print(f"   {col}: {count}/{len(df)} records ({percent:.1f}%)")
        else:
            print("✅ All important columns have good data distribution")
        
        # Check for null values
        null_columns = df.columns[df.isnull().any()].tolist()
        if null_columns:
            print(f"⚠️  Columns with null values: {null_columns}")
        else:
            print("✅ No null values found")
        
        # Show data ranges
        print(f"\n📈 Data Ranges:")
        numeric_cols = df.select_dtypes(include=['number']).columns
        for col in numeric_cols[:10]:  # Show first 10 numeric columns
            if col in ['id', 'created_at', 'updated_at']:
                continue
            min_val = df[col].min()
            max_val = df[col].max()
            print(f"   {col}: {min_val} to {max_val}")
    
    def show_sample_data(self, df, n=5):
        """Show sample data"""
        if df is None or df.empty:
            print("❌ No data to display")
            return
        
        print(f"\n📋 Sample Data (showing {min(n, len(df))} records):")
        print("=" * 80)
        
        # Select important columns for display
        display_cols = ['time', 'index_name', 'strike', 'ce_oi', 'pe_oi', 'ce_volume', 'pe_volume', 
                       'ce_ltp', 'pe_ltp', 'ce_iv', 'pe_iv', 'ce_delta', 'pe_delta']
        
        available_cols = [col for col in display_cols if col in df.columns]
        sample_df = df[available_cols].head(n)
        
        print(sample_df.to_string(index=False))
    
    def get_timestamp_summary(self):
        """Get summary of available timestamps"""
        try:
            connection = self.get_connection()
            if not connection:
                return None
            
            query = """
            SELECT 
                DATE(time) as date,
                COUNT(DISTINCT time) as timestamps,
                COUNT(*) as total_records,
                MIN(time) as first_time,
                MAX(time) as last_time
            FROM option_snapshots 
            GROUP BY DATE(time)
            ORDER BY date DESC
            LIMIT 10
            """
            
            df = pd.read_sql(query, connection)
            connection.close()
            
            return df
            
        except Exception as e:
            print(f"❌ Error fetching timestamp summary: {str(e)}")
            return None

def main():
    """Main verification function"""
    print("🔍 MySQL Data Verification Tool")
    print("=" * 50)
    
    verifier = MySQLDataVerifier()
    
    # Get recent data
    print("📊 Fetching recent data...")
    recent_data = verifier.get_recent_data(limit=100)
    
    if recent_data is not None:
        print(f"✅ Found {len(recent_data)} recent records")
        
        # Show sample data
        verifier.show_sample_data(recent_data, n=10)
        
        # Check data quality
        verifier.check_data_quality(recent_data)
        
        # Show timestamp summary
        print(f"\n📅 Timestamp Summary:")
        print("=" * 50)
        summary = verifier.get_timestamp_summary()
        if summary is not None:
            print(summary.to_string(index=False))
        
        # Show latest timestamp data
        if not recent_data.empty:
            latest_time = recent_data['time'].iloc[0]
            print(f"\n🔍 Latest timestamp data ({latest_time}):")
            print("=" * 50)
            latest_data = verifier.get_data_by_timestamp(latest_time)
            if latest_data is not None:
                verifier.show_sample_data(latest_data, n=5)
    
    else:
        print("❌ Could not fetch data from MySQL")

if __name__ == "__main__":
    main() 