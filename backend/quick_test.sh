#!/bin/bash
# ThetaData v3 CORRECTED Test
# Based on actual Terminal error messages

BASE_URL="http://localhost:25503"
TOMORROW=$(date -v+1d +%Y-%m-%d 2>/dev/null || date -d "+1 day" +%Y-%m-%d 2>/dev/null)

echo "════════════════════════════════════════════════════════════════════════"
echo "ThetaData v3 CORRECTED TEST"
echo "════════════════════════════════════════════════════════════════════════"
echo "FIXES:"
echo "  1. right parameter: 'call' or 'put' (NOT '*')"
echo "  2. Getting both calls and puts requires 2 separate requests"
echo "════════════════════════════════════════════════════════════════════════"
echo ""

test_endpoint() {
    local name="$1"
    local url="$2"
    
    printf "%-70s ... " "$name"
    
    RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" "$url")
    HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
    
    if [ "$HTTP_CODE" = "200" ]; then
        echo "✅ WORKS"
        return 0
    elif [ "$HTTP_CODE" = "403" ]; then
        echo "🔒 FORBIDDEN (need paid subscription)"
        return 1
    elif [ "$HTTP_CODE" = "404" ]; then
        echo "❌ NOT FOUND"
        return 1
    else
        echo "❓ HTTP $HTTP_CODE"
        return 1
    fi
}

echo "Testing with CORRECT parameters:"
echo ""

# Test greeks for calls
test_endpoint "Greeks ALL CALLS" "$BASE_URL/v3/option/snapshot/greeks/all?symbol=SPY&expiration=$TOMORROW&strike=*&right=call"

# Test greeks for puts
test_endpoint "Greeks ALL PUTS" "$BASE_URL/v3/option/snapshot/greeks/all?symbol=SPY&expiration=$TOMORROW&strike=*&right=put"

# Test single strike
test_endpoint "Greeks SINGLE (580 call)" "$BASE_URL/v3/option/snapshot/greeks/all?symbol=SPY&expiration=$TOMORROW&strike=580&right=call"

# Test quote endpoint
test_endpoint "Quote (580 call)" "$BASE_URL/v3/option/snapshot/quote?symbol=SPY&expiration=$TOMORROW&strike=580&right=call"

# Test OI endpoint
test_endpoint "Open Interest (580 call)" "$BASE_URL/v3/option/snapshot/open_interest?symbol=SPY&expiration=$TOMORROW&strike=580&right=call"

echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo "SAMPLE DATA - GREEKS FOR ALL SPY CALLS"
echo "════════════════════════════════════════════════════════════════════════"
echo ""

echo "Getting ALL CALL strikes + Greeks for SPY $TOMORROW:"
CALLS=$(curl -s "$BASE_URL/v3/option/snapshot/greeks/all?symbol=SPY&expiration=$TOMORROW&strike=*&right=call")

if [ -n "$CALLS" ] && ! echo "$CALLS" | grep -qi "error\|not found"; then
    LINE_COUNT=$(echo "$CALLS" | wc -l)
    echo "$CALLS" | head -15
    echo ""
    echo "   ✅ SUCCESS! Retrieved $LINE_COUNT lines"
    echo ""
    
    # Check headers
    HEADER=$(echo "$CALLS" | head -1)
    echo "   Checking headers:"
    
    if echo "$HEADER" | grep -qi "delta"; then
        echo "   ✅ delta"
    fi
    if echo "$HEADER" | grep -qi "gamma"; then
        echo "   ✅ gamma"
    fi
    if echo "$HEADER" | grep -qi "strike"; then
        echo "   ✅ strike"
    fi
    if echo "$HEADER" | grep -qi "bid"; then
        echo "   ✅ bid"
    fi
    if echo "$HEADER" | grep -qi "ask"; then
        echo "   ✅ ask"
    fi
    if echo "$HEADER" | grep -qi "volume"; then
        echo "   ✅ volume"
    else
        echo "   ⚠️  volume (may need /quote endpoint)"
    fi
    if echo "$HEADER" | grep -qi "open_interest"; then
        echo "   ✅ open_interest"
    else
        echo "   ⚠️  open_interest (may need /open_interest endpoint)"
    fi
else
    echo "   ❌ Failed or no data"
    echo "$CALLS" | head -10
fi

echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo "SAMPLE DATA - GREEKS FOR ALL SPY PUTS"
echo "════════════════════════════════════════════════════════════════════════"
echo ""

echo "Getting ALL PUT strikes + Greeks for SPY $TOMORROW:"
PUTS=$(curl -s "$BASE_URL/v3/option/snapshot/greeks/all?symbol=SPY&expiration=$TOMORROW&strike=*&right=put")

if [ -n "$PUTS" ] && ! echo "$PUTS" | grep -qi "error\|not found"; then
    LINE_COUNT=$(echo "$PUTS" | wc -l)
    echo "$PUTS" | head -10
    echo ""
    echo "   ✅ SUCCESS! Retrieved $LINE_COUNT lines"
else
    echo "   ❌ Failed or no data"
fi

echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo "TESTING ADDITIONAL DATA (Quote + OI)"
echo "════════════════════════════════════════════════════════════════════════"
echo ""

# Test if we need additional endpoints for volume/OI
echo "1. Testing Quote endpoint (for volume):"
QUOTE=$(curl -s "$BASE_URL/v3/option/snapshot/quote?symbol=SPY&expiration=$TOMORROW&strike=580&right=call")
if [ -n "$QUOTE" ] && ! echo "$QUOTE" | grep -qi "error\|not found"; then
    echo "$QUOTE" | head -5
    if echo "$QUOTE" | grep -qi "volume"; then
        echo "   ✅ Volume found in quote endpoint"
    fi
else
    echo "   ❌ No data"
fi

echo ""
echo "2. Testing Open Interest endpoint:"
OI=$(curl -s "$BASE_URL/v3/option/snapshot/open_interest?symbol=SPY&expiration=$TOMORROW&strike=580&right=call")
if [ -n "$OI" ] && ! echo "$OI" | grep -qi "error\|not found"; then
    echo "$OI" | head -5
    echo "   ✅ OI endpoint works"
else
    echo "   ❌ No data"
fi

echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo "IMPLEMENTATION STRATEGY FOR DAY TRADING"
echo "════════════════════════════════════════════════════════════════════════"
echo ""
echo "Based on test results:"
echo ""
echo "PER SYMBOL (e.g., SPY):"
echo "  1. GET /option/snapshot/greeks/all?right=call&strike=*"
echo "     → All call strikes + Greeks"
echo ""
echo "  2. GET /option/snapshot/greeks/all?right=put&strike=*"
echo "     → All put strikes + Greeks"
echo ""
echo "If Volume/OI missing from greeks:"
echo "  3. GET /option/snapshot/quote (may need per-strike)"
echo "  4. GET /option/snapshot/open_interest (may need per-strike)"
echo ""
echo "TOTAL API CALLS:"
echo "  - Best case: 2 calls per symbol (calls + puts)"
echo "  - Worst case: 2 + (N strikes × 2) if need individual quote/OI"
echo "  - With ±10% filtering: ~40-60 calls per symbol"
echo ""
echo "SPEED ESTIMATE:"
echo "  - 2 calls per symbol: < 1 second ✅"
echo "  - 40-60 calls per symbol: 2-3 seconds with threading ✅"
echo ""
echo "FOR 12 WATCHLIST SYMBOLS:"
echo "  - Best case: 24 calls total (~12 seconds)"
echo "  - With filtering + threading: ~20-30 seconds"
echo "  - With 60-second cache: Very acceptable for day trading! ✅"
echo ""
echo "════════════════════════════════════════════════════════════════════════"