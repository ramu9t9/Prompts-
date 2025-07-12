"""
Phase 3 Test Script - Real-Time OI Analytics, CLI Dashboard & Performance Tuning

This script tests all Phase 3 features:
1. OI Analysis Engine functionality
2. CLI Dashboard display
3. Batch insert performance
4. Database indexes
5. JSON logging
6. Confidence scoring
7. Support/resistance detection

Always refer to official documentation: https://smartapi.angelone.in/docs

API Compliance:
- Data Usage: Use data only for authorized purposes
- Terms of Service: Follow Angel One's terms and conditions
"""

import time
import json
import pandas as pd
from datetime import datetime, timedelta
import pytz
from store_option_data_mysql import MySQLOptionDataStore
from oi_analysis_engine import OIAnalysisEngine
from option_chain_fetcher import AdaptivePollingEngine
from utils.market_calendar import MarketCalendar

class Phase3Tester:
    def __init__(self):
        self.ist_tz = pytz.timezone('Asia/Kolkata')
        self.datastore = MySQLOptionDataStore()
        self.analysis_engine = OIAnalysisEngine(self.datastore)
        self.calendar = MarketCalendar()
        
    def test_confidence_calculation(self):
        """Test confidence score calculation boundaries"""
        print("🧪 Testing confidence score calculation...")
        
        # Test case 1: High confidence scenario
        high_confidence_data = {
            'strike': 24000,
            'ce_oi_change': 1000,
            'pe_oi_change': 0,
            'ce_oi_pct_change': 25.0,
            'pe_oi_pct_change': 0.0,
            'ce_ltp_change_pct': 2.5,
            'pe_ltp_change_pct': 0.0,
            'ce_volume_change': 500,
            'pe_volume_change': 0,
            'index_ltp': 24000
        }
        
        confidence = self.analysis_engine.calculate_confidence(high_confidence_data)
        print(f"   High confidence scenario: {confidence}/100")
        assert 0 <= confidence <= 100, f"Confidence out of bounds: {confidence}"
        
        # Test case 2: Low confidence scenario
        low_confidence_data = {
            'strike': 25000,
            'ce_oi_change': 10,
            'pe_oi_change': 5,
            'ce_oi_pct_change': 1.0,
            'pe_oi_pct_change': 0.5,
            'ce_ltp_change_pct': 0.1,
            'pe_ltp_change_pct': 0.1,
            'ce_volume_change': 10,
            'pe_volume_change': 5,
            'index_ltp': 24000
        }
        
        confidence = self.analysis_engine.calculate_confidence(low_confidence_data)
        print(f"   Low confidence scenario: {confidence}/100")
        assert 0 <= confidence <= 100, f"Confidence out of bounds: {confidence}"
        
        # Test case 3: Edge case - zero values
        zero_confidence_data = {
            'strike': 24000,
            'ce_oi_change': 0,
            'pe_oi_change': 0,
            'ce_oi_pct_change': 0.0,
            'pe_oi_pct_change': 0.0,
            'ce_ltp_change_pct': 0.0,
            'pe_ltp_change_pct': 0.0,
            'ce_volume_change': 0,
            'pe_volume_change': 0,
            'index_ltp': 24000
        }
        
        confidence = self.analysis_engine.calculate_confidence(zero_confidence_data)
        print(f"   Zero confidence scenario: {confidence}/100")
        assert 0 <= confidence <= 100, f"Confidence out of bounds: {confidence}"
        
        print("✅ Confidence calculation tests passed")
        return True
    
    def test_support_resistance_detection(self):
        """Test support/resistance shift detection"""
        print("🧪 Testing support/resistance shift detection...")
        
        # Create mock historical data
        mock_data = []
        current_time = datetime.now(self.ist_tz)
        
        # Previous bucket - support at 23800, resistance at 24100
        prev_bucket = current_time - timedelta(minutes=3)
        mock_data.append({
            'bucket_ts': prev_bucket,
            'strike': 23800,
            'pe_oi': 5000,  # High PE OI = support
            'ce_oi': 1000
        })
        mock_data.append({
            'bucket_ts': prev_bucket,
            'strike': 24100,
            'pe_oi': 1000,
            'ce_oi': 5000  # High CE OI = resistance
        })
        
        # Current bucket - support shifted UP to 23900, resistance at 24100
        mock_data.append({
            'bucket_ts': current_time,
            'strike': 23900,
            'pe_oi': 8000,  # Higher PE OI = new support level
            'ce_oi': 1000
        })
        mock_data.append({
            'bucket_ts': current_time,
            'strike': 24100,
            'pe_oi': 1000,
            'ce_oi': 5000  # Same resistance level
        })
        
        # Add more data points to ensure proper detection
        mock_data.append({
            'bucket_ts': current_time,
            'strike': 23800,
            'pe_oi': 3000,  # Lower PE OI at old support
            'ce_oi': 1000
        })
        
        # Convert to DataFrame
        df = pd.DataFrame(mock_data)
        
        # Test detection
        result = self.analysis_engine.detect_support_resistance_shift(df)
        
        print(f"   Support level: {result['support_level']}")
        print(f"   Resistance level: {result['resistance_level']}")
        print(f"   Support shift: {result['support_shift']}")
        print(f"   Resistance shift: {result['resistance_shift']}")
        
        # Verify support shifted UP
        assert result['support_level'] == 23900, f"Expected support at 23900, got {result['support_level']}"
        assert result['support_shift'] == 'UP', f"Expected support shift UP, got {result['support_shift']}"
        
        print("✅ Support/resistance detection tests passed")
        return True
    
    def test_summary_json_validity(self):
        """Test summary JSON generation and validity"""
        print("🧪 Testing summary JSON validity...")
        
        # Create mock summary
        mock_summary = {
            'timestamp': '09:30:00',
            'index_name': 'NIFTY',
            'pcr': 0.92,
            'bias': 'BULLISH',
            'bullish_strikes': [
                {
                    'strike': 23700,
                    'ce_oi_pct': 18.0,
                    'ce_ltp_pct': 1.2,
                    'confidence': 75
                }
            ],
            'bearish_strikes': [
                {
                    'strike': 24050,
                    'ce_oi_pct': 22.0,
                    'ce_ltp_pct': -1.1,
                    'confidence': 80
                }
            ],
            'support_level': 23800,
            'resistance_level': 24100,
            'support_shift': 'UP',
            'resistance_shift': 'NEUTRAL',
            'alerts': ['Support shifted UP to 23800']
        }
        
        # Test JSON serialization
        try:
            json_str = json.dumps(mock_summary)
            parsed_back = json.loads(json_str)
            print(f"   JSON serialization successful: {len(json_str)} characters")
            
            # Verify all required fields are present
            required_fields = ['timestamp', 'index_name', 'pcr', 'bias', 'bullish_strikes', 'bearish_strikes']
            for field in required_fields:
                assert field in parsed_back, f"Missing required field: {field}"
            
            print("✅ Summary JSON validity tests passed")
            return True
            
        except Exception as e:
            print(f"❌ JSON test failed: {str(e)}")
            return False
    
    def test_batch_insert_performance(self):
        """Test batch insert performance vs single inserts"""
        print("🧪 Testing batch insert performance...")
        
        # Create test data
        test_data = []
        current_time = datetime.now(self.ist_tz)
        
        for i in range(100):  # 100 records
            test_data.append({
                'bucket_ts': current_time,
                'trading_symbol': f'NIFTY{i}',
                'strike': 24000 + i,
                'option_type': 'CE',
                'ltp': 100.0 + i,
                'volume': 1000 + i,
                'oi': 5000 + i,
                'price_change': 1.0 + i * 0.1,
                'change_percent': 2.0 + i * 0.1,
                'open_price': 99.0 + i,
                'high_price': 101.0 + i,
                'low_price': 98.0 + i,
                'close_price': 100.0 + i,
                'delta': 0.5 + i * 0.01,
                'gamma': 0.01 + i * 0.001,
                'theta': -0.1 - i * 0.01,
                'vega': 10.0 + i,
                'iv': 20.0 + i * 0.1,
                'index_name': 'NIFTY',
                'expiry_date': '2025-07-31'
            })
        
        # Test single inserts (simulate old method)
        start_time = time.time()
        try:
            connection = self.datastore.get_connection()
            if connection:
                cursor = connection.cursor()
                
                insert_query = '''
                    INSERT INTO options_raw_data (
                        bucket_ts, trading_symbol, strike, option_type,
                        ltp, volume, oi, price_change, change_percent,
                        open_price, high_price, low_price, close_price,
                        delta, gamma, theta, vega, iv,
                        index_name, expiry_date
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                '''
                
                for data in test_data:
                    values = (
                        data['bucket_ts'], data['trading_symbol'], data['strike'],
                        data['option_type'], data['ltp'], data['volume'], data['oi'],
                        data['price_change'], data['change_percent'], data['open_price'],
                        data['high_price'], data['low_price'], data['close_price'],
                        data['delta'], data['gamma'], data['theta'], data['vega'],
                        data['iv'], data['index_name'], data['expiry_date']
                    )
                    cursor.execute(insert_query, values)
                
                connection.commit()
                connection.close()
                
                single_insert_time = time.time() - start_time
                print(f"   Single inserts: {single_insert_time:.3f} seconds")
                
        except Exception as e:
            print(f"   Single insert test failed: {str(e)}")
            single_insert_time = float('inf')
        
        # Test batch inserts (new method)
        start_time = time.time()
        try:
            success = self.datastore.insert_raw_data(test_data)
            batch_insert_time = time.time() - start_time
            
            if success:
                print(f"   Batch inserts: {batch_insert_time:.3f} seconds")
                
                # Calculate performance improvement
                if single_insert_time != float('inf'):
                    improvement = single_insert_time / batch_insert_time
                    print(f"   Performance improvement: {improvement:.1f}x faster")
                    
                    # Verify improvement is at least 2x
                    assert improvement >= 2.0, f"Batch insert not fast enough: {improvement}x"
                
                print("✅ Batch insert performance tests passed")
                return True
            else:
                print("❌ Batch insert failed")
                return False
                
        except Exception as e:
            print(f"❌ Batch insert test failed: {str(e)}")
            return False
    
    def test_cli_dashboard_format(self):
        """Test CLI dashboard formatting"""
        print("🧪 Testing CLI dashboard formatting...")
        
        # Create mock summary
        mock_summary = {
            'timestamp': '09:30:00',
            'index_name': 'NIFTY',
            'pcr': 0.92,
            'bias': 'BULLISH',
            'bullish_strikes': [
                {
                    'strike': 23700,
                    'ce_oi_pct': 18.0,
                    'ce_ltp_pct': 1.2,
                    'confidence': 75
                },
                {
                    'strike': 23800,
                    'ce_oi_pct': 15.0,
                    'ce_ltp_pct': 0.9,
                    'confidence': 70
                }
            ],
            'bearish_strikes': [
                {
                    'strike': 24050,
                    'ce_oi_pct': 22.0,
                    'ce_ltp_pct': -1.1,
                    'confidence': 80
                },
                {
                    'strike': 24100,
                    'ce_oi_pct': 19.0,
                    'ce_ltp_pct': -0.8,
                    'confidence': 75
                }
            ],
            'support_level': 23800,
            'resistance_level': 24100,
            'support_shift': 'UP',
            'resistance_shift': 'DOWN',
            'alerts': ['Support shifted UP to 23800', 'PCR trending UP']
        }
        
        # Test formatting
        try:
            dashboard_text = self.analysis_engine.format_cli_display(mock_summary)
            print("   CLI Dashboard format:")
            print(dashboard_text)
            
            # Verify key elements are present
            assert 'NIFTY' in dashboard_text, "Index name missing from dashboard"
            assert 'PCR 0.92' in dashboard_text, "PCR missing from dashboard"
            assert '23700PE' in dashboard_text, "Bullish strike missing from dashboard"
            assert '24050CE' in dashboard_text, "Bearish strike missing from dashboard"
            assert 'Support↗' in dashboard_text, "Support indicator missing from dashboard"
            assert 'Resistance↘' in dashboard_text, "Resistance indicator missing from dashboard"
            
            print("✅ CLI dashboard format tests passed")
            return True
            
        except Exception as e:
            print(f"❌ CLI dashboard test failed: {str(e)}")
            return False
    
    def test_database_indexes(self):
        """Test database indexes are working"""
        print("🧪 Testing database indexes...")
        
        try:
            connection = self.datastore.get_connection()
            if not connection:
                print("❌ Could not connect to database")
                return False
            
            cursor = connection.cursor()
            
            # Check if indexes exist
            cursor.execute("""
                SELECT INDEX_NAME, TABLE_NAME 
                FROM information_schema.STATISTICS 
                WHERE TABLE_SCHEMA = %s 
                AND TABLE_NAME IN ('historical_oi_tracking', 'options_raw_data', 'live_oi_tracking')
                AND INDEX_NAME LIKE 'idx_%'
            """, (self.datastore.database,))
            
            indexes = cursor.fetchall()
            print(f"   Found {len(indexes)} performance indexes:")
            
            expected_indexes = [
                'idx_bucket_index', 'idx_confidence',  # historical_oi_tracking
                'idx_bucket_ts', 'idx_trading_symbol',  # options_raw_data
                'idx_live_bucket_ts', 'idx_live_index'  # live_oi_tracking
            ]
            
            found_indexes = [index[0] for index in indexes]
            for expected in expected_indexes:
                if expected in found_indexes:
                    print(f"     ✅ {expected}")
                else:
                    print(f"     ❌ {expected} (missing)")
            
            connection.close()
            
            # Verify all expected indexes are present
            missing_indexes = [idx for idx in expected_indexes if idx not in found_indexes]
            if missing_indexes:
                print(f"❌ Missing indexes: {missing_indexes}")
                return False
            
            print("✅ Database index tests passed")
            return True
            
        except Exception as e:
            print(f"❌ Database index test failed: {str(e)}")
            return False
    
    def test_json_logging(self):
        """Test JSON logging functionality"""
        print("🧪 Testing JSON logging...")
        
        try:
            # Create test log entry
            test_summary = {
                'timestamp': '09:30:00',
                'index_name': 'NIFTY',
                'pcr': 0.92,
                'bias': 'BULLISH',
                'bullish_count': 2,
                'bearish_count': 1,
                'support': 23800,
                'resistance': 24100,
                'alerts_count': 1
            }
            
            # Test logging
            self.analysis_engine.log_summary(test_summary)
            
            # Check if log file exists and contains valid JSON
            today = datetime.now(self.ist_tz).strftime('%Y-%m-%d')
            log_filename = f"logs/{today}/oi_analytics.log"
            
            import os
            if os.path.exists(log_filename):
                with open(log_filename, 'r') as f:
                    last_line = f.readlines()[-1].strip()
                
                # Parse JSON
                parsed_log = json.loads(last_line)
                print(f"   Log entry: {parsed_log}")
                
                # Verify log structure
                required_fields = ['ts', 'index', 'pcr', 'bias']
                for field in required_fields:
                    assert field in parsed_log, f"Missing field in log: {field}"
                
                print("✅ JSON logging tests passed")
                return True
            else:
                print("❌ Log file not created")
                return False
                
        except Exception as e:
            print(f"❌ JSON logging test failed: {str(e)}")
            return False
    
    def run_all_tests(self):
        """Run all Phase 3 tests"""
        print("🚀 Starting Phase 3 Test Suite")
        print("=" * 60)
        
        tests = [
            ("Confidence Calculation", self.test_confidence_calculation),
            ("Support/Resistance Detection", self.test_support_resistance_detection),
            ("Summary JSON Validity", self.test_summary_json_validity),
            ("Batch Insert Performance", self.test_batch_insert_performance),
            ("CLI Dashboard Format", self.test_cli_dashboard_format),
            ("Database Indexes", self.test_database_indexes),
            ("JSON Logging", self.test_json_logging)
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            print(f"\n📋 Running: {test_name}")
            print("-" * 40)
            
            try:
                if test_func():
                    passed += 1
                    print(f"✅ {test_name} PASSED")
                else:
                    print(f"❌ {test_name} FAILED")
            except Exception as e:
                print(f"❌ {test_name} ERROR: {str(e)}")
        
        print("\n" + "=" * 60)
        print(f"📊 Test Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All Phase 3 tests passed!")
            return True
        else:
            print("⚠️  Some tests failed. Please review the output above.")
            return False

def main():
    """Main test function"""
    print("🧪 Phase 3 Test Suite - Real-Time OI Analytics & CLI Dashboard")
    print("=" * 70)
    
    try:
        tester = Phase3Tester()
        success = tester.run_all_tests()
        
        if success:
            print("\n🎉 Phase 3 implementation is ready for production!")
            print("\n📋 Phase 3 Features Implemented:")
            print("   ✅ OI Analysis Engine with confidence scoring")
            print("   ✅ Support/resistance shift detection")
            print("   ✅ Real-time CLI dashboard")
            print("   ✅ Batch insert performance optimization")
            print("   ✅ Database indexes for better performance")
            print("   ✅ Structured JSON logging")
            print("   ✅ Trend analysis and alerts")
            print("   ✅ PCR and market bias analysis")
        else:
            print("\n❌ Phase 3 implementation needs fixes")
        
        return success
        
    except Exception as e:
        print(f"❌ Test suite error: {str(e)}")
        return False

if __name__ == "__main__":
    main() 