"""
Backtest Results Visualizer
Creates charts and analysis of backtest performance
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import numpy as np

class BacktestVisualizer:
    def __init__(self, data_dir: str = 'synthetic_data_pltr'):
        """Load backtest results and daily OHLCV data"""
        self.data_dir = data_dir
        self.results = pd.read_csv(f'{data_dir}/backtest_results.csv')
        self.daily_ohlcv = pd.read_csv(f'{data_dir}/daily_ohlcv.csv')
        
        # Convert dates
        self.results['date'] = pd.to_datetime(self.results['date'])
        self.daily_ohlcv['date'] = pd.to_datetime(self.daily_ohlcv['date'])
        
        print(f"📊 Loaded {len(self.results)} backtest results")
        
    def create_comprehensive_report(self):
        """Generate comprehensive visual report"""
        
        # Set style
        plt.style.use('dark_background')
        sns.set_palette("husl")
        
        # Create figure with subplots
        fig = plt.figure(figsize=(20, 12))
        fig.suptitle('TRADING SYSTEM BACKTEST ANALYSIS - PLTR 90 DAYS', 
                     fontsize=20, fontweight='bold', color='#00ff00')
        
        # 1. Equity Curve (signals only)
        ax1 = plt.subplot(3, 3, 1)
        signals_only = self.results[self.results['signal'].notna()].copy()
        if len(signals_only) > 0:
            signals_only['cumulative_pnl'] = signals_only['pnl_pct'].cumsum()
            ax1.plot(signals_only['date'], signals_only['cumulative_pnl'], 
                    color='#00ff00', linewidth=2, label='Cumulative P&L')
            ax1.fill_between(signals_only['date'], signals_only['cumulative_pnl'], 
                            alpha=0.3, color='#00ff00')
            ax1.axhline(y=0, color='white', linestyle='--', alpha=0.5)
            ax1.set_title('Equity Curve', fontsize=12, fontweight='bold')
            ax1.set_ylabel('Cumulative Return (%)')
            ax1.grid(True, alpha=0.2)
            ax1.legend()
        
        # 2. Win Rate by Signal Type
        ax2 = plt.subplot(3, 3, 2)
        if len(signals_only) > 0:
            signal_perf = signals_only.groupby('signal').agg({
                'pnl': lambda x: (x > 0).sum() / len(x) * 100
            })
            colors = ['#00ff00' if val > 50 else '#ff0000' for val in signal_perf['pnl']]
            ax2.bar(signal_perf.index, signal_perf['pnl'], color=colors, alpha=0.7)
            ax2.axhline(y=50, color='yellow', linestyle='--', label='50% Breakeven')
            ax2.set_title('Win Rate by Signal Type', fontsize=12, fontweight='bold')
            ax2.set_ylabel('Win Rate (%)')
            ax2.legend()
            ax2.grid(True, alpha=0.2)
        
        # 3. P&L Distribution
        ax3 = plt.subplot(3, 3, 3)
        if len(signals_only) > 0:
            winning = signals_only[signals_only['pnl'] > 0]['pnl_pct']
            losing = signals_only[signals_only['pnl'] < 0]['pnl_pct']
            
            ax3.hist(winning, bins=20, alpha=0.7, color='#00ff00', label='Winners')
            ax3.hist(losing, bins=20, alpha=0.7, color='#ff0000', label='Losers')
            ax3.axvline(x=0, color='white', linestyle='--', alpha=0.5)
            ax3.set_title('P&L Distribution', fontsize=12, fontweight='bold')
            ax3.set_xlabel('P&L (%)')
            ax3.set_ylabel('Frequency')
            ax3.legend()
            ax3.grid(True, alpha=0.2)
        
        # 4. Signals Over Time with Price
        ax4 = plt.subplot(3, 3, 4)
        ax4.plot(self.daily_ohlcv['date'], self.daily_ohlcv['close'], 
                color='white', alpha=0.5, linewidth=1)
        
        buys = signals_only[signals_only['signal'] == 'BUY']
        sells = signals_only[signals_only['signal'] == 'SELL']
        
        # Color by outcome
        buy_wins = buys[buys['pnl'] > 0]
        buy_losses = buys[buys['pnl'] <= 0]
        sell_wins = sells[sells['pnl'] > 0]
        sell_losses = sells[sells['pnl'] <= 0]
        
        if len(buy_wins) > 0:
            ax4.scatter(buy_wins['date'], buy_wins['entry_price'], 
                       color='#00ff00', marker='^', s=100, label='BUY Win', zorder=5)
        if len(buy_losses) > 0:
            ax4.scatter(buy_losses['date'], buy_losses['entry_price'], 
                       color='#ff0000', marker='^', s=100, label='BUY Loss', zorder=5)
        if len(sell_wins) > 0:
            ax4.scatter(sell_wins['date'], sell_wins['entry_price'], 
                       color='#00ff00', marker='v', s=100, label='SELL Win', zorder=5)
        if len(sell_losses) > 0:
            ax4.scatter(sell_losses['date'], sell_losses['entry_price'], 
                       color='#ff0000', marker='v', s=100, label='SELL Loss', zorder=5)
        
        ax4.set_title('Signals on Price Chart', fontsize=12, fontweight='bold')
        ax4.set_ylabel('Price ($)')
        ax4.legend(loc='upper left', fontsize=8)
        ax4.grid(True, alpha=0.2)
        
        # 5. Performance by Confidence Level
        ax5 = plt.subplot(3, 3, 5)
        if len(signals_only) > 0:
            # Bin confidence levels
            signals_only['conf_bin'] = pd.cut(signals_only['confidence'], 
                                              bins=[0, 60, 75, 90, 100],
                                              labels=['Low (0-60)', 'Medium (60-75)', 
                                                     'High (75-90)', 'Very High (90+)'])
            
            conf_perf = signals_only.groupby('conf_bin').agg({
                'pnl_pct': 'mean',
                'pnl': lambda x: (x > 0).sum() / len(x) * 100
            }).round(2)
            
            x = np.arange(len(conf_perf))
            width = 0.35
            
            ax5.bar(x - width/2, conf_perf['pnl_pct'], width, 
                   label='Avg P&L %', color='#00ccff', alpha=0.7)
            ax5_twin = ax5.twinx()
            ax5_twin.bar(x + width/2, conf_perf['pnl'], width, 
                        label='Win Rate %', color='#ffcc00', alpha=0.7)
            
            ax5.set_xlabel('Confidence Level')
            ax5.set_ylabel('Avg P&L (%)', color='#00ccff')
            ax5_twin.set_ylabel('Win Rate (%)', color='#ffcc00')
            ax5.set_xticks(x)
            ax5.set_xticklabels(conf_perf.index, rotation=45, ha='right')
            ax5.set_title('Performance by Confidence', fontsize=12, fontweight='bold')
            ax5.grid(True, alpha=0.2)
        
        # 6. Signal Frequency by Market Regime
        ax6 = plt.subplot(3, 3, 6)
        if len(signals_only) > 0:
            regime_signals = signals_only['regime'].value_counts()
            colors_regime = {'uptrend': '#00ff00', 'downtrend': '#ff0000', 
                            'choppy': '#ffff00', 'breakout': '#ff00ff'}
            colors_list = [colors_regime.get(r, 'white') for r in regime_signals.index]
            
            ax6.bar(regime_signals.index, regime_signals.values, 
                   color=colors_list, alpha=0.7)
            ax6.set_title('Signals by Market Regime', fontsize=12, fontweight='bold')
            ax6.set_ylabel('Number of Signals')
            ax6.grid(True, alpha=0.2)
        
        # 7. Monthly Performance
        ax7 = plt.subplot(3, 3, 7)
        if len(signals_only) > 0:
            signals_only['month'] = signals_only['date'].dt.to_period('M')
            monthly = signals_only.groupby('month').agg({
                'pnl_pct': 'sum',
                'signal': 'count'
            })
            
            colors = ['#00ff00' if val > 0 else '#ff0000' for val in monthly['pnl_pct']]
            ax7.bar(range(len(monthly)), monthly['pnl_pct'], color=colors, alpha=0.7)
            ax7.axhline(y=0, color='white', linestyle='--', alpha=0.5)
            ax7.set_title('Monthly P&L', fontsize=12, fontweight='bold')
            ax7.set_xlabel('Month')
            ax7.set_ylabel('P&L (%)')
            ax7.set_xticks(range(len(monthly)))
            ax7.set_xticklabels([str(m) for m in monthly.index], rotation=45)
            ax7.grid(True, alpha=0.2)
        
        # 8. Gap Analysis
        ax8 = plt.subplot(3, 3, 8)
        gap_signals = signals_only[signals_only['gap_type'] != 'NO_GAP']
        if len(gap_signals) > 0:
            gap_perf = gap_signals.groupby('gap_type').agg({
                'pnl_pct': 'mean',
                'signal': 'count'
            }).round(2)
            
            colors = ['#00ff00' if gap_perf.loc[idx, 'pnl_pct'] > 0 else '#ff0000' 
                     for idx in gap_perf.index]
            ax8.bar(gap_perf.index, gap_perf['pnl_pct'], color=colors, alpha=0.7)
            ax8.axhline(y=0, color='white', linestyle='--', alpha=0.5)
            ax8.set_title('Performance on Gap Days', fontsize=12, fontweight='bold')
            ax8.set_ylabel('Avg P&L (%)')
            
            # Add count labels
            for i, (idx, row) in enumerate(gap_perf.iterrows()):
                ax8.text(i, row['pnl_pct'], f"n={int(row['signal'])}", 
                        ha='center', va='bottom', fontsize=8)
            ax8.grid(True, alpha=0.2)
        
        # 9. News Impact Analysis
        ax9 = plt.subplot(3, 3, 9)
        news_signals = signals_only[signals_only['news_impact'] != 'NONE']
        if len(news_signals) > 0:
            news_perf = news_signals.groupby('news_impact').agg({
                'pnl_pct': 'mean',
                'signal': 'count'
            }).round(2)
            
            # Order by impact
            order = ['HIGH', 'MEDIUM', 'LOW']
            news_perf = news_perf.reindex(order, fill_value=0)
            
            colors = ['#00ff00' if news_perf.loc[idx, 'pnl_pct'] > 0 else '#ff0000' 
                     for idx in news_perf.index]
            ax9.bar(news_perf.index, news_perf['pnl_pct'], color=colors, alpha=0.7)
            ax9.axhline(y=0, color='white', linestyle='--', alpha=0.5)
            ax9.set_title('Performance by News Impact', fontsize=12, fontweight='bold')
            ax9.set_ylabel('Avg P&L (%)')
            
            # Add count labels
            for i, (idx, row) in enumerate(news_perf.iterrows()):
                ax9.text(i, row['pnl_pct'], f"n={int(row['signal'])}", 
                        ha='center', va='bottom', fontsize=8)
            ax9.grid(True, alpha=0.2)
        
        plt.tight_layout()
        
        # Save figure
        output_file = f'{self.data_dir}/backtest_analysis.png'
        plt.savefig(output_file, dpi=150, facecolor='#0a0a0a')
        print(f"📊 Chart saved to: {output_file}")
        
        plt.show()
        
    def generate_detailed_statistics(self):
        """Generate detailed statistics report"""
        signals_only = self.results[self.results['signal'].notna()].copy()
        
        if len(signals_only) == 0:
            print("⚠️  No signals to analyze")
            return
        
        print("\n" + "=" * 80)
        print("📊 DETAILED BACKTEST STATISTICS")
        print("=" * 80)
        
        # Overall metrics
        winning = signals_only[signals_only['pnl'] > 0]
        losing = signals_only[signals_only['pnl'] <= 0]
        
        print(f"\n📈 OVERALL METRICS:")
        print(f"   Total Signals: {len(signals_only)}")
        print(f"   Winning Trades: {len(winning)}")
        print(f"   Losing Trades: {len(losing)}")
        print(f"   Win Rate: {len(winning) / len(signals_only) * 100:.2f}%")
        print(f"   Average Win: ${winning['pnl'].mean():.2f} ({winning['pnl_pct'].mean():.2f}%)")
        print(f"   Average Loss: ${losing['pnl'].mean():.2f} ({losing['pnl_pct'].mean():.2f}%)")
        print(f"   Profit Factor: {abs(winning['pnl'].sum() / losing['pnl'].sum()):.2f}")
        print(f"   Total P&L: ${signals_only['pnl'].sum():.2f} ({signals_only['pnl_pct'].sum():.2f}%)")
        
        # By signal type
        print(f"\n📊 BY SIGNAL TYPE:")
        for signal_type in ['BUY', 'SELL']:
            subset = signals_only[signals_only['signal'] == signal_type]
            if len(subset) > 0:
                wins = subset[subset['pnl'] > 0]
                print(f"\n   {signal_type}:")
                print(f"     Total: {len(subset)}")
                print(f"     Win Rate: {len(wins) / len(subset) * 100:.2f}%")
                print(f"     Avg P&L: {subset['pnl_pct'].mean():.2f}%")
                print(f"     Total P&L: {subset['pnl_pct'].sum():.2f}%")
        
        # By confidence
        print(f"\n🎯 BY CONFIDENCE LEVEL:")
        strong = signals_only[signals_only['alert_type'].str.contains('STRONG')]
        regular = signals_only[~signals_only['alert_type'].str.contains('STRONG')]
        
        for name, subset in [('STRONG', strong), ('Regular', regular)]:
            if len(subset) > 0:
                wins = subset[subset['pnl'] > 0]
                print(f"\n   {name} Signals:")
                print(f"     Count: {len(subset)}")
                print(f"     Win Rate: {len(wins) / len(subset) * 100:.2f}%")
                print(f"     Avg P&L: {subset['pnl_pct'].mean():.2f}%")
                print(f"     Total P&L: {subset['pnl_pct'].sum():.2f}%")
        
        # By market regime
        print(f"\n🌊 BY MARKET REGIME:")
        for regime in signals_only['regime'].unique():
            subset = signals_only[signals_only['regime'] == regime]
            wins = subset[subset['pnl'] > 0]
            print(f"\n   {regime.upper()}:")
            print(f"     Signals: {len(subset)}")
            print(f"     Win Rate: {len(wins) / len(subset) * 100:.2f}%")
            print(f"     Avg P&L: {subset['pnl_pct'].mean():.2f}%")
        
        # By gap presence
        print(f"\n📊 GAP ANALYSIS:")
        for gap_type in ['GAP_UP', 'GAP_DOWN', 'NO_GAP']:
            subset = signals_only[signals_only['gap_type'] == gap_type]
            if len(subset) > 0:
                wins = subset[subset['pnl'] > 0]
                print(f"\n   {gap_type}:")
                print(f"     Signals: {len(subset)}")
                print(f"     Win Rate: {len(wins) / len(subset) * 100:.2f}%")
                print(f"     Avg P&L: {subset['pnl_pct'].mean():.2f}%")
        
        # By news impact
        print(f"\n📰 NEWS IMPACT ANALYSIS:")
        for impact in ['HIGH', 'MEDIUM', 'LOW', 'NONE']:
            subset = signals_only[signals_only['news_impact'] == impact]
            if len(subset) > 0:
                wins = subset[subset['pnl'] > 0]
                print(f"\n   {impact} Impact:")
                print(f"     Signals: {len(subset)}")
                print(f"     Win Rate: {len(wins) / len(subset) * 100:.2f}%")
                print(f"     Avg P&L: {subset['pnl_pct'].mean():.2f}%")
        
        # Trade outcomes
        print(f"\n🎲 TRADE OUTCOMES:")
        outcome_counts = signals_only['outcome'].value_counts()
        for outcome, count in outcome_counts.items():
            subset = signals_only[signals_only['outcome'] == outcome]
            print(f"   {outcome}: {count} ({count/len(signals_only)*100:.1f}%)")
            print(f"     Avg P&L: {subset['pnl_pct'].mean():.2f}%")
        
        print("\n" + "=" * 80)


if __name__ == '__main__':
    visualizer = BacktestVisualizer('synthetic_data_pltr')
    
    # Generate detailed statistics
    visualizer.generate_detailed_statistics()
    
    # Create comprehensive visual report
    print("\n📊 Generating visual report...")
    visualizer.create_comprehensive_report()
    
    print("\n✅ Analysis complete!")
