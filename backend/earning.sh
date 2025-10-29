#!/bin/bash
# earnings_results.sh - Fetch actual earnings results with EPS/Revenue

# Load .env
source ~/Desktop/trading-platform/backend/.env

TICKERS="MSFT,META,GOOG"
# Look back 90 days for recent earnings
START_DATE=$(date -v-90d +%Y-%m-%d 2>/dev/null || date -d "-90 days" +%Y-%m-%d)
TODAY=$(date +%Y-%m-%d)

echo "📊 Fetching Benzinga Earnings Results (last 90 days)..."
EARNINGS=$(curl -s "https://api.benzinga.com/api/v2.1/calendar/earnings?token=$BENZINGA_API_KEY&parameters[tickers]=$TICKERS&parameters[date_from]=$START_DATE&parameters[date_to]=$TODAY&parameters[importance]=0")

echo "📈 Fetching current prices..."
DISCORD_MSG="**📊 Recent Earnings Results**\n\n"

for ticker in MSFT META GOOG; do
    echo "Processing $ticker..."
    
    # Get latest earnings result for this ticker
    RESULT=$(echo "$EARNINGS" | jq -r --arg t "$ticker" '
        .earnings[] | 
        select(.ticker == $t) | 
        select(.eps != null or .eps_est != null or .revenue != null) |
        {
            date: .date,
            time: .time,
            eps: .eps,
            eps_est: .eps_est,
            eps_prior: .eps_prior,
            revenue: .revenue,
            revenue_est: .revenue_est,
            revenue_prior: .revenue_prior
        }
    ' | head -1)
    
    if [ ! -z "$RESULT" ] && [ "$RESULT" != "null" ]; then
        DATE=$(echo "$RESULT" | jq -r '.date')
        EPS=$(echo "$RESULT" | jq -r '.eps // "N/A"')
        EPS_EST=$(echo "$RESULT" | jq -r '.eps_est // "N/A"')
        REV=$(echo "$RESULT" | jq -r '.revenue // "N/A"')
        REV_EST=$(echo "$RESULT" | jq -r '.revenue_est // "N/A"')
        
        # Calculate beat/miss
        EPS_BEAT=""
        if [ "$EPS" != "N/A" ] && [ "$EPS_EST" != "N/A" ]; then
            EPS_DIFF=$(echo "$EPS - $EPS_EST" | bc 2>/dev/null)
            if (( $(echo "$EPS_DIFF > 0" | bc -l 2>/dev/null) )); then
                EPS_BEAT="✅ BEAT (+\$$EPS_DIFF)"
            else
                EPS_BEAT="❌ MISS ($EPS_DIFF)"
            fi
        fi
        
        REV_BEAT=""
        if [ "$REV" != "N/A" ] && [ "$REV_EST" != "N/A" ]; then
            REV_DIFF=$(echo "scale=2; $REV - $REV_EST" | bc 2>/dev/null)
            if (( $(echo "$REV_DIFF > 0" | bc -l 2>/dev/null) )); then
                REV_BEAT="✅ BEAT (+\$${REV_DIFF}B)"
            else
                REV_BEAT="❌ MISS (\$${REV_DIFF}B)"
            fi
        fi
        
        DISCORD_MSG+="**$ticker** - $DATE\n"
        DISCORD_MSG+="EPS: \$$EPS vs \$$EPS_EST est. $EPS_BEAT\n"
        DISCORD_MSG+="Revenue: \$${REV}B vs \$${REV_EST}B est. $REV_BEAT\n"
    else
        DISCORD_MSG+="**$ticker** - No recent earnings data\n"
    fi
    
    # Get current price
    PRICE_DATA=$(curl -s "https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/$ticker?apiKey=$POLYGON_API_KEY")
    PRICE=$(echo "$PRICE_DATA" | jq -r '.ticker.day.c // "N/A"')
    CHANGE=$(echo "$PRICE_DATA" | jq -r '.ticker.todaysChangePerc // "N/A"')
    
    DISCORD_MSG+="Current: \$$PRICE (${CHANGE}%)\n\n"
done

# Send to Discord
echo "📡 Sending to Discord..."
curl -X POST "$DISCORD_REALTIME_EARNINGS" \
    -H "Content-Type: application/json" \
    -d "{\"content\":\"$DISCORD_MSG\"}"

echo -e "\n✅ Alert sent!"
echo -e "\n$DISCORD_MSG"