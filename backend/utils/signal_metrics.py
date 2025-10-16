"""
backend/utils/signal_metrics.py
Signal Performance Tracking System
Tracks signal accuracy, win rate, and R:R performance
"""

import pandas as pd
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging


class SignalMetricsTracker:
    def __init__(self, metrics_file: str = None):
        """
        Initialize Signal Metrics Tracker
        
        Args:
            metrics_file: Path to metrics CSV file
        """
        self.logger = logging.getLogger(__name__)
        
        if metrics_file is None:
            metrics_dir = Path(__file__).parent.parent / 'data' / 'metrics'
            metrics_dir.mkdir(parents=True, exist_ok=True)
            self.metrics_file = metrics_dir / 'signal_metrics.csv'
        else:
            self.metrics_file = Path(metrics_file)
        
        # Initialize or load metrics
        self.metrics_df = self._load_metrics()
        
        self.logger.info(f"Signal metrics tracker initialized: {self.metrics_file}")
    
    def _load_metrics(self) -> pd.DataFrame:
        """Load existing metrics or create new DataFrame"""
        if self.metrics_file.exists():
            try:
                df = pd.read_csv(self.metrics_file)
                self.logger.info(f"Loaded {len(df)} historical signals")
                return df
            except Exception as e:
                self.logger.error(f"Error loading metrics: {str(e)}")
        
        # Create new DataFrame
        return pd.DataFrame(columns=[
            'signal_id',
            'timestamp',
            'symbol',
            'alert_type',
            'confidence',
            'entry_price',
            'tp1',
            'tp2',
            'stop_loss',
            'risk_reward_ratio',
            'factors_bullish',
            'factors_bearish',
            'rvol',
            'volume_spike',
            'confluence_score',
            'gap_detected',
            'news_impact',
            'status',  # OPEN, TP1_HIT, TP2_HIT, STOPPED_OUT, EXPIRED
            'outcome_timestamp',
            'outcome_price',
            'profit_loss_percent',
            'actual_rr_achieved'
        ])
    
    def _save_metrics(self):
        """Save metrics to CSV"""
        try:
            self.metrics_df.to_csv(self.metrics_file, index=False)
            self.logger.debug(f"Metrics saved to {self.metrics_file}")
        except Exception as e:
            self.logger.error(f"Error saving metrics: {str(e)}")
    
    def record_signal(self, analysis: Dict) -> str:
        """
        Record a new signal
        
        Args:
            analysis: Analysis result from enhanced_professional_analyzer
        
        Returns:
            signal_id: Unique identifier for this signal
        """
        try:
            signal_id = f"{analysis['symbol']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            entry_targets = analysis.get('entry_targets', {})
            volume_data = analysis.get('volume_analysis', {})
            key_levels = analysis.get('key_levels', {})
            gap_data = analysis.get('gap_data', {})
            news = analysis.get('news', {})
            
            new_record = {
                'signal_id': signal_id,
                'timestamp': datetime.now().isoformat(),
                'symbol': analysis['symbol'],
                'alert_type': analysis.get('alert_type', 'MONITOR'),
                'confidence': analysis.get('confidence', 0),
                'entry_price': entry_targets.get('entry', 0),
                'tp1': entry_targets.get('tp1', 0),
                'tp2': entry_targets.get('tp2', 0),
                'stop_loss': entry_targets.get('stop_loss', 0),
                'risk_reward_ratio': entry_targets.get('risk_reward', 0),
                'factors_bullish': analysis.get('bullish_score', 0),
                'factors_bearish': analysis.get('bearish_score', 0),
                'rvol': volume_data.get('rvol', {}).get('rvol', 0),
                'volume_spike': volume_data.get('volume_spike', {}).get('spike_detected', False),
                'confluence_score': key_levels.get('confluence_score', 0),
                'gap_detected': gap_data.get('gap_type', 'NONE') != 'NO_GAP',
                'news_impact': news.get('news_impact', 'NONE'),
                'status': 'OPEN',
                'outcome_timestamp': None,
                'outcome_price': None,
                'profit_loss_percent': None,
                'actual_rr_achieved': None
            }
            
            # Append to DataFrame
            self.metrics_df = pd.concat([
                self.metrics_df,
                pd.DataFrame([new_record])
            ], ignore_index=True)
            
            self._save_metrics()
            
            self.logger.info(f"Recorded signal: {signal_id}")
            return signal_id
            
        except Exception as e:
            self.logger.error(f"Error recording signal: {str(e)}")
            return ""
    
    def update_signal_outcome(self, signal_id: str, outcome_price: float, 
                             status: str = 'CLOSED') -> bool:
        """
        Update signal with outcome
        
        Args:
            signal_id: Signal identifier
            outcome_price: Price at which position closed
            status: TP1_HIT, TP2_HIT, STOPPED_OUT, EXPIRED
        
        Returns:
            True if updated successfully
        """
        try:
            idx = self.metrics_df[self.metrics_df['signal_id'] == signal_id].index
            
            if len(idx) == 0:
                self.logger.warning(f"Signal not found: {signal_id}")
                return False
            
            idx = idx[0]
            
            entry = self.metrics_df.loc[idx, 'entry_price']
            stop_loss = self.metrics_df.loc[idx, 'stop_loss']
            alert_type = self.metrics_df.loc[idx, 'alert_type']
            
            # Calculate P&L
            if 'BUY' in alert_type:
                pl_percent = ((outcome_price - entry) / entry) * 100
            else:  # SELL
                pl_percent = ((entry - outcome_price) / entry) * 100
            
            # Calculate actual R:R achieved
            risk = abs(entry - stop_loss)
            reward_achieved = abs(outcome_price - entry)
            actual_rr = reward_achieved / risk if risk > 0 else 0
            
            # Update record
            self.metrics_df.loc[idx, 'status'] = status
            self.metrics_df.loc[idx, 'outcome_timestamp'] = datetime.now().isoformat()
            self.metrics_df.loc[idx, 'outcome_price'] = outcome_price
            self.metrics_df.loc[idx, 'profit_loss_percent'] = round(pl_percent, 2)
            self.metrics_df.loc[idx, 'actual_rr_achieved'] = round(actual_rr, 2)
            
            self._save_metrics()
            
            self.logger.info(f"Updated signal {signal_id}: {status}, P&L: {pl_percent:.2f}%")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating signal outcome: {str(e)}")
            return False
    
    def get_win_rate(self, days: int = None, alert_type: str = None) -> Dict:
        """
        Calculate win rate for closed signals
        
        Args:
            days: Only include signals from last N days
            alert_type: Filter by alert type (BUY, SELL, etc.)
        
        Returns:
            Dictionary with win rate statistics
        """
        try:
            df = self.metrics_df.copy()
            
            # Filter by days
            if days:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                cutoff = datetime.now() - timedelta(days=days)
                df = df[df['timestamp'] >= cutoff]
            
            # Filter by alert type
            if alert_type:
                df = df[df['alert_type'].str.contains(alert_type, na=False)]
            
            # Get closed signals only
            closed = df[df['status'].isin(['TP1_HIT', 'TP2_HIT', 'STOPPED_OUT'])]
            
            if len(closed) == 0:
                return {
                    'total_signals': len(df),
                    'closed_signals': 0,
                    'win_rate': 0,
                    'avg_rr_achieved': 0
                }
            
            # Count wins and losses
            wins = closed[closed['profit_loss_percent'] > 0]
            losses = closed[closed['profit_loss_percent'] <= 0]
            
            win_rate = (len(wins) / len(closed)) * 100
            avg_win = wins['profit_loss_percent'].mean() if len(wins) > 0 else 0
            avg_loss = losses['profit_loss_percent'].mean() if len(losses) > 0 else 0
            avg_rr = closed['actual_rr_achieved'].mean()
            
            return {
                'total_signals': len(df),
                'closed_signals': len(closed),
                'wins': len(wins),
                'losses': len(losses),
                'win_rate': round(win_rate, 2),
                'avg_win_percent': round(avg_win, 2),
                'avg_loss_percent': round(avg_loss, 2),
                'avg_rr_achieved': round(avg_rr, 2)
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating win rate: {str(e)}")
            return {}
    
    def get_performance_by_symbol(self, symbol: str) -> Dict:
        """Get performance statistics for a specific symbol"""
        try:
            df = self.metrics_df[self.metrics_df['symbol'] == symbol].copy()
            
            if len(df) == 0:
                return {'symbol': symbol, 'total_signals': 0}
            
            closed = df[df['status'].isin(['TP1_HIT', 'TP2_HIT', 'STOPPED_OUT'])]
            
            if len(closed) == 0:
                return {
                    'symbol': symbol,
                    'total_signals': len(df),
                    'closed_signals': 0
                }
            
            wins = closed[closed['profit_loss_percent'] > 0]
            win_rate = (len(wins) / len(closed)) * 100
            
            return {
                'symbol': symbol,
                'total_signals': len(df),
                'closed_signals': len(closed),
                'wins': len(wins),
                'losses': len(closed) - len(wins),
                'win_rate': round(win_rate, 2),
                'avg_confidence': round(df['confidence'].mean(), 2),
                'avg_rr_ratio': round(df['risk_reward_ratio'].mean(), 2)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting symbol performance: {str(e)}")
            return {}
    
    def get_daily_summary(self, date: str = None) -> Dict:
        """
        Get summary of signals for a specific day
        
        Args:
            date: Date in YYYY-MM-DD format (default: today)
        
        Returns:
            Daily summary statistics
        """
        try:
            if date is None:
                date = datetime.now().strftime('%Y-%m-%d')
            
            df = self.metrics_df.copy()
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['date'] = df['timestamp'].dt.date
            
            daily = df[df['date'] == pd.to_datetime(date).date()]
            
            if len(daily) == 0:
                return {
                    'date': date,
                    'total_signals': 0
                }
            
            return {
                'date': date,
                'total_signals': len(daily),
                'strong_signals': len(daily[daily['alert_type'].str.contains('STRONG', na=False)]),
                'avg_confidence': round(daily['confidence'].mean(), 2),
                'symbols': daily['symbol'].unique().tolist(),
                'alert_types': daily['alert_type'].value_counts().to_dict()
            }
            
        except Exception as e:
            self.logger.error(f"Error generating daily summary: {str(e)}")
            return {}
    
    def generate_report(self, days: int = 7) -> str:
        """
        Generate text report of performance
        
        Args:
            days: Number of days to include in report
        
        Returns:
            Formatted text report
        """
        try:
            overall = self.get_win_rate(days=days)
            
            report = []
            report.append("=" * 60)
            report.append(f"SIGNAL PERFORMANCE REPORT (Last {days} Days)")
            report.append("=" * 60)
            report.append(f"Total Signals: {overall.get('total_signals', 0)}")
            report.append(f"Closed Signals: {overall.get('closed_signals', 0)}")
            report.append(f"Win Rate: {overall.get('win_rate', 0):.2f}%")
            report.append(f"Average R:R Achieved: {overall.get('avg_rr_achieved', 0):.2f}")
            report.append(f"Average Win: +{overall.get('avg_win_percent', 0):.2f}%")
            report.append(f"Average Loss: {overall.get('avg_loss_percent', 0):.2f}%")
            
            # Top performing symbols
            df = self.metrics_df.copy()
            if days:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                cutoff = datetime.now() - timedelta(days=days)
                df = df[df['timestamp'] >= cutoff]
            
            if len(df) > 0:
                symbol_counts = df['symbol'].value_counts()
                report.append("\nMost Active Symbols:")
                for symbol, count in symbol_counts.head(5).items():
                    report.append(f"  • {symbol}: {count} signals")
            
            report.append("=" * 60)
            
            return "\n".join(report)
            
        except Exception as e:
            self.logger.error(f"Error generating report: {str(e)}")
            return "Error generating report"
    
    def export_to_csv(self, output_file: str = None) -> bool:
        """Export metrics to custom CSV file"""
        try:
            if output_file is None:
                output_file = f"signal_metrics_{datetime.now().strftime('%Y%m%d')}.csv"
            
            self.metrics_df.to_csv(output_file, index=False)
            self.logger.info(f"Metrics exported to {output_file}")
            return True
        except Exception as e:
            self.logger.error(f"Error exporting metrics: {str(e)}")
            return False


# CLI for testing
def main():
    """Command-line interface"""
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    tracker = SignalMetricsTracker()
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'report':
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
            print(tracker.generate_report(days=days))
        
        elif command == 'winrate':
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
            stats = tracker.get_win_rate(days=days)
            
            print("=" * 60)
            print(f"WIN RATE (Last {days} Days)")
            print("=" * 60)
            for key, value in stats.items():
                print(f"{key}: {value}")
        
        elif command == 'symbol':
            if len(sys.argv) < 3:
                print("Usage: python signal_metrics.py symbol SYMBOL")
                return
            
            symbol = sys.argv[2].upper()
            stats = tracker.get_performance_by_symbol(symbol)
            
            print("=" * 60)
            print(f"PERFORMANCE: {symbol}")
            print("=" * 60)
            for key, value in stats.items():
                print(f"{key}: {value}")
        
        elif command == 'export':
            output = sys.argv[2] if len(sys.argv) > 2 else None
            if tracker.export_to_csv(output):
                print(f"✅ Metrics exported successfully")
        
        else:
            print(f"Unknown command: {command}")
            print("\nAvailable commands:")
            print("  report [days]  - Generate performance report")
            print("  winrate [days] - Show win rate statistics")
            print("  symbol SYMBOL  - Show performance for specific symbol")
            print("  export [file]  - Export metrics to CSV")
    
    else:
        # Default: show 7-day report
        print(tracker.generate_report(days=7))


if __name__ == '__main__':
    main()
