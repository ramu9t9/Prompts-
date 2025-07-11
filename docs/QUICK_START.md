# 🚀 Quick Start Guide - Angel One Options Analytics Tracker

## ⚠️ IMPORTANT: API Compliance

**Before using this system, ensure you comply with Angel One API guidelines:**

- **Official Documentation**: https://smartapi.angelone.in/docs
- **Rate Limits**: https://smartapi.angelone.in/docs/rate-limits
- **Terms of Service**: https://smartapi.angelone.in/terms

**Current implementation respects:**
- ✅ 3-minute intervals (within rate limits)
- ✅ Market hours only (9:18 AM - 3:30 PM IST)
- ✅ Proper session management
- ✅ Error handling and retry logic

## ✅ Your Credentials Are Configured!

Your Angel One credentials have been automatically configured:
- **Client ID**: R117172
- **API Key**: P9ErUZG0
- **Password**: 9029
- **TOTP Secret**: Y4GDOA6SL5VOCKQPFLR5EM3HOY
- **Session Secret**: 7fcb7f2a-fd0a-4d12-a010-16d37fbdbd6e

## 🚀 Ready to Use!

### Step 1: Install Dependencies
```bash
cd angel_oi_tracker
pip install -r requirements.txt
```

### Step 2: Test the System
```bash
# Test basic functionality
python test_system.py

# Test with your actual credentials (when market is open)
python test_with_credentials.py
```

### Step 3: Start Data Collection

#### Option A: Real-time Tracking (Recommended)
```bash
python main.py
```
This will:
- Login to Angel One automatically
- Fetch option chain data every 3 minutes
- Store data in SQLite database
- Calculate changes and analytics

#### Option B: Historical Data Backfill
```bash
python startup_backfill.py
```
This will:
- Fill missing data from yesterday
- Fill today's missed data
- Ensure no duplicates

## 📊 What Data You'll Get

### Real-time Data (Every 3 Minutes)
- **NIFTY & BANKNIFTY** option chains
- **ATM ±5 strikes** automatically calculated
- **Complete Greeks**: Delta, Theta, Vega, Gamma
- **OI & LTP** with change calculations
- **Volume & IV** data

### Database Storage
- **SQLite database**: `option_chain.db`
- **Table**: `option_snapshots`
- **Indexes**: Optimized for fast queries

## 🔍 Sample Queries

### Get Latest Data
```sql
SELECT * FROM option_snapshots 
WHERE index_name = 'NIFTY' 
ORDER BY time DESC 
LIMIT 10;
```

### Find High OI Change Strikes
```sql
SELECT strike, ce_oi_change, pe_oi_change 
FROM option_snapshots 
WHERE time = '2024-01-15 14:30:00'
ORDER BY ABS(ce_oi_change) DESC;
```

### ATM Strike Analysis
```sql
SELECT * FROM option_snapshots 
WHERE strike = 19500  -- Example ATM strike
ORDER BY time DESC;
```

## ⏰ Market Hours
- **Trading Days**: Monday to Friday
- **Market Hours**: 9:18 AM to 3:30 PM IST
- **Data Collection**: Every 3 minutes during market hours

## 🛠️ System Components

### Core Files
- `main.py` - Real-time scheduler
- `startup_backfill.py` - Historical data engine
- `option_chain_fetcher.py` - Data fetching
- `store_option_data.py` - Data storage & analytics

### Utilities
- `utils/atm_utils.py` - ATM calculation
- `utils/strike_range.py` - Strike filtering
- `utils/symbols.py` - Index tokens

## 🔧 Troubleshooting

### Common Issues

1. **"Login Failed"**
   - Check if market is open (9:18 AM - 3:30 PM IST)
   - Verify your TOTP app is working
   - Ensure API access is enabled

2. **"No Data Fetched"**
   - Market might be closed
   - Check internet connection
   - Verify API rate limits

3. **"Database Error"**
   - Run: `python create_db.py`
   - Check file permissions

### Testing Commands
```bash
# Test system components
python test_system.py

# Test with real API (market hours only)
python test_with_credentials.py

# Check database
sqlite3 option_chain.db ".tables"
```

## 📈 Next Steps

1. **Start Real-time Tracking**: `python main.py`
2. **Monitor Data**: Check `option_chain.db`
3. **Analyze Patterns**: Use SQL queries
4. **Future Enhancements**: AI integration, dashboard

## 🔒 Security Notes
- ✅ Credentials are stored locally
- ✅ `.gitignore` prevents accidental commits
- ✅ Session management included
- ⚠️ Keep `angel_config.txt` secure

---

**🎉 You're all set! The system is ready to collect real-time options data for your analysis.** 