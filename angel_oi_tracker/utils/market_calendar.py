"""
Market Calendar Utility for Phase 2

This module provides market calendar functionality for adaptive polling and gap-fill operations.
Always refer to official documentation: https://smartapi.angelone.in/docs

API Compliance:
- Data Usage: Use data only for authorized purposes
- Terms of Service: Follow Angel One's terms and conditions
"""

from datetime import datetime, timedelta
import pytz

class MarketCalendar:
    def __init__(self):
        self.ist_tz = pytz.timezone('Asia/Kolkata')
        
        # Market hours (IST)
        self.MARKET_START_HOUR = 9
        self.MARKET_START_MINUTE = 18
        self.MARKET_END_HOUR = 15
        self.MARKET_END_MINUTE = 30
        
        # Polling constants
        self.POLL_FREQ = 20  # seconds
        self.REFRESH_WINDOW = 30  # seconds (max drift NSE push vs fetch)
        self.BUCKET_INTERVAL = 3  # minutes
    
    def is_market_live_now(self):
        """
        Check if market is currently live (09:18:00 - 15:30:00 IST on weekdays)
        
        Returns:
            bool: True if market is live, False otherwise
        """
        now = datetime.now(self.ist_tz)
        
        # Check if it's weekend
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Check market hours
        market_start = now.replace(
            hour=self.MARKET_START_HOUR,
            minute=self.MARKET_START_MINUTE,
            second=0,
            microsecond=0
        )
        market_end = now.replace(
            hour=self.MARKET_END_HOUR,
            minute=self.MARKET_END_MINUTE,
            second=0,
            microsecond=0
        )
        
        return market_start <= now <= market_end
    
    def is_market_open(self):
        """
        Alias for is_market_live_now() for backward compatibility
        """
        return self.is_market_live_now()
    
    def get_market_hours(self, date=None):
        """
        Get market start and end times for a given date
        
        Args:
            date: datetime object (default: today)
            
        Returns:
            tuple: (market_start, market_end) datetime objects
        """
        if date is None:
            date = datetime.now(self.ist_tz)
        
        market_start = date.replace(
            hour=self.MARKET_START_HOUR,
            minute=self.MARKET_START_MINUTE,
            second=0,
            microsecond=0
        )
        market_end = date.replace(
            hour=self.MARKET_END_HOUR,
            minute=self.MARKET_END_MINUTE,
            second=0,
            microsecond=0
        )
        
        return market_start, market_end
    
    def get_last_market_day(self):
        """
        Get the last market day (excluding weekends)
        
        Returns:
            datetime: Last market day
        """
        now = datetime.now(self.ist_tz)
        current_day = now
        
        # Go back until we find a weekday
        while current_day.weekday() >= 5:  # Saturday = 5, Sunday = 6
            current_day -= timedelta(days=1)
        
        return current_day
    
    def get_last_market_day_open(self):
        """
        Get the market open time for the last market day
        
        Returns:
            datetime: Market open time for last market day
        """
        last_market_day = self.get_last_market_day()
        market_start, _ = self.get_market_hours(last_market_day)
        return market_start
    
    def next_open_datetime(self):
        """
        Get the next market open datetime
        
        Returns:
            datetime: Next market open time
        """
        now = datetime.now(self.ist_tz)
        
        # If it's weekend, find next Monday
        if now.weekday() >= 5:  # Weekend
            days_ahead = 7 - now.weekday()  # Days until Monday
            next_monday = now + timedelta(days=days_ahead)
            market_start, _ = self.get_market_hours(next_monday)
            return market_start
        
        # If it's before market hours today
        market_start, _ = self.get_market_hours(now)
        if now < market_start:
            return market_start
        
        # If it's after market hours today, find next weekday
        days_ahead = 1
        while True:
            next_day = now + timedelta(days=days_ahead)
            if next_day.weekday() < 5:  # Weekday
                market_start, _ = self.get_market_hours(next_day)
                return market_start
            days_ahead += 1
    
    def is_new_market_day(self, last_bucket_ts=None):
        """
        Check if we're starting a new market day
        
        Args:
            last_bucket_ts: Last bucket timestamp from database
            
        Returns:
            bool: True if new market day, False otherwise
        """
        now = datetime.now(self.ist_tz)
        
        if last_bucket_ts is None:
            return True
        
        # Convert to IST if needed
        if last_bucket_ts.tzinfo is None:
            last_bucket_ts = self.ist_tz.localize(last_bucket_ts)
        
        # Check if last bucket was from a different day
        return last_bucket_ts.date() != now.date()
    
    def floor_to_3min(self, timestamp):
        """
        Floor timestamp to the nearest 3-minute bucket
        
        Args:
            timestamp: datetime object
            
        Returns:
            datetime: Floored timestamp
        """
        # Convert to minutes since midnight, floor to 3-minute intervals
        minutes_since_midnight = timestamp.hour * 60 + timestamp.minute
        floored_minutes = (minutes_since_midnight // self.BUCKET_INTERVAL) * self.BUCKET_INTERVAL
        
        # Ensure floored_minutes is within valid range (0-59)
        if floored_minutes >= 60:
            floored_minutes = 57  # Last valid 3-minute interval
        
        # Create new timestamp with floored minutes
        floored_time = timestamp.replace(minute=floored_minutes, second=0, microsecond=0)
        return floored_time
    
    def generate_bucket_timestamps(self, start_time, end_time):
        """
        Generate list of 3-minute bucket timestamps between start and end
        
        Args:
            start_time: datetime object
            end_time: datetime object
            
        Returns:
            list: List of datetime objects for each 3-minute bucket
        """
        timestamps = []
        current_time = self.floor_to_3min(start_time)
        end_time = self.floor_to_3min(end_time)
        
        while current_time <= end_time:
            timestamps.append(current_time)
            current_time += timedelta(minutes=self.BUCKET_INTERVAL)
        
        return timestamps
    
    def get_missing_buckets(self, start_time, end_time, existing_buckets):
        """
        Get list of missing bucket timestamps
        
        Args:
            start_time: datetime object
            end_time: datetime object
            existing_buckets: set of existing bucket timestamps
            
        Returns:
            list: List of missing bucket timestamps
        """
        all_buckets = set(self.generate_bucket_timestamps(start_time, end_time))
        missing_buckets = all_buckets - existing_buckets
        return sorted(list(missing_buckets))
    
    def should_poll_now(self, last_poll_time=None):
        """
        Check if we should poll now based on polling frequency
        
        Args:
            last_poll_time: Last poll timestamp
            
        Returns:
            bool: True if should poll, False otherwise
        """
        if last_poll_time is None:
            return True
        
        now = datetime.now(self.ist_tz)
        time_since_last_poll = (now - last_poll_time).total_seconds()
        
        return time_since_last_poll >= self.POLL_FREQ
    
    def get_market_status(self):
        """
        Get detailed market status information
        
        Returns:
            dict: Market status information
        """
        now = datetime.now(self.ist_tz)
        is_live = self.is_market_live_now()
        is_weekend = now.weekday() >= 5
        
        market_start, market_end = self.get_market_hours(now)
        next_open = self.next_open_datetime()
        
        return {
            'current_time': now,
            'is_live': is_live,
            'is_weekend': is_weekend,
            'market_start': market_start,
            'market_end': market_end,
            'next_open': next_open,
            'weekday': now.weekday(),
            'weekday_name': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][now.weekday()]
        } 