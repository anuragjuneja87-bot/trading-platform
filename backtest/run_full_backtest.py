"""
Complete Backtest Runner
Executes all steps: Data Generation → Backtesting → Analysis
"""

import sys
import os
from datetime import datetime

def print_header(text):
    """Print formatted header"""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80 + "\n")

def run_complete_backtest(symbol: str = 'PLTR', days: int = 90, start_price: float = 25.0):
    """
    Run complete backtesting process
    
    Args:
        symbol: Stock symbol to test
        days: Number of days to generate
        start_price: Starting price for synthetic data
    """
    
    print_header("🚀 TRADING SYSTEM BACKTEST - COMPLETE PIPELINE")
    print(f"Symbol: {symbol}")
    print(f"Period: {days} days")
    print(f"Start Price: ${start_price}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Step 1: Generate Synthetic Data
    print_header("STEP 1/3: Generating Synthetic Data")
    
    try:
        # Import and run data generator
        from synthetic_data_generator import SyntheticDataGenerator
        
        generator = SyntheticDataGenerator(
            symbol=symbol,
            days=days,
            start_price=start_price
        )
        
        data_dir = f'synthetic_data_{symbol.lower()}'
        summary = generator.generate_complete_dataset(output_dir=data_dir)
        
        print(f"\n✅ Synthetic data generated successfully!")
        print(f"   Location: {data_dir}/")
        
    except Exception as e:
        print(f"\n❌ ERROR in data generation: {str(e)}")
        return False
    
    # Step 2: Run Backtest
    print_header("STEP 2/3: Running Backtest")
    
    try:
        from backtest_system import SyntheticDataBacktester
        
        backtester = SyntheticDataBacktester(data_dir=data_dir)
        results = backtester.backtest_all_days()
        
        print(f"\n✅ Backtest completed successfully!")
        print(f"   Results: {data_dir}/backtest_results.csv")
        
    except Exception as e:
        print(f"\n❌ ERROR in backtesting: {str(e)}")
        return False
    
    # Step 3: Generate Analysis
    print_header("STEP 3/3: Generating Analysis & Visualizations")
    
    try:
        from backtest_visualizer import BacktestVisualizer
        
        visualizer = BacktestVisualizer(data_dir=data_dir)
        
        # Generate statistics
        print("\n📊 Generating detailed statistics...")
        visualizer.generate_detailed_statistics()
        
        # Generate charts
        print("\n📈 Creating visualization dashboard...")
        visualizer.create_comprehensive_report()
        
        print(f"\n✅ Analysis completed successfully!")
        print(f"   Chart: {data_dir}/backtest_analysis.png")
        
    except Exception as e:
        print(f"\n❌ ERROR in analysis: {str(e)}")
        print(f"   (Charts may require matplotlib - install with: pip install matplotlib seaborn)")
        # Don't return False - analysis is optional
    
    # Final Summary
    print_header("✅ BACKTEST COMPLETE")
    
    print("📁 Generated Files:")
    print(f"   • {data_dir}/daily_ohlcv.csv")
    print(f"   • {data_dir}/news_events.csv")
    print(f"   • {data_dir}/social_sentiment.csv")
    print(f"   • {data_dir}/dark_pool.csv")
    print(f"   • {data_dir}/options_flow.csv")
    print(f"   • {data_dir}/backtest_results.csv")
    print(f"   • {data_dir}/backtest_analysis.png")
    print(f"   • {data_dir}/summary.json")
    
    print("\n🎯 Next Steps:")
    print("   1. Review backtest_results.csv for detailed signal-by-signal analysis")
    print("   2. Examine backtest_analysis.png for visual performance breakdown")
    print("   3. Analyze which conditions (gaps, news, regime) produce best signals")
    print("   4. Adjust signal thresholds if needed")
    print("   5. Re-run backtest with modified parameters")
    
    print("\n💡 Key Files to Review:")
    print("   • backtest_results.csv - Every signal with P&L")
    print("   • backtest_analysis.png - Performance charts")
    print("   • summary.json - Dataset overview")
    
    print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return True


def run_custom_backtest():
    """Interactive mode for custom parameters"""
    print_header("🎛️  CUSTOM BACKTEST SETUP")
    
    # Get user inputs
    symbol = input("Enter symbol (default: PLTR): ").strip().upper() or 'PLTR'
    
    try:
        days = int(input("Enter number of days (default: 90): ") or 90)
    except ValueError:
        days = 90
    
    try:
        start_price = float(input(f"Enter starting price for {symbol} (default: 25.0): ") or 25.0)
    except ValueError:
        start_price = 25.0
    
    # Confirm
    print(f"\n📋 Backtest Configuration:")
    print(f"   Symbol: {symbol}")
    print(f"   Days: {days}")
    print(f"   Start Price: ${start_price}")
    
    confirm = input("\nProceed? (y/n): ").strip().lower()
    if confirm != 'y':
        print("❌ Backtest cancelled")
        return False
    
    # Run backtest
    return run_complete_backtest(symbol, days, start_price)


def main():
    """Main entry point"""
    
    if len(sys.argv) > 1:
        # Command line mode
        if sys.argv[1] == 'custom':
            run_custom_backtest()
        elif sys.argv[1] == 'help':
            print("Trading System Backtest Runner")
            print("=" * 80)
            print("\nUsage:")
            print("  python run_full_backtest.py              - Run with PLTR defaults")
            print("  python run_full_backtest.py custom       - Interactive custom setup")
            print("  python run_full_backtest.py help         - Show this help")
            print("\nDefault Configuration:")
            print("  Symbol: PLTR")
            print("  Days: 90")
            print("  Start Price: $25.00")
            print("\nOutput:")
            print("  • Synthetic market data (OHLCV, news, dark pool, options)")
            print("  • Backtest results with P&L for each signal")
            print("  • Performance analysis charts")
            print("  • Detailed statistics report")
        else:
            print(f"Unknown command: {sys.argv[1]}")
            print("Use 'python run_full_backtest.py help' for usage")
    else:
        # Default mode - PLTR
        run_complete_backtest(
            symbol='PLTR',
            days=90,
            start_price=25.0
        )


if __name__ == '__main__':
    main()
