#!/usr/bin/env python3
"""
MySQL Database Setup for Angel One Options Analytics Tracker
"""

import mysql.connector
from mysql.connector import Error
import os
from datetime import datetime

class MySQLSetup:
    def __init__(self, host='localhost', user='root', password='', database='options_analytics'):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        
    def create_connection(self):
        """Create MySQL connection"""
        try:
            connection = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password
            )
            return connection
        except Error as e:
            print(f"❌ Error connecting to MySQL: {e}")
            return None
    
    def create_database(self):
        """Create the database if it doesn't exist"""
        try:
            connection = self.create_connection()
            if connection is None:
                return False
            
            cursor = connection.cursor()
            
            # Create database
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.database}")
            print(f"✅ Database '{self.database}' created/verified")
            
            # Use the database
            cursor.execute(f"USE {self.database}")
            
            connection.commit()
            connection.close()
            return True
            
        except Error as e:
            print(f"❌ Error creating database: {e}")
            return False
    
    def create_tables(self):
        """Create the option_snapshots table"""
        try:
            connection = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database
            )
            
            cursor = connection.cursor()
            
            # Create option_snapshots table
            create_table_query = """
            CREATE TABLE IF NOT EXISTS option_snapshots (
                id INT AUTO_INCREMENT PRIMARY KEY,
                time DATETIME,
                index_name VARCHAR(20),
                expiry DATE,
                strike INT,
                
                ce_oi BIGINT, ce_oi_change BIGINT, ce_oi_percent_change DECIMAL(10,4),
                ce_ltp DECIMAL(10,2), ce_ltp_change DECIMAL(10,2), ce_ltp_percent_change DECIMAL(10,4),
                ce_volume BIGINT, ce_iv DECIMAL(10,4), ce_delta DECIMAL(10,4), 
                ce_theta DECIMAL(10,4), ce_vega DECIMAL(10,4), ce_gamma DECIMAL(10,4),
                ce_vs_pe_oi_bar DECIMAL(10,4),
                
                pe_oi BIGINT, pe_oi_change BIGINT, pe_oi_percent_change DECIMAL(10,4),
                pe_ltp DECIMAL(10,2), pe_ltp_change DECIMAL(10,2), pe_ltp_percent_change DECIMAL(10,4),
                pe_volume BIGINT, pe_iv DECIMAL(10,4), pe_delta DECIMAL(10,4), 
                pe_theta DECIMAL(10,4), pe_vega DECIMAL(10,4), pe_gamma DECIMAL(10,4),
                pe_vs_ce_oi_bar DECIMAL(10,4),
                
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
            
            cursor.execute(create_table_query)
            print("✅ Table 'option_snapshots' created successfully")
            
            # Create indexes for better performance
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_time ON option_snapshots(time)",
                "CREATE INDEX IF NOT EXISTS idx_index_strike ON option_snapshots(index_name, strike)",
                "CREATE INDEX IF NOT EXISTS idx_expiry ON option_snapshots(expiry)",
                "CREATE INDEX IF NOT EXISTS idx_created_at ON option_snapshots(created_at)"
            ]
            
            for index_query in indexes:
                try:
                    cursor.execute(index_query)
                except Error as e:
                    print(f"⚠️  Index creation warning: {e}")
            
            print("✅ Performance indexes created")
            
            connection.commit()
            connection.close()
            return True
            
        except Error as e:
            print(f"❌ Error creating tables: {e}")
            return False
    
    def setup_database(self):
        """Complete database setup"""
        print("🚀 Setting up MySQL Database for Options Analytics")
        print("=" * 60)
        
        # Create database
        if not self.create_database():
            return False
        
        # Create tables
        if not self.create_tables():
            return False
        
        print(f"\n✅ MySQL Database setup completed successfully!")
        print(f"📊 Database: {self.database}")
        print(f"📋 Table: option_snapshots")
        print(f"🔍 Indexes: time, index+strike, expiry, created_at")
        
        return True

def main():
    # Configuration - Update these with your MySQL credentials
    config = {
        'host': 'localhost',
        'user': 'root',  # Change to your MySQL username
        'password': 'YourNewPassword',  # Updated with user's password
        'database': 'options_analytics'
    }
    
    # You can also set these via environment variables
    config['host'] = os.getenv('MYSQL_HOST', config['host'])
    config['user'] = os.getenv('MYSQL_USER', config['user'])
    config['password'] = os.getenv('MYSQL_PASSWORD', config['password'])
    config['database'] = os.getenv('MYSQL_DATABASE', config['database'])
    
    print("🔧 MySQL Configuration:")
    print(f"   Host: {config['host']}")
    print(f"   User: {config['user']}")
    print(f"   Database: {config['database']}")
    print()
    
    # Setup database
    mysql_setup = MySQLSetup(**config)
    success = mysql_setup.setup_database()
    
    if success:
        print("\n🎉 MySQL setup completed! You can now run the tracker with MySQL.")
        print("\n📝 Next steps:")
        print("1. Update your configuration with MySQL credentials")
        print("2. Run the data migration script (if needed)")
        print("3. Start the tracker with MySQL storage")
    else:
        print("\n❌ MySQL setup failed. Please check your configuration.")

if __name__ == "__main__":
    main() 