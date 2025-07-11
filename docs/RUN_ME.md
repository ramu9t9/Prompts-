# 🚀 How to Run Your Angel One Options Tracker

## ⚠️ IMPORTANT: API Compliance

**This system uses Angel One SmartAPI and must comply with official guidelines:**

- **Documentation**: https://smartapi.angelone.in/docs
- **Rate Limits**: https://smartapi.angelone.in/docs/rate-limits
- **Terms**: https://smartapi.angelone.in/terms

**Current implementation is compliant:**
- ✅ 3-minute intervals (within limits)
- ✅ Market hours only (9:18 AM - 3:30 PM IST)
- ✅ Proper authentication and session management

## ✅ Your System is Ready!

Your Angel One Options Analytics Tracker is fully configured with your credentials:
- **Client ID**: R117172
- **API Key**: P9ErUZG0
- **Password**: 9029
- **TOTP Secret**: Y4GDOA6SL5VOCKQPFLR5EM3HOY

## 🚀 Quick Start (Choose One Option)

### Option 1: Double-click to Run (Easiest)
1. **Double-click** `check_system.bat` to verify everything works
2. **Double-click** `run_tracker.bat` to start real-time tracking

### Option 2: Command Line
1. **Open Command Prompt** in this folder
2. **Run**: `python main.py`

### Option 3: PowerShell
1. **Open PowerShell** in this folder
2. **Run**: `python main.py`

## 📊 What You'll Get

- **Real-time data** every 3 minutes during market hours
- **NIFTY & BANKNIFTY** option chains
- **ATM ±5 strikes** automatically calculated
- **Complete analytics** with change calculations
- **SQLite database** for data storage

## ⏰ Market Hours

- **Trading Days**: Monday to Friday
- **Market Hours**: 9:18 AM to 3:30 PM IST
- **Data Collection**: Every 3 minutes

## 🔧 Troubleshooting

### If you get "No module named 'smartapi'" error:
```bash
pip install smartapi-python
```

### If you get "File not found" error:
Make sure you're in the `angel_oi_tracker` folder

### If market is closed:
- Wait for market hours (9:18 AM - 3:30 PM IST)
- Or run backfill: `python startup_backfill.py`

## 📁 Important Files

- `main.py` - Real-time tracker
- `angel_config.txt` - Your credentials
- `option_chain.db` - Database (created automatically)
- `check_system.bat` - System check
- `run_tracker.bat` - Start tracker

## 🎯 Next Steps

1. **Test the system**: Double-click `check_system.bat`
2. **Start tracking**: Double-click `run_tracker.bat`
3. **Monitor data**: Check `option_chain.db` file

---

**🎉 You're all set! Your options tracker is ready to collect real-time data!** 