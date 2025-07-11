# MySQL Migration Guide for Angel One Options Analytics Tracker

This guide explains how to migrate from SQLite to MySQL for better performance, concurrent access, and scalability.

## 🚀 Quick Start

### 1. Prerequisites
- MySQL Server installed and running
- Python 3.7+ with pip
- Existing SQLite database with data (optional)

### 2. Setup MySQL Database
```bash
# Run the MySQL setup script
python angel_oi_tracker/mysql_setup.py
```

Or use the batch file:
```bash
setup_mysql.bat
```

### 3. Migrate Existing Data (Optional)
If you have existing SQLite data:
```bash
# Run the migration script
python angel_oi_tracker/migrate_to_mysql.py
```

Or use the batch file:
```bash
migrate_to_mysql.bat
```

### 4. Start Tracker with MySQL
```bash
# Start the tracker (now uses MySQL)
python angel_oi_tracker/main.py
```

## 📋 Configuration

### Environment Variables
Set these environment variables for MySQL connection:

```bash
# Windows
set MYSQL_HOST=localhost
set MYSQL_USER=root
set MYSQL_PASSWORD=your_password
set MYSQL_DATABASE=options_analytics

# Linux/Mac
export MYSQL_HOST=localhost
export MYSQL_USER=root
export MYSQL_PASSWORD=your_password
export MYSQL_DATABASE=options_analytics
```

### Default Configuration
If environment variables are not set, the system uses:
- Host: `localhost`
- User: `root`
- Password: `` (empty)
- Database: `options_analytics`

## 🗄️ Database Schema

### Table: `option_snapshots`
```sql
CREATE TABLE option_snapshots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    time DATETIME,
    index_name VARCHAR(20),
    expiry DATE,
    strike INT,
    
    -- CE (Call) Data
    ce_oi BIGINT, ce_oi_change BIGINT, ce_oi_percent_change DECIMAL(10,4),
    ce_ltp DECIMAL(10,2), ce_ltp_change DECIMAL(10,2), ce_ltp_percent_change DECIMAL(10,4),
    ce_volume BIGINT, ce_iv DECIMAL(10,4), ce_delta DECIMAL(10,4), 
    ce_theta DECIMAL(10,4), ce_vega DECIMAL(10,4), ce_gamma DECIMAL(10,4),
    ce_vs_pe_oi_bar DECIMAL(10,4),
    
    -- PE (Put) Data
    pe_oi BIGINT, pe_oi_change BIGINT, pe_oi_percent_change DECIMAL(10,4),
    pe_ltp DECIMAL(10,2), pe_ltp_change DECIMAL(10,2), pe_ltp_percent_change DECIMAL(10,4),
    pe_volume BIGINT, pe_iv DECIMAL(10,4), pe_delta DECIMAL(10,4), 
    pe_theta DECIMAL(10,4), pe_vega DECIMAL(10,4), pe_gamma DECIMAL(10,4),
    pe_vs_ce_oi_bar DECIMAL(10,4),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### Indexes
- `idx_time` - For time-based queries
- `idx_index_strike` - For index and strike combinations
- `idx_expiry` - For expiry date queries
- `idx_created_at` - For creation time queries

## 📊 Data Viewing

### View MySQL Data
```bash
# View data from MySQL database
python angel_oi_tracker/view_data_mysql.py
```

Or use the batch file:
```bash
view_mysql_data.bat
```

### Available Queries
- Latest data (last 20 records)
- Summary statistics
- Index-specific data (NIFTY, BANKNIFTY)
- High volume options
- Strike analysis

## 🔧 Troubleshooting

### Common Issues

#### 1. Connection Error
```
Error connecting to MySQL: 2003 (HY000): Can't connect to MySQL server
```
**Solution**: Ensure MySQL server is running and accessible.

#### 2. Authentication Error
```
Error connecting to MySQL: 1045 (28000): Access denied
```
**Solution**: Check username and password in environment variables.

#### 3. Database Not Found
```
Error connecting to MySQL: 1049 (42000): Unknown database
```
**Solution**: Run the MySQL setup script to create the database.

#### 4. Table Not Found
```
Error: Table 'option_snapshots' doesn't exist
```
**Solution**: Run the MySQL setup script to create tables.

### Performance Optimization

#### 1. Connection Pooling
For high-frequency data collection, consider implementing connection pooling:

```python
import mysql.connector.pooling

config = {
    'pool_name': 'mypool',
    'pool_size': 5,
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'options_analytics'
}

connection_pool = mysql.connector.pooling.MySQLConnectionPool(**config)
```

#### 2. Batch Inserts
For better performance during backfill, use batch inserts:

```python
# Insert multiple records at once
cursor.executemany(insert_query, records_list)
```

#### 3. Index Optimization
Monitor query performance and add indexes as needed:

```sql
-- Example: Add index for specific queries
CREATE INDEX idx_time_index ON option_snapshots(time, index_name);
```

## 📈 Benefits of MySQL Migration

### 1. Performance
- Better query performance for large datasets
- Optimized indexes for complex queries
- Efficient storage and retrieval

### 2. Scalability
- Handle concurrent connections
- Support for larger datasets
- Better memory management

### 3. Features
- ACID compliance
- Transaction support
- Advanced querying capabilities
- Backup and recovery tools

### 4. Integration
- Easy integration with other tools
- Support for multiple applications
- Standard SQL interface

## 🔄 Migration Process

### Step 1: Backup SQLite Data
```bash
# Create backup of SQLite database
cp options_analytics.db options_analytics_backup.db
```

### Step 2: Setup MySQL
```bash
python angel_oi_tracker/mysql_setup.py
```

### Step 3: Migrate Data
```bash
python angel_oi_tracker/migrate_to_mysql.py
```

### Step 4: Verify Migration
```bash
python angel_oi_tracker/view_data_mysql.py
```

### Step 5: Test Tracker
```bash
python angel_oi_tracker/main.py
```

## 📝 API Compliance

This migration maintains full compliance with Angel One API:
- **Documentation**: https://smartapi.angelone.in/docs
- **Rate Limits**: https://smartapi.angelone.in/docs/rate-limits
- **Terms of Service**: https://smartapi.angelone.in/terms

The MySQL storage layer respects all API limits and usage guidelines.

## 🛠️ Maintenance

### Regular Tasks
1. **Monitor Database Size**: Check table growth
2. **Optimize Queries**: Review slow queries
3. **Backup Data**: Regular MySQL backups
4. **Update Indexes**: Add indexes for new query patterns

### Backup Commands
```bash
# MySQL backup
mysqldump -u root -p options_analytics > backup_$(date +%Y%m%d).sql

# Restore backup
mysql -u root -p options_analytics < backup_20231201.sql
```

## 📞 Support

For issues related to:
- **MySQL Setup**: Check MySQL server logs
- **Migration**: Review migration script output
- **Performance**: Monitor query execution times
- **API Issues**: Refer to Angel One documentation

---

**Note**: Always backup your data before migration and test thoroughly in a development environment first. 