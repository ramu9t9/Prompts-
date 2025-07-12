"""
Market Direction Analysis using OI Tracker v3

This script demonstrates all features and how to use them for market direction prediction.
Features include:
1. OI Change Analysis
2. Put-Call Ratio (PCR) Analysis
3. Strike-wise OI Distribution
4. CE vs PE Ratio Trends
5. Historical OI Patterns

Always refer to official documentation: https://smartapi.angelone.in/docs
"""

from datetime import datetime, timedelta
import pytz
from option_chain_fetcher import OIAnalysis
from store_option_data_mysql import MySQLOptionDataStore

class MarketDirectionAnalyzer:
    def __init__(self):
        self.ist_tz = pytz.timezone('Asia/Kolkata')
        self.analyzer = OIAnalysis()
        self.store = MySQLOptionDataStore()
    
    def analyze_market_direction(self, index_name='NIFTY', hours_back=24):
        """Comprehensive market direction analysis"""
        print(f"🎯 Market Direction Analysis for {index_name}")
        print("=" * 60)
        
        # Get OI summary
        summary = self.analyzer.get_oi_summary(index_name, hours_back)
        if not summary:
            print(f"❌ No data available for {index_name}")
            return None
        
        # Print basic summary
        self.analyzer.print_oi_summary(index_name, hours_back)
        
        # Analyze market direction indicators
        direction_signals = self._get_direction_signals(summary)
        
        print(f"\n📊 Market Direction Signals:")
        print("-" * 40)
        for signal, value in direction_signals.items():
            print(f"{signal}: {value}")
        
        # Get overall direction
        overall_direction = self._get_overall_direction(direction_signals)
        print(f"\n🎯 Overall Market Direction: {overall_direction}")
        
        return {
            'summary': summary,
            'signals': direction_signals,
            'direction': overall_direction
        }
    
    def _get_direction_signals(self, summary):
        """Extract market direction signals from OI summary"""
        signals = {}
        
        # 1. Put-Call Ratio (PCR) Analysis
        pcr = summary['pcr']
        if pcr > 1.2:
            signals['PCR Signal'] = f"BULLISH (PCR: {pcr:.2f} > 1.2)"
        elif pcr < 0.8:
            signals['PCR Signal'] = f"BEARISH (PCR: {pcr:.2f} < 0.8)"
        else:
            signals['PCR Signal'] = f"NEUTRAL (PCR: {pcr:.2f})"
        
        # 2. CE vs PE OI Distribution
        total_ce_oi = summary['total_ce_oi']
        total_pe_oi = summary['total_pe_oi']
        
        if total_ce_oi > total_pe_oi * 1.5:
            signals['CE/PE Distribution'] = f"BEARISH (CE OI {total_ce_oi:,} >> PE OI {total_pe_oi:,})"
        elif total_pe_oi > total_ce_oi * 1.5:
            signals['CE/PE Distribution'] = f"BULLISH (PE OI {total_pe_oi:,} >> CE OI {total_ce_oi:,})"
        else:
            signals['CE/PE Distribution'] = f"NEUTRAL (CE: {total_ce_oi:,}, PE: {total_pe_oi:,})"
        
        # 3. ATM Strike Analysis
        atm_analysis = self._analyze_atm_strikes(summary)
        signals['ATM Strike Analysis'] = atm_analysis
        
        # 4. OI Concentration Analysis
        concentration = self._analyze_oi_concentration(summary)
        signals['OI Concentration'] = concentration
        
        return signals
    
    def _analyze_atm_strikes(self, summary):
        """Analyze OI around ATM strikes"""
        strikes = summary['strikes']
        if not strikes:
            return "No strike data available"
        
        # Find ATM strikes (around current market level)
        atm_strikes = []
        for strike in strikes:
            strike_data = strikes[strike]
            ce_oi = strike_data['ce_oi']
            pe_oi = strike_data['pe_oi']
            
            # If significant OI exists at this strike
            if ce_oi > 100000 or pe_oi > 100000:
                atm_strikes.append({
                    'strike': strike,
                    'ce_oi': ce_oi,
                    'pe_oi': pe_oi
                })
        
        if not atm_strikes:
            return "No significant ATM OI"
        
        # Analyze ATM OI distribution
        total_ce_atm = sum(s['ce_oi'] for s in atm_strikes)
        total_pe_atm = sum(s['pe_oi'] for s in atm_strikes)
        
        if total_pe_atm > total_ce_atm * 1.3:
            return f"BULLISH ATM (PE: {total_pe_atm:,} > CE: {total_ce_atm:,})"
        elif total_ce_atm > total_pe_atm * 1.3:
            return f"BEARISH ATM (CE: {total_ce_atm:,} > PE: {total_pe_atm:,})"
        else:
            return f"NEUTRAL ATM (CE: {total_ce_atm:,}, PE: {total_pe_atm:,})"
    
    def _analyze_oi_concentration(self, summary):
        """Analyze OI concentration across strikes"""
        strikes = summary['strikes']
        if not strikes:
            return "No strike data available"
        
        # Find strikes with highest OI
        high_oi_strikes = []
        for strike in strikes:
            strike_data = strikes[strike]
            total_oi = strike_data['ce_oi'] + strike_data['pe_oi']
            if total_oi > 1000000:  # 1M+ OI
                high_oi_strikes.append({
                    'strike': strike,
                    'total_oi': total_oi,
                    'ce_oi': strike_data['ce_oi'],
                    'pe_oi': strike_data['pe_oi']
                })
        
        if not high_oi_strikes:
            return "No high OI concentration"
        
        # Sort by total OI
        high_oi_strikes.sort(key=lambda x: x['total_oi'], reverse=True)
        
        # Analyze top 3 strikes
        top_strikes = high_oi_strikes[:3]
        total_ce_top = sum(s['ce_oi'] for s in top_strikes)
        total_pe_top = sum(s['pe_oi'] for s in top_strikes)
        
        if total_pe_top > total_ce_top * 1.5:
            return f"BULLISH Concentration (Top strikes PE-heavy: {total_pe_top:,} vs {total_ce_top:,})"
        elif total_ce_top > total_pe_top * 1.5:
            return f"BEARISH Concentration (Top strikes CE-heavy: {total_ce_top:,} vs {total_pe_top:,})"
        else:
            return f"NEUTRAL Concentration (Top strikes balanced: CE {total_ce_top:,}, PE {total_pe_top:,})"
    
    def _get_overall_direction(self, signals):
        """Determine overall market direction from signals"""
        bullish_count = 0
        bearish_count = 0
        
        for signal, value in signals.items():
            if 'BULLISH' in value:
                bullish_count += 1
            elif 'BEARISH' in value:
                bearish_count += 1
        
        if bullish_count > bearish_count:
            return "🟢 BULLISH"
        elif bearish_count > bullish_count:
            return "🔴 BEARISH"
        else:
            return "🟡 NEUTRAL"
    
    def analyze_oi_changes(self, trading_symbol, hours_back=6):
        """Analyze OI changes for a specific trading symbol"""
        print(f"\n📈 OI Changes Analysis for {trading_symbol}")
        print("-" * 50)
        
        end_time = datetime.now(self.ist_tz)
        start_time = end_time - timedelta(hours=hours_back)
        
        changes = self.analyzer.get_oi_changes(trading_symbol, start_time, end_time)
        if not changes:
            print(f"❌ No OI changes data for {trading_symbol}")
            return None
        
        print(f"📊 Analyzing {len(changes)} OI changes over {hours_back} hours")
        
        # Calculate cumulative changes
        total_ce_change = sum(c['ce_oi_change'] for c in changes)
        total_pe_change = sum(c['pe_oi_change'] for c in changes)
        
        print(f"📈 Total CE OI Change: {total_ce_change:+,}")
        print(f"📉 Total PE OI Change: {total_pe_change:+,}")
        
        # Determine trend
        if total_pe_change > total_ce_change * 1.2:
            trend = "🟢 BULLISH (PE OI building up)"
        elif total_ce_change > total_pe_change * 1.2:
            trend = "🔴 BEARISH (CE OI building up)"
        else:
            trend = "🟡 NEUTRAL (Balanced OI changes)"
        
        print(f"🎯 Trend: {trend}")
        
        # Show recent changes
        print(f"\n📋 Recent OI Changes:")
        print("-" * 30)
        for i, change in enumerate(changes[-5:], 1):  # Last 5 changes
            print(f"{i}. {change['timestamp'].strftime('%H:%M')} - "
                  f"CE: {change['ce_oi_change']:+,} ({change['ce_oi_pct_change']:+.1f}%), "
                  f"PE: {change['pe_oi_change']:+,} ({change['pe_oi_pct_change']:+.1f}%)")
        
        return {
            'changes': changes,
            'total_ce_change': total_ce_change,
            'total_pe_change': total_pe_change,
            'trend': trend
        }
    
    def get_strike_analysis(self, index_name, hours_back=24):
        """Get detailed strike-wise analysis"""
        print(f"\n🎯 Strike-wise Analysis for {index_name}")
        print("-" * 50)
        
        end_time = datetime.now(self.ist_tz)
        start_time = end_time - timedelta(hours=hours_back)
        
        analysis = self.analyzer.get_strike_analysis(index_name, start_time, end_time)
        if not analysis:
            print(f"❌ No strike analysis data for {index_name}")
            return None
        
        print(f"📊 Analyzing {len(analysis)} strikes over {hours_back} hours")
        
        # Find strikes with highest OI
        high_oi_strikes = []
        for strike, data in analysis.items():
            total_oi = data['ce']['avg_oi'] + data['pe']['avg_oi']
            if total_oi > 500000:  # 500K+ average OI
                high_oi_strikes.append({
                    'strike': strike,
                    'total_oi': total_oi,
                    'ce_avg': data['ce']['avg_oi'],
                    'pe_avg': data['pe']['avg_oi'],
                    'data_points': data['data_points']
                })
        
        if high_oi_strikes:
            high_oi_strikes.sort(key=lambda x: x['total_oi'], reverse=True)
            print(f"\n🏆 Top High OI Strikes:")
            print("-" * 30)
            for i, strike_data in enumerate(high_oi_strikes[:5], 1):
                print(f"{i}. Strike {strike_data['strike']}: "
                      f"Total OI: {strike_data['total_oi']:,} "
                      f"(CE: {strike_data['ce_avg']:,}, PE: {strike_data['pe_avg']:,})")
        
        return analysis
    
    def run_complete_analysis(self, index_name='NIFTY'):
        """Run complete market analysis"""
        print("🚀 Complete Market Analysis")
        print("=" * 60)
        
        # 1. Market Direction Analysis
        direction_result = self.analyze_market_direction(index_name, 24)
        
        # 2. Strike Analysis
        strike_result = self.get_strike_analysis(index_name, 24)
        
        # 3. OI Changes for top strikes
        if direction_result and direction_result['summary']['strikes']:
            top_strikes = list(direction_result['summary']['strikes'].keys())[:3]
            for strike in top_strikes:
                symbol = f"{index_name}{strike}"
                self.analyze_oi_changes(symbol, 6)
        
        print(f"\n✅ Complete analysis finished!")
        return {
            'direction': direction_result,
            'strikes': strike_result
        }

def main():
    """Main function for testing market analysis"""
    analyzer = MarketDirectionAnalyzer()
    
    # Run complete analysis
    result = analyzer.run_complete_analysis('NIFTY')
    
    print(f"\n📋 Analysis Summary:")
    print("-" * 30)
    if result['direction']:
        print(f"Market Direction: {result['direction']['direction']}")
        print(f"PCR: {result['direction']['summary']['pcr']:.2f}")
        print(f"Total CE OI: {result['direction']['summary']['total_ce_oi']:,}")
        print(f"Total PE OI: {result['direction']['summary']['total_pe_oi']:,}")

if __name__ == "__main__":
    main() 