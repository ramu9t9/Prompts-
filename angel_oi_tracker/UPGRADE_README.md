# OI Tracking System Upgrade

## Overview

This upgrade implements an adaptive polling system that stores exactly one snapshot per official 3-minute bucket, using Angel One's `getMarketData` for OI and `getCandleData` for close prices.

## Key Features

### 🎯 Adaptive Polling
- **20-second polling intervals** for real-time OI monitoring
- **OI change detection** - only saves when OI changes
- **3-minute bucket alignment** - ensures uniform timestamps
- **In-memory comparison** - efficient change detection

### 📊 Enhanced Data Schema
- **Index candle data**: open, high, low, close, volume from `getCandleData`
- **OI change tracking**: absolute and percentage changes
- **Unique constraints**: one snapshot per 3-minute bucket per strike
- **Backward compatibility**: existing data preserved

### 🔄 Live + Backfill Logic
- **Live polling**: adaptive 20-second intervals during market hours
- **Backfill system**: historical data with same schema
- **Uniform analytics**: both live and backfill use candle close prices

## New Files

### Core System
- `option_chain_fetcher_v2.py` - Adaptive polling with OI change detection
- `store_option_data_mysql_v2.py` - New schema storage with candle data
- `main_v2.py` - 20-second polling scheduler
- `new_schema.sql` - Updated database schema

### Testing & Migration
- `test_upgraded_system.py` - 10-minute test to verify system
- `scripts/migrate_to_new_schema.py` - Database migration script

## Database Schema Changes

### New Columns Added
```sql
-- Index candle data (from getCandleData)
index_open DECIMAL(10,2),      -- Index open price
index_high DECIMAL(10,2),      -- Index high price  
index_low DECIMAL(10,2),       -- Index low price
index_close DECIMAL(10,2),     -- Index close price (candle close)
index_volume BIGINT,           -- Index volume
```

### Unique Constraint
```sql
-- Ensure one snapshot per 3-minute bucket per strike
UNIQUE KEY unique_snapshot (time, index_name, expiry, strike)
```

## Installation & Setup

### 1. Database Migration
```bash
# Run the migration script to update your database
cd scripts
python migrate_to_new_schema.py
```

### 2. Test the System
```bash
# Run a 10-minute test to verify everything works
cd angel_oi_tracker
python test_upgraded_system.py
```

### 3. Start Live Tracking
```bash
# Start the new adaptive polling system
python main_v2.py
```

## How It Works

### 1. 20-Second Polling Loop
```python
# Main polling loop runs every 20 seconds
while not stop_event.is_set():
    # Fetch OI data using getMarketData
    # Detect changes compared to previous snapshot
    # Check if 3-minute bucket has changed
    # Save snapshot if OI changed OR bucket changed
    time.sleep(20)
```

### 2. OI Change Detection
```python
# Compare current OI with in-memory previous snapshot
if current_oi != previous_oi:
    changes_detected.append({
        'strike': strike,
        'type': option_type,
        'prev_oi': prev_oi,
        'current_oi': current_oi,
        'change': current_oi - prev_oi
    })
```

### 3. 3-Minute Bucket Alignment
```python
def floor_to_3min(timestamp):
    # Convert to minutes since midnight, floor to 3-minute intervals
    minutes_since_midnight = timestamp.hour * 60 + timestamp.minute
    floored_minutes = (minutes_since_midnight // 3) * 3
    return timestamp.replace(minute=floored_minutes, second=0, microsecond=0)
```

### 4. Candle Data Integration
```python
# Fetch 3-minute candle for index close price
candle_params = {
    "exchange": "NSE",
    "symboltoken": str(token),
    "interval": "THREE_MINUTE",
    "fromdate": bucket_time.strftime('%Y-%m-%d %H:%M:%S'),
    "todate": (bucket_time + timedelta(minutes=3)).strftime('%Y-%m-%d %H:%M:%S')
}
response = smart_api.getCandleData(candle_params)
```

## Testing

### Expected Results (10-minute test)
- **Polling frequency**: ~3 polls per minute (20-second intervals)
- **Snapshots per bucket**: ≤1 per 3-minute bucket
- **Candle data**: All snapshots include index close prices
- **OI changes**: Detected and stored when they occur

### Verification Commands
```sql
-- Check snapshots per 3-minute bucket
SELECT time, COUNT(*) as snapshots 
FROM option_snapshots 
WHERE time >= '2024-01-01 09:18:00' 
GROUP BY time 
ORDER BY time;

-- Verify candle data is present
SELECT time, index_name, strike, index_close 
FROM option_snapshots 
WHERE index_close > 0 
ORDER BY time DESC 
LIMIT 10;
```

## API Compliance

### Rate Limits
- **getMarketData**: Used for OI, LTP, Volume (every 20 seconds)
- **getCandleData**: Used for index close prices (every 3 minutes)
- **optionGreek**: Used for Greeks and IV (every 3 minutes)

### Session Management
- Automatic re-authentication on session expiry
- Graceful error handling for API failures
- Retry logic for transient errors

## Migration from Old System

### Data Preservation
- Existing data is preserved during migration
- Backup table created automatically
- New columns added with default values

### Code Updates
- Update imports to use `_v2` modules
- Replace scheduler with adaptive polling
- Update analytics to use candle close prices

### Backward Compatibility
- Legacy functions maintained for gradual migration
- Old data format still supported
- Gradual transition recommended

## Troubleshooting

### Common Issues

1. **Migration fails**
   - Check MySQL permissions
   - Verify database connection
   - Ensure sufficient disk space for backup

2. **No OI changes detected**
   - Normal during low market activity
   - Check if market is open
   - Verify API credentials

3. **Multiple snapshots per bucket**
   - Check unique constraint
   - Verify timestamp flooring logic
   - Review polling frequency

### Debug Commands
```bash
# Check database schema
mysql -u root -p options_analytics -e "DESCRIBE option_snapshots;"

# Monitor live data collection
mysql -u root -p options_analytics -e "
SELECT time, index_name, COUNT(*) as snapshots 
FROM option_snapshots 
WHERE time >= NOW() - INTERVAL 1 HOUR 
GROUP BY time 
ORDER BY time DESC;"
```

## Performance Considerations

### Memory Usage
- In-memory previous snapshots: ~1MB per index
- Efficient change detection
- Minimal memory footprint

### Database Performance
- Unique constraints prevent duplicates
- Indexed columns for fast queries
- Efficient storage with proper data types

### API Usage
- Optimized polling frequency
- Respects rate limits
- Efficient data fetching

## Future Enhancements

### Planned Features
- **Real-time alerts**: OI change notifications
- **Advanced analytics**: PCR, IV skew analysis
- **Web dashboard**: Real-time data visualization
- **Multi-timeframe**: 1-minute, 5-minute buckets

### Scalability
- **Horizontal scaling**: Multiple instances
- **Load balancing**: Distributed polling
- **Data archiving**: Historical data management

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review API documentation
3. Test with the provided test script
4. Monitor system logs for errors

---

**Note**: This upgrade maintains full backward compatibility while adding powerful new features for precise OI tracking and analytics. 