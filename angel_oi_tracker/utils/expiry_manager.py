"""
Expiry Date Management Module

This module handles expiry date detection and management for options contracts.
It automatically detects the current expiry and handles multiple expiry scenarios.

Always refer to official documentation: https://smartapi.angelone.in/docs
"""

import os
import json
from datetime import datetime, timedelta
import pytz
from .scrip_master import load_scrip_master, search_symbols

class ExpiryManager:
    def __init__(self):
        self.ist_tz = pytz.timezone('Asia/Kolkata')
        self.cache = {}  # Cache expiry dates to avoid repeated lookups
        
    def get_current_expiry(self, index_name):
        """
        Get the current expiry date for an index.
        Returns the nearest expiry date that hasn't passed yet.
        """
        cache_key = f"{index_name}_current_expiry"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            # Get all option contracts for this index
            scrips = load_scrip_master()
            current_time = datetime.now(self.ist_tz)
            
            # Find all expiry dates for this index
            expiry_dates = set()
            for scrip in scrips:
                symbol = scrip.get("symbol", "").upper()
                if symbol.startswith(index_name.upper()):
                    # Extract expiry date from symbol (e.g., NIFTY24JUL17500CE -> 24JUL)
                    expiry_part = self._extract_expiry_from_symbol(symbol)
                    if expiry_part:
                        expiry_date = self._parse_expiry_date(expiry_part, current_time.year)
                        if expiry_date:
                            expiry_dates.add(expiry_date)
            
            if not expiry_dates:
                print(f"⚠️  No expiry dates found for {index_name}")
                return None
            
            # Find the current expiry (nearest future date)
            current_expiry = None
            for expiry in sorted(expiry_dates):
                if expiry > current_time:
                    current_expiry = expiry
                    break
            
            # If no future expiry found, use the latest available
            if not current_expiry:
                current_expiry = max(expiry_dates)
                print(f"⚠️  Using latest available expiry for {index_name}: {current_expiry.strftime('%d%b%Y')}")
            else:
                print(f"✅ Current expiry for {index_name}: {current_expiry.strftime('%d%b%Y')}")
            
            # Cache the result
            self.cache[cache_key] = current_expiry
            return current_expiry
            
        except Exception as e:
            print(f"❌ Error getting current expiry for {index_name}: {str(e)}")
            return None
    
    def _extract_expiry_from_symbol(self, symbol):
        """Extract expiry part from option symbol"""
        try:
            # Handle different symbol formats
            # NIFTY24JUL17500CE -> 24JUL
            # NIFTY24JUL202417500CE -> 24JUL2024
            
            # Find the pattern: number + month + optional year
            import re
            pattern = r'(\d{1,2}[A-Z]{3}\d{0,4})'
            match = re.search(pattern, symbol)
            if match:
                return match.group(1)
            return None
        except Exception:
            return None
    
    def _parse_expiry_date(self, expiry_str, current_year):
        """Parse expiry string to datetime object"""
        try:
            # Handle formats: 24JUL, 24JUL2024
            if len(expiry_str) == 5:  # 24JUL
                day = int(expiry_str[:2])
                month_str = expiry_str[2:5]
                year = current_year
            elif len(expiry_str) == 9:  # 24JUL2024
                day = int(expiry_str[:2])
                month_str = expiry_str[2:5]
                year = int(expiry_str[5:9])
            else:
                return None
            
            # Convert month string to number
            month_map = {
                'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
                'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
            }
            
            month = month_map.get(month_str.upper())
            if not month:
                return None
            
            # Create datetime object
            expiry_date = datetime(current_year, month, day, 15, 30, 0, tzinfo=self.ist_tz)
            
            # Adjust year if expiry has passed
            if expiry_date < datetime.now(self.ist_tz):
                expiry_date = datetime(current_year + 1, month, day, 15, 30, 0, tzinfo=self.ist_tz)
            
            return expiry_date
            
        except Exception as e:
            print(f"❌ Error parsing expiry date {expiry_str}: {str(e)}")
            return None
    
    def get_all_expiries(self, index_name):
        """Get all available expiry dates for an index"""
        try:
            scrips = load_scrip_master()
            expiry_dates = set()
            
            for scrip in scrips:
                symbol = scrip.get("symbol", "").upper()
                if symbol.startswith(index_name.upper()):
                    expiry_part = self._extract_expiry_from_symbol(symbol)
                    if expiry_part:
                        current_time = datetime.now(self.ist_tz)
                        expiry_date = self._parse_expiry_date(expiry_part, current_time.year)
                        if expiry_date:
                            expiry_dates.add(expiry_date)
            
            return sorted(expiry_dates)
            
        except Exception as e:
            print(f"❌ Error getting all expiries for {index_name}: {str(e)}")
            return []
    
    def is_expiry_valid(self, index_name, expiry_date):
        """Check if an expiry date is valid for the given index"""
        try:
            all_expiries = self.get_all_expiries(index_name)
            return expiry_date in all_expiries
        except Exception:
            return False
    
    def get_next_expiry(self, index_name):
        """Get the next expiry after the current one"""
        try:
            all_expiries = self.get_all_expiries(index_name)
            current_expiry = self.get_current_expiry(index_name)
            
            if not current_expiry or not all_expiries:
                return None
            
            # Find the next expiry
            for expiry in all_expiries:
                if expiry > current_expiry:
                    return expiry
            
            return None
            
        except Exception as e:
            print(f"❌ Error getting next expiry for {index_name}: {str(e)}")
            return None

# Global instance
expiry_manager = ExpiryManager()

def get_current_expiry(index_name):
    """Get current expiry for an index"""
    return expiry_manager.get_current_expiry(index_name)

def get_all_expiries(index_name):
    """Get all expiries for an index"""
    return expiry_manager.get_all_expiries(index_name)

def is_expiry_valid(index_name, expiry_date):
    """Check if expiry is valid"""
    return expiry_manager.is_expiry_valid(index_name, expiry_date) 