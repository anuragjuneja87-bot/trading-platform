"""
Backtesting System
Feeds synthetic data into your analyzer and evaluates signals
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from typing import Dict, List, Optional
import os

class SyntheticDataBacktester:
    def __init__(self, data_dir: str = 'synthetic_data_pltr'):
        """
        Initialize backtester with synthetic data
        
        Args:
            data_dir: Directory containing synthetic data files
        """
        self.data_dir = data_dir
        self.load_data()
        
    def load_data(self):
        """Load all synthetic data files"""
        print("📂 Loading synthetic data...")
        
        self.daily_ohlcv = pd.read_csv(f'{self.data_dir}/daily_ohlcv.csv')
        self.news_events = pd.read_csv(f'{self.data_dir}/news_events.csv')
        self.social_sentiment = pd.read_csv(f'{self.data_dir}/social_sentiment.csv')
        self.dark_pool = pd.read_csv(f'{self.data_dir}/dark_pool.csv')
        self.options_flow = pd.read_csv(f'{self.data_dir}/options_flow.csv')
        
        with open(f'{self.data_dir}/summary.json', 'r') as f:
            self.summary = json.load(f)
        
        print(f"✅ Loaded {len(self.daily_ohlcv)} days of data")
        print(f"   Period: {self.summary['start_date']} to {self.summary['end_date']}")
        
    def get_data_for_date(self, date: str, lookback_days: int = 30) -> Dict:
        """
        Get all data available for a specific date (what analyzer would see)
        
        Args:
            date: Date to analyze (YYYY-MM-DD)
            lookback_days: Days of historical data to include
        
        Returns:
            Dict with all data sources for that date
        """
        # Get current day
        current_day = self.daily_ohlcv[self.daily_ohlcv['date'] == date]
        if current_day.empty:
            return None
        
        current_day = current_day.iloc[0]
        
        # Get historical OHLCV (for technical analysis)
        date_idx = self.daily_ohlcv[self.daily_ohlcv['date'] == date].index[0]
        start_idx = max(0, date_idx - lookback_days)
        historical_ohlcv = self.daily_ohlcv.iloc[start_idx:date_idx + 1]
        
        # Get news from last 24 hours
        news_today = self.news_events[self.news_events['date'] == date]
        
        # Get social sentiment from today
        social_today = self.social_sentiment[self.social_sentiment['date'] == date]
        
        # Get dark pool from today
        dark_pool_today = self.dark_pool[self.dark_pool['date'] == date]
        
        # Get options flow from today
        options_today = self.options_flow[self.options_flow['date'] == date]
        
        return {
            'date': date,
            'current_price': current_day['close'],
            'open': current_day['open'],
            'high': current_day['high'],
            'low': current_day['low'],
            'close': current_day['close'],
            'volume': current_day['volume'],
            'regime': current_day['regime'],
            'historical_ohlcv': historical_ohlcv,
            'news': news_today,
            'social': social_today,
            'dark_pool': dark_pool_today,
            'options': options_today
        }
    
    def calculate_vwap(self, date_data: Dict) -> float:
        """Calculate VWAP from synthetic data"""
        # Simple approximation: average of high, low, close
        return (date_data['high'] + date_data['low'] + date_data['close']) / 3
    
    def calculate_camarilla(self, date_data: Dict) -> Dict:
        """Calculate Camarilla levels from previous day"""
        hist = date_data['historical_ohlcv']
        if len(hist) < 2:
            return {'R4': 0, 'R3': 0, 'S3': 0, 'S4': 0}
        
        prev_day = hist.iloc[-2]  # Previous day
        high = prev_day['high']
        low = prev_day['low']
        close = prev_day['close']
        
        range_val = high - low
        
        r4 = close + (range_val * 1.1 / 2)
        r3 = close + (range_val * 1.1 / 4)
        s3 = close - (range_val * 1.1 / 4)
        s4 = close - (range_val * 1.1 / 2)
        
        return {
            'R4': round(r4, 2),
            'R3': round(r3, 2),
            'S3': round(s3, 2),
            'S4': round(s4, 2)
        }
    
    def calculate_support_resistance(self, date_data: Dict) -> Dict:
        """Calculate support/resistance"""
        hist = date_data['historical_ohlcv']
        if len(hist) < 10:
            return {'support': 0, 'resistance': 0}
        
        recent = hist.tail(10)
        resistance = recent['high'].quantile(0.75)
        support = recent['low'].quantile(0.25)
        
        return {
            'support': round(support, 2),
            'resistance': round(resistance, 2)
        }
    
    def detect_gap(self, date_data: Dict) -> Dict:
        """Detect gap from previous close"""
        hist = date_data['historical_ohlcv']
        if len(hist) < 2:
            return {'gap_type': 'NO_GAP', 'gap_size': 0}
        
        prev_close = hist.iloc[-2]['close']
        current_open = date_data['open']
        
        gap_amount = current_open - prev_close
        gap_percentage = (gap_amount / prev_close) * 100
        
        if gap_percentage > 1.0:
            gap_type = 'GAP_UP'
        elif gap_percentage < -1.0:
            gap_type = 'GAP_DOWN'
        else:
            gap_type = 'NO_GAP'
        
        return {
            'gap_type': gap_type,
            'gap_size': round(gap_percentage, 2),
            'gap_amount': round(gap_amount, 2)
        }
    
    def analyze_news_sentiment(self, date_data: Dict) -> Dict:
        """Analyze news sentiment"""
        news = date_data['news']
        
        if news.empty:
            return {
                'sentiment': 'NEUTRAL',
                'urgency': 'LOW',
                'news_impact': 'NONE',
                'sentiment_score': 0,
                'count': 0
            }
        
        # Map sentiment to scores
        sentiment_map = {
            'very_positive': 3,
            'positive': 1,
            'neutral': 0,
            'negative': -1,
            'very_negative': -3
        }
        
        sentiment_score = sum([sentiment_map.get(s, 0) for s in news['sentiment']])
        
        # Determine overall sentiment
        if sentiment_score >= 5:
            sentiment = 'VERY POSITIVE'
        elif sentiment_score >= 2:
            sentiment = 'POSITIVE'
        elif sentiment_score <= -5:
            sentiment = 'VERY NEGATIVE'
        elif sentiment_score <= -2:
            sentiment = 'NEGATIVE'
        else:
            sentiment = 'NEUTRAL'
        
        # News impact
        high_impact_count = len(news[news['impact'] == 'high'])
        if high_impact_count >= 2:
            news_impact = 'HIGH'
        elif high_impact_count >= 1:
            news_impact = 'MEDIUM'
        elif len(news) > 0:
            news_impact = 'LOW'
        else:
            news_impact = 'NONE'
        
        urgency = 'HIGH' if news_impact == 'HIGH' else 'MEDIUM' if news_impact == 'MEDIUM' else 'LOW'
        
        return {
            'sentiment': sentiment,
            'urgency': urgency,
            'news_impact': news_impact,
            'sentiment_score': sentiment_score,
            'count': len(news),
            'headlines': news['headline'].tolist()[:3] if len(news) > 0 else []
        }
    
    def analyze_dark_pool(self, date_data: Dict) -> Dict:
        """Analyze dark pool activity"""
        dp = date_data['dark_pool']
        
        if dp.empty:
            return {
                'activity': 'NEUTRAL',
                'institutional_flow': 'NEUTRAL',
                'large_trades': 0
            }
        
        buys = dp[dp['side'] == 'buy']
        sells = dp[dp['side'] == 'sell']
        
        buy_volume = buys['size'].sum()
        sell_volume = sells['size'].sum()
        
        # Determine flow
        if buy_volume > sell_volume * 1.3:
            institutional_flow = 'BUYING'
            activity = 'HEAVY'
        elif sell_volume > buy_volume * 1.3:
            institutional_flow = 'SELLING'
            activity = 'HEAVY'
        else:
            institutional_flow = 'NEUTRAL'
            activity = 'MODERATE'
        
        # Count large trades (>100k shares)
        large_trades = len(dp[dp['size'] > 100000])
        
        return {
            'activity': activity,
            'institutional_flow': institutional_flow,
            'large_trades': large_trades,
            'buy_volume': int(buy_volume),
            'sell_volume': int(sell_volume)
        }
    
    def analyze_options_flow(self, date_data: Dict) -> Dict:
        """Analyze options flow"""
        opts = date_data['options']
        
        if opts.empty:
            return {
                'sentiment': 'NEUTRAL',
                'put_call_ratio': 1.0,
                'unusual_activity': False
            }
        
        calls = opts[opts['type'] == 'call']
        puts = opts[opts['type'] == 'put']
        
        call_volume = len(calls)
        put_volume = len(puts)
        
        put_call_ratio = put_volume / call_volume if call_volume > 0 else 1.0
        
        if put_call_ratio > 1.2:
            sentiment = 'BEARISH'
        elif put_call_ratio < 0.8:
            sentiment = 'BULLISH'
        else:
            sentiment = 'NEUTRAL'
        
        unusual_activity = len(opts[opts['unusual'] == True]) > 3
        
        return {
            'sentiment': sentiment,
            'put_call_ratio': round(put_call_ratio, 2),
            'unusual_activity': unusual_activity,
            'call_volume': call_volume,
            'put_volume': put_volume
        }
    
    def calculate_bias(self, date_data: Dict, timeframe: str = '1H') -> Dict:
        """Calculate directional bias"""
        hist = date_data['historical_ohlcv']
        
        if timeframe == '1D':
            lookback = 20
        else:  # 1H approximation using daily
            lookback = 5
        
        if len(hist) < lookback:
            return {'bias': 'NEUTRAL', 'strength': 0}
        
        recent = hist.tail(lookback)
        
        # Simple EMA crossover
        ema_short = recent['close'].ewm(span=3, adjust=False).mean().iloc[-1]
        ema_long = recent['close'].ewm(span=9, adjust=False).mean().iloc[-1]
        current_price = date_data['close']
        
        if ema_short > ema_long and current_price > ema_short:
            bias = 'BULLISH'
            strength = min(((ema_short - ema_long) / ema_long) * 100, 100)
        elif ema_short < ema_long and current_price < ema_short:
            bias = 'BEARISH'
            strength = min(((ema_long - ema_short) / ema_short) * 100, 100)
        else:
            bias = 'NEUTRAL'
            strength = 0
        
        return {
            'bias': bias,
            'strength': round(strength, 1)
        }
    
    def generate_signal(self, date_data: Dict) -> Dict:
        """
        Generate trading signal using same logic as your analyzer
        """
        # Get all indicators
        vwap = self.calculate_vwap(date_data)
        camarilla = self.calculate_camarilla(date_data)
        support_resistance = self.calculate_support_resistance(date_data)
        gap_data = self.detect_gap(date_data)
        news = self.analyze_news_sentiment(date_data)
        dark_pool = self.analyze_dark_pool(date_data)
        options = self.analyze_options_flow(date_data)
        bias_1h = self.calculate_bias(date_data, '1H')
        bias_daily = self.calculate_bias(date_data, '1D')
        
        current_price = date_data['close']
        
        # Score factors (same logic as analyzer)
        bullish_factors = 0
        bearish_factors = 0
        
        # Gap factors (high priority)
        if gap_data['gap_type'] == 'GAP_DOWN' and abs(gap_data['gap_size']) > 2:
            bearish_factors += 4
        elif gap_data['gap_type'] == 'GAP_UP' and gap_data['gap_size'] > 2:
            bullish_factors += 4
        
        # News factors (high priority)
        if news['sentiment'] == 'VERY NEGATIVE':
            bearish_factors += 3
        elif news['sentiment'] == 'NEGATIVE':
            bearish_factors += 2
        elif news['sentiment'] == 'VERY POSITIVE':
            bullish_factors += 3
        elif news['sentiment'] == 'POSITIVE':
            bullish_factors += 2
        
        # Bias factors
        if bias_1h['bias'] == 'BULLISH': bullish_factors += 2
        if bias_daily['bias'] == 'BULLISH': bullish_factors += 1
        if bias_1h['bias'] == 'BEARISH': bearish_factors += 2
        if bias_daily['bias'] == 'BEARISH': bearish_factors += 1
        
        # VWAP
        if current_price > vwap: bullish_factors += 1
        if current_price < vwap: bearish_factors += 1
        
        # Options
        if options['sentiment'] == 'BULLISH': bullish_factors += 2
        if options['sentiment'] == 'BEARISH': bearish_factors += 2
        
        # Dark pool
        if dark_pool['institutional_flow'] == 'BUYING': bullish_factors += 3
        if dark_pool['institutional_flow'] == 'SELLING': bearish_factors += 3
        
        # Camarilla levels
        if current_price <= camarilla['S3']: bullish_factors += 2
        if current_price >= camarilla['R3']: bearish_factors += 2
        
        # Lower threshold for high-impact news or large gaps
        signal_threshold = 6
        if news['news_impact'] == 'HIGH' or abs(gap_data.get('gap_size', 0)) > 3:
            signal_threshold = 4
        
        # Determine signal
        signal = None
        confidence = 0.0
        alert_type = 'MONITOR'
        
        if bullish_factors >= signal_threshold:
            signal = 'BUY'
            confidence = min(bullish_factors / 15 * 100, 95)
            alert_type = 'STRONG BUY' if bullish_factors >= signal_threshold + 3 else 'BUY'
        elif bearish_factors >= signal_threshold:
            signal = 'SELL'
            confidence = min(bearish_factors / 15 * 100, 95)
            alert_type = 'STRONG SELL' if bearish_factors >= signal_threshold + 3 else 'SELL'
        
        # Calculate entry/targets
        entry_targets = {}
        if signal == 'BUY':
            entry = min(current_price, support_resistance['support'] + 0.10)
            tp1 = camarilla['R3']
            stop_loss = support_resistance['support'] - 0.20
            risk = abs(entry - stop_loss)
            reward = abs(tp1 - entry)
            entry_targets = {
                'entry': round(entry, 2),
                'tp1': round(tp1, 2),
                'stop_loss': round(stop_loss, 2),
                'risk_reward': round(reward / risk if risk > 0 else 0, 2)
            }
        elif signal == 'SELL':
            entry = max(current_price, support_resistance['resistance'] - 0.10)
            tp1 = camarilla['S3']
            stop_loss = support_resistance['resistance'] + 0.20
            risk = abs(entry - stop_loss)
            reward = abs(entry - tp1)
            entry_targets = {
                'entry': round(entry, 2),
                'tp1': round(tp1, 2),
                'stop_loss': round(stop_loss, 2),
                'risk_reward': round(reward / risk if risk > 0 else 0, 2)
            }
        
        return {
            'date': date_data['date'],
            'signal': signal,
            'alert_type': alert_type,
            'confidence': round(confidence, 1),
            'current_price': current_price,
            'vwap': vwap,
            'gap_data': gap_data,
            'news': news,
            'dark_pool': dark_pool,
            'options': options,
            'bias_1h': bias_1h['bias'],
            'bias_daily': bias_daily['bias'],
            'camarilla': camarilla,
            'support_resistance': support_resistance,
            'entry_targets': entry_targets,
            'bullish_score': bullish_factors,
            'bearish_score': bearish_factors,
            'regime': date_data['regime']
        }
    
    def backtest_all_days(self) -> pd.DataFrame:
        """Run backtest on all days"""
        print("\n🚀 Starting backtest...")
        print("=" * 80)
        
        results = []
        
        for idx, row in self.daily_ohlcv.iterrows():
            date = row['date']
            
            # Get data for this date
            date_data = self.get_data_for_date(date)
            if date_data is None:
                continue
            
            # Generate signal
            signal_result = self.generate_signal(date_data)
            
            # Calculate actual returns for next day (if signal was taken)
            if idx < len(self.daily_ohlcv) - 1:
                next_day = self.daily_ohlcv.iloc[idx + 1]
                
                if signal_result['signal'] == 'BUY':
                    entry = signal_result['entry_targets'].get('entry', date_data['close'])
                    tp1 = signal_result['entry_targets'].get('tp1', 0)
                    sl = signal_result['entry_targets'].get('stop_loss', 0)
                    
                    # Simplified: check if TP or SL hit
                    if next_day['high'] >= tp1:
                        pnl = tp1 - entry
                        outcome = 'TP_HIT'
                    elif next_day['low'] <= sl:
                        pnl = sl - entry
                        outcome = 'SL_HIT'
                    else:
                        pnl = next_day['close'] - entry
                        outcome = 'HELD'
                    
                    pnl_pct = (pnl / entry) * 100
                    
                elif signal_result['signal'] == 'SELL':
                    entry = signal_result['entry_targets'].get('entry', date_data['close'])
                    tp1 = signal_result['entry_targets'].get('tp1', 0)
                    sl = signal_result['entry_targets'].get('stop_loss', 0)
                    
                    if next_day['low'] <= tp1:
                        pnl = entry - tp1
                        outcome = 'TP_HIT'
                    elif next_day['high'] >= sl:
                        pnl = entry - sl
                        outcome = 'SL_HIT'
                    else:
                        pnl = entry - next_day['close']
                        outcome = 'HELD'
                    
                    pnl_pct = (pnl / entry) * 100
                else:
                    pnl = 0
                    pnl_pct = 0
                    outcome = 'NO_SIGNAL'
            else:
                pnl = 0
                pnl_pct = 0
                outcome = 'NO_NEXT_DAY'
            
            # Store result
            results.append({
                'date': date,
                'signal': signal_result['signal'],
                'alert_type': signal_result['alert_type'],
                'confidence': signal_result['confidence'],
                'entry_price': signal_result['entry_targets'].get('entry', 0) if signal_result['entry_targets'] else 0,
                'tp1': signal_result['entry_targets'].get('tp1', 0) if signal_result['entry_targets'] else 0,
                'stop_loss': signal_result['entry_targets'].get('stop_loss', 0) if signal_result['entry_targets'] else 0,
                'pnl': round(pnl, 2),
                'pnl_pct': round(pnl_pct, 2),
                'outcome': outcome,
                'bullish_score': signal_result['bullish_score'],
                'bearish_score': signal_result['bearish_score'],
                'gap_type': signal_result['gap_data']['gap_type'],
                'gap_size': signal_result['gap_data']['gap_size'],
                'news_sentiment': signal_result['news']['sentiment'],
                'news_impact': signal_result['news']['news_impact'],
                'dark_pool_flow': signal_result['dark_pool']['institutional_flow'],
                'options_sentiment': signal_result['options']['sentiment'],
                'regime': signal_result['regime']
            })
            
            # Print progress
            if signal_result['signal']:
                print(f"📅 {date}: {signal_result['alert_type']:15s} | "
                      f"Conf: {signal_result['confidence']:5.1f}% | "
                      f"P&L: {pnl_pct:+6.2f}% | "
                      f"Outcome: {outcome}")
        
        results_df = pd.DataFrame(results)
        
        # Calculate statistics
        print("\n" + "=" * 80)
        print("📊 BACKTEST RESULTS")
        print("=" * 80)
        
        # Filter to actual signals
        signals_df = results_df[results_df['signal'].notna()]
        
        if len(signals_df) > 0:
            print(f"\n📈 OVERALL STATISTICS:")
            print(f"   Total Days: {len(results_df)}")
            print(f"   Total Signals: {len(signals_df)}")
            print(f"   BUY Signals: {len(signals_df[signals_df['signal'] == 'BUY'])}")
            print(f"   SELL Signals: {len(signals_df[signals_df['signal'] == 'SELL'])}")
            print(f"   Signal Rate: {len(signals_df) / len(results_df) * 100:.1f}%")
            
            print(f"\n💰 PERFORMANCE:")
            winning_trades = signals_df[signals_df['pnl'] > 0]
            losing_trades = signals_df[signals_df['pnl'] < 0]
            
            win_rate = len(winning_trades) / len(signals_df) * 100 if len(signals_df) > 0 else 0
            avg_win = winning_trades['pnl_pct'].mean() if len(winning_trades) > 0 else 0
            avg_loss = losing_trades['pnl_pct'].mean() if len(losing_trades) > 0 else 0
            
            print(f"   Win Rate: {win_rate:.1f}%")
            print(f"   Winners: {len(winning_trades)}")
            print(f"   Losers: {len(losing_trades)}")
            print(f"   Avg Win: {avg_win:+.2f}%")
            print(f"   Avg Loss: {avg_loss:+.2f}%")
            print(f"   Total P&L: {signals_df['pnl_pct'].sum():.2f}%")
            print(f"   Avg P&L per trade: {signals_df['pnl_pct'].mean():+.2f}%")
            
            # Best and worst trades
            print(f"\n🏆 BEST TRADES:")
            best = signals_df.nlargest(3, 'pnl_pct')[['date', 'signal', 'alert_type', 'pnl_pct', 'outcome']]
            print(best.to_string(index=False))
            
            print(f"\n❌ WORST TRADES:")
            worst = signals_df.nsmallest(3, 'pnl_pct')[['date', 'signal', 'alert_type', 'pnl_pct', 'outcome']]
            print(worst.to_string(index=False))
            
            # By confidence level
            print(f"\n🎯 BY CONFIDENCE LEVEL:")
            strong_signals = signals_df[signals_df['alert_type'].str.contains('STRONG')]
            regular_signals = signals_df[~signals_df['alert_type'].str.contains('STRONG')]
            
            if len(strong_signals) > 0:
                print(f"   STRONG Signals: {len(strong_signals)}")
                print(f"     Win Rate: {len(strong_signals[strong_signals['pnl'] > 0]) / len(strong_signals) * 100:.1f}%")
                print(f"     Avg P&L: {strong_signals['pnl_pct'].mean():+.2f}%")
            
            if len(regular_signals) > 0:
                print(f"   Regular Signals: {len(regular_signals)}")
                print(f"     Win Rate: {len(regular_signals[regular_signals['pnl'] > 0]) / len(regular_signals) * 100:.1f}%")
                print(f"     Avg P&L: {regular_signals['pnl_pct'].mean():+.2f}%")
        else:
            print("⚠️  No signals generated during backtest period")
        
        # Save results
        output_file = f'{self.data_dir}/backtest_results.csv'
        results_df.to_csv(output_file, index=False)
        print(f"\n💾 Results saved to: {output_file}")
        
        return results_df


if __name__ == '__main__':
    # Run backtest
    backtester = SyntheticDataBacktester('synthetic_data_pltr')
    results = backtester.backtest_all_days()
    
    print("\n✅ Backtest complete!")
    print("\n📝 Review the backtest_results.csv file for detailed analysis")
    print("\n🎯 Next: Analyze which conditions produce best signals")
