#!/usr/bin/env python3
"""
Database Migration Script for OI Tracking v3

This script migrates the existing option_snapshots table to the new v3 schema
with simplified structure focusing on essential data with candle close prices.

New Schema:
- bucket_ts TIMESTAMP (3-minute bucket timestamp)
- trading_symbol VARCHAR(25) (e.g., NIFTY19500)
- option_type CHAR(2) (CE/PE)
- strike INT
- ce_oi BIGINT, ce_price_close DECIMAL(10,2)
- pe_oi BIGINT, pe_price_close DECIMAL(10,2)
"""

import mysql.connector
from mysql.connector import Error
import os
from datetime import datetime

class V3SchemaMigrator:
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
    
    def check_current_schema(self):
        """Check the current table schema"""
        try:
            connection = self.get_connection()
            if connection is None:
                return None
            
            cursor = connection.cursor()
            
            # Check if table exists
            cursor.execute("SHOW TABLES LIKE 'option_snapshots'")
            table_exists = cursor.fetchone()
            
            if not table_exists:
                print("📋 Table 'option_snapshots' does not exist. Will create new v3 schema.")
                connection.close()
                return {'table_exists': False, 'needs_migration': True}
            
            # Get table structure
            cursor.execute("DESCRIBE option_snapshots")
            columns = cursor.fetchall()
            
            connection.close()
            
            # Check if new schema columns exist
            column_names = [col[0] for col in columns]
            new_columns = ['bucket_ts', 'trading_symbol', 'option_type', 'ce_price_close', 'pe_price_close']
            
            missing_columns = [col for col in new_columns if col not in column_names]
            
            return {
                'table_exists': True,
                'columns': columns,
                'column_names': column_names,
                'missing_columns': missing_columns,
                'needs_migration': len(missing_columns) > 0
            }
            
        except Error as e:
            print(f"❌ Error checking schema: {e}")
            return None
    
    def backup_existing_data(self):
        """Create a backup of existing data"""
        try:
            connection = self.get_connection()
            if connection is None:
                return False
            
            cursor = connection.cursor()
            
            # Create backup table
            backup_table = f"option_snapshots_backup_v3_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            print(f"📦 Creating backup table: {backup_table}")
            
            # Copy table structure and data
            cursor.execute(f"CREATE TABLE {backup_table} LIKE option_snapshots")
            cursor.execute(f"INSERT INTO {backup_table} SELECT * FROM option_snapshots")
            
            connection.commit()
            connection.close()
            
            print(f"✅ Backup created: {backup_table}")
            return True
            
        except Error as e:
            print(f"❌ Error creating backup: {e}")
            return False
    
    def drop_old_table(self):
        """Drop the old table to create new schema"""
        try:
            connection = self.get_connection()
            if connection is None:
                return False
            
            cursor = connection.cursor()
            
            print("🗑️  Dropping old table...")
            cursor.execute("DROP TABLE IF EXISTS option_snapshots")
            
            connection.commit()
            connection.close()
            
            print("✅ Old table dropped")
            return True
            
        except Error as e:
            print(f"❌ Error dropping old table: {e}")
            return False
    
    def create_new_schema(self):
        """Create the new v3 schema"""
        try:
            connection = self.get_connection()
            if connection is None:
                return False
            
            cursor = connection.cursor()
            
            # Create new v3 schema
            create_table_query = """
            CREATE TABLE option_snapshots (
                bucket_ts TIMESTAMP NOT NULL,
                trading_symbol VARCHAR(25) NOT NULL,
                option_type CHAR(2) NOT NULL,
                strike INT NOT NULL,
                ce_oi BIGINT DEFAULT 0,
                ce_price_close DECIMAL(10,2) DEFAULT 0,
                pe_oi BIGINT DEFAULT 0,
                pe_price_close DECIMAL(10,2) DEFAULT 0,
                PRIMARY KEY(bucket_ts, trading_symbol)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
            
            print("🔧 Creating new v3 schema...")
            cursor.execute(create_table_query)
            
            # Create indexes
            indexes = [
                "CREATE INDEX idx_bucket_ts ON option_snapshots(bucket_ts)",
                "CREATE INDEX idx_trading_symbol ON option_snapshots(trading_symbol)",
                "CREATE INDEX idx_strike ON option_snapshots(strike)",
                "CREATE INDEX idx_bucket_symbol ON option_snapshots(bucket_ts, trading_symbol)"
            ]
            
            for index_query in indexes:
                try:
                    cursor.execute(index_query)
                    print(f"✅ Created index: {index_query.split()[-1]}")
                except Error as e:
                    print(f"⚠️  Index creation warning: {e}")
            
            connection.commit()
            connection.close()
            
            print("✅ New v3 schema created successfully")
            return True
            
        except Error as e:
            print(f"❌ Error creating new schema: {e}")
            return False
    
    def verify_migration(self):
        """Verify that the migration was successful"""
        try:
            connection = self.get_connection()
            if connection is None:
                return False
            
            cursor = connection.cursor()
            
            # Check if table exists
            cursor.execute("SHOW TABLES LIKE 'option_snapshots'")
            table_exists = cursor.fetchone()
            
            if not table_exists:
                print("❌ Table 'option_snapshots' not found after migration")
                return False
            
            # Check if all new columns exist
            cursor.execute("DESCRIBE option_snapshots")
            columns = cursor.fetchall()
            column_names = [col[0] for col in columns]
            
            new_columns = ['bucket_ts', 'trading_symbol', 'option_type', 'strike', 'ce_oi', 'ce_price_close', 'pe_oi', 'pe_price_close']
            missing_columns = [col for col in new_columns if col not in column_names]
            
            if missing_columns:
                print(f"❌ Migration incomplete. Missing columns: {missing_columns}")
                return False
            
            # Check primary key
            cursor.execute("""
                SELECT CONSTRAINT_NAME 
                FROM information_schema.TABLE_CONSTRAINTS 
                WHERE TABLE_SCHEMA = %s 
                AND TABLE_NAME = 'option_snapshots' 
                AND CONSTRAINT_TYPE = 'PRIMARY KEY'
            """, (self.database,))
            
            primary_keys = cursor.fetchall()
            
            connection.close()
            
            if primary_keys:
                print("✅ Migration verification successful")
                print(f"   New columns: {new_columns}")
                print(f"   Primary key: {primary_keys[0][0]}")
                return True
            else:
                print("❌ Primary key not found")
                return False
            
        except Error as e:
            print(f"❌ Error verifying migration: {e}")
            return False
    
    def run_migration(self):
        """Run the complete migration process"""
        print("🚀 Starting Database Migration to v3 Schema")
        print("=" * 60)
        
        # Check current schema
        print("🔍 Checking current schema...")
        schema_info = self.check_current_schema()
        
        if schema_info is None:
            print("❌ Cannot check schema. Exiting.")
            return False
        
        if not schema_info['needs_migration']:
            print("✅ Schema is already v3. No migration needed.")
            return True
        
        if schema_info['table_exists']:
            print(f"📋 Current columns: {len(schema_info['column_names'])}")
            print(f"📋 Missing columns: {schema_info['missing_columns']}")
        else:
            print("📋 No existing table found. Will create new v3 schema.")
        
        # Confirm migration
        print("\n⚠️  This will replace your existing option_snapshots table.")
        print("   A backup will be created automatically.")
        response = input("   Continue with migration? (y/N): ")
        
        if response.lower() != 'y':
            print("❌ Migration cancelled.")
            return False
        
        # Create backup
        if schema_info['table_exists']:
            print("\n📦 Creating backup...")
            if not self.backup_existing_data():
                print("❌ Backup failed. Migration cancelled.")
                return False
        
        # Drop old table
        if schema_info['table_exists']:
            print("\n🗑️  Dropping old table...")
            if not self.drop_old_table():
                print("❌ Failed to drop old table. Migration failed.")
                return False
        
        # Create new schema
        print("\n🔧 Creating new v3 schema...")
        if not self.create_new_schema():
            print("❌ Failed to create new schema. Migration failed.")
            return False
        
        # Verify migration
        print("\n🔍 Verifying migration...")
        if not self.verify_migration():
            print("❌ Migration verification failed.")
            return False
        
        print("\n" + "=" * 60)
        print("🎉 MIGRATION TO v3 COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print("✅ New schema features:")
        print("   - Simplified structure with essential data")
        print("   - bucket_ts for 3-minute bucket timestamps")
        print("   - trading_symbol for easy identification")
        print("   - ce_price_close and pe_price_close from getCandleData")
        print("   - Primary key on (bucket_ts, trading_symbol)")
        print("\n📋 Next steps:")
        print("   1. Test the new adaptive polling system")
        print("   2. Run the test script: python test_adaptive_system.py")
        print("   3. Start live tracking with the new system")
        
        return True

def main():
    """Main migration function"""
    # Configuration
    config = {
        'host': 'localhost',
        'user': 'root',
        'password': 'YourNewPassword',
        'database': 'options_analytics'
    }
    
    # You can also set these via environment variables
    config['host'] = os.getenv('MYSQL_HOST', config['host'])
    config['user'] = os.getenv('MYSQL_USER', config['user'])
    config['password'] = os.getenv('MYSQL_PASSWORD', config['password'])
    config['database'] = os.getenv('MYSQL_DATABASE', config['database'])
    
    print("🔧 Migration Configuration:")
    print(f"   Host: {config['host']}")
    print(f"   User: {config['user']}")
    print(f"   Database: {config['database']}")
    print()
    
    # Run migration
    migrator = V3SchemaMigrator(**config)
    success = migrator.run_migration()
    
    if not success:
        print("\n❌ Migration failed. Please check the errors above.")
        sys.exit(1)
    else:
        print("\n🎉 Migration completed successfully!")

if __name__ == "__main__":
    main() 