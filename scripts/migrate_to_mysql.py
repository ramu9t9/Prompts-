#!/usr/bin/env python3
"""
Data Migration Script: SQLite to MySQL

This script migrates existing option data from SQLite to MySQL database.
"""

import sqlite3
import mysql.connector
from mysql.connector import Error
import os
from datetime import datetime
import pytz
import time

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

class DataMigrator:
    def __init__(self, sqlite_db_path='angel_oi_tracker/option_chain.db', 
                 mysql_host='localhost', mysql_user='root', mysql_password='YourNewPassword', 
                 mysql_database='options_analytics'):
        self.sqlite_db_path = sqlite_db_path
        self.mysql_host = mysql_host
        self.mysql_user = mysql_user
        self.mysql_password = mysql_password
        self.mysql_database = mysql_database
        
        # Load from environment variables if available
        self.mysql_host = os.getenv('MYSQL_HOST', self.mysql_host)
        self.mysql_user = os.getenv('MYSQL_USER', self.mysql_user)
        self.mysql_password = os.getenv('MYSQL_PASSWORD', self.mysql_password)
        self.mysql_database = os.getenv('MYSQL_DATABASE', self.mysql_database)
    
    def check_sqlite_data(self):
        """Check if SQLite database exists and has data"""
        try:
            if not os.path.exists(self.sqlite_db_path):
                print(f"❌ SQLite database not found: {self.sqlite_db_path}")
                return False
            
            conn = sqlite3.connect(self.sqlite_db_path)
            cursor = conn.cursor()
            
            # Check if table exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='option_snapshots'
            """)
            
            if not cursor.fetchone():
                print("❌ Table 'option_snapshots' not found in SQLite database")
                conn.close()
                return False
            
            # Count records
            cursor.execute("SELECT COUNT(*) FROM option_snapshots")
            result = cursor.fetchone()
            count = result[0] if result is not None else 0
            
            print(f"📊 Found {count} records in SQLite database")
            conn.close()
            return count > 0
            
        except Exception as e:
            print(f"❌ Error checking SQLite data: {e}")
            return False
    
    def get_mysql_connection(self):
        """Get MySQL connection"""
        try:
            connection = mysql.connector.connect(
                host=self.mysql_host,
                user=self.mysql_user,
                password=self.mysql_password,
                database=self.mysql_database
            )
            return connection
        except Error as e:
            print(f"❌ Error connecting to MySQL: {e}")
            return None
    
    def migrate_data(self):
        """Migrate data from SQLite to MySQL"""
        try:
            print("🚀 Starting data migration from SQLite to MySQL")
            print("=" * 60)
            
            # Check SQLite data
            if not self.check_sqlite_data():
                return False
            
            # Connect to SQLite
            sqlite_conn = sqlite3.connect(self.sqlite_db_path)
            sqlite_cursor = sqlite_conn.cursor()
            
            # Connect to MySQL
            mysql_conn = self.get_mysql_connection()
            if mysql_conn is None:
                sqlite_conn.close()
                return False
            
            mysql_cursor = mysql_conn.cursor()
            
            # Check if created_at and updated_at columns exist in SQLite
            sqlite_cursor.execute("PRAGMA table_info(option_snapshots)")
            columns = [row[1] for row in sqlite_cursor.fetchall()]
            has_created = 'created_at' in columns
            has_updated = 'updated_at' in columns
            
            # Build select query based on available columns
            select_cols = [
                'time', 'index_name', 'expiry', 'strike',
                'ce_oi', 'ce_oi_change', 'ce_oi_percent_change',
                'ce_ltp', 'ce_ltp_change', 'ce_ltp_percent_change',
                'ce_volume', 'ce_iv', 'ce_delta', 'ce_theta', 'ce_vega', 'ce_gamma',
                'ce_vs_pe_oi_bar',
                'pe_oi', 'pe_oi_change', 'pe_oi_percent_change',
                'pe_ltp', 'pe_ltp_change', 'pe_ltp_percent_change',
                'pe_volume', 'pe_iv', 'pe_delta', 'pe_theta', 'pe_vega', 'pe_gamma',
                'pe_vs_ce_oi_bar'
            ]
            if has_created:
                select_cols.append('created_at')
            if has_updated:
                select_cols.append('updated_at')
            
            select_query = f"SELECT {', '.join(select_cols)} FROM option_snapshots ORDER BY time"
            sqlite_cursor.execute(select_query)
            records = sqlite_cursor.fetchall()
            total_records = len(records)
            
            if total_records == 0:
                print("⚠️  No records to migrate")
                sqlite_conn.close()
                mysql_conn.close()
                return True
            
            print(f"📦 Migrating {total_records} records...")
            
            # Insert into MySQL
            insert_cols = [
                'time', 'index_name', 'expiry', 'strike',
                'ce_oi', 'ce_oi_change', 'ce_oi_percent_change',
                'ce_ltp', 'ce_ltp_change', 'ce_ltp_percent_change',
                'ce_volume', 'ce_iv', 'ce_delta', 'ce_theta', 'ce_vega', 'ce_gamma',
                'ce_vs_pe_oi_bar',
                'pe_oi', 'pe_oi_change', 'pe_oi_percent_change',
                'pe_ltp', 'pe_ltp_change', 'pe_ltp_percent_change',
                'pe_volume', 'pe_iv', 'pe_delta', 'pe_theta', 'pe_vega', 'pe_gamma',
                'pe_vs_ce_oi_bar',
                'created_at', 'updated_at'
            ]
            insert_query = f"""
                INSERT INTO option_snapshots (
                    {', '.join(insert_cols)}
                ) VALUES ({', '.join(['%s'] * len(insert_cols))})
            """
            
            migrated_count = 0
            for i, record in enumerate(records):
                # If created_at/updated_at missing, use current timestamp
                record = list(record)
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                if not has_created:
                    record.append(now)
                if not has_updated:
                    record.append(now)
                try:
                    mysql_cursor.execute(insert_query, tuple(record))
                    migrated_count += 1
                    if (i + 1) % 100 == 0:
                        print(f"   Progress: {i + 1}/{total_records} records migrated")
                except Error as e:
                    print(f"⚠️  Error migrating record {i + 1}: {e}")
                    continue
            mysql_conn.commit()
            print(f"\n✅ Migration completed!")
            print(f"📊 Total records: {total_records}")
            print(f"✅ Successfully migrated: {migrated_count}")
            print(f"❌ Failed: {total_records - migrated_count}")
            sqlite_conn.close()
            mysql_conn.close()
            return migrated_count > 0
        except Exception as e:
            print(f"❌ Error during migration: {e}")
            return False
    
    def verify_migration(self):
        """Verify that data was migrated correctly"""
        try:
            print("\n🔍 Verifying migration...")
            
            # Count SQLite records
            sqlite_conn = sqlite3.connect(self.sqlite_db_path)
            sqlite_cursor = sqlite_conn.cursor()
            sqlite_cursor.execute("SELECT COUNT(*) FROM option_snapshots")
            result = sqlite_cursor.fetchone()
            sqlite_count = result[0] if result is not None else 0
            sqlite_conn.close()
            
            # Count MySQL records
            mysql_conn = self.get_mysql_connection()
            if mysql_conn is None:
                return False
            
            mysql_cursor = mysql_conn.cursor()
            mysql_cursor.execute("SELECT COUNT(*) FROM option_snapshots")
            result = mysql_cursor.fetchone()
            mysql_count = result[0] if result is not None else 0
            mysql_conn.close()
            
            print(f"📊 SQLite records: {sqlite_count}")
            print(f"📊 MySQL records: {mysql_count}")
            
            if sqlite_count == mysql_count:
                print("✅ Migration verification successful!")
                return True
            else:
                print("❌ Migration verification failed - record counts don't match")
                return False
                
        except Exception as e:
            print(f"❌ Error during verification: {e}")
            return False

def main():
    print("🔄 SQLite to MySQL Data Migration Tool")
    print("=" * 50)
    
    # Configuration
    config = {
        'sqlite_db_path': 'angel_oi_tracker/option_chain.db',
        'mysql_host': 'localhost',
        'mysql_user': 'root',
        'mysql_password': 'YourNewPassword',
        'mysql_database': 'options_analytics'
    }
    
    # Load from environment variables
    config['mysql_host'] = os.getenv('MYSQL_HOST', config['mysql_host'])
    config['mysql_user'] = os.getenv('MYSQL_USER', config['mysql_user'])
    config['mysql_password'] = os.getenv('MYSQL_PASSWORD', config['mysql_password'])
    config['mysql_database'] = os.getenv('MYSQL_DATABASE', config['mysql_database'])
    
    print("🔧 Configuration:")
    print(f"   SQLite DB: {config['sqlite_db_path']}")
    print(f"   MySQL Host: {config['mysql_host']}")
    print(f"   MySQL User: {config['mysql_user']}")
    print(f"   MySQL Database: {config['mysql_database']}")
    print()
    
    # Create migrator and run migration
    migrator = DataMigrator(**config)
    
    # Run migration
    success = migrator.migrate_data()
    
    if success:
        # Verify migration
        migrator.verify_migration()
        
        print("\n🎉 Migration completed successfully!")
        print("\n📝 Next steps:")
        print("1. Update your configuration to use MySQL")
        print("2. Test the tracker with MySQL storage")
        print("3. Backup your SQLite database before removing it")
    else:
        print("\n❌ Migration failed. Please check your configuration and try again.")

if __name__ == "__main__":
    main() 