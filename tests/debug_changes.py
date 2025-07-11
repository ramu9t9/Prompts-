"""
Debug Change Calculations

This tool helps debug why change columns are always zero by checking:
1. Multiple records for the same strike
2. Previous snapshot logic
3. Change calculation process
"""

import mysql.connector
import pandas as pd
from datetime import datetime, timedelta
import pytz

class ChangeDebugger:
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
    
    def check_multiple_records_per_strike(self):
        """Check if there are multiple records for the same strike"""
        try:
            connection = self.get_connection()
            if not connection:
                return None
            
            query = """
            SELECT index_name, expiry, strike, COUNT(*) as record_count
            FROM option_snapshots
            GROUP BY index_name, expiry, strike
            HAVING record_count > 1
            ORDER BY record_count DESC
            LIMIT 10
            """
            
            df = pd.read_sql(query, connection)
            connection.close()
            
            return df
            
        except Exception as e:
            print(f"❌ Error checking multiple records: {str(e)}")
            return None
    
    def get_strike_timeline(self, index_name, strike):
        """Get timeline of records for a specific strike"""
        try:
            connection = self.get_connection()
            if not connection:
                return None
            
            query = """
            SELECT time, ce_oi, ce_oi_change, ce_oi_percent_change, 
                   ce_ltp, ce_ltp_change, ce_ltp_percent_change,
                   pe_oi, pe_oi_change, pe_oi_percent_change,
                   pe_ltp, pe_ltp_change, pe_ltp_percent_change
            FROM option_snapshots
            WHERE index_name = %s AND strike = %s
            ORDER BY time ASC
            """
            
            df = pd.read_sql(query, connection, params=(index_name, int(strike)))
            connection.close()
            
            return df
            
        except Exception as e:
            print(f"❌ Error getting strike timeline: {str(e)}")
            return None
    
    def test_previous_snapshot_logic(self, index_name, strike, timestamp):
        """Test the previous snapshot logic"""
        try:
            connection = self.get_connection()
            if not connection:
                return None
            
            # Test the exact query used in get_previous_snapshot
            query = """
            SELECT ce_oi, ce_ltp, pe_oi, pe_ltp
            FROM option_snapshots
            WHERE index_name = %s AND expiry = '2025-07-31' AND strike = %s AND time < %s
            ORDER BY time DESC
            LIMIT 1
            """
            
            cursor = connection.cursor()
            cursor.execute(query, (index_name, int(strike), timestamp))
            result = cursor.fetchone()
            connection.close()
            
            if result:
                # Use tuple unpacking to avoid linter issues
                ce_oi, ce_ltp, pe_oi, pe_ltp = result
                return {
                    'ce_oi': ce_oi,
                    'ce_ltp': ce_ltp,
                    'pe_oi': pe_oi,
                    'pe_ltp': pe_ltp
                }
            return None
            
        except Exception as e:
            print(f"❌ Error testing previous snapshot: {str(e)}")
            return None
    
    def calculate_changes_manually(self, current_data, previous_data):
        """Calculate changes manually to verify logic"""
        if not previous_data:
            return {
                'ce_oi_change': 0, 'ce_oi_percent_change': 0,
                'ce_ltp_change': 0, 'ce_ltp_percent_change': 0,
                'pe_oi_change': 0, 'pe_oi_percent_change': 0,
                'pe_ltp_change': 0, 'pe_ltp_percent_change': 0
            }
        
        # Convert to float
        def safe_float(value):
            if value is None:
                return 0.0
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0.0
        
        # Current values
        ce_oi_current = safe_float(current_data.get('ce_oi', 0))
        ce_ltp_current = safe_float(current_data.get('ce_ltp', 0))
        pe_oi_current = safe_float(current_data.get('pe_oi', 0))
        pe_ltp_current = safe_float(current_data.get('pe_ltp', 0))
        
        # Previous values
        ce_oi_prev = safe_float(previous_data.get('ce_oi', 0))
        ce_ltp_prev = safe_float(previous_data.get('ce_ltp', 0))
        pe_oi_prev = safe_float(previous_data.get('pe_oi', 0))
        pe_ltp_prev = safe_float(previous_data.get('pe_ltp', 0))
        
        # Calculate changes
        ce_oi_change = ce_oi_current - ce_oi_prev
        ce_oi_percent_change = (ce_oi_change / (ce_oi_prev + 1e-5)) * 100
        
        ce_ltp_change = ce_ltp_current - ce_ltp_prev
        ce_ltp_percent_change = (ce_ltp_change / (ce_ltp_prev + 1e-5)) * 100
        
        pe_oi_change = pe_oi_current - pe_oi_prev
        pe_oi_percent_change = (pe_oi_change / (pe_oi_prev + 1e-5)) * 100
        
        pe_ltp_change = pe_ltp_current - pe_ltp_prev
        pe_ltp_percent_change = (pe_ltp_change / (pe_ltp_prev + 1e-5)) * 100
        
        return {
            'ce_oi_change': ce_oi_change,
            'ce_oi_percent_change': ce_oi_percent_change,
            'ce_ltp_change': ce_ltp_change,
            'ce_ltp_percent_change': ce_ltp_percent_change,
            'pe_oi_change': pe_oi_change,
            'pe_oi_percent_change': pe_oi_percent_change,
            'pe_ltp_change': pe_ltp_change,
            'pe_ltp_percent_change': pe_ltp_percent_change
        }

def main():
    """Main debug function"""
    print("🔍 Debug Change Calculations")
    print("=" * 50)
    
    debugger = ChangeDebugger()
    
    # 1. Check for multiple records per strike
    print("📊 Checking for multiple records per strike...")
    multiple_records = debugger.check_multiple_records_per_strike()
    
    if multiple_records is not None and not multiple_records.empty:
        print("✅ Found strikes with multiple records:")
        print(multiple_records.to_string(index=False))
        
        # 2. Get timeline for a strike with multiple records
        if len(multiple_records) > 0:
            sample_strike = multiple_records.iloc[0]
            index_name = sample_strike['index_name']
            strike = sample_strike['strike']
            
            print(f"\n📈 Timeline for {index_name} Strike {strike}:")
            print("=" * 60)
            
            timeline = debugger.get_strike_timeline(index_name, strike)
            if timeline is not None and not timeline.empty:
                print(timeline.to_string(index=False))
                
                # 3. Test previous snapshot logic for the latest record
                if len(timeline) > 1:
                    latest_record = timeline.iloc[-1]
                    latest_time = latest_record['time']
                    
                    print(f"\n🔍 Testing previous snapshot for {latest_time}:")
                    print("=" * 50)
                    
                    previous_data = debugger.test_previous_snapshot_logic(index_name, strike, latest_time)
                    if previous_data:
                        print(f"✅ Found previous data: {previous_data}")
                        
                        # 4. Calculate changes manually
                        current_data = {
                            'ce_oi': latest_record['ce_oi'],
                            'ce_ltp': latest_record['ce_ltp'],
                            'pe_oi': latest_record['pe_oi'],
                            'pe_ltp': latest_record['pe_ltp']
                        }
                        
                        calculated_changes = debugger.calculate_changes_manually(current_data, previous_data)
                        print(f"📊 Calculated changes: {calculated_changes}")
                        
                        # 5. Compare with stored changes
                        stored_changes = {
                            'ce_oi_change': latest_record['ce_oi_change'],
                            'ce_oi_percent_change': latest_record['ce_oi_percent_change'],
                            'ce_ltp_change': latest_record['ce_ltp_change'],
                            'ce_ltp_percent_change': latest_record['ce_ltp_percent_change'],
                            'pe_oi_change': latest_record['pe_oi_change'],
                            'pe_oi_percent_change': latest_record['pe_oi_percent_change'],
                            'pe_ltp_change': latest_record['pe_ltp_change'],
                            'pe_ltp_percent_change': latest_record['pe_ltp_percent_change']
                        }
                        print(f"💾 Stored changes: {stored_changes}")
                        
                        # Check if they match
                        if calculated_changes == stored_changes:
                            print("✅ Changes match!")
                        else:
                            print("❌ Changes don't match!")
                    else:
                        print("❌ No previous data found")
                else:
                    print("⚠️  Only one record found for this strike")
            else:
                print("❌ Could not get timeline")
    else:
        print("❌ No strikes with multiple records found")
        print("This explains why change columns are zero - no previous data to compare against")

if __name__ == "__main__":
    main() 