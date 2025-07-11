# 🚀 Angel One Options Analytics Tracker

A comprehensive Python-based options chain tracker that fetches real-time option chain data for **NIFTY** and **BANKNIFTY** from Angel One SmartAPI, calculates changes over time, and stores snapshots in MySQL for advanced analytics.

## 📁 Project Structure

```
OI Tracker/
├── angel_oi_tracker/           # Main application
│   ├── main.py                # Core scheduler (real-time tracking)
│   ├── angel_login.py         # Authentication module
│   ├── option_chain_fetcher.py # Data fetching from Angel One API
│   ├── store_option_data_mysql.py # MySQL data storage
│   ├── verify_mysql_data.py   # Data verification utilities
│   ├── view_data_mysql.py     # Data viewing and analysis
│   ├── angel_config.txt       # Configuration file
│   ├── requirements.txt       # Python dependencies
│   ├── .gitignore            # Git ignore rules
│   └── utils/                 # Utility modules
│       ├── __init__.py
│       ├── atm_utils.py       # ATM strike calculations
│       ├── strike_range.py    # Strike filtering logic
│       ├── symbols.py         # Index tokens and symbols
│       ├── scrip_master.py    # Scrip master utilities
│       └── OpenAPIScripMaster.json # Angel One scrip master data
├── tests/                     # Test files and debugging scripts
├── docs/                      # Documentation files
└── scripts/                   # Setup, migration, and utility scripts
```

## 🚀 Quick Start

### 1. Install Dependencies
```bash
cd angel_oi_tracker
pip install -r requirements.txt
```

### 2. Configure Credentials
Edit `angel_oi_tracker/angel_config.txt` with your Angel One credentials:
```txt
API_KEY=your_angel_api_key
CLIENT_ID=your_client_id
PASSWORD=your_password
TOTP_KEY=your_totp_secret_key
```

### 3. Setup MySQL Database
```bash
cd scripts
python mysql_setup.py
```

### 4. Start Real-time Tracking
```bash
cd angel_oi_tracker
python main.py
```

## 📊 Features

- **Real-time Data Collection**: Fetches option chain data every 3 minutes during market hours
- **Multi-Index Support**: NIFTY and BANKNIFTY
- **ATM Detection**: Automatically calculates ATM strikes and filters ±5 strikes
- **Complete Analytics**: OI, LTP, Volume, Greeks (Delta, Theta, Vega, Gamma), IV
- **MySQL Storage**: Efficient database storage with change calculations
- **Backfill Engine**: Historical data recovery
- **Market Hours**: Operates only during trading hours (9:18 AM - 3:30 PM IST)

## 🔧 Key Components

### Core Application (`angel_oi_tracker/`)
- `main.py` - Real-time scheduler using APScheduler
- `angel_login.py` - TOTP-based authentication
- `option_chain_fetcher.py` - API data fetching and processing
- `store_option_data_mysql.py` - MySQL data storage and analytics

### Utilities (`angel_oi_tracker/utils/`)
- `atm_utils.py` - ATM strike calculations
- `strike_range.py` - Strike filtering logic
- `symbols.py` - Index tokens and symbol management
- `scrip_master.py` - Angel One scrip master utilities

### Testing (`tests/`)
- Various test scripts for debugging and validation
- System health checks and API testing

### Documentation (`docs/`)
- Complete documentation and guides
- API compliance information
- Quick start guides

### Scripts (`scripts/`)
- Database setup and migration scripts
- Batch files for easy execution
- Legacy SQLite utilities

## ⚠️ API Compliance

This project uses Angel One SmartAPI and complies with official guidelines:
- **Documentation**: https://smartapi.angelone.in/docs
- **Rate Limits**: https://smartapi.angelone.in/docs/rate-limits
- **Terms of Service**: https://smartapi.angelone.in/terms

## 📈 Usage Examples

### Start Real-time Tracking
```bash
cd angel_oi_tracker
python main.py
```

### View Data
```bash
cd angel_oi_tracker
python view_data_mysql.py
```

### Verify Data
```bash
cd angel_oi_tracker
python verify_mysql_data.py
```

### Run Tests
```bash
cd tests
python test_system.py
```

## 🔒 Security Notes

- Never commit credentials to version control
- Use environment variables or config files for sensitive data
- Keep TOTP secret secure
- Regularly rotate API keys

## 📖 Documentation

For detailed documentation, see the `docs/` folder:
- `docs/README.md` - Complete project documentation
- `docs/QUICK_START.md` - Quick start guide
- `docs/API_COMPLIANCE.md` - API compliance guidelines
- `docs/MYSQL_MIGRATION_README.md` - MySQL migration guide

## 🛠️ Troubleshooting

### Common Issues
1. **Login Failed**: Check credentials and TOTP
2. **No Data**: Verify market hours and internet connection
3. **Database Error**: Run MySQL setup script

### Testing
```bash
cd tests
python status_check.py
```

---

**🎉 Your Angel One Options Analytics Tracker is now organized and ready to use!** 