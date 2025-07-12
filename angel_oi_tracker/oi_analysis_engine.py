"""
OI Analysis Engine - Real-Time Analytics & CLI Dashboard

This module provides real-time OI analytics, confidence scoring, and trend detection
for the CLI dashboard. It queries only the historical_oi_tracking table.

Key Features:
- Confidence score calculation (0-100)
- Support/resistance shift detection
- Live summary generation for CLI
- Trend analysis with alerts
- PCR and market bias analysis

Always refer to official documentation: https://smartapi.angelone.in/docs

API Compliance:
- Data Usage: Use data only for authorized purposes
- Terms of Service: Follow Angel One's terms and conditions
"""

import pandas as pd
import numpy as np
import logging
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import pytz
from sqlalchemy import create_engine, text

class OIAnalysisEngine:
    """
    Real-Time OI Analytics Engine for Phase 3
    
    Provides comprehensive options analytics including:
    - Confidence scoring for OI changes
    - Support/Resistance detection
    - Bullish/Bearish strike analysis
    - PCR calculation and market bias
    - Real-time alerts and trend detection
    """
    
    def __init__(self, datastore):
        self.datastore = datastore
        self.ist_tz = datastore.ist_tz
        
        # Analysis parameters
        self.confidence_threshold = 50
        self.max_strikes_display = 5
        self.trend_buckets = 3
        
        # Setup logging
        self.setup_logging()
        
        self.logger.info("OI Analysis Engine initialized")
    
    def setup_logging(self):
        """Setup JSON logging for analytics"""
        try:
            log_dir = "logs"
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            today = datetime.now(self.ist_tz).strftime('%Y-%m-%d')
            log_file = f"{log_dir}/oi_analytics_{today}.log"
            
            # Configure JSON logging
            logging.basicConfig(
                level=logging.INFO,
                format='%(message)s',
                handlers=[
                    logging.FileHandler(log_file),
                    logging.StreamHandler()
                ]
            )
            
            self.logger = logging.getLogger('oi_analytics')
            
        except Exception as e:
            print(f"Error setting up logging: {str(e)}")
            self.logger = logging.getLogger('oi_analytics')
    
    def calculate_confidence(self, strike_row: pd.Series) -> int:
        """
        Calculate confidence score for OI changes (0-100)
        
        Higher confidence when:
        - Large OI changes
        - Price movement aligns with OI direction
        - High volume
        - Consistent pattern across multiple strikes
        """
        try:
            confidence = 0
            
            # Base confidence from OI change magnitude
            ce_oi_change = abs(float(strike_row.get('ce_oi_change', 0) or 0))
            pe_oi_change = abs(float(strike_row.get('pe_oi_change', 0) or 0))
            
            # OI change scoring (0-40 points)
            max_oi_change = max(ce_oi_change, pe_oi_change)
            if max_oi_change > 10000:
                confidence += 40
            elif max_oi_change > 5000:
                confidence += 30
            elif max_oi_change > 1000:
                confidence += 20
            elif max_oi_change > 100:
                confidence += 10
            
            # Percentage change scoring (0-30 points)
            ce_pct = abs(float(strike_row.get('ce_oi_pct_change', 0) or 0))
            pe_pct = abs(float(strike_row.get('pe_oi_pct_change', 0) or 0))
            max_pct = max(ce_pct, pe_pct)
            
            if max_pct > 50:
                confidence += 30
            elif max_pct > 25:
                confidence += 20
            elif max_pct > 10:
                confidence += 15
            elif max_pct > 5:
                confidence += 10
            
            # Price alignment scoring (0-20 points)
            ce_oi_up = float(strike_row.get('ce_oi_change', 0) or 0) > 0
            pe_oi_up = float(strike_row.get('pe_oi_change', 0) or 0) > 0
            ce_price_up = float(strike_row.get('ce_ltp_change_pct', 0) or 0) > 0
            pe_price_up = float(strike_row.get('pe_ltp_change_pct', 0) or 0) > 0
            
            # CE OI up + CE price up = bearish signal (selling pressure)
            if ce_oi_up and ce_price_up:
                confidence += 20
            # PE OI up + PE price up = bullish signal (buying pressure)
            elif pe_oi_up and pe_price_up:
                confidence += 20
            # Mixed signals reduce confidence
            elif (ce_oi_up and pe_oi_up) or (ce_price_up and pe_price_up):
                confidence += 10
            
            # Volume/activity scoring (0-10 points)
            total_oi = float(strike_row.get('ce_oi', 0) or 0) + float(strike_row.get('pe_oi', 0) or 0)
            if total_oi > 50000:
                confidence += 10
            elif total_oi > 20000:
                confidence += 7
            elif total_oi > 10000:
                confidence += 5
            elif total_oi > 5000:
                confidence += 3
            
            return min(confidence, 100)
            
        except Exception as e:
            self.logger.error(f"Error calculating confidence: {str(e)}")
            return 0
    
    def detect_support_resistance_shift(self, history_df: pd.DataFrame) -> Dict:
        """
        Detect support and resistance levels and their shifts
        
        Returns:
        - support_level: Current support level (strike with max PE OI)
        - resistance_level: Current resistance level (strike with max CE OI)
        - support_shift: Direction of support shift (UP/DOWN/NEUTRAL)
        - resistance_shift: Direction of resistance shift (UP/DOWN/NEUTRAL)
        """
        try:
            if history_df.empty:
                return {
                    'support_level': None,
                    'resistance_level': None,
                    'support_shift': 'NEUTRAL',
                    'resistance_shift': 'NEUTRAL'
                }
            
            # Get unique sorted buckets
            buckets = sorted(history_df['bucket_ts'].unique())
            if len(buckets) < 2:
                # Not enough data to detect shift
                latest_bucket = buckets[-1]
                latest_data = history_df[history_df['bucket_ts'] == latest_bucket]
                support_level = int(latest_data.loc[latest_data['pe_oi'].astype(float).idxmax(), 'strike']) if not latest_data.empty else None
                resistance_level = int(latest_data.loc[latest_data['ce_oi'].astype(float).idxmax(), 'strike']) if not latest_data.empty else None
                return {
                    'support_level': support_level,
                    'resistance_level': resistance_level,
                    'support_shift': 'NEUTRAL',
                    'resistance_shift': 'NEUTRAL'
                }
            # Previous and current buckets
            prev_bucket = buckets[-2]
            curr_bucket = buckets[-1]
            prev_data = history_df[history_df['bucket_ts'] == prev_bucket]
            curr_data = history_df[history_df['bucket_ts'] == curr_bucket]
            # Ensure DataFrame type
            if not isinstance(prev_data, pd.DataFrame):
                prev_data = pd.DataFrame(prev_data)
            if not isinstance(curr_data, pd.DataFrame):
                curr_data = pd.DataFrame(curr_data)
            # Support: max PE OI
            prev_support = int(prev_data.loc[prev_data['pe_oi'].astype(float).idxmax(), 'strike']) if not prev_data.empty else None
            curr_support = int(curr_data.loc[curr_data['pe_oi'].astype(float).idxmax(), 'strike']) if not curr_data.empty else None
            # Resistance: max CE OI
            prev_resist = int(prev_data.loc[prev_data['ce_oi'].astype(float).idxmax(), 'strike']) if not prev_data.empty else None
            curr_resist = int(curr_data.loc[curr_data['ce_oi'].astype(float).idxmax(), 'strike']) if not curr_data.empty else None
            # Detect shift
            support_shift = 'NEUTRAL'
            if prev_support is not None and curr_support is not None:
                if curr_support > prev_support:
                    support_shift = 'UP'
                elif curr_support < prev_support:
                    support_shift = 'DOWN'
            resistance_shift = 'NEUTRAL'
            if prev_resist is not None and curr_resist is not None:
                if curr_resist > prev_resist:
                    resistance_shift = 'UP'
                elif curr_resist < prev_resist:
                    resistance_shift = 'DOWN'
            return {
                'support_level': curr_support,
                'resistance_level': curr_resist,
                'support_shift': support_shift,
                'resistance_shift': resistance_shift
            }
        except Exception as e:
            self.logger.error(f"Error in support/resistance shift detection: {str(e)}")
            return {
                'support_level': None,
                'resistance_level': None,
                'support_shift': 'NEUTRAL',
                'resistance_shift': 'NEUTRAL'
            }
    
    def get_historical_data(self, bucket_ts: datetime, index_name: str, hours_back: int = 2) -> pd.DataFrame:
        """Get historical OI data for analysis"""
        try:
            connection = self.datastore.get_connection()
            if connection is None:
                return pd.DataFrame()
            
            # Calculate time range
            end_time = bucket_ts
            start_time = end_time - timedelta(hours=hours_back)
            
            query = """
                SELECT * FROM historical_oi_tracking 
                WHERE index_name = %s 
                AND bucket_ts BETWEEN %s AND %s
                ORDER BY bucket_ts ASC, strike ASC
            """
            
            # Use pandas read_sql with connection (suppress warning)
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                df = pd.read_sql(query, connection, params=(index_name, start_time, end_time))
            
            connection.close()
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error getting historical data: {str(e)}")
            return pd.DataFrame()
    
    def analyze_bullish_bearish_strikes(self, history_df: pd.DataFrame) -> Tuple[List[Dict], List[Dict]]:
        """Analyze and rank bullish and bearish strikes"""
        try:
            if history_df.empty:
                return [], []
            
            # Get latest bucket data
            latest_bucket = history_df.iloc[-1]['bucket_ts']
            latest_data = history_df[history_df['bucket_ts'] == latest_bucket].copy()
            
            if latest_data.empty:
                return [], []
            
            # Calculate confidence scores
            latest_data['confidence'] = latest_data.apply(self.calculate_confidence, axis=1)
            
            # Filter strikes with significant OI changes
            significant_data = latest_data[
                (latest_data['ce_oi_change'] > 0) | 
                (latest_data['pe_oi_change'] > 0)
            ].copy()
            
            if significant_data.empty:
                return [], []
            
            # Classify strikes as bullish or bearish
            bullish_strikes = []
            bearish_strikes = []
            
            for _, row in significant_data.iterrows():
                strike_info = {
                    'strike': int(row['strike']),
                    'ce_oi_change': int(row['ce_oi_change']),
                    'pe_oi_change': int(row['pe_oi_change']),
                    'ce_oi_pct': float(row['ce_oi_pct_change']),
                    'pe_oi_pct': float(row['pe_oi_pct_change']),
                    'ce_ltp_pct': float(row['ce_ltp_change_pct']),
                    'pe_ltp_pct': float(row['pe_ltp_change_pct']),
                    'confidence': int(row['confidence'])
                }
                
                # Determine if bullish or bearish based on OI and price patterns
                ce_dominant = float(row['ce_oi_change']) > float(row['pe_oi_change'])
                price_aligned = False
                
                if ce_dominant:
                    # CE OI up + CE price up = bearish (selling pressure)
                    price_aligned = float(row['ce_ltp_pct']) > 0
                    if price_aligned:
                        bearish_strikes.append(strike_info)
                    else:
                        bullish_strikes.append(strike_info)
                else:
                    # PE OI up + PE price up = bullish (buying pressure)
                    price_aligned = float(row['pe_ltp_pct']) > 0
                    if price_aligned:
                        bullish_strikes.append(strike_info)
                    else:
                        bearish_strikes.append(strike_info)
            
            # Sort by confidence and limit to top N
            bullish_strikes.sort(key=lambda x: x['confidence'], reverse=True)
            bearish_strikes.sort(key=lambda x: x['confidence'], reverse=True)
            
            return (
                bullish_strikes[:self.max_strikes_display],
                bearish_strikes[:self.max_strikes_display]
            )
            
        except Exception as e:
            self.logger.error(f"Error analyzing bullish/bearish strikes: {str(e)}")
            return [], []
    
    def calculate_pcr_and_bias(self, history_df: pd.DataFrame) -> Tuple[float, str]:
        """Calculate PCR and determine market bias"""
        try:
            if history_df.empty:
                return 0.0, "NEUTRAL"
            
            # Get latest bucket data
            latest_bucket = history_df.iloc[-1]['bucket_ts']
            latest_data = history_df[history_df['bucket_ts'] == latest_bucket]
            
            if latest_data.empty:
                return 0.0, "NEUTRAL"
            
            # Calculate total CE and PE OI
            total_ce_oi = float(latest_data['ce_oi'].sum() or 0)
            total_pe_oi = float(latest_data['pe_oi'].sum() or 0)
            
            # Calculate PCR
            if total_ce_oi > 0:
                pcr = total_pe_oi / total_ce_oi
            else:
                pcr = 0.0
            
            # Determine market bias
            if pcr > 1.2:
                bias = "BULLISH"
            elif pcr < 0.8:
                bias = "BEARISH"
            else:
                bias = "NEUTRAL"
            
            return round(pcr, 4), bias
            
        except Exception as e:
            self.logger.error(f"Error calculating PCR and bias: {str(e)}")
            return 0.0, "NEUTRAL"
    
    def generate_live_summary(self, bucket_ts: datetime, index_name: str) -> Dict:
        """
        Generate comprehensive live summary for CLI dashboard
        
        Returns:
        - timestamp: Bucket timestamp
        - index_name: Index being analyzed
        - pcr: Put-Call Ratio
        - bias: Market bias (BULLISH/BEARISH/NEUTRAL)
        - bullish_strikes: Top bullish strikes
        - bearish_strikes: Top bearish strikes
        - support_level: Current support level
        - resistance_level: Current resistance level
        - support_shift: Support shift direction
        - resistance_shift: Resistance shift direction
        - alerts: List of trend alerts
        """
        try:
            # Get historical data for analysis
            history_df = self.get_historical_data(bucket_ts, index_name)
            
            if history_df.empty:
                return {
                    'timestamp': bucket_ts.strftime('%H:%M:%S'),
                    'index_name': index_name,
                    'pcr': 0.0,
                    'bias': 'NEUTRAL',
                    'bullish_strikes': [],
                    'bearish_strikes': [],
                    'support_level': None,
                    'resistance_level': None,
                    'support_shift': 'NEUTRAL',
                    'resistance_shift': 'NEUTRAL',
                    'alerts': []
                }
            
            # Calculate PCR and bias
            pcr, bias = self.calculate_pcr_and_bias(history_df)
            
            # Analyze bullish/bearish strikes
            bullish_strikes, bearish_strikes = self.analyze_bullish_bearish_strikes(history_df)
            
            # Detect support/resistance shifts
            sr_analysis = self.detect_support_resistance_shift(history_df)
            
            # Generate alerts
            alerts = self.generate_alerts(history_df, sr_analysis, pcr)
            
            # Create summary
            summary = {
                'timestamp': bucket_ts.strftime('%H:%M:%S'),
                'index_name': index_name,
                'pcr': pcr,
                'bias': bias,
                'bullish_strikes': bullish_strikes,
                'bearish_strikes': bearish_strikes,
                'support_level': sr_analysis['support_level'],
                'resistance_level': sr_analysis['resistance_level'],
                'support_shift': sr_analysis['support_shift'],
                'resistance_shift': sr_analysis['resistance_shift'],
                'alerts': alerts
            }
            
            # Log summary as JSON
            self.log_summary(summary)
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error generating live summary: {str(e)}")
            return {
                'timestamp': bucket_ts.strftime('%H:%M:%S'),
                'index_name': index_name,
                'pcr': 0.0,
                'bias': 'NEUTRAL',
                'bullish_strikes': [],
                'bearish_strikes': [],
                'support_level': None,
                'resistance_level': None,
                'support_shift': 'NEUTRAL',
                'resistance_shift': 'NEUTRAL',
                'alerts': []
            }
    
    def generate_alerts(self, history_df: pd.DataFrame, sr_analysis: Dict, pcr: float) -> List[str]:
        """Generate trend alerts based on analysis"""
        alerts = []
        
        try:
            # Support shift alert
            if sr_analysis['support_shift'] == 'UP':
                alerts.append(f"Support shifted UP to {sr_analysis['support_level']}")
            elif sr_analysis['support_shift'] == 'DOWN':
                alerts.append(f"Support shifted DOWN to {sr_analysis['support_level']}")
            
            # Resistance shift alert
            if sr_analysis['resistance_shift'] == 'UP':
                alerts.append(f"Resistance shifted UP to {sr_analysis['resistance_level']}")
            elif sr_analysis['resistance_shift'] == 'DOWN':
                alerts.append(f"Resistance shifted DOWN to {sr_analysis['resistance_level']}")
            
            # PCR trend alert
            if len(history_df) >= self.trend_buckets:
                recent_pcrs = []
                for i in range(self.trend_buckets):
                    bucket_data = history_df.iloc[-(i+1)]
                    bucket_ce_oi = float(bucket_data['ce_oi'] or 0)
                    bucket_pe_oi = float(bucket_data['pe_oi'] or 0)
                    if bucket_ce_oi > 0:
                        bucket_pcr = bucket_pe_oi / bucket_ce_oi
                        recent_pcrs.append(bucket_pcr)
                
                if len(recent_pcrs) >= 2:
                    pcr_trend = recent_pcrs[-1] - recent_pcrs[0]
                    if pcr_trend > 0.1:
                        alerts.append("PCR trending UP - Bullish momentum")
                    elif pcr_trend < -0.1:
                        alerts.append("PCR trending DOWN - Bearish momentum")
            
            # Extreme PCR alerts
            if pcr > 1.5:
                alerts.append("Extreme PCR (>1.5) - Strong bullish sentiment")
            elif pcr < 0.5:
                alerts.append("Extreme PCR (<0.5) - Strong bearish sentiment")
            
        except Exception as e:
            self.logger.error(f"Error generating alerts: {str(e)}")
        
        return alerts
    
    def log_summary(self, summary: Dict):
        """Log summary as JSON for external processing"""
        try:
            # Create simplified log entry matching test expectations
            log_entry = {
                'ts': summary.get('timestamp', 'N/A'),
                'index': summary.get('index_name', 'NIFTY'),
                'pcr': summary.get('pcr', 0.0),
                'bias': summary.get('bias', 'NEUTRAL'),
                'bullish_count': len(summary.get('bullish_strikes', [])),
                'bearish_count': len(summary.get('bearish_strikes', [])),
                'support': summary.get('support_level'),
                'resistance': summary.get('resistance_level'),
                'alerts_count': len(summary.get('alerts', []))
            }
            
            # Write to dedicated analytics log file
            today = datetime.now(self.ist_tz).strftime('%Y-%m-%d')
            log_dir = f"logs/{today}"
            os.makedirs(log_dir, exist_ok=True)
            
            log_filename = f"{log_dir}/oi_analytics.log"
            with open(log_filename, 'a') as f:
                json_str = json.dumps(log_entry, default=str)
                f.write(json_str + '\n')
                
        except Exception as e:
            self.logger.error(f"JSON logging error: {str(e)}")
    
    def format_cli_display(self, summary: Dict) -> str:
        """Format summary for CLI dashboard display"""
        try:
            output = []
            index_name = summary.get('index_name', 'NIFTY')
            timestamp = summary.get('timestamp', 'N/A')
            pcr = summary.get('pcr', 0)
            bias = summary.get('bias', 'N/A')
            # Ensure PCR is always shown as 'PCR: xx.xx'
            output.append(f"\n📊 OI Analytics Dashboard - {index_name}")
            output.append("=" * 60)
            output.append(f"⏰ {timestamp} | PCR {pcr:.2f} | Bias: {bias}")
            
            # Support/Resistance
            if summary.get('support_level'):
                shift = summary.get('support_shift', 'NEUTRAL')
                arrow = "↗" if shift == "UP" else "↘" if shift == "DOWN" else ""
                output.append(f"📉 Support{arrow}: {summary.get('support_level')}")
            if summary.get('resistance_level'):
                shift = summary.get('resistance_shift', 'NEUTRAL')
                arrow = "↗" if shift == "UP" else "↘" if shift == "DOWN" else ""
                output.append(f"📈 Resistance{arrow}: {summary.get('resistance_level')}")
            
            # Bullish strikes
            if summary.get('bullish_strikes'):
                output.append("\n🟢 Top Bullish Strikes:")
                for strike in summary['bullish_strikes']:
                    strike_val = strike.get('strike', 'N/A')
                    output.append(f"   {strike_val}PE")
            
            # Bearish strikes
            if summary.get('bearish_strikes'):
                output.append("\n🔴 Top Bearish Strikes:")
                for strike in summary['bearish_strikes']:
                    strike_val = strike.get('strike', 'N/A')
                    output.append(f"   {strike_val}CE")
            
            # Alerts
            if summary.get('alerts'):
                output.append("\n🚨 Alerts:")
                for alert in summary['alerts']:
                    output.append(f"   • {alert}")
            
            return "\n".join(output)
            
        except Exception as e:
            return f"Error formatting display: {str(e)}" 