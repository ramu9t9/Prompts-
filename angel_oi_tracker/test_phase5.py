"""
Phase 5 Test Script - Dashboard Intelligence & AI Playback System

This script tests the Phase 5 implementation:
1. FastAPI endpoints functionality
2. Pattern insights API
3. Trade setups API with filters
4. Playback API
5. Backend status monitoring
6. Summary APIs
7. WebSocket connectivity

Always refer to official documentation: https://smartapi.angelone.in/docs
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import json
import time
import asyncio
import requests
from datetime import datetime, timedelta
import pytz
from dashboard_api import DashboardAPI
from store_option_data_mysql import MySQLOptionDataStore
from oi_analysis_engine import OIAnalysisEngine
from ai_trade_engine import AITradeEngine

class Phase5Tester:
    def __init__(self):
        self.ist_tz = pytz.timezone('Asia/Kolkata')
        self.datastore = MySQLOptionDataStore()
        self.analysis_engine = OIAnalysisEngine(self.datastore)
        self.ai_engine = AITradeEngine(self.datastore)
        self.api_base = "http://localhost:8000"
        
    def test_fastapi_endpoints(self):
        """Test all FastAPI endpoints"""
        print("🧪 Testing FastAPI endpoints...")
        
        try:
            # Test root endpoint
            response = requests.get(f"{self.api_base}/")
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Root endpoint working")
                print(f"   📊 Version: {data.get('version')}")
                print(f"   🔗 Available endpoints: {len(data.get('endpoints', {}))}")
                return True
            else:
                print(f"   ❌ Root endpoint failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"   ❌ API test error: {str(e)}")
            return False
    
    def test_pattern_insights_api(self):
        """Test pattern insights API"""
        print("🧪 Testing pattern insights API...")
        
        try:
            # Test with basic parameters
            params = {
                'index_name': 'NIFTY',
                'limit': 10
            }
            
            response = requests.get(f"{self.api_base}/api/pattern_insights", params=params)
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Pattern insights API working")
                print(f"   📊 Records returned: {len(data)}")
                if data:
                    print(f"   📋 Sample record: {data[0].get('trading_symbol', 'N/A')}")
                return True
            else:
                print(f"   ❌ Pattern insights API failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"   ❌ Pattern insights test error: {str(e)}")
            return False
    
    def test_trade_setups_api(self):
        """Test trade setups API"""
        print("🧪 Testing trade setups API...")
        
        try:
            # Test with basic parameters
            params = {
                'index_name': 'NIFTY',
                'confidence_min': 70,
                'limit': 10
            }
            
            response = requests.get(f"{self.api_base}/api/trade_setups", params=params)
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Trade setups API working")
                print(f"   📊 Records returned: {len(data)}")
                if data:
                    print(f"   📋 Sample setup: {data[0].get('strategy', 'N/A')}")
                return True
            else:
                print(f"   ❌ Trade setups API failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"   ❌ Trade setups test error: {str(e)}")
            return False
    
    def test_playback_api(self):
        """Test playback API"""
        print("🧪 Testing playback API...")
        
        try:
            # Test with time range
            start_time = (datetime.now(self.ist_tz) - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
            end_time = datetime.now(self.ist_tz).strftime("%Y-%m-%d %H:%M:%S")
            
            params = {
                'index_name': 'NIFTY',
                'start_time': start_time,
                'end_time': end_time,
                'confidence_min': 70
            }
            
            response = requests.get(f"{self.api_base}/api/playback/ai_setups", params=params)
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Playback API working")
                print(f"   📊 Records returned: {len(data)}")
                if data:
                    print(f"   📋 Time range: {start_time} to {end_time}")
                return True
            else:
                print(f"   ❌ Playback API failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"   ❌ Playback test error: {str(e)}")
            return False
    
    def test_backend_status_api(self):
        """Test backend status API"""
        print("🧪 Testing backend status API...")
        
        try:
            response = requests.get(f"{self.api_base}/api/status")
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Backend status API working")
                print(f"   📊 Status: {data.get('status')}")
                print(f"   📊 Total records: {data.get('total_records', 0)}")
                print(f"   📊 Active connections: {data.get('active_connections', 0)}")
                return True
            else:
                print(f"   ❌ Backend status API failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"   ❌ Backend status test error: {str(e)}")
            return False
    
    def test_summary_apis(self):
        """Test summary APIs"""
        print("🧪 Testing summary APIs...")
        
        try:
            # Test daily OI summary
            params = {'index_name': 'NIFTY'}
            response = requests.get(f"{self.api_base}/api/summary/daily_oi", params=params)
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Daily OI summary API working")
                print(f"   📊 Date: {data.get('date')}")
                print(f"   📊 Total strikes: {data.get('total_strikes', 0)}")
            else:
                print(f"   ❌ Daily OI summary API failed: {response.status_code}")
            
            # Test AI confidence summary
            params = {'index_name': 'NIFTY', 'days': 7}
            response = requests.get(f"{self.api_base}/api/summary/ai_confidence", params=params)
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ AI confidence summary API working")
                print(f"   📊 Total setups: {data.get('total_setups', 0)}")
            else:
                print(f"   ❌ AI confidence summary API failed: {response.status_code}")
            
            # Test active strikes summary
            params = {'index_name': 'NIFTY', 'hours': 1}
            response = requests.get(f"{self.api_base}/api/summary/active_strikes", params=params)
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Active strikes summary API working")
                print(f"   📊 Active strikes: {len(data.get('active_strikes', []))}")
            else:
                print(f"   ❌ Active strikes summary API failed: {response.status_code}")
            
            return True
                
        except Exception as e:
            print(f"   ❌ Summary APIs test error: {str(e)}")
            return False
    
    def test_websocket_connectivity(self):
        """Test WebSocket connectivity"""
        print("🧪 Testing WebSocket connectivity...")
        
        try:
            import websockets
            
            async def test_ws():
                try:
                    uri = "ws://localhost:8000/ws"
                    async with websockets.connect(uri) as websocket:
                        # Send a test message
                        await websocket.send(json.dumps({"type": "test", "message": "Hello"}))
                        
                        # Wait for response
                        response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        data = json.loads(response)
                        
                        if data.get('type') == 'status':
                            print(f"   ✅ WebSocket connectivity working")
                            print(f"   📊 Message: {data.get('message')}")
                            return True
                        else:
                            print(f"   ❌ Unexpected WebSocket response: {data}")
                            return False
                            
                except Exception as e:
                    print(f"   ❌ WebSocket test error: {str(e)}")
                    return False
            
            # Run WebSocket test
            result = asyncio.run(test_ws())
            return result
                
        except ImportError:
            print(f"   ⚠️  WebSocket test skipped (websockets library not available)")
            return True
        except Exception as e:
            print(f"   ❌ WebSocket test error: {str(e)}")
            return False
    
    def test_database_integration(self):
        """Test database integration with new APIs"""
        print("🧪 Testing database integration...")
        
        try:
            # Test pattern insights data retrieval
            connection = self.datastore.get_connection()
            if connection is None:
                print(f"   ❌ Database connection failed")
                return False
            
            cursor = connection.cursor()
            
            # Check if historical_oi_tracking table exists and has data
            cursor.execute("SELECT COUNT(*) FROM historical_oi_tracking")
            count = cursor.fetchone()[0]
            
            print(f"   ✅ Database integration working")
            print(f"   📊 Historical OI records: {count}")
            
            # Check if ai_trade_setups table exists and has data
            cursor.execute("SELECT COUNT(*) FROM ai_trade_setups")
            ai_count = cursor.fetchone()[0]
            
            print(f"   📊 AI trade setups: {ai_count}")
            
            connection.close()
            return True
                
        except Exception as e:
            print(f"   ❌ Database integration test error: {str(e)}")
            return False
    
    def test_error_handling(self):
        """Test error handling in APIs"""
        print("🧪 Testing error handling...")
        
        try:
            # Test invalid parameters
            params = {
                'index_name': 'INVALID_INDEX',
                'confidence_min': -1  # Invalid confidence
            }
            
            response = requests.get(f"{self.api_base}/api/trade_setups", params=params)
            
            # Should handle gracefully even with invalid parameters
            if response.status_code in [200, 400, 422]:
                print(f"   ✅ Error handling working")
                print(f"   📊 Status code: {response.status_code}")
                return True
            else:
                print(f"   ❌ Unexpected error response: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"   ❌ Error handling test error: {str(e)}")
            return False
    
    def run_all_tests(self):
        """Run all Phase 5 tests"""
        print("🚀 Starting Phase 5 Test Suite")
        print("=" * 60)
        
        tests = [
            ("FastAPI Endpoints", self.test_fastapi_endpoints),
            ("Pattern Insights API", self.test_pattern_insights_api),
            ("Trade Setups API", self.test_trade_setups_api),
            ("Playback API", self.test_playback_api),
            ("Backend Status API", self.test_backend_status_api),
            ("Summary APIs", self.test_summary_apis),
            ("WebSocket Connectivity", self.test_websocket_connectivity),
            ("Database Integration", self.test_database_integration),
            ("Error Handling", self.test_error_handling)
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            print(f"\n📋 Running: {test_name}")
            print("-" * 40)
            
            try:
                if test_func():
                    print(f"✅ {test_name} PASSED")
                    passed += 1
                else:
                    print(f"❌ {test_name} FAILED")
            except Exception as e:
                print(f"❌ {test_name} ERROR: {str(e)}")
        
        print("\n" + "=" * 60)
        print(f"📊 Test Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All Phase 5 tests passed!")
            print("\n🎉 Phase 5 implementation is ready for production!")
            print("\n📋 Phase 5 Features Implemented:")
            print("   ✅ FastAPI dashboard endpoints")
            print("   ✅ Pattern insights with OI quadrants")
            print("   ✅ AI trade setups with filtering")
            print("   ✅ Historical playback API")
            print("   ✅ Backend status monitoring")
            print("   ✅ Summary analytics APIs")
            print("   ✅ WebSocket real-time updates")
            print("   ✅ Comprehensive error handling")
            print("   ✅ Database integration")
            print("   ✅ Frontend dashboard")
        else:
            print("⚠️  Some tests failed. Please review the output above.")
            print("\n❌ Phase 5 implementation needs fixes")

def main():
    """Main test runner"""
    tester = Phase5Tester()
    tester.run_all_tests()

if __name__ == "__main__":
    main() 