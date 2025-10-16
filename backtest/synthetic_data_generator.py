"""
Synthetic Trading Data Generator
Creates 90 days of realistic trading data for backtesting
Includes: OHLCV, News, Social Media, Dark Pool, Options Flow
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import random
from typing import List, Dict

class SyntheticDataGenerator:
    def __init__(self, symbol: str = 'PLTR', days: int = 90, start_price: float = 25.0):
        """
        Initialize synthetic data generator
        
        Args:
            symbol: Stock symbol
            days: Number of days to generate
            start_price: Starting price
        """
        self.symbol = symbol
        self.days = days
        self.start_price = start_price
        
        # News templates
        self.positive_news = [
            "{symbol} secures major ${amount}M government contract with {agency}",
            "{symbol} announces partnership with {company} for AI expansion",
            "Analyst upgrades {symbol} to Buy with ${target} price target",
            "{symbol} reports strong Q{quarter} earnings, beats estimates by {percent}%",
            "{symbol} wins {customer} as new enterprise client",
            "Breaking: {symbol} unveils breakthrough in {tech} technology",
            "{symbol} stock rallies on positive analyst commentary",
            "{symbol} announces $500M share buyback program",
            "Institutional investors increase {symbol} holdings by {percent}%",
            "{symbol} signs multi-year deal with {sector} leader"
        ]
        
        self.negative_news = [
            "{symbol} delays key product launch citing technical issues",
            "Analyst downgrades {symbol} on valuation concerns",
            "{symbol} faces security audit over {issue} concerns",
            "Short-seller releases critical report on {symbol}",
            "{symbol} misses Q{quarter} revenue estimates",
            "Concerns raised over {symbol}'s {metric} growth slowdown",
            "{symbol} loses major contract to competitor",
            "Insider selling detected at {symbol}",
            "Regulatory scrutiny increases for {symbol}'s {business} segment",
            "{symbol} warns of headwinds in {sector} sector"
        ]
        
        self.neutral_news = [
            "{symbol} scheduled to present at {conference} conference",
            "Analysts maintain Hold rating on {symbol}",
            "{symbol} announces routine earnings call date",
            "Trading volume increases in {symbol} ahead of {event}",
            "{symbol} adds new board member with {background} experience",
            "Options activity picks up in {symbol}",
            "{symbol} stock consolidates in tight range",
            "Market makers adjust {symbol} spreads",
            "{symbol} included in new ETF portfolio",
            "Technical analysis shows {symbol} at key level"
        ]
        
        # Social media templates
        self.bullish_social = [
            "PLTR breaking out! Chart looking beautiful 📈",
            "Accumulating more $PLTR here, this won't stay under ${price} long",
            "Dark pool activity in PLTR picking up 👀",
            "$PLTR whale alert! Someone just bought {shares}K shares",
            "PLTR weekly calls printing! Target ${target}",
            "This PLTR setup reminds me of the last breakout",
            "Big money moving into $PLTR, watch this",
            "PLTR above all key moving averages = bullish",
            "Government contracts = PLTR moon mission 🚀",
            "Institutions loading $PLTR at these levels"
        ]
        
        self.bearish_social = [
            "$PLTR looking heavy, might see ${price} soon",
            "PLTR rejection at resistance again 😬",
            "Sold my PLTR position, not liking this action",
            "Dark pools showing distribution in $PLTR",
            "PLTR puts were the play today",
            "This PLTR rally feels weak, be careful",
            "Major resistance at ${price} for PLTR",
            "Insider selling in $PLTR = red flag",
            "PLTR failing at key levels, bearish setup",
            "Taking profits on $PLTR, topping pattern forming"
        ]
        
    def generate_base_price_series(self) -> pd.DataFrame:
        """Generate base OHLCV data with realistic price action"""
        dates = []
        current_date = datetime.now() - timedelta(days=self.days)
        
        # Skip weekends
        while len(dates) < self.days:
            if current_date.weekday() < 5:  # Monday-Friday
                dates.append(current_date)
            current_date += timedelta(days=1)
        
        # Generate price with trends, volatility clusters, and mean reversion
        prices = [self.start_price]
        
        # Market regimes
        regime_length = 15  # Days per regime
        regimes = []
        for i in range(0, self.days, regime_length):
            regime_type = random.choices(
                ['uptrend', 'downtrend', 'choppy', 'breakout'],
                weights=[0.3, 0.2, 0.35, 0.15]
            )[0]
            regimes.extend([regime_type] * min(regime_length, self.days - i))
        
        for i in range(1, self.days):
            regime = regimes[i] if i < len(regimes) else 'choppy'
            
            # Base daily return based on regime
            if regime == 'uptrend':
                mean_return = 0.008  # 0.8% average daily
                volatility = 0.015
            elif regime == 'downtrend':
                mean_return = -0.006  # -0.6% average daily
                volatility = 0.020
            elif regime == 'breakout':
                mean_return = 0.015  # 1.5% average daily
                volatility = 0.025
            else:  # choppy
                mean_return = 0.001
                volatility = 0.012
            
            # Add momentum
            if i > 3:
                momentum = (prices[i-1] - prices[i-4]) / prices[i-4]
                mean_return += momentum * 0.3
            
            # Generate return
            daily_return = np.random.normal(mean_return, volatility)
            
            # Occasional gaps (10% chance)
            if random.random() < 0.10:
                gap = np.random.normal(0, 0.02)
                daily_return += gap
            
            new_price = prices[-1] * (1 + daily_return)
            prices.append(max(new_price, 1.0))  # Price floor at $1
        
        # Generate OHLC from close prices
        data = []
        for i, (date, close) in enumerate(zip(dates, prices)):
            # Intraday volatility
            intraday_vol = close * np.random.uniform(0.01, 0.03)
            
            high = close + np.random.uniform(0, intraday_vol)
            low = close - np.random.uniform(0, intraday_vol)
            open_price = np.random.uniform(low, high)
            
            # Volume - correlate with price movement
            price_change = abs(close - prices[i-1]) / prices[i-1] if i > 0 else 0.01
            base_volume = 15_000_000  # 15M shares base
            volume = int(base_volume * (1 + price_change * 10) * np.random.uniform(0.7, 1.5))
            
            data.append({
                'date': date.strftime('%Y-%m-%d'),
                'open': round(open_price, 2),
                'high': round(high, 2),
                'low': round(low, 2),
                'close': round(close, 2),
                'volume': volume,
                'regime': regime if i < len(regimes) else 'choppy'
            })
        
        return pd.DataFrame(data)
    
    def generate_news_events(self, price_df: pd.DataFrame) -> List[Dict]:
        """Generate news events correlated with price action"""
        news_events = []
        
        for idx, row in price_df.iterrows():
            # Calculate price change
            if idx > 0:
                prev_close = price_df.iloc[idx-1]['close']
                price_change_pct = ((row['close'] - prev_close) / prev_close) * 100
            else:
                price_change_pct = 0
            
            # News probability based on price movement
            news_prob = 0.15  # Base 15% chance
            if abs(price_change_pct) > 3:
                news_prob = 0.8  # 80% chance on big moves
            elif abs(price_change_pct) > 1.5:
                news_prob = 0.4
            
            if random.random() < news_prob:
                # Determine sentiment based on price action
                if price_change_pct > 2:
                    sentiment = 'very_positive'
                    template = random.choice(self.positive_news)
                elif price_change_pct > 0.5:
                    sentiment = 'positive'
                    template = random.choice(self.positive_news)
                elif price_change_pct < -2:
                    sentiment = 'very_negative'
                    template = random.choice(self.negative_news)
                elif price_change_pct < -0.5:
                    sentiment = 'negative'
                    template = random.choice(self.negative_news)
                else:
                    sentiment = 'neutral'
                    template = random.choice(self.neutral_news)
                
                # Fill template
                headline = template.format(
                    symbol=self.symbol,
                    amount=random.randint(50, 500),
                    agency=random.choice(['DoD', 'Army', 'Navy', 'CIA', 'NSA']),
                    company=random.choice(['Microsoft', 'AWS', 'Google Cloud', 'IBM']),
                    target=round(row['close'] * random.uniform(1.1, 1.3), 2),
                    quarter=random.choice(['Q1', 'Q2', 'Q3', 'Q4']),
                    percent=random.randint(5, 25),
                    customer=random.choice(['Fortune 500', 'Global Bank', 'Tech Giant']),
                    tech=random.choice(['AI', 'data analytics', 'machine learning']),
                    issue=random.choice(['data privacy', 'contract', 'compliance']),
                    metric=random.choice(['revenue', 'user', 'contract']),
                    business=random.choice(['government', 'commercial', 'international']),
                    sector=random.choice(['defense', 'tech', 'enterprise']),
                    conference=random.choice(['Goldman Sachs', 'Morgan Stanley', 'JPMorgan']),
                    event=random.choice(['earnings', 'product launch', 'conference']),
                    background=random.choice(['technology', 'finance', 'government'])
                )
                
                # Time of day
                hour = random.choice([7, 8, 9, 16, 17, 18])  # Pre-market or after-hours
                timestamp = datetime.strptime(row['date'], '%Y-%m-%d').replace(
                    hour=hour, minute=random.randint(0, 59)
                )
                
                news_events.append({
                    'date': row['date'],
                    'timestamp': timestamp.isoformat(),
                    'headline': headline,
                    'sentiment': sentiment,
                    'impact': 'high' if abs(price_change_pct) > 2 else 'medium' if abs(price_change_pct) > 1 else 'low',
                    'price_change': round(price_change_pct, 2)
                })
        
        return news_events
    
    def generate_social_sentiment(self, price_df: pd.DataFrame) -> List[Dict]:
        """Generate Twitter/Reddit sentiment data"""
        social_data = []
        
        for idx, row in price_df.iterrows():
            date = row['date']
            
            # Calculate intraday sentiment
            if idx > 0:
                prev_close = price_df.iloc[idx-1]['close']
                price_change_pct = ((row['close'] - prev_close) / prev_close) * 100
            else:
                price_change_pct = 0
            
            # Generate 5-15 social posts per day
            num_posts = random.randint(5, 15)
            
            for _ in range(num_posts):
                # Sentiment correlates with price but with noise
                sentiment_score = price_change_pct + np.random.normal(0, 1)
                
                if sentiment_score > 1.5:
                    sentiment = 'bullish'
                    post = random.choice(self.bullish_social).format(
                        price=round(row['close'], 2),
                        shares=random.randint(10, 500),
                        target=round(row['close'] * 1.1, 2)
                    )
                elif sentiment_score < -1.5:
                    sentiment = 'bearish'
                    post = random.choice(self.bearish_social).format(
                        price=round(row['close'] * 0.95, 2)
                    )
                else:
                    sentiment = 'neutral'
                    post = f"Watching $PLTR at ${row['close']}, key level here"
                
                platform = random.choice(['twitter', 'reddit', 'stocktwits'])
                engagement = random.randint(10, 5000)
                
                hour = random.randint(6, 22)
                timestamp = datetime.strptime(date, '%Y-%m-%d').replace(
                    hour=hour, minute=random.randint(0, 59)
                )
                
                social_data.append({
                    'date': date,
                    'timestamp': timestamp.isoformat(),
                    'platform': platform,
                    'post': post,
                    'sentiment': sentiment,
                    'engagement': engagement,
                    'sentiment_score': round(sentiment_score, 2)
                })
        
        return social_data
    
    def generate_dark_pool_data(self, price_df: pd.DataFrame) -> List[Dict]:
        """Generate dark pool activity"""
        dark_pool_data = []
        
        for idx, row in price_df.iterrows():
            # Dark pool activity correlates with volume and volatility
            volume_ratio = row['volume'] / 15_000_000
            
            # Generate 10-30 dark pool prints per day
            num_prints = int(random.uniform(10, 30) * volume_ratio)
            
            for _ in range(num_prints):
                # Large block sizes
                block_size = random.choice([
                    random.randint(10000, 50000),  # Small institutional
                    random.randint(50000, 100000),  # Medium institutional
                    random.randint(100000, 500000)  # Large institutional/whale
                ])
                
                # Price near market
                price = row['close'] * random.uniform(0.998, 1.002)
                
                # Time distribution
                hour = random.randint(9, 16)
                minute = random.randint(0, 59)
                timestamp = datetime.strptime(row['date'], '%Y-%m-%d').replace(
                    hour=hour, minute=minute
                )
                
                # Determine if buy or sell based on price action
                if idx > 0:
                    price_trend = row['close'] - price_df.iloc[idx-1]['close']
                    if price_trend > 0:
                        side = random.choices(['buy', 'sell'], weights=[0.65, 0.35])[0]
                    else:
                        side = random.choices(['buy', 'sell'], weights=[0.35, 0.65])[0]
                else:
                    side = random.choice(['buy', 'sell'])
                
                dark_pool_data.append({
                    'date': row['date'],
                    'timestamp': timestamp.isoformat(),
                    'size': block_size,
                    'price': round(price, 2),
                    'side': side,
                    'notional_value': round(block_size * price, 2),
                    'exchange': random.choice(['UBS', 'MS', 'GS', 'CITI', 'BARCLAYS'])
                })
        
        return dark_pool_data
    
    def generate_options_flow(self, price_df: pd.DataFrame) -> List[Dict]:
        """Generate options flow data"""
        options_data = []
        
        for idx, row in price_df.iterrows():
            # Options activity increases with volatility
            if idx > 0:
                price_change = abs(row['close'] - price_df.iloc[idx-1]['close']) / price_df.iloc[idx-1]['close']
            else:
                price_change = 0.01
            
            # Generate 15-50 options trades per day
            num_trades = int(random.uniform(15, 50) * (1 + price_change * 20))
            
            for _ in range(num_trades):
                # Strike selection
                current_price = row['close']
                strike_offset = random.uniform(-0.10, 0.10)  # +/- 10%
                strike = round(current_price * (1 + strike_offset), 0)
                
                # Call or Put
                if idx > 0:
                    price_trend = row['close'] - price_df.iloc[idx-1]['close']
                    if price_trend > 0:
                        option_type = random.choices(['call', 'put'], weights=[0.6, 0.4])[0]
                    else:
                        option_type = random.choices(['call', 'put'], weights=[0.4, 0.6])[0]
                else:
                    option_type = random.choice(['call', 'put'])
                
                # Expiration (weekly or monthly)
                days_to_exp = random.choice([3, 7, 14, 30, 60])
                expiration = (datetime.strptime(row['date'], '%Y-%m-%d') + 
                             timedelta(days=days_to_exp)).strftime('%Y-%m-%d')
                
                # Contract size
                contracts = random.choice([
                    random.randint(1, 10),      # Retail
                    random.randint(10, 50),     # Small trader
                    random.randint(50, 200),    # Active trader
                    random.randint(200, 1000)   # Institutional
                ])
                
                # Premium
                premium = random.uniform(0.50, 5.00)
                
                # Time
                hour = random.randint(9, 16)
                minute = random.randint(0, 59)
                timestamp = datetime.strptime(row['date'], '%Y-%m-%d').replace(
                    hour=hour, minute=minute
                )
                
                # Unusual activity flag (large size relative to open interest)
                unusual = contracts > 200 and random.random() < 0.15
                
                options_data.append({
                    'date': row['date'],
                    'timestamp': timestamp.isoformat(),
                    'type': option_type,
                    'strike': strike,
                    'expiration': expiration,
                    'contracts': contracts,
                    'premium': round(premium, 2),
                    'notional_value': round(contracts * 100 * premium, 2),
                    'unusual': unusual,
                    'sentiment': option_type  # Calls = bullish, Puts = bearish
                })
        
        return options_data
    
    def generate_intraday_data(self, date: str, ohlc: Dict) -> List[Dict]:
        """Generate 1-minute bars for a day"""
        intraday_data = []
        
        # Market hours: 9:30 AM - 4:00 PM ET (390 minutes)
        start_time = datetime.strptime(date, '%Y-%m-%d').replace(hour=9, minute=30)
        
        # Opening range price
        current_price = ohlc['open']
        
        # Target close
        target_close = ohlc['close']
        daily_range = ohlc['high'] - ohlc['low']
        
        for minute in range(390):
            timestamp = start_time + timedelta(minutes=minute)
            
            # Gradual drift toward close with noise
            progress = minute / 390
            drift = (target_close - ohlc['open']) * progress
            noise = np.random.normal(0, daily_range * 0.02)
            
            close = current_price + drift / 50 + noise
            
            # Constrain to daily range
            close = max(min(close, ohlc['high']), ohlc['low'])
            
            # Generate OHLC
            bar_range = daily_range * 0.01
            high = close + random.uniform(0, bar_range)
            low = close - random.uniform(0, bar_range)
            open_price = random.uniform(low, high)
            
            # Volume distribution (higher at open/close)
            if minute < 30 or minute > 360:
                volume_mult = 2.0
            elif minute < 60 or minute > 330:
                volume_mult = 1.5
            else:
                volume_mult = 1.0
            
            volume = int(ohlc['volume'] / 390 * volume_mult * random.uniform(0.5, 1.5))
            
            intraday_data.append({
                'timestamp': timestamp.isoformat(),
                'open': round(open_price, 2),
                'high': round(high, 2),
                'low': round(low, 2),
                'close': round(close, 2),
                'volume': volume
            })
            
            current_price = close
        
        return intraday_data
    
    def generate_complete_dataset(self, output_dir: str = 'synthetic_data'):
        """Generate complete dataset and save to files"""
        import os
        
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"🚀 Generating {self.days} days of synthetic data for {self.symbol}...")
        print("=" * 80)
        
        # 1. Generate base OHLCV
        print("📊 Generating daily OHLCV data...")
        price_df = self.generate_base_price_series()
        price_df.to_csv(f'{output_dir}/daily_ohlcv.csv', index=False)
        print(f"✅ Daily OHLCV: {len(price_df)} days")
        print(f"   Price range: ${price_df['close'].min():.2f} - ${price_df['close'].max():.2f}")
        
        # 2. Generate news
        print("\n📰 Generating news events...")
        news_data = self.generate_news_events(price_df)
        pd.DataFrame(news_data).to_csv(f'{output_dir}/news_events.csv', index=False)
        print(f"✅ News events: {len(news_data)} articles")
        sentiment_counts = pd.DataFrame(news_data)['sentiment'].value_counts()
        print(f"   {sentiment_counts.to_dict()}")
        
        # 3. Generate social sentiment
        print("\n💬 Generating social media data...")
        social_data = self.generate_social_sentiment(price_df)
        pd.DataFrame(social_data).to_csv(f'{output_dir}/social_sentiment.csv', index=False)
        print(f"✅ Social posts: {len(social_data)} posts")
        platform_counts = pd.DataFrame(social_data)['platform'].value_counts()
        print(f"   {platform_counts.to_dict()}")
        
        # 4. Generate dark pool
        print("\n🏦 Generating dark pool data...")
        dark_pool_data = self.generate_dark_pool_data(price_df)
        pd.DataFrame(dark_pool_data).to_csv(f'{output_dir}/dark_pool.csv', index=False)
        print(f"✅ Dark pool prints: {len(dark_pool_data)} blocks")
        total_volume = sum([d['size'] for d in dark_pool_data])
        print(f"   Total volume: {total_volume:,} shares")
        
        # 5. Generate options flow
        print("\n📈 Generating options flow data...")
        options_data = self.generate_options_flow(price_df)
        pd.DataFrame(options_data).to_csv(f'{output_dir}/options_flow.csv', index=False)
        print(f"✅ Options trades: {len(options_data)} contracts")
        unusual_count = sum([1 for o in options_data if o['unusual']])
        print(f"   Unusual activity: {unusual_count} trades")
        
        # 6. Generate intraday for a sample of days (first 5 and last 5)
        print("\n⏱️  Generating intraday data (sample days)...")
        intraday_dir = f'{output_dir}/intraday'
        os.makedirs(intraday_dir, exist_ok=True)
        
        sample_days = list(range(5)) + list(range(len(price_df)-5, len(price_df)))
        for idx in sample_days:
            row = price_df.iloc[idx]
            intraday = self.generate_intraday_data(row['date'], row)
            pd.DataFrame(intraday).to_csv(
                f'{intraday_dir}/intraday_{row["date"]}.csv', 
                index=False
            )
        print(f"✅ Intraday data: {len(sample_days)} days (1-minute bars)")
        
        # 7. Generate summary statistics
        print("\n📊 Generating summary statistics...")
        summary = {
            'symbol': self.symbol,
            'days': self.days,
            'start_date': price_df['date'].iloc[0],
            'end_date': price_df['date'].iloc[-1],
            'start_price': float(price_df['close'].iloc[0]),
            'end_price': float(price_df['close'].iloc[-1]),
            'total_return_pct': float(((price_df['close'].iloc[-1] - price_df['close'].iloc[0]) / 
                                       price_df['close'].iloc[0]) * 100),
            'max_price': float(price_df['high'].max()),
            'min_price': float(price_df['low'].min()),
            'avg_volume': int(price_df['volume'].mean()),
            'total_news_events': len(news_data),
            'total_social_posts': len(social_data),
            'total_dark_pool_blocks': len(dark_pool_data),
            'total_options_trades': len(options_data),
            'data_quality': 'synthetic',
            'generated_at': datetime.now().isoformat()
        }
        
        with open(f'{output_dir}/summary.json', 'w') as f:
            json.dump(summary, f, indent=2)
        
        print("\n" + "=" * 80)
        print("✅ DATA GENERATION COMPLETE!")
        print("=" * 80)
        print(f"\n📁 Files saved to: {output_dir}/")
        print(f"   • daily_ohlcv.csv")
        print(f"   • news_events.csv")
        print(f"   • social_sentiment.csv")
        print(f"   • dark_pool.csv")
        print(f"   • options_flow.csv")
        print(f"   • intraday/*.csv (sample days)")
        print(f"   • summary.json")
        
        print(f"\n📈 SUMMARY:")
        print(f"   Symbol: {summary['symbol']}")
        print(f"   Period: {summary['start_date']} to {summary['end_date']}")
        print(f"   Price: ${summary['start_price']:.2f} → ${summary['end_price']:.2f}")
        print(f"   Return: {summary['total_return_pct']:.2f}%")
        print(f"   Range: ${summary['min_price']:.2f} - ${summary['max_price']:.2f}")
        
        print("\n🎯 NEXT STEPS:")
        print("   1. Review the generated data")
        print("   2. Run backtester with this data")
        print("   3. Analyze signals and performance")
        
        return summary


if __name__ == '__main__':
    # Generate 90 days of PLTR data
    generator = SyntheticDataGenerator(
        symbol='PLTR',
        days=90,
        start_price=25.00
    )
    
    summary = generator.generate_complete_dataset(output_dir='synthetic_data_pltr')
    
    print("\n✨ Ready for backtesting!")
