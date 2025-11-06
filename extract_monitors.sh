#!/bin/bash
# Extract All Monitor Files for Code Review
# Run this from your trading-platform directory

echo "=========================================="
echo "EXTRACTING MONITOR FILES FOR CODE REVIEW"
echo "=========================================="
echo ""

OUTPUT_FILE="/tmp/all_monitors_for_review.txt"

# Clear output file
> "$OUTPUT_FILE"

# Function to add file with separator
add_file() {
    local file=$1
    local name=$2
    
    if [ -f "$file" ]; then
        echo "" >> "$OUTPUT_FILE"
        echo "==========================================" >> "$OUTPUT_FILE"
        echo "$name" >> "$OUTPUT_FILE"
        echo "==========================================" >> "$OUTPUT_FILE"
        echo "" >> "$OUTPUT_FILE"
        cat "$file" >> "$OUTPUT_FILE"
        echo "✅ Added: $name"
    else
        echo "⚠️  Not found: $file"
    fi
}

# Add all monitor files
add_file "backend/monitors/unusual_activity_monitor.py" "UNUSUAL ACTIVITY MONITOR"
add_file "backend/monitors/momentum_signal_monitor.py" "MOMENTUM SIGNAL MONITOR"
add_file "backend/monitors/wall_strength_monitor.py" "WALL STRENGTH MONITOR"
add_file "backend/monitors/realtime_volume_spike_monitor.py" "REALTIME VOLUME SPIKE MONITOR"
add_file "backend/monitors/odte_gamma_monitor.py" "ODTE GAMMA MONITOR (WORKING - FOR COMPARISON)"
add_file "backend/monitors/extended_hours_volume_monitor.py" "EXTENDED HOURS VOLUME MONITOR"

# Check for discord alerter
add_file "backend/alerts/discord_alerter.py" "DISCORD ALERTER (SHARED)"

# Add relevant parts of app.py
if [ -f "backend/app.py" ]; then
    echo "" >> "$OUTPUT_FILE"
    echo "==========================================" >> "$OUTPUT_FILE"
    echo "APP.PY - MONITOR INITIALIZATION SECTION" >> "$OUTPUT_FILE"
    echo "==========================================" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    
    # Extract monitor initialization section
    grep -A 10 "unusual_activity_monitor\|momentum_monitor\|wall_strength_monitor\|volume_spike_monitor" backend/app.py | head -100 >> "$OUTPUT_FILE"
    
    echo "✅ Added: App.py monitor initialization"
fi

echo ""
echo "=========================================="
echo "✅ ALL FILES EXTRACTED"
echo "=========================================="
echo ""
echo "Output saved to: $OUTPUT_FILE"
echo ""
echo "📁 File size: $(wc -l < "$OUTPUT_FILE") lines"
echo ""
echo "🚀 NEXT STEPS:"
echo "1. Download: $OUTPUT_FILE"
echo "2. Start new chat with Claude"
echo "3. Upload: SESSION_STATE_2025-11-06.md"
echo "4. Upload: all_monitors_for_review.txt"
echo "5. Say: 'Review these monitors and fix Discord 400 errors'"
echo ""
echo "=========================================="
