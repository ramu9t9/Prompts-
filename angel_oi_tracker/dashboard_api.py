"""
Phase 5: Dashboard Intelligence & AI Playback System

This module provides FastAPI endpoints for the intelligent dashboard system.
Integrates seamlessly with existing backend infrastructure from Phases 1-4.

Key Features:
- Pattern Insights API (OI Quadrants)
- AI Trade Setups API (Live & Historical)
- Playback API for historical analysis
- Backend Status Monitoring
- WebSocket support for real-time updates

Always refer to official documentation: https://smartapi.angelone.in/docs
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pytz
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from store_option_data_mysql import MySQLOptionDataStore
from oi_analysis_engine import OIAnalysisEngine
from ai_trade_engine import AITradeEngine

class DashboardAPI:
    def __init__(self):
        self.app = FastAPI(
            title="OI Tracker Dashboard API",
            description="Phase 5: Dashboard Intelligence & AI Playback System",
            version="5.0.0"
        )
        
        # Setup CORS for frontend integration
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Initialize components
        self.ist_tz = pytz.timezone('Asia/Kolkata')
        self.datastore = MySQLOptionDataStore()
        self.analysis_engine = OIAnalysisEngine(self.datastore)
        self.ai_engine = AITradeEngine(self.datastore)
        
        # Setup logging
        self.setup_logging()
        
        # Register routes
        self.register_routes()
        
        # WebSocket connections
        self.active_connections: List[WebSocket] = []
    
    def setup_logging(self):
        """Setup logging for dashboard API"""
        try:
            log_dir = "logs"
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            today = datetime.now(self.ist_tz).strftime('%Y-%m-%d')
            log_file = f"{log_dir}/dashboard_api_{today}.log"
            
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler(log_file),
                    logging.StreamHandler()
                ]
            )
            
            self.logger = logging.getLogger('dashboard_api')
            
        except Exception as e:
            print(f"Error setting up logging: {str(e)}")
            self.logger = logging.getLogger('dashboard_api')
    
    def register_routes(self):
        """Register all API routes"""
        
        @self.app.get("/")
        async def root():
            """API root endpoint"""
            return {
                "message": "OI Tracker Dashboard API - Phase 5",
                "version": "5.0.0",
                "status": "operational",
                "endpoints": {
                    "pattern_insights": "/api/pattern_insights",
                    "trade_setups": "/api/trade_setups", 
                    "playback": "/api/playback/ai_setups",
                    "status": "/api/status",
                    "summary": "/api/summary/daily_oi",
                    "websocket": "/ws"
                }
            }
        
        @self.app.get("/api/pattern_insights")
        async def get_pattern_insights(
            index_name: str = Query("NIFTY", description="Index name (NIFTY/BANKNIFTY)"),
            start_time: Optional[str] = Query(None, description="Start time (YYYY-MM-DD HH:MM:SS)"),
            end_time: Optional[str] = Query(None, description="End time (YYYY-MM-DD HH:MM:SS)"),
            strike_range: int = Query(5, description="ATM ± N strikes"),
            quadrant: Optional[str] = Query(None, description="OI quadrant filter"),
            limit: int = Query(100, description="Number of records to return")
        ):
            """Get OI pattern insights from historical_oi_tracking"""
            try:
                # Parse time parameters
                if not start_time:
                    start_time_dt = datetime.now(self.ist_tz) - timedelta(hours=1)
                else:
                    start_time_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
                    start_time_dt = self.ist_tz.localize(start_time_dt)
                
                if not end_time:
                    end_time_dt = datetime.now(self.ist_tz)
                else:
                    end_time_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
                    end_time_dt = self.ist_tz.localize(end_time_dt)
                
                # Get pattern insights
                insights = await self._get_pattern_insights(
                    index_name, start_time_dt, end_time_dt, strike_range, quadrant, limit
                )
                
                self.logger.info(f"Pattern insights requested for {index_name}: {len(insights)} records")
                return JSONResponse(content=insights)
                
            except Exception as e:
                self.logger.error(f"Error getting pattern insights: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/trade_setups")
        async def get_trade_setups(
            index_name: str = Query("NIFTY", description="Index name (NIFTY/BANKNIFTY)"),
            confidence_min: int = Query(70, description="Minimum confidence score"),
            start_time: Optional[str] = Query(None, description="Start time (YYYY-MM-DD HH:MM:SS)"),
            end_time: Optional[str] = Query(None, description="End time (YYYY-MM-DD HH:MM:SS)"),
            bias: Optional[str] = Query(None, description="Bias filter (BULLISH/BEARISH/NEUTRAL)"),
            limit: int = Query(50, description="Number of records to return")
        ):
            """Get AI trade setups from ai_trade_setups"""
            try:
                # Parse time parameters
                if not start_time:
                    start_time_dt = datetime.now(self.ist_tz) - timedelta(hours=24)
                else:
                    start_time_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
                    start_time_dt = self.ist_tz.localize(start_time_dt)
                
                if not end_time:
                    end_time_dt = datetime.now(self.ist_tz)
                else:
                    end_time_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
                    end_time_dt = self.ist_tz.localize(end_time_dt)
                
                # Get trade setups
                setups = await self._get_trade_setups(
                    index_name, confidence_min, start_time_dt, end_time_dt, bias, limit
                )
                
                self.logger.info(f"Trade setups requested for {index_name}: {len(setups)} records")
                return JSONResponse(content=setups)
                
            except Exception as e:
                self.logger.error(f"Error getting trade setups: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/playback/ai_setups")
        async def get_playback_setups(
            index_name: str = Query("NIFTY", description="Index name (NIFTY/BANKNIFTY)"),
            start_time: str = Query(..., description="Start time (YYYY-MM-DD HH:MM:SS)"),
            end_time: str = Query(..., description="End time (YYYY-MM-DD HH:MM:SS)"),
            confidence_min: int = Query(70, description="Minimum confidence score")
        ):
            """Get AI setups for playback timeline"""
            try:
                # Parse time parameters
                start_time_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
                start_time_dt = self.ist_tz.localize(start_time_dt)
                end_time_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
                end_time_dt = self.ist_tz.localize(end_time_dt)
                
                # Get playback data
                playback_data = await self._get_playback_data(
                    index_name, start_time_dt, end_time_dt, confidence_min
                )
                
                self.logger.info(f"Playback data requested for {index_name}: {len(playback_data)} records")
                return JSONResponse(content=playback_data)
                
            except Exception as e:
                self.logger.error(f"Error getting playback data: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/status")
        async def get_backend_status():
            """Get backend system status"""
            try:
                status = await self._get_backend_status()
                return JSONResponse(content=status)
                
            except Exception as e:
                self.logger.error(f"Error getting backend status: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/summary/daily_oi")
        async def get_daily_oi_summary(
            index_name: str = Query("NIFTY", description="Index name (NIFTY/BANKNIFTY)"),
            date: str = Query(None, description="Date (YYYY-MM-DD)")
        ):
            """Get daily OI quadrant summary"""
            try:
                if not date:
                    date = datetime.now(self.ist_tz).strftime("%Y-%m-%d")
                
                summary = await self._get_daily_oi_summary(index_name, date)
                return JSONResponse(content=summary)
                
            except Exception as e:
                self.logger.error(f"Error getting daily OI summary: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/summary/ai_confidence")
        async def get_ai_confidence_summary(
            index_name: str = Query("NIFTY", description="Index name (NIFTY/BANKNIFTY)"),
            days: int = Query(7, description="Number of days to analyze")
        ):
            """Get AI confidence score histogram"""
            try:
                summary = await self._get_ai_confidence_summary(index_name, days)
                return JSONResponse(content=summary)
                
            except Exception as e:
                self.logger.error(f"Error getting AI confidence summary: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/summary/active_strikes")
        async def get_active_strikes_summary(
            index_name: str = Query("NIFTY", description="Index name (NIFTY/BANKNIFTY)"),
            hours: int = Query(1, description="Hours to look back")
        ):
            """Get top active strikes by OI change"""
            try:
                summary = await self._get_active_strikes_summary(index_name, hours)
                return JSONResponse(content=summary)
                
            except Exception as e:
                self.logger.error(f"Error getting active strikes summary: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates"""
            await websocket.accept()
            self.active_connections.append(websocket)
            
            try:
                while True:
                    # Send periodic updates
                    await websocket.send_text(json.dumps({
                        "type": "status",
                        "timestamp": datetime.now(self.ist_tz).isoformat(),
                        "message": "Connected to OI Tracker Dashboard"
                    }))
                    
                    # Wait for client message or timeout
                    try:
                        data = await websocket.receive_text()
                        # Handle client messages if needed
                    except WebSocketDisconnect:
                        break
                        
            except WebSocketDisconnect:
                self.active_connections.remove(websocket)
    
    async def _get_pattern_insights(self, index_name: str, start_time: datetime, 
                                  end_time: datetime, strike_range: int, 
                                  quadrant: Optional[str], limit: int) -> List[Dict]:
        """Get OI pattern insights from historical_oi_tracking"""
        try:
            connection = self.datastore.get_connection()
            if connection is None:
                return []
            
            cursor = connection.cursor(dictionary=True)
            
            # Build query with filters
            query = """
                SELECT 
                    bucket_ts, trading_symbol, strike, index_name,
                    ce_oi, pe_oi, total_oi,
                    ce_oi_change, pe_oi_change,
                    ce_oi_pct_change, pe_oi_pct_change,
                    ce_ltp, pe_ltp, index_ltp,
                    oi_quadrant, confidence_score, delta_band
                FROM historical_oi_tracking 
                WHERE index_name = %s 
                AND bucket_ts BETWEEN %s AND %s
            """
            params = [index_name, start_time, end_time]
            
            # Add quadrant filter if specified
            if quadrant:
                query += " AND oi_quadrant = %s"
                params.append(quadrant)
            
            # Add strike range filter (ATM ± N)
            # This would need spot price calculation, simplified for now
            query += " ORDER BY bucket_ts DESC, confidence_score DESC LIMIT %s"
            params.append(limit)
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            # Convert datetime objects to strings and Decimal to float for JSON serialization
            for result in results:
                if result.get('bucket_ts'):
                    result['bucket_ts'] = result['bucket_ts'].isoformat()
                # Convert Decimal objects to float
                for key, value in result.items():
                    if hasattr(value, '__float__'):
                        result[key] = float(value)
            
            connection.close()
            return results
            
        except Exception as e:
            self.logger.error(f"Error in _get_pattern_insights: {str(e)}")
            return []
    
    async def _get_trade_setups(self, index_name: str, confidence_min: int,
                               start_time: datetime, end_time: datetime,
                               bias: Optional[str], limit: int) -> List[Dict]:
        """Get AI trade setups from ai_trade_setups"""
        try:
            connection = self.datastore.get_connection()
            if connection is None:
                return []
            
            cursor = connection.cursor(dictionary=True)
            
            # Build query with filters
            query = """
                SELECT 
                    id, bucket_ts, index_name, bias, strategy,
                    entry_strike, entry_type, entry_price, stop_loss, target,
                    confidence, rationale, model_used,
                    spot_ltp, pcr_oi, pcr_volume, vwap, cpr_top, cpr_bottom,
                    created_at
                FROM ai_trade_setups 
                WHERE index_name = %s 
                AND confidence >= %s
                AND bucket_ts BETWEEN %s AND %s
            """
            params = [index_name, confidence_min, start_time, end_time]
            
            # Add bias filter if specified
            if bias:
                query += " AND bias = %s"
                params.append(bias)
            
            query += " ORDER BY bucket_ts DESC, confidence DESC LIMIT %s"
            params.append(limit)
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            # Convert datetime objects to strings and Decimal to float for JSON serialization
            for result in results:
                if result.get('bucket_ts'):
                    result['bucket_ts'] = result['bucket_ts'].isoformat()
                if result.get('created_at'):
                    result['created_at'] = result['created_at'].isoformat()
                # Convert Decimal objects to float
                for key, value in result.items():
                    if hasattr(value, '__float__'):
                        result[key] = float(value)
            
            connection.close()
            return results
            
        except Exception as e:
            self.logger.error(f"Error in _get_trade_setups: {str(e)}")
            return []
    
    async def _get_playback_data(self, index_name: str, start_time: datetime,
                                end_time: datetime, confidence_min: int) -> List[Dict]:
        """Get AI setups for playback timeline"""
        try:
            connection = self.datastore.get_connection()
            if connection is None:
                return []
            
            cursor = connection.cursor(dictionary=True)
            
            query = """
                SELECT 
                    bucket_ts, bias, strategy, entry_strike, entry_type,
                    entry_price, stop_loss, target, confidence, rationale
                FROM ai_trade_setups 
                WHERE index_name = %s 
                AND confidence >= %s
                AND bucket_ts BETWEEN %s AND %s
                ORDER BY bucket_ts ASC
            """
            
            cursor.execute(query, (index_name, confidence_min, start_time, end_time))
            results = cursor.fetchall()
            
            # Convert datetime objects to strings and Decimal to float for JSON serialization
            for result in results:
                if result.get('bucket_ts'):
                    result['bucket_ts'] = result['bucket_ts'].isoformat()
                # Convert Decimal objects to float
                for key, value in result.items():
                    if hasattr(value, '__float__'):
                        result[key] = float(value)
            
            connection.close()
            return results
            
        except Exception as e:
            self.logger.error(f"Error in _get_playback_data: {str(e)}")
            return []
    
    async def _get_backend_status(self) -> Dict:
        """Get backend system status"""
        try:
            connection = self.datastore.get_connection()
            if connection is None:
                return {"status": "error", "message": "Database connection failed"}
            
            cursor = connection.cursor(dictionary=True)
            
            # Get last snapshot timestamp
            cursor.execute("SELECT MAX(bucket_ts) as last_snapshot FROM options_raw_data")
            last_snapshot = cursor.fetchone()
            
            # Get last AI insight timestamp
            cursor.execute("SELECT MAX(bucket_ts) as last_ai_insight FROM ai_trade_setups")
            last_ai_insight = cursor.fetchone()
            
            # Get system info
            cursor.execute("SELECT COUNT(*) as total_records FROM options_raw_data")
            total_records = cursor.fetchone()
            
            # Check Angel One token validity (simplified)
            token_valid = True  # This would need actual token validation
            
            connection.close()
            
            status = {
                "status": "operational",
                "timestamp": datetime.now(self.ist_tz).isoformat(),
                "last_snapshot": last_snapshot['last_snapshot'].isoformat() if last_snapshot['last_snapshot'] else None,
                "last_ai_insight": last_ai_insight['last_ai_insight'].isoformat() if last_ai_insight['last_ai_insight'] else None,
                "total_records": total_records['total_records'] if total_records else 0,
                "token_valid": token_valid,
                "polling_interval": "3 minutes",
                "active_connections": len(self.active_connections)
            }
            
            return status
            
        except Exception as e:
            self.logger.error(f"Error in _get_backend_status: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    async def _get_daily_oi_summary(self, index_name: str, date: str) -> Dict:
        """Get daily OI quadrant summary"""
        try:
            connection = self.datastore.get_connection()
            if connection is None:
                return {}
            
            cursor = connection.cursor(dictionary=True)
            
            # Get quadrant counts for the day
            query = """
                SELECT 
                    oi_quadrant,
                    COUNT(*) as count,
                    AVG(confidence_score) as avg_confidence
                FROM historical_oi_tracking 
                WHERE index_name = %s 
                AND DATE(bucket_ts) = %s
                GROUP BY oi_quadrant
                ORDER BY count DESC
            """
            
            cursor.execute(query, (index_name, date))
            results = cursor.fetchall()
            
            connection.close()
            
            summary = {
                "date": date,
                "index_name": index_name,
                "quadrants": results,
                "total_strikes": sum(r['count'] for r in results)
            }
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error in _get_daily_oi_summary: {str(e)}")
            return {}
    
    async def _get_ai_confidence_summary(self, index_name: str, days: int) -> Dict:
        """Get AI confidence score histogram"""
        try:
            connection = self.datastore.get_connection()
            if connection is None:
                return {}
            
            cursor = connection.cursor(dictionary=True)
            
            # Get confidence distribution
            query = """
                SELECT 
                    CASE 
                        WHEN confidence >= 90 THEN '90-100'
                        WHEN confidence >= 80 THEN '80-89'
                        WHEN confidence >= 70 THEN '70-79'
                        WHEN confidence >= 60 THEN '60-69'
                        ELSE '0-59'
                    END as confidence_range,
                    COUNT(*) as count
                FROM ai_trade_setups 
                WHERE index_name = %s 
                AND bucket_ts >= DATE_SUB(NOW(), INTERVAL %s DAY)
                GROUP BY confidence_range
                ORDER BY confidence_range DESC
            """
            
            cursor.execute(query, (index_name, days))
            results = cursor.fetchall()
            
            connection.close()
            
            summary = {
                "index_name": index_name,
                "days": days,
                "confidence_distribution": results,
                "total_setups": sum(r['count'] for r in results)
            }
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error in _get_ai_confidence_summary: {str(e)}")
            return {}
    
    async def _get_active_strikes_summary(self, index_name: str, hours: int) -> Dict:
        """Get top active strikes by OI change"""
        try:
            connection = self.datastore.get_connection()
            if connection is None:
                return {}
            
            cursor = connection.cursor(dictionary=True)
            
            # Get top strikes by OI change
            query = """
                SELECT 
                    strike, trading_symbol,
                    ce_oi_change, pe_oi_change,
                    ce_oi_pct_change, pe_oi_pct_change,
                    oi_quadrant, confidence_score
                FROM historical_oi_tracking 
                WHERE index_name = %s 
                AND bucket_ts >= DATE_SUB(NOW(), INTERVAL %s HOUR)
                ORDER BY ABS(ce_oi_change) + ABS(pe_oi_change) DESC
                LIMIT 10
            """
            
            cursor.execute(query, (index_name, hours))
            results = cursor.fetchall()
            
            connection.close()
            
            summary = {
                "index_name": index_name,
                "hours": hours,
                "active_strikes": results
            }
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error in _get_active_strikes_summary: {str(e)}")
            return {}
    
    def run(self, host: str = "0.0.0.0", port: int = 8000):
        """Run the FastAPI server"""
        uvicorn.run(self.app, host=host, port=port)

# Global API instance
dashboard_api = DashboardAPI()

if __name__ == "__main__":
    dashboard_api.run() 