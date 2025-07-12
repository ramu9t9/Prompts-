"""
AI Trade Intelligence Engine - Phase 4

This module integrates with the existing options analytics system to generate
AI-powered trade insights using OpenRouter API.

Key Features:
- Data aggregation from existing tables
- Market context compilation
- OpenRouter API integration
- Trade setup storage and CLI display
- Model rotation and fallback handling

Always refer to official documentation: https://smartapi.angelone.in/docs
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pytz
from utils.llm_client import openrouter_client
from store_option_data_mysql import MySQLOptionDataStore
from oi_analysis_engine import OIAnalysisEngine
import os

class AITradeEngine:
    def __init__(self, datastore: MySQLOptionDataStore = None):
        """
        Initialize AI Trade Engine
        
        Args:
            datastore: MySQL data store instance
        """
        self.datastore = datastore or MySQLOptionDataStore()
        self.ist_tz = pytz.timezone('Asia/Kolkata')
        self.analysis_engine = OIAnalysisEngine(self.datastore)
        
        # Setup logging
        self.setup_logging()
        
        # Configuration
        self.atm_range = 4  # ATM ±4 strikes
        self.min_confidence = 70  # Minimum confidence for trade setup
        self.max_setups_per_bucket = 1  # Max trade setups per bucket
        
        self.logger.info("AI Trade Engine initialized")
    
    def setup_logging(self):
        """Setup logging for AI trade engine"""
        try:
            log_dir = "logs"
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            today = datetime.now(self.ist_tz).strftime('%Y-%m-%d')
            log_file = f"{log_dir}/ai_trade_engine_{today}.log"
            
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler(log_file),
                    logging.StreamHandler()
                ]
            )
            
            self.logger = logging.getLogger('ai_trade_engine')
            
        except Exception as e:
            print(f"Error setting up logging: {str(e)}")
            self.logger = logging.getLogger('ai_trade_engine')
    
    def generate_trade_insights(self, bucket_ts: datetime, index_name: str = "NIFTY") -> Optional[Dict]:
        """
        Generate AI trade insights for a specific bucket and index
        
        Args:
            bucket_ts: Bucket timestamp
            index_name: Index name (NIFTY/BANKNIFTY)
            
        Returns:
            Trade insight or None if failed
        """
        try:
            # Step 1: Aggregate market data
            market_data = self._aggregate_market_data(bucket_ts, index_name)
            if not market_data:
                self.logger.warning(f"No market data available for {index_name} at {bucket_ts}")
                return None
            
            # Step 2: Add global context
            market_data = self._add_global_context(market_data, bucket_ts, index_name)
            
            # Step 3: Generate AI insight
            trade_insight = self._generate_ai_insight(market_data)
            if not trade_insight:
                self.logger.warning(f"Failed to generate AI insight for {index_name}")
                return None
            
            # Step 4: Store and display
            self._store_trade_setup(trade_insight, bucket_ts, index_name, market_data)
            self._display_trade_setup(trade_insight, index_name)
            
            return trade_insight
            
        except Exception as e:
            self.logger.error(f"Error generating trade insights: {str(e)}")
            return None
    
    def _aggregate_market_data(self, bucket_ts: datetime, index_name: str) -> Optional[Dict]:
        """Aggregate market data from existing tables"""
        try:
            # Get historical data for analysis
            history_df = self.analysis_engine.get_historical_data(bucket_ts, index_name, hours_back=1)
            if history_df.empty:
                return None
            
            # Get latest bucket data
            latest_data = history_df[history_df['bucket_ts'] == bucket_ts].copy()
            if latest_data.empty:
                return None
            
            # Get spot LTP
            spot_ltp = self._get_spot_ltp(index_name)
            
            # Compile option chain data (ATM ±4 strikes)
            option_chain = self._compile_option_chain(latest_data, spot_ltp)
            
            # Calculate PCR
            pcr_data = self._calculate_pcr(latest_data)
            
            market_data = {
                'timestamp': bucket_ts.isoformat(),
                'index': index_name,
                'spot': {'ltp': spot_ltp},
                'pcr': pcr_data,
                'option_chain': option_chain
            }
            
            return market_data
            
        except Exception as e:
            self.logger.error(f"Error aggregating market data: {str(e)}")
            return None
    
    def _add_global_context(self, market_data: Dict, bucket_ts: datetime, index_name: str) -> Dict:
        """Add global market context (VWAP, CPR, etc.)"""
        try:
            # Get additional market levels
            levels = self._get_market_levels(index_name, bucket_ts)
            market_data['levels'] = levels
            
            # Add futures data if available
            futures_data = self._get_futures_data(index_name)
            if futures_data:
                market_data['futures'] = futures_data
            
            return market_data
            
        except Exception as e:
            self.logger.error(f"Error adding global context: {str(e)}")
            return market_data
    
    def _generate_ai_insight(self, market_data: Dict) -> Optional[Dict]:
        """Generate AI insight using OpenRouter API"""
        try:
            # Try with default model first
            insight = openrouter_client.generate_trade_insight(market_data)
            
            if insight and insight.get('confidence', 0) >= self.min_confidence:
                return insight
            
            # If low confidence or failed, try with different model
            self.logger.info("Trying with different model due to low confidence or failure")
            rotated_model = openrouter_client.rotate_model()
            insight = openrouter_client.generate_trade_insight(market_data, rotated_model)
            
            if insight and insight.get('confidence', 0) >= self.min_confidence:
                return insight
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error generating AI insight: {str(e)}")
            return None
    
    def _compile_option_chain(self, data: Any, spot_ltp: float) -> List[Dict]:
        """Compile option chain data for ATM ±4 strikes"""
        try:
            option_chain = []
            
            # Find ATM strike
            atm_strike = round(spot_ltp / 50) * 50  # Round to nearest 50
            
            # Get strikes in range
            strikes_range = range(atm_strike - (self.atm_range * 50), 
                                atm_strike + (self.atm_range * 50) + 1, 50)
            
            for strike in strikes_range:
                # Get CE data
                ce_data = data[data['strike'] == strike].iloc[0] if not data[data['strike'] == strike].empty else None
                if ce_data is not None:
                    option_chain.append({
                        'strike': int(strike),
                        'type': 'CE',
                        'ltp': float(ce_data.get('ce_ltp', 0)),
                        'oi': int(ce_data.get('ce_oi', 0)),
                        'oi_change': int(ce_data.get('ce_oi_change', 0)),
                        'volume': int(ce_data.get('ce_volume', 0)),
                        'delta': 0.5,  # Placeholder - would need Greeks data
                        'iv': 15.0,    # Placeholder - would need IV data
                        'theta': -2.0  # Placeholder - would need Greeks data
                    })
                
                # Get PE data
                pe_data = data[data['strike'] == strike].iloc[0] if not data[data['strike'] == strike].empty else None
                if pe_data is not None:
                    option_chain.append({
                        'strike': int(strike),
                        'type': 'PE',
                        'ltp': float(pe_data.get('pe_ltp', 0)),
                        'oi': int(pe_data.get('pe_oi', 0)),
                        'oi_change': int(pe_data.get('pe_oi_change', 0)),
                        'volume': int(pe_data.get('pe_volume', 0)),
                        'delta': -0.5,  # Placeholder - would need Greeks data
                        'iv': 15.0,     # Placeholder - would need IV data
                        'theta': -2.0   # Placeholder - would need Greeks data
                    })
            
            return option_chain
            
        except Exception as e:
            self.logger.error(f"Error compiling option chain: {str(e)}")
            return []
    
    def _calculate_pcr(self, data: Any) -> Dict:
        """Calculate PCR (Put-Call Ratio)"""
        try:
            total_ce_oi = data['ce_oi'].sum() if 'ce_oi' in data.columns else 0
            total_pe_oi = data['pe_oi'].sum() if 'pe_oi' in data.columns else 0
            total_ce_volume = data['ce_volume'].sum() if 'ce_volume' in data.columns else 0
            total_pe_volume = data['pe_volume'].sum() if 'pe_volume' in data.columns else 0
            
            pcr_oi = total_pe_oi / (total_ce_oi + 1e-5)
            pcr_volume = total_pe_volume / (total_ce_volume + 1e-5)
            
            return {
                'oi': round(pcr_oi, 4),
                'volume': round(pcr_volume, 4)
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating PCR: {str(e)}")
            return {'oi': 1.0, 'volume': 1.0}
    
    def _get_spot_ltp(self, index_name: str) -> float:
        """Get spot LTP for index"""
        try:
            # This would need to be implemented with actual market data
            # For now, return a placeholder
            if index_name == "NIFTY":
                return 24000.0
            elif index_name == "BANKNIFTY":
                return 48000.0
            else:
                return 24000.0
        except Exception as e:
            self.logger.error(f"Error getting spot LTP: {str(e)}")
            return 24000.0
    
    def _get_market_levels(self, index_name: str, bucket_ts: datetime) -> Dict:
        """Get market levels (VWAP, CPR, etc.)"""
        try:
            # This would need to be implemented with actual market data
            # For now, return placeholder values
            return {
                'vwap': 24000.0,
                'cpr_top': 24100.0,
                'cpr_bottom': 23900.0,
                'day_open': 23950.0,
                'pd_high': 24200.0,
                'pd_low': 23800.0
            }
        except Exception as e:
            self.logger.error(f"Error getting market levels: {str(e)}")
            return {}
    
    def _get_futures_data(self, index_name: str) -> Optional[Dict]:
        """Get futures data"""
        try:
            # This would need to be implemented with actual futures data
            # For now, return None
            return None
        except Exception as e:
            self.logger.error(f"Error getting futures data: {str(e)}")
            return None
    
    def _store_trade_setup(self, trade_insight: Dict, bucket_ts: datetime, 
                          index_name: str, market_data: Dict):
        """Store trade setup in database"""
        try:
            # Prepare data for storage
            setup_data = {
                'bucket_ts': bucket_ts,
                'index_name': index_name,
                'bias': trade_insight['bias'],
                'strategy': trade_insight['strategy'],
                'entry_strike': trade_insight['entry_strike'],
                'entry_type': trade_insight['entry_type'],
                'entry_price': trade_insight['entry_price'],
                'stop_loss': trade_insight['stop_loss'],
                'target': trade_insight['target'],
                'confidence': trade_insight['confidence'],
                'rationale': trade_insight['rationale'],
                'model_used': openrouter_client.default_model,
                'response_raw': json.dumps(trade_insight),
                'spot_ltp': market_data.get('spot', {}).get('ltp'),
                'pcr_oi': market_data.get('pcr', {}).get('oi'),
                'pcr_volume': market_data.get('pcr', {}).get('volume'),
                'vwap': market_data.get('levels', {}).get('vwap'),
                'cpr_top': market_data.get('levels', {}).get('cpr_top'),
                'cpr_bottom': market_data.get('levels', {}).get('cpr_bottom')
            }
            
            # Store in database
            success = self.datastore.insert_ai_trade_setup(setup_data)
            if success:
                self.logger.info(f"Trade setup stored for {index_name} at {bucket_ts}")
            else:
                self.logger.error(f"Failed to store trade setup for {index_name}")
                
        except Exception as e:
            self.logger.error(f"Error storing trade setup: {str(e)}")
    
    def _display_trade_setup(self, trade_insight: Dict, index_name: str):
        """Display trade setup in CLI"""
        try:
            print(f"\n🤖 AI Trade Setup - {index_name}")
            print("=" * 50)
            print(f"📊 Bias: {trade_insight['bias']}")
            print(f"🎯 Strategy: {trade_insight['strategy']}")
            print(f"📍 Entry: {trade_insight['entry_strike']} {trade_insight['entry_type']} @ {trade_insight['entry_price']}")
            print(f"🛑 Stop Loss: {trade_insight['stop_loss']}")
            print(f"🎯 Target: {trade_insight['target']}")
            print(f"📈 Confidence: {trade_insight['confidence']}%")
            print(f"💡 Rationale: {trade_insight['rationale']}")
            print(f"🤖 Model: {openrouter_client.default_model}")
            
        except Exception as e:
            self.logger.error(f"Error displaying trade setup: {str(e)}")

# Global AI trade engine instance
ai_trade_engine = AITradeEngine() 