# 🚀 Angel One Options Analytics Tracker

A comprehensive Python-based options chain tracker that fetches real-time option chain data for **NIFTY** and **BANKNIFTY** from Angel One SmartAPI, calculates changes over time, and stores snapshots in SQLite for advanced analytics.

## ⚠️ IMPORTANT: Angel One API Guidelines

**Always refer to the official Angel One API documentation to respect API limits and rules:**

- **Official Documentation**: https://smartapi.angelone.in/docs
- **API Rate Limits**: https://smartapi.angelone.in/docs/rate-limits
- **SmartAPI Python SDK**: https://smartapi.angelone.in/docs/python
- **Authentication Guide**: https://smartapi.angelone.in/docs/authentication

### 🔒 API Compliance Requirements:
- **Rate Limits**: Respect the API call frequency limits
- **Session Management**: Handle session expiry and re-authentication
- **Error Handling**: Implement proper error handling for API failures
- **Data Usage**: Use data only for authorized purposes
- **Terms of Service**: Follow Angel One's terms and conditions

### 📊 Current Implementation Compliance:
- ✅ 3-minute intervals (within rate limits)
- ✅ Proper session management with TOTP
- ✅ Error handling and retry logic
- ✅ Market hours restriction (9:18 AM - 3:30 PM IST)
- ✅ Automatic re-authentication on session expiry

## 📋 Features

### ✅ Phase 1: Live Data Collection
- **Real-time Data Fetching**: Collects option chain data every 3 minutes
- **Complete Option Details**: OI, LTP, Volume, Greeks (Delta, Theta, Vega, Gamma), IV
- **Multi-Index Support**: NIFTY and BANKNIFTY
- **SQLite Storage**: Efficient local database storage

### ✅ Phase 2: ATM Detection & Filtering
- **Dynamic ATM Calculation**: Finds nearest strike based on index LTP
- **Smart Strike Filtering**: ±5 strikes around ATM
- **Index-Specific Logic**: Different strike intervals (NIFTY: 50, BANKNIFTY: 100)

### ✅ Phase 3: Advanced Analytics
- **Change Calculations**: OI/LTP changes and percentage changes
- **OI Bar Indicators**: CE vs PE OI ratios
- **Backfill Engine**: Historical data recovery
- **APScheduler Integration**: Automated real-time updates

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| **Data Source** | Angel One SmartAPI |
| **Backend** | Python + SQLite |
| **Scheduling** | APScheduler |
| **Authentication** | TOTP (pyotp) |
| **Timezone** | IST (Asia/Kolkata) |

## 📁 Project Structure

```
angel_oi_tracker/
│
├── main.py                          # Main real-time scheduler script
├── startup_backfill.py             # Backfills previous day data
├── create_db.py                    # Initializes DB schema
├── requirements.txt                # Python dependencies
│
├── utils/
│   ├── __init__.py                 # Utils package
│   ├── atm_utils.py                # ATM detection logic
│   ├── strike_range.py             # Strike filtering logic
│   └── symbols.py                  # Exchange tokens per index
│
├── angel_login.py                  # Angel API login using TOTP
├── option_chain_fetcher.py        # Data fetch logic, filtering, ATM calc
├── store_option_data.py           # Data formatting + SQLite insertion
└── option_chain.db                # SQLite database file
```

## 🚀 Quick Start

### 1. Installation

```bash
# Clone or download the project
cd angel_oi_tracker

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Create `angel_config.txt` in the project root:

```txt
API_KEY=your_angel_api_key
CLIENT_ID=your_client_id
PASSWORD=your_password
TOTP_KEY=your_totp_secret_key
```

**OR** set environment variables:

```bash
export ANGEL_API_KEY="your_api_key"
export ANGEL_CLIENT_ID="your_client_id"
export ANGEL_PASSWORD="your_password"
export ANGEL_TOTP_KEY="your_totp_secret"
```

### 3. Database Setup

```bash
python create_db.py
```

### 4. Run Backfill (Optional)

```bash
python startup_backfill.py
```

### 5. Start Real-time Tracker

```bash
python main.py
```

## 📊 Database Schema

### `option_snapshots` Table

```sql
CREATE TABLE option_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    time TEXT,                    -- Timestamp in IST
    index_name TEXT,              -- NIFTY or BANKNIFTY
    expiry TEXT,                  -- Expiry date
    strike INTEGER,               -- Strike price
    
    -- CE (Call) Data
    ce_oi REAL,                   -- Open Interest
    ce_oi_change REAL,            -- OI change from previous snapshot
    ce_oi_percent_change REAL,    -- OI % change
    ce_ltp REAL,                  -- Last Traded Price
    ce_ltp_change REAL,           -- LTP change
    ce_ltp_percent_change REAL,   -- LTP % change
    ce_volume INTEGER,            -- Volume
    ce_iv REAL,                   -- Implied Volatility
    ce_delta REAL,                -- Delta
    ce_theta REAL,                -- Theta
    ce_vega REAL,                 -- Vega
    ce_gamma REAL,                -- Gamma
    ce_vs_pe_oi_bar REAL,         -- CE vs PE OI ratio
    
    -- PE (Put) Data
    pe_oi REAL,                   -- Open Interest
    pe_oi_change REAL,            -- OI change
    pe_oi_percent_change REAL,    -- OI % change
    pe_ltp REAL,                  -- Last Traded Price
    pe_ltp_change REAL,           -- LTP change
    pe_ltp_percent_change REAL,   -- LTP % change
    pe_volume INTEGER,            -- Volume
    pe_iv REAL,                   -- Implied Volatility
    pe_delta REAL,                -- Delta
    pe_theta REAL,                -- Theta
    pe_vega REAL,                 -- Vega
    pe_gamma REAL,                -- Gamma
    pe_vs_ce_oi_bar REAL          -- PE vs CE OI ratio
);
```

## 🔧 Key Components

### 1. **ATM Detection** (`utils/atm_utils.py`)
- Calculates ATM strike based on current index LTP
- Supports different strike intervals per index
- Provides strike range filtering

### 2. **Data Fetcher** (`option_chain_fetcher.py`)
- Fetches real-time option chain data
- Implements ATM-based filtering
- Handles multiple indices simultaneously

### 3. **Data Storage** (`store_option_data.py`)
- Calculates changes from previous snapshots
- Computes OI bar indicators
- Efficient SQLite insertion

### 4. **Backfill Engine** (`startup_backfill.py`)
- Fills historical data gaps
- Prevents duplicate entries
- Handles yesterday and today's missed data

### 5. **Real-time Scheduler** (`main.py`)
- APScheduler-powered automation
- 3-minute intervals during market hours
- Automatic re-authentication

## 📈 Usage Examples

### Query Recent Data
```sql
-- Get latest NIFTY data
SELECT * FROM option_snapshots 
WHERE index_name = 'NIFTY' 
ORDER BY time DESC 
LIMIT 10;

-- Get ATM strikes only
SELECT * FROM option_snapshots 
WHERE strike = 19500  -- Example ATM strike
ORDER BY time DESC;
```

### Analyze OI Changes
```sql
-- Find high OI change strikes
SELECT strike, ce_oi_change, pe_oi_change 
FROM option_snapshots 
WHERE time = '2024-01-15 14:30:00'
ORDER BY ABS(ce_oi_change) DESC;
```

## 🔒 Security Notes

- **Never commit credentials** to version control
- Use environment variables or config files
- Keep TOTP secret secure
- Regularly rotate API keys

## 🚨 Troubleshooting

### Common Issues

1. **Login Failed**
   - Check API key and credentials
   - Verify TOTP secret is correct
   - Ensure account has API access

2. **No Data Fetched**
   - Check market hours (9:18 AM - 3:30 PM IST)
   - Verify internet connection
   - Check API rate limits

3. **Database Errors**
   - Run `python create_db.py` to recreate database
   - Check file permissions
   - Ensure SQLite is installed

## 🔮 Future Enhancements

- **Pattern Detection**: Long Buildup, Short Covering analysis
- **AI Integration**: OpenRouter-powered insights
- **Dashboard**: Web-based visualization
- **Alerts**: Price/OI change notifications
- **Multi-Expiry**: Support for weekly/monthly expiries

## 📞 Support

For issues or questions:
1. Check the troubleshooting section
2. Review Angel One API documentation
3. Verify your credentials and permissions

---

**⚠️ Disclaimer**: This tool is for educational and research purposes. Always verify data accuracy and consult financial advisors before making trading decisions. 