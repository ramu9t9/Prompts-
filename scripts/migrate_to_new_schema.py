#!/usr/bin/env python3
"""
Database Migration Script for Upgraded OI Tracking System

This script migrates the existing option_snapshots table to include
the new candle data columns (index_open, index_high, index_low, index_close, index_volume).

Run this script to upgrade your existing database to the new schema.
"""

import mysql.connector
from mysql.connector import Error
import os
from datetime import datetime

class SchemaMigrator:
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
            
            # Get table structure
            cursor.execute("DESCRIBE option_snapshots")
            columns = cursor.fetchall()
            
            connection.close()
            
            # Check if new columns already exist
            column_names = [col[0] for col in columns]
            new_columns = ['index_open', 'index_high', 'index_low', 'index_close', 'index_volume']
            
            missing_columns = [col for col in new_columns if col not in column_names]
            
            return {
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
            backup_table = f"option_snapshots_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
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
    
    def add_new_columns(self):
        """Add new candle data columns to the table"""
        try:
            connection = self.get_connection()
            if connection is None:
                return False
            
            cursor = connection.cursor()
            
            # Add new columns
            new_columns = [
                "ALTER TABLE option_snapshots ADD COLUMN index_open DECIMAL(10,2) AFTER strike",
                "ALTER TABLE option_snapshots ADD COLUMN index_high DECIMAL(10,2) AFTER index_open",
                "ALTER TABLE option_snapshots ADD COLUMN index_low DECIMAL(10,2) AFTER index_high",
                "ALTER TABLE option_snapshots ADD COLUMN index_close DECIMAL(10,2) NOT NULL DEFAULT 0 AFTER index_low",
                "ALTER TABLE option_snapshots ADD COLUMN index_volume BIGINT AFTER index_close"
            ]
            
            for query in new_columns:
                try:
                    print(f"🔧 Executing: {query}")
                    cursor.execute(query)
                    print("✅ Column added successfully")
                except Error as e:
                    if "Duplicate column name" in str(e):
                        print("⚠️  Column already exists, skipping")
                    else:
                        print(f"❌ Error adding column: {e}")
                        return False
            
            connection.commit()
            connection.close()
            
            print("✅ All new columns added successfully")
            return True
            
        except Error as e:
            print(f"❌ Error adding columns: {e}")
            return False
    
    def add_unique_constraint(self):
        """Add unique constraint to ensure one snapshot per 3-minute bucket per strike"""
        try:
            connection = self.get_connection()
            if connection is None:
                return False
            
            cursor = connection.cursor()
            
            # Check if unique constraint already exists
            cursor.execute("""
                SELECT CONSTRAINT_NAME 
                FROM information_schema.TABLE_CONSTRAINTS 
                WHERE TABLE_SCHEMA = %s 
                AND TABLE_NAME = 'option_snapshots' 
                AND CONSTRAINT_TYPE = 'UNIQUE'
            """, (self.database,))
            
            existing_constraints = cursor.fetchall()
            
            if not existing_constraints:
                print("🔧 Adding unique constraint...")
                cursor.execute("""
                    ALTER TABLE option_snapshots 
                    ADD CONSTRAINT unique_snapshot 
                    UNIQUE (time, index_name, expiry, strike)
                """)
                print("✅ Unique constraint added")
            else:
                print("⚠️  Unique constraint already exists")
            
            connection.commit()
            connection.close()
            return True
            
        except Error as e:
            print(f"❌ Error adding unique constraint: {e}")
            return False
    
    def verify_migration(self):
        """Verify that the migration was successful"""
        try:
            connection = self.get_connection()
            if connection is None:
                return False
            
            cursor = connection.cursor()
            
            # Check if all new columns exist
            cursor.execute("DESCRIBE option_snapshots")
            columns = cursor.fetchall()
            column_names = [col[0] for col in columns]
            
            new_columns = ['index_open', 'index_high', 'index_low', 'index_close', 'index_volume']
            missing_columns = [col for col in new_columns if col not in column_names]
            
            if missing_columns:
                print(f"❌ Migration incomplete. Missing columns: {missing_columns}")
                return False
            
            # Check unique constraint
            cursor.execute("""
                SELECT CONSTRAINT_NAME 
                FROM information_schema.TABLE_CONSTRAINTS 
                WHERE TABLE_SCHEMA = %s 
                AND TABLE_NAME = 'option_snapshots' 
                AND CONSTRAINT_TYPE = 'UNIQUE'
            """, (self.database,))
            
            constraints = cursor.fetchall()
            
            connection.close()
            
            if constraints:
                print("✅ Migration verification successful")
                print(f"   New columns: {new_columns}")
                print(f"   Unique constraints: {len(constraints)}")
                return True
            else:
                print("❌ Unique constraint not found")
                return False
            
        except Error as e:
            print(f"❌ Error verifying migration: {e}")
            return False
    
    def run_migration(self):
        """Run the complete migration process"""
        print("🚀 Starting Database Schema Migration")
        print("=" * 60)
        
        # Check current schema
        print("🔍 Checking current schema...")
        schema_info = self.check_current_schema()
        
        if schema_info is None:
            print("❌ Cannot check schema. Exiting.")
            return False
        
        if not schema_info['needs_migration']:
            print("✅ Schema is already up to date. No migration needed.")
            return True
        
        print(f"📋 Current columns: {len(schema_info['column_names'])}")
        print(f"📋 Missing columns: {schema_info['missing_columns']}")
        
        # Confirm migration
        print("\n⚠️  This will modify your existing option_snapshots table.")
        print("   A backup will be created automatically.")
        response = input("   Continue with migration? (y/N): ")
        
        if response.lower() != 'y':
            print("❌ Migration cancelled.")
            return False
        
        # Create backup
        print("\n📦 Creating backup...")
        if not self.backup_existing_data():
            print("❌ Backup failed. Migration cancelled.")
            return False
        
        # Add new columns
        print("\n🔧 Adding new columns...")
        if not self.add_new_columns():
            print("❌ Failed to add columns. Migration failed.")
            return False
        
        # Add unique constraint
        print("\n🔧 Adding unique constraint...")
        if not self.add_unique_constraint():
            print("❌ Failed to add unique constraint. Migration failed.")
            return False
        
        # Verify migration
        print("\n🔍 Verifying migration...")
        if not self.verify_migration():
            print("❌ Migration verification failed.")
            return False
        
        print("\n" + "=" * 60)
        print("🎉 MIGRATION COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print("✅ New schema features:")
        print("   - Index candle data (open, high, low, close, volume)")
        print("   - Unique constraint for 3-minute buckets")
        print("   - Ready for adaptive polling system")
        print("\n📋 Next steps:")
        print("   1. Update your code to use the new schema")
        print("   2. Test the upgraded system")
        print("   3. Monitor data collection")
        
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
    migrator = SchemaMigrator(**config)
    success = migrator.run_migration()
    
    if not success:
        print("\n❌ Migration failed. Please check the errors above.")
        sys.exit(1)
    else:
        print("\n🎉 Migration completed successfully!")

if __name__ == "__main__":
    main() 